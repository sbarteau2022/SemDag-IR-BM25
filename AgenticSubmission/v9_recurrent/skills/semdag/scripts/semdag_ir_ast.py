"""Build the SemDAG hybrid recurrent typed graph IR (stdlib only, deterministic).

One graph. Nodes: file, module (external), class, function, method, loop, recursion.
Forward edges (each one is also stored with its inverse, see INVERSE):
  contains      file/class/function/loop -> class/function/method/loop (lexical nesting)
  imports       file -> file | module (src/ layouts and re-exports resolved)
  inherits      class -> base class inside the repository
  calls         function -> function, recursion kept (self, MRO, super(), modules, classes)
  instantiates  function -> class (the call also gets a `calls` edge to its __init__)
  loop_calls    loop -> function or class called in that loop body (innermost loop)
  loop_back     loop -> itself: one iteration feeding the next, with the carried names
  recurses      function -> function for every call edge inside a recursive cycle
  member_of     function -> recursion node (one per strongly connected call cycle)
  condenses_to  recursion node <-> function: call order between collapsed cycles
A loop node records its kind, nesting depth, owner, iteration targets, loop-carried names
(assigned in the body and read in the body or condition) and exits (break, return, raise,
yield). Every function carries `topo_rank`: collapsing each recursion node leaves an acyclic
call order, so a lower rank calls a higher one and members of one cycle share a rank.

A structural graph, not full Python semantics: dynamic dispatch, monkey patching and runtime
imports stay unresolved, and an ambiguous name is left unresolved rather than guessed.
"""
import ast
import builtins
import heapq
import json
import sys
from collections import defaultdict

import cache

FRONT_END = "stdlib-ast/recurrent-v1"
INVERSE = {"contains": "contained_in", "imports": "imported_by", "inherits": "inherited_by",
           "calls": "called_by", "instantiates": "instantiated_by", "loop_calls": "called_in_loop",
           "recurses": "recursed_by", "member_of": "has_member", "condenses_to": "condensed_from"}
BUILTIN_NAMES = set(dir(builtins))
COMPREHENSIONS = {ast.ListComp: "listcomp", ast.SetComp: "setcomp", ast.DictComp: "dictcomp",
                  ast.GeneratorExp: "genexp"}
MRO_DEPTH = 8
REEXPORT_DEPTH = 3
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


# ------------------------------------------------------------------ helpers
def module_names(py_files, has_file):
    """Module name per file with source roots (src/, lib/, ...) stripped: walk up while the
    directory is a package (has __init__.py); the first non-package ancestor is the root."""
    out = {}
    for rel in py_files:
        parts = rel[:-3].split("/")
        i = len(parts) - 1
        while i > 0 and has_file("/".join(parts[:i]) + "/__init__.py"):
            i -= 1
        mod_parts = parts[i:]
        if mod_parts[-1] == "__init__":
            mod_parts = mod_parts[:-1]
        out[rel] = ".".join(mod_parts) if mod_parts else "__init__"
    return out


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "super":
        parts.append("super()")
        return ".".join(reversed(parts))
    return None


def _names(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _local_names(fn):
    """Parameters and names bound directly inside a function (nested scopes excluded). Names
    bound by a function-level import are left out: the import table resolves them."""
    names = {a.arg for a in ast.walk(fn.args) if isinstance(a, ast.arg)}
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            continue
        if isinstance(node, ast.Lambda):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        stack.extend(ast.iter_child_nodes(node))
    return names


def _exposed(stmts, assigned, exposed, stored, exits):
    """Walk statements in execution order. A name read before this iteration assigned it is
    upward-exposed; with a store anywhere in the loop it is carried from the previous iteration."""
    for node in stmts:
        _expose(node, assigned, exposed, stored, exits)


def _expose(node, assigned, exposed, stored, exits):
    if isinstance(node, SCOPES):
        if not isinstance(node, ast.Lambda):
            assigned.add(node.name)
            stored.add(node.name)
        return
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        if node.value is not None:
            _expose(node.value, assigned, exposed, stored, exits)
        for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
            _expose(t, assigned, exposed, stored, exits)
        return
    if isinstance(node, ast.AugAssign):
        _expose(node.value, assigned, exposed, stored, exits)
        if isinstance(node.target, ast.Name):
            if node.target.id not in assigned:
                exposed.add(node.target.id)
            assigned.add(node.target.id)
            stored.add(node.target.id)
        else:
            _expose(node.target, assigned, exposed, stored, exits)
        return
    if isinstance(node, ast.NamedExpr):
        _expose(node.value, assigned, exposed, stored, exits)
        assigned.add(node.target.id)
        stored.add(node.target.id)
        return
    if isinstance(node, (ast.For, ast.AsyncFor)):  # nested loop: its iterable first
        _expose(node.iter, assigned, exposed, stored, exits)
        _expose(node.target, assigned, exposed, stored, exits)
        _exposed(node.body + node.orelse, assigned, exposed, stored, exits)
        return
    if isinstance(node, ast.Name):
        if isinstance(node.ctx, ast.Load):
            if node.id not in assigned:
                exposed.add(node.id)
        else:
            assigned.add(node.id)
            stored.add(node.id)
        return
    kind = {ast.Break: "break", ast.Continue: "continue", ast.Return: "return", ast.Raise: "raise",
            ast.Yield: "yield", ast.YieldFrom: "yield"}.get(type(node))
    if kind:
        exits[kind] += 1
    for child in ast.iter_child_nodes(node):
        _expose(child, assigned, exposed, stored, exits)


def _loop_facts(node):
    """Iteration targets, loop-carried names (read in an iteration before that iteration
    assigns them, and assigned somewhere in the loop) and exits; nested scopes excluded."""
    exits = defaultdict(int)
    exposed, stored = set(), set()
    if isinstance(node, (ast.For, ast.AsyncFor)):
        targets = _names(node.target)
        assigned = set(targets)
        _exposed(node.body, assigned, exposed, stored, exits)
        _exposed(node.orelse, set(targets), set(), set(), exits)
    elif isinstance(node, ast.While):
        targets = set()
        _exposed([node.test] + node.body, set(), exposed, stored, exits)
        _exposed(node.orelse, set(), set(), set(), exits)
    else:
        targets = set().union(*(_names(g.target) for g in node.generators))
        body = [node.elt] if hasattr(node, "elt") else [node.key, node.value]
        cond = [c for g in node.generators for c in g.ifs]
        _exposed(cond + body, set(targets), exposed, stored, exits)
    return sorted(targets), sorted((exposed & stored) - targets), dict(sorted(exits.items()))


def _local_types(fn):
    """Locals bound exactly once, by a call: `env = Environment(...)` gives env -> "Environment".
    The resolver keeps only the ones that name a repository class."""
    calls, counts = {}, defaultdict(int)
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, SCOPES):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            counts[node.id] += 1
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)):
            expr = _dotted(node.value.func)
            if expr:
                calls[node.targets[0].id] = expr
        stack.extend(ast.iter_child_nodes(node))
    for a in ast.walk(fn.args):
        if isinstance(a, ast.arg):
            counts[a.arg] += 1
    return {k: v for k, v in calls.items() if counts[k] == 1}


# ------------------------------------------------------------------ build
def build(container_id: str) -> dict:
    snap = cache.read(container_id, "snapshot.json")
    files = snap["files"]
    py = sorted(r for r, e in files.items() if r.endswith(".py") and "content" in e)
    mod_of = module_names(py, lambda r: r in files)
    file_of_mod = {}
    for rel in py:  # first wins; paths are sorted, so this is deterministic
        file_of_mod.setdefault(mod_of[rel], rel)

    nodes, edges = {}, []
    top_defs = defaultdict(dict)        # module -> name -> [ids] (module-level defs and classes)
    class_members = defaultdict(dict)   # class id -> name -> [method ids]
    class_bases, class_file = {}, {}
    unique_fn = defaultdict(list)       # name -> [module-level function ids]
    imports = defaultdict(lambda: {"modules": {}, "symbols": {}})
    raw_calls = []
    loops_of = defaultdict(list)

    def add_node(nid, kind, name, file, line, **extra):
        if nid not in nodes:
            n = {"id": nid, "kind": kind, "name": name, "file": file, "line": line}
            n.update({k: v for k, v in extra.items() if v is not None})
            nodes[nid] = n

    def edge(src, dst, rel, **extra):
        e = {"src": src, "dst": dst, "rel": rel}
        e.update({k: v for k, v in extra.items() if v is not None})
        edges.append(e)

    for rel in py:
        try:
            tree = ast.parse(files[rel]["content"])
        except (SyntaxError, ValueError, RecursionError):
            continue
        mod = mod_of[rel]
        is_pkg = rel.endswith("__init__.py")
        file_id = f"file:{rel}"
        add_node(file_id, "file", rel, rel, 1, module=mod)

        class Builder(ast.NodeVisitor):
            # frame: (id, kind, enclosing class id, qualname parts, locals, local types)
            def __init__(self):
                self.stack = [(file_id, "file", None, [], set(), {})]

            def owner(self):
                """Innermost function frame (calls and loops belong to it), else the file."""
                for frame in reversed(self.stack):
                    if frame[1] in ("function", "file"):
                        return frame
                return self.stack[0]

            def visit_ClassDef(self, node):
                pid, pkind, _, qual, _, _ = self.stack[-1]
                q = qual + [node.name]
                cid = f"{rel}::{'.'.join(q)}#cls@{node.lineno}"
                add_node(cid, "class", node.name, rel, node.lineno, end_line=node.end_lineno,
                         qualname=".".join(q), module=mod)
                edge(pid, cid, "contains")
                class_bases[cid] = [b for b in (_dotted(x) for x in node.bases) if b]
                class_file[cid] = rel
                if pkind == "file":
                    top_defs[mod].setdefault(node.name, []).append(cid)
                for d in node.decorator_list + node.bases:
                    self.visit(d)
                self.stack.append((cid, "class", cid, q, set(), {}))
                for stmt in node.body:
                    self.visit(stmt)
                self.stack.pop()

            def _function(self, node):
                pid, pkind, pcls, qual, _, _ = self.stack[-1]
                q = qual + [node.name]
                kind = "method" if pkind == "class" else "function"
                fid = f"{rel}::{'.'.join(q)}#fn@{node.lineno}"
                start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                add_node(fid, kind, node.name, rel, node.lineno, end_line=node.end_lineno,
                         start_line=start, qualname=".".join(q),
                         cls=nodes[pcls]["name"] if pcls else None, module=mod,
                         is_async=isinstance(node, ast.AsyncFunctionDef))
                edge(pid, fid, "contains")
                if any((_dotted(d) or "").split(".")[-1] == "overload" for d in node.decorator_list):
                    nodes[fid]["overload"] = True  # typing stubs: never a call target
                elif pkind == "class":
                    class_members[pid].setdefault(node.name, []).append(fid)
                elif pkind == "file":
                    top_defs[mod].setdefault(node.name, []).append(fid)
                    unique_fn[node.name].append(fid)
                # decorators and defaults are evaluated in the enclosing scope
                for d in node.decorator_list + node.args.defaults + [d for d in node.args.kw_defaults if d]:
                    self.visit(d)
                self.stack.append((fid, "function", pcls, q, _local_names(node), _local_types(node)))
                for stmt in node.body:
                    self.visit(stmt)
                self.stack.pop()

            visit_FunctionDef = visit_AsyncFunctionDef = _function

            def _loop(self, node, loop_kind, children):
                pid, _, pcls, qual, locs, types = self.stack[-1]
                own = self.owner()
                depth = 1 + sum(1 for f in self.stack if f[1] == "loop" and nodes[f[0]]["owner"] == own[0])
                lid = f"{rel}::{'.'.join(qual) or '<module>'}#loop@{node.lineno}:{node.col_offset}"
                targets, carried, exits = _loop_facts(node)
                add_node(lid, "loop", loop_kind, rel, node.lineno, end_line=node.end_lineno,
                         loop_kind=loop_kind, depth=depth, owner=own[0], targets=targets,
                         carried=carried, exits=exits)
                edge(pid, lid, "contains")
                edge(lid, lid, "loop_back", carried=carried or None)
                loops_of[own[0]].append(lid)
                self.stack.append((lid, "loop", pcls, qual, locs, types))
                for child in children:
                    self.visit(child)
                self.stack.pop()

            def visit_For(self, node):
                self.visit(node.iter)  # evaluated once, outside the recurrence
                self._loop(node, "async_for" if isinstance(node, ast.AsyncFor) else "for",
                           [node.target] + node.body + node.orelse)

            visit_AsyncFor = visit_For

            def visit_While(self, node):
                self._loop(node, "while", [node.test] + node.body + node.orelse)

            def _comp(self, node):
                self.visit(node.generators[0].iter)
                rest = [g.iter for g in node.generators[1:]] + [c for g in node.generators for c in g.ifs]
                body = [node.elt] if hasattr(node, "elt") else [node.key, node.value]
                self._loop(node, COMPREHENSIONS[type(node)], rest + body)

            visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _comp

            def visit_Call(self, node):
                own = self.owner()
                target = _dotted(node.func)
                if target and own[1] == "function":
                    loop = next((f[0] for f in reversed(self.stack) if f[1] == "loop"), None)
                    if loop and nodes[loop]["owner"] != own[0]:
                        loop = None
                    raw_calls.append({"caller": own[0], "target": target, "file": rel, "module": mod,
                                      "cls": own[2], "locals": own[4], "types": own[5], "line": node.lineno,
                                      "loop": loop})
                self.generic_visit(node)

            def visit_Import(self, node):
                for alias in node.names:
                    if alias.asname:
                        imports[rel]["modules"][alias.asname] = alias.name
                    else:
                        root = alias.name.split(".")[0]
                        imports[rel]["modules"].setdefault(root, root)
                    self._import_edge(alias.name)

            def visit_ImportFrom(self, node):
                level = node.level or 0
                if level:
                    pkg = mod.split(".") if is_pkg else mod.split(".")[:-1]
                    base = pkg[:len(pkg) - level + 1] if level - 1 <= len(pkg) else []
                    target_mod = ".".join(base + ([node.module] if node.module else []))
                else:
                    target_mod = node.module or ""
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    local = alias.asname or alias.name
                    sub = f"{target_mod}.{alias.name}" if target_mod else alias.name
                    if sub in file_of_mod:  # `from pkg import submodule`
                        imports[rel]["modules"][local] = sub
                        self._import_edge(sub)
                    else:
                        imports[rel]["symbols"][local] = (target_mod, alias.name)
                self._import_edge(target_mod)

            def _import_edge(self, target_mod):
                if not target_mod:
                    return
                target_file = file_of_mod.get(target_mod)
                if target_file:
                    dst = f"file:{target_file}"
                else:
                    dst = f"module:{target_mod}"
                    add_node(dst, "module", target_mod, "", 0)
                if dst != file_id:
                    edge(file_id, dst, "imports")

        Builder().visit(tree)

    # ---------------------------------------------------------- symbol resolution
    def one(ids):
        return ids[0] if ids and len(ids) == 1 else None

    def last(ids):
        """Within one scope the last binding wins (redefinitions, property setters)."""
        return ids[-1] if ids else None

    def lookup(module, name, depth=0):
        """Definition of `name` in `module`, following re-exports (`from .x import name`)."""
        hit = last(top_defs.get(module, {}).get(name, []))
        if hit or depth >= REEXPORT_DEPTH:
            return hit
        rel = file_of_mod.get(module)
        sym = imports[rel]["symbols"].get(name) if rel else None
        return lookup(sym[0], sym[1], depth + 1) if sym else None

    def resolve_class_expr(expr, rel, module):
        parts = expr.split(".")
        if len(parts) == 1:
            sym = imports[rel]["symbols"].get(parts[0])
            hit = lookup(sym[0], sym[1]) if sym else lookup(module, parts[0])
        else:
            alias = imports[rel]["modules"].get(parts[0])
            hit = lookup(".".join([alias] + parts[1:-1]), parts[-1]) if alias else None
        return hit if hit and nodes[hit]["kind"] == "class" else None

    bases_of = {}
    for cid in sorted(class_bases):
        rel = class_file[cid]
        resolved = [resolve_class_expr(b, rel, mod_of[rel]) for b in class_bases[cid]]
        bases_of[cid] = [b for b in resolved if b and b != cid]
        for b in bases_of[cid]:
            edge(cid, b, "inherits")

    def method_in_mro(cid, name, skip_self=False):
        seen, queue = set(), [cid]
        for _ in range(MRO_DEPTH):
            nxt = []
            for c in queue:
                if c in seen:
                    continue
                seen.add(c)
                if not (skip_self and c == cid):
                    hit = last(class_members.get(c, {}).get(name, []))
                    if hit:
                        return hit
                nxt.extend(bases_of.get(c, []))
            if not nxt:
                return None
            queue = nxt
        return None

    for call in raw_calls:
        parts = call["target"].split(".")
        rel, module, cls = call["file"], call["module"], call["cls"]
        hit, resolution = None, None
        if len(parts) == 1:
            name = parts[0]
            sym = imports[rel]["symbols"].get(name)
            if name in call["locals"]:
                hit = None  # a parameter or local shadows every outer binding: never guess
            elif sym:
                hit, resolution = lookup(sym[0], sym[1]), "from_import"
            elif name not in imports[rel]["modules"]:
                hit, resolution = lookup(module, name), "same_module"
                if hit is None and name not in BUILTIN_NAMES:
                    hit, resolution = one(unique_fn.get(name, [])), "unique_global"
        elif parts[0] in ("self", "cls") and cls and len(parts) == 2:
            hit, resolution = method_in_mro(cls, parts[1]), "self_mro"
        elif parts[0] == "super()" and cls and len(parts) == 2:
            hit, resolution = method_in_mro(cls, parts[1], skip_self=True), "super"
        elif parts[0] in imports[rel]["modules"] and parts[0] not in call["locals"]:
            full = [imports[rel]["modules"][parts[0]]] + parts[1:-1]
            resolution = "module_import"
            for cut in range(len(full), 0, -1):  # longest module prefix, then [Class.]name
                m = ".".join(full[:cut])
                if m in file_of_mod:
                    rest = full[cut:] + [parts[-1]]
                    if len(rest) == 1:
                        hit = lookup(m, rest[0])
                    elif len(rest) == 2:
                        c = lookup(m, rest[0])
                        hit = method_in_mro(c, rest[1]) if c and nodes[c]["kind"] == "class" else None
                    break
        elif len(parts) == 2 and parts[0] in call["types"]:
            c = resolve_class_expr(call["types"][parts[0]], rel, module)
            if c:  # `env = Environment(); env.parse()` -> Environment.parse
                hit, resolution = method_in_mro(c, parts[1]), "local_instance"
        elif len(parts) == 2 and parts[0] not in call["locals"]:
            c = resolve_class_expr(parts[0], rel, module)
            if c:
                hit, resolution = method_in_mro(c, parts[1]), "class_qualified"
        if not hit:
            continue
        line, loop = call["line"], call["loop"]
        if nodes[hit]["kind"] == "class":  # a class call instantiates it and runs its __init__
            edge(call["caller"], hit, "instantiates", line=line, resolution=resolution)
            if loop:
                edge(loop, hit, "loop_calls", line=line)
            hit = method_in_mro(hit, "__init__")
            if not hit:
                continue
        if nodes[hit]["kind"] in ("function", "method"):
            edge(call["caller"], hit, "calls", line=line, resolution=resolution)
            if loop:
                edge(loop, hit, "loop_calls", line=line)

    # ---------------------------------------------------------- recurrence and condensation
    uniq = {}
    for e in edges:
        uniq.setdefault((e["src"], e["dst"], e["rel"]), e)
    call_adj = defaultdict(set)
    for (s, d, r) in uniq:
        if r == "calls":
            call_adj[s].add(d)
    fn_ids = sorted(n for n, v in nodes.items() if v["kind"] in ("function", "method"))
    comp_of, comps = _tarjan(fn_ids, call_adj)
    recursive = {c for c, m in comps.items() if len(m) > 1 or m[0] in call_adj[m[0]]}
    for (s, d, r), e in list(uniq.items()):
        if r == "calls" and comp_of[s] == comp_of[d]:
            uniq[(s, d, "recurses")] = {"src": s, "dst": d, "rel": "recurses", "line": e.get("line")}
    for c in recursive:  # each recursive cycle is a typed node in the same graph
        members = comps[c]
        first = nodes[members[0]]
        add_node(c, "recursion", first["name"], first["file"], first["line"],
                 size=len(members), members=members)
        for m in members:
            nodes[m]["recursive"] = True
            nodes[m]["scc"] = c
            nodes[m]["scc_size"] = len(members)
            uniq[(m, c, "member_of")] = {"src": m, "dst": c, "rel": "member_of"}
    for owner, lids in loops_of.items():
        nodes[owner]["loops"] = len(lids)
        nodes[owner]["max_loop_depth"] = max(nodes[l]["depth"] for l in lids)

    # The condensed call order lives on the nodes of the one graph: collapsing each recursion
    # node's members leaves an acyclic order, so `topo_rank` sorts callers before callees and
    # equal ranks share a cycle. `condenses_to` edges link components that call each other.
    cond = sorted({(comp_of[s], comp_of[d]) for s in call_adj for d in call_adj[s]
                   if comp_of[s] != comp_of[d]})
    topo = _topo(sorted(comps), cond)
    rank = {c: i for i, c in enumerate(topo)}
    for fid in fn_ids:
        nodes[fid]["topo_rank"] = rank.get(comp_of[fid])
    for s, d in cond:
        if s in recursive or d in recursive:
            src = s if s in recursive else comps[s][0]
            dst = d if d in recursive else comps[d][0]
            uniq[(src, dst, "condenses_to")] = {"src": src, "dst": dst, "rel": "condenses_to"}
    acyclic = len(topo) == len(comps)

    forward = [uniq[k] for k in sorted(uniq)]
    inverse = [{"src": e["dst"], "dst": e["src"], "rel": INVERSE[e["rel"]]}
               for e in forward if e["rel"] in INVERSE]
    by_rel = defaultdict(int)
    for e in forward:
        by_rel[e["rel"]] += 1
    counts = {"nodes": len(nodes), "edges": len(forward) + len(inverse), "forward_edges": len(forward),
              "calls": by_rel["calls"], "contains": by_rel["contains"], "imports": by_rel["imports"],
              "inherits": by_rel["inherits"], "instantiates": by_rel["instantiates"],
              "loops": sum(1 for n in nodes.values() if n["kind"] == "loop"),
              "loop_calls": by_rel["loop_calls"], "recurses": by_rel["recurses"],
              "recursion_nodes": len(recursive), "condensed_acyclic": acyclic}
    ir = {"tree_sha256": snap["tree_sha256"], "front_end": FRONT_END,
          "nodes": [nodes[k] for k in sorted(nodes)], "edges": forward + inverse, "counts": counts}
    cache.write(container_id, "semdag_ir.json", ir)
    cache.mark_stage(container_id, "semdag_ir", counts)
    return ir


def _tarjan(order, adj):
    """Iterative Tarjan SCC: (node -> component id, component id -> sorted members)."""
    index, low, on, stack, comp_of, comps = {}, {}, set(), [], {}, {}
    counter = 0
    for root in order:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on.add(root)
        work = [(root, iter(sorted(adj.get(root, ()))))]
        while work:
            v, it = work[-1]
            pushed = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(sorted(adj.get(w, ())))))
                    pushed = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if pushed:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                members = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    members.append(w)
                    if w == v:
                        break
                members.sort()
                cid = f"scc:{members[0]}"
                comps[cid] = members
                for m in members:
                    comp_of[m] = cid
    return comp_of, comps


def _topo(comp_ids, dag_edges):
    """Kahn's algorithm, deterministic: callers before callees."""
    indeg = {c: 0 for c in comp_ids}
    out = defaultdict(list)
    for s, d in dag_edges:
        out[s].append(d)
        indeg[d] += 1
    ready = sorted(c for c, k in indeg.items() if k == 0)
    heapq.heapify(ready)
    order = []
    while ready:
        c = heapq.heappop(ready)
        order.append(c)
        for d in out[c]:
            indeg[d] -= 1
            if indeg[d] == 0:
                heapq.heappush(ready, d)
    return order


if __name__ == "__main__":
    ir = build(sys.argv[1])
    print(json.dumps({"stage": "semdag_ir(recurrent)", **ir["counts"]}))
