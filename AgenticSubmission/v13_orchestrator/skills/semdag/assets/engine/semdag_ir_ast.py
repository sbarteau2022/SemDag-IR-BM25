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

v2 (v11_task_ir): carried locations include attribute chains (`self.pos`) and subscripted bases
(`buf[]`) and come from a must-defined dataflow in which branches meet by intersection; each loop
also records its own condition (`test`) and every exit with the condition guarding it
(`exit_conds`); `x: T = ...` types a local; function-level imports are scoped to that function;
method lookup follows the C3 linearization.

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

FRONT_END = "stdlib-ast/recurrent-v2"
INVERSE = {"contains": "contained_in", "imports": "imported_by", "inherits": "inherited_by",
           "calls": "called_by", "instantiates": "instantiated_by", "loop_calls": "called_in_loop",
           "recurses": "recursed_by", "member_of": "has_member", "condenses_to": "condensed_from"}
BUILTIN_NAMES = set(dir(builtins))
COMPREHENSIONS = {ast.ListComp: "listcomp", ast.SetComp: "setcomp", ast.DictComp: "dictcomp",
                  ast.GeneratorExp: "genexp"}
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


def _key(node):
    """Name of a storage location: `x`, `self.pos`, `obj.a.b`, or `buf[]` for any subscript of buf."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _dotted(node)
    if isinstance(node, ast.Subscript):
        base = _key(node.value)
        return f"{base}[]" if base else None
    return None


def _src(node, limit=80):
    try:
        text = ast.unparse(node)
    except Exception:  # noqa: BLE001  (unparse of exotic nodes)
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


class _Flow:
    """Must-defined dataflow over one loop body (v11).

    A location is carried when some path reads it before the current iteration has definitely
    written it, and the loop writes it somewhere. `defined` is the set of locations written on
    every path so far; branches meet by intersection, a branch that cannot fall through (return,
    raise, break, continue) does not constrain the meet, and a nested loop's body may run zero
    times, so it adds nothing after it. Locations are names, attribute chains (`self.pos`) and
    subscripted bases (`buf[]`). Each exit is recorded with the branch condition that guards it."""

    EXIT = {ast.Return: "return", ast.Raise: "raise", ast.Break: "break", ast.Continue: "continue"}
    MUTATING = {"append", "extend", "insert", "pop", "remove", "clear", "update", "add",
                "discard", "setdefault", "sort", "reverse"}

    def __init__(self):
        self.exposed, self.stored = set(), set()
        self.exits = defaultdict(int)
        self.exit_conds = []
        self.conds = []      # guards of the current path, innermost last
        self.nest = 0        # nested loops: their break/continue do not leave this loop

    # ---- expressions (loads)
    def load(self, node, defined):
        if node is None:
            return
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load) and node.id not in defined:
                self.exposed.add(node.id)
            return
        if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, ast.Load):
            k = _key(node)
            if k and k not in defined:
                self.exposed.add(k)
            self.load(node.value, defined)
            if isinstance(node, ast.Subscript):
                self.load(node.slice, defined)
            return
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in self.MUTATING:
                recv = _key(node.func.value)
                if recv:
                    if recv not in defined:
                        self.exposed.add(recv)
                    self.stored.add(recv)
            self.load(node.func, defined)
            for arg in node.args:
                self.load(arg, defined)
            for kw in node.keywords:
                self.load(kw.value, defined)
            return
        if isinstance(node, ast.NamedExpr):
            self.load(node.value, defined)
            self.store(node.target, defined)
            return
        if isinstance(node, ast.Lambda):
            for d in node.args.defaults + [d for d in node.args.kw_defaults if d]:
                self.load(d, defined)
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            inner = set(defined)
            for g in node.generators:
                self.load(g.iter, inner)
                inner |= _names(g.target)
                for c in g.ifs:
                    self.load(c, inner)
            for part in ([node.elt] if hasattr(node, "elt") else [node.key, node.value]):
                self.load(part, inner)
            return
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            self.exits["yield"] += 1
        for child in ast.iter_child_nodes(node):
            self.load(child, defined)

    # ---- stores
    def store(self, target, defined):
        if isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self.store(elt, defined)
            return
        if isinstance(target, ast.Starred):
            self.store(target.value, defined)
            return
        if isinstance(target, (ast.Attribute, ast.Subscript)):
            self.load(target.value, defined)
            if isinstance(target, ast.Subscript):
                self.load(target.slice, defined)
        k = _key(target)
        if k:
            defined.add(k)
            self.stored.add(k)

    def _exit(self, node, kind):
        self.exits[kind] += 1
        if kind in ("break", "continue") and self.nest:
            return
        if len(self.exit_conds) < 8:
            self.exit_conds.append({"kind": kind, "line": node.lineno,
                                    "cond": " and ".join(self.conds[-2:]) or None})

    # ---- statements; returns the defined set after the block, or None if it cannot fall through
    def block(self, stmts, defined):
        for s in stmts:
            if defined is None:
                return None
            defined = self.stmt(s, defined)
        return defined

    def branch(self, cond, stmts, defined):
        if cond:
            self.conds.append(cond)
        try:
            return self.block(stmts, set(defined))
        finally:
            if cond:
                self.conds.pop()

    @staticmethod
    def meet(*outs):
        live = [o for o in outs if o is not None]
        if not live:
            return None
        out = set(live[0])
        for o in live[1:]:
            out &= o
        return out

    def stmt(self, node, defined):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for d in node.decorator_list:
                self.load(d, defined)
            if not isinstance(node, ast.ClassDef):
                for d in node.args.defaults + [d for d in node.args.kw_defaults if d]:
                    self.load(d, defined)
            defined.add(node.name)
            self.stored.add(node.name)
            return defined
        if isinstance(node, ast.Assign):
            self.load(node.value, defined)
            for t in node.targets:
                self.store(t, defined)
            return defined
        if isinstance(node, ast.AnnAssign):
            if node.value is not None:
                self.load(node.value, defined)
                self.store(node.target, defined)
            return defined
        if isinstance(node, ast.AugAssign):
            k = _key(node.target)
            if k and k not in defined:
                self.exposed.add(k)
            if isinstance(node.target, (ast.Attribute, ast.Subscript)):
                self.load(node.target.value, defined)
            self.load(node.value, defined)
            self.store(node.target, defined)
            return defined
        if isinstance(node, ast.If):
            self.load(node.test, defined)
            c = _src(node.test, 60)
            a = self.branch(c, node.body, defined)
            b = self.branch(f"not ({c})" if c else None, node.orelse, defined)
            return self.meet(a, b)
        if isinstance(node, (ast.For, ast.AsyncFor)):
            self.load(node.iter, defined)
            self.nest += 1
            inner = set(defined)
            self.store(node.target, inner)
            self.block(node.body, inner)
            self.nest -= 1
            self.block(node.orelse, set(defined))
            return defined
        if isinstance(node, ast.While):
            self.load(node.test, defined)
            self.nest += 1
            self.block(node.body, set(defined))
            self.nest -= 1
            self.block(node.orelse, set(defined))
            return defined
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                self.load(item.context_expr, defined)
                if item.optional_vars is not None:
                    self.store(item.optional_vars, defined)
            return self.block(node.body, defined)
        if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            body = self.block(node.body, set(defined))
            body = self.block(node.orelse, body) if body is not None else None
            outs = [body]
            for h in node.handlers:
                hd = set(defined)
                if h.type is not None:
                    self.load(h.type, hd)
                if h.name:
                    hd.add(h.name)
                outs.append(self.block(h.body, hd))
            out = self.meet(*outs)
            if node.finalbody:
                fin = self.block(node.finalbody, set(defined) if out is None else set(out))
                return None if out is None else fin
            return out
        if hasattr(ast, "Match") and isinstance(node, ast.Match):
            self.load(node.subject, defined)
            outs = []
            for case in node.cases:
                cd = set(defined)
                for n in ast.walk(case.pattern):
                    name = getattr(n, "name", None)
                    if isinstance(name, str):
                        cd.add(name)
                        self.stored.add(name)
                if case.guard is not None:
                    self.load(case.guard, cd)
                outs.append(self.branch(_src(case.pattern, 40), case.body, cd))
            return self.meet(*(outs + [set(defined)]))
        kind = self.EXIT.get(type(node))
        if kind:
            for child in ast.iter_child_nodes(node):
                self.load(child, defined)
            self._exit(node, kind)
            return None
        if isinstance(node, ast.Delete):
            for t in node.targets:
                k = _key(t)
                if k:
                    defined.discard(k)
                    self.stored.add(k)
            return defined
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name != "*":
                    n = alias.asname or alias.name.split(".")[0]
                    defined.add(n)
                    self.stored.add(n)
            return defined
        for child in ast.iter_child_nodes(node):
            self.load(child, defined)
        return defined


def _loop_facts(node):
    """Facts of one loop: iteration targets, carried locations (must-defined dataflow, see
    _Flow), exit counts, each exit with its guarding condition, and the loop's own test."""
    f = _Flow()
    if isinstance(node, (ast.For, ast.AsyncFor)):
        targets = _names(node.target)
        defined = set(targets)
        f.block(node.body, defined)
        f.block(node.orelse, set(targets))
        test = _src(ast.Compare(left=node.target, ops=[ast.In()], comparators=[node.iter]), 80)
    elif isinstance(node, ast.While):
        targets = set()
        f.load(node.test, set())
        f.block(node.body, set())
        f.block(node.orelse, set())
        test = _src(node.test, 80)
    else:
        targets = set().union(*(_names(g.target) for g in node.generators))
        inner = set(targets)
        for g in node.generators:
            for c in g.ifs:
                f.load(c, inner)
        for part in ([node.elt] if hasattr(node, "elt") else [node.key, node.value]):
            f.load(part, inner)
        test = None
    carried = sorted((f.exposed & f.stored) - targets)
    return {"targets": sorted(targets), "carried": carried, "exits": dict(sorted(f.exits.items())),
            "exit_conds": f.exit_conds, "test": test}


def _local_types(fn):
    """Locals bound exactly once, by a call or an annotation: `env = Environment(...)` and
    `env: Environment = make()` both give env -> "Environment". The resolver keeps only the ones
    that name a repository class."""
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
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            ann = node.annotation
            if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
                try:
                    ann = ast.parse(ann.value, mode="eval").body
                except SyntaxError:
                    ann = None
            expr = _dotted(ann) if isinstance(ann, (ast.Name, ast.Attribute)) else None
            if expr is None and isinstance(node.value, ast.Call):
                expr = _dotted(node.value.func)
            if expr:
                calls[node.target.id] = expr
        stack.extend(ast.iter_child_nodes(node))
    for a in ast.walk(fn.args):
        if isinstance(a, ast.arg):
            counts[a.arg] += 1
    return {k: v for k, v in calls.items() if counts[k] == 1}


def c3_merge(seqs):
    """C3 linearization merge; None when the hierarchy has no consistent order."""
    seqs = [list(s) for s in seqs if s]
    out = []
    while seqs:
        for s in seqs:
            head = s[0]
            if not any(head in t[1:] for t in seqs):
                break
        else:
            return None
        out.append(head)
        seqs = [[c for c in s if c != head] for s in seqs]
        seqs = [s for s in seqs if s]
    return out


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
    fn_imports = defaultdict(lambda: {"modules": {}, "symbols": {}})   # function id -> local imports
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
                facts = _loop_facts(node)
                carried = facts["carried"]
                add_node(lid, "loop", loop_kind, rel, node.lineno, end_line=node.end_lineno,
                         loop_kind=loop_kind, depth=depth, owner=own[0], targets=facts["targets"],
                         carried=carried, exits=facts["exits"], test=facts["test"],
                         exit_conds=facts["exit_conds"] or None)
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
                    scopes = tuple(f[0] for f in self.stack if f[1] == "function")
                    raw_calls.append({"caller": own[0], "target": target, "file": rel, "module": mod,
                                      "scopes": scopes,
                                      "cls": own[2], "locals": own[4], "types": own[5], "line": node.lineno,
                                      "loop": loop})
                self.generic_visit(node)

            def _table(self):
                """Import table of the innermost function, or the file's own table. A function-level
                import binds a local name only (v11): it must not resolve calls elsewhere in the file."""
                own = self.owner()
                return fn_imports[own[0]] if own[1] == "function" else imports[rel]

            def visit_Import(self, node):
                table = self._table()
                for alias in node.names:
                    if alias.asname:
                        table["modules"][alias.asname] = alias.name
                        table["symbols"].pop(alias.asname, None)
                    else:
                        root = alias.name.split(".")[0]
                        if table is imports[rel]:
                            table["modules"].setdefault(root, root)
                        else:
                            table["modules"][root] = root
                        table["symbols"].pop(root, None)
                    self._import_edge(alias.name)

            def visit_ImportFrom(self, node):
                level = node.level or 0
                if level:
                    pkg = mod.split(".") if is_pkg else mod.split(".")[:-1]
                    base = pkg[:len(pkg) - level + 1] if level - 1 <= len(pkg) else []
                    target_mod = ".".join(base + ([node.module] if node.module else []))
                else:
                    target_mod = node.module or ""
                table = self._table()
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    local = alias.asname or alias.name
                    sub = f"{target_mod}.{alias.name}" if target_mod else alias.name
                    if sub in file_of_mod:  # `from pkg import submodule`
                        table["modules"][local] = sub
                        table["symbols"].pop(local, None)
                        self._import_edge(sub)
                    else:
                        table["symbols"][local] = (target_mod, alias.name)
                        table["modules"].pop(local, None)
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

    def resolve_class_expr(expr, rel, module, table=None):
        table = table or imports[rel]
        parts = expr.split(".")
        if len(parts) == 1:
            sym = table["symbols"].get(parts[0])
            if sym:
                hit = lookup(sym[0], sym[1])
            elif parts[0] in table["modules"]:
                hit = None  # bound to a module, not a class
            else:
                hit = lookup(module, parts[0])
        else:
            alias = table["modules"].get(parts[0])
            hit = lookup(".".join([alias] + parts[1:-1]), parts[-1]) if alias else None
        return hit if hit and nodes[hit]["kind"] == "class" else None

    bases_of = {}
    for cid in sorted(class_bases):
        rel = class_file[cid]
        resolved = [resolve_class_expr(b, rel, mod_of[rel]) for b in class_bases[cid]]
        bases_of[cid] = [b for b in resolved if b and b != cid]
        for b in bases_of[cid]:
            edge(cid, b, "inherits")

    mro_memo = {}

    def mro(cid, active=()):
        """C3 linearization over the repository bases (v11; external bases are not in the graph).
        An inconsistent hierarchy falls back to depth-first, left-to-right order without repeats."""
        if cid in mro_memo:
            return mro_memo[cid]
        if cid in active:            # inheritance cycle in broken code: stop here
            return [cid]
        bases = bases_of.get(cid, [])
        parents = [mro(b, active + (cid,)) for b in bases]
        merged = c3_merge(parents + [list(bases)])
        if merged is None:
            merged, seen = [], {cid}
            for p in parents:
                for c in p:
                    if c not in seen:
                        seen.add(c)
                        merged.append(c)
        out = [cid] + [c for c in merged if c != cid]
        if not active:
            mro_memo[cid] = out
        return out

    def method_in_mro(cid, name, skip_self=False):
        for c in mro(cid):
            if skip_self and c == cid:
                continue
            hit = last(class_members.get(c, {}).get(name, []))
            if hit:
                return hit
        return None

    scope_memo = {}

    def scope_table(rel, scopes):
        """The import table a call sees: the file's, overlaid by each enclosing function's."""
        key = (rel, scopes)
        if key in scope_memo:
            return scope_memo[key]
        mods, syms = dict(imports[rel]["modules"]), dict(imports[rel]["symbols"])
        for fid in scopes:
            t = fn_imports.get(fid)
            if not t:
                continue
            for k, v in t["modules"].items():
                mods[k] = v
                syms.pop(k, None)
            for k, v in t["symbols"].items():
                syms[k] = v
                mods.pop(k, None)
        scope_memo[key] = {"modules": mods, "symbols": syms}
        return scope_memo[key]

    for call in raw_calls:
        parts = call["target"].split(".")
        rel, module, cls = call["file"], call["module"], call["cls"]
        table = scope_table(rel, call["scopes"])
        hit, resolution = None, None
        if len(parts) == 1:
            name = parts[0]
            sym = table["symbols"].get(name)
            if name in call["locals"]:
                hit = None  # a parameter or local shadows every outer binding: never guess
            elif sym:
                hit, resolution = lookup(sym[0], sym[1]), "from_import"
            elif name not in table["modules"]:
                hit, resolution = lookup(module, name), "same_module"
                if hit is None and name not in BUILTIN_NAMES:
                    hit, resolution = one(unique_fn.get(name, [])), "unique_global"
        elif parts[0] in ("self", "cls") and cls and len(parts) == 2:
            hit, resolution = method_in_mro(cls, parts[1]), "self_mro"
        elif parts[0] == "super()" and cls and len(parts) == 2:
            hit, resolution = method_in_mro(cls, parts[1], skip_self=True), "super"
        elif parts[0] in table["modules"] and parts[0] not in call["locals"]:
            full = [table["modules"][parts[0]]] + parts[1:-1]
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
            c = resolve_class_expr(call["types"][parts[0]], rel, module, table)
            if c:  # `env = Environment(); env.parse()` -> Environment.parse
                hit, resolution = method_in_mro(c, parts[1]), "local_instance"
        elif len(parts) == 2 and parts[0] not in call["locals"]:
            c = resolve_class_expr(parts[0], rel, module, table)
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
