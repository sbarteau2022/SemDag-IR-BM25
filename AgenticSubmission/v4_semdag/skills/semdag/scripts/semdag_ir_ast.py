"""Build the deterministic, stdlib-only SemDAG structural IR.

The IR keeps lexical containment, conservative resolved calls, and imports
resolved to repository files when possible.  It is a structural graph, not a
claim of full Python semantics: dynamic dispatch and runtime imports remain
explicitly unresolved.
"""
import sys, json, ast
from collections import defaultdict
import cache

def build(container_id: str) -> dict:
    snap = cache.read(container_id, "snapshot.json")
    nodes = {}
    edges = []
    defs_by_name = defaultdict(list)
    defs_by_module = defaultdict(dict)
    defs_by_class = defaultdict(dict)
    raw_calls = []
    imports = defaultdict(lambda: {"modules": {}, "symbols": {}})
    module_by_file = {}
    file_by_module = {}

    def module_name(rel):
        name = rel[:-3].replace("/", ".")
        return name[:-9] if name.endswith(".__init__") else name

    def add_node(nid, kind, name, file, line, **extra):
        if nid not in nodes:
            n = {"id": nid, "kind": kind, "name": name, "file": file, "line": line}
            n.update({k: v for k, v in extra.items() if v is not None})
            nodes[nid] = n
            if kind in ("function", "method"):
                defs_by_name[name].append(nid)

    def dotted_expr(node):
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr); node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
            return ".".join(reversed(parts))
        return None

    py_entries = [(rel, entry) for rel, entry in sorted(snap["files"].items())
                  if "content" in entry and rel.endswith(".py")]
    for rel, _ in py_entries:
        mod = module_name(rel)
        module_by_file[rel] = mod
        file_by_module[mod] = rel

    for rel, entry in py_entries:
        try:
            tree = ast.parse(entry["content"])
        except SyntaxError:
            continue
        file_id = f"file:{rel}"
        mod = module_by_file[rel]
        add_node(file_id, "file", rel, rel, 1, module=mod)

        class Builder(ast.NodeVisitor):
            def __init__(self):
                self.stack = [(file_id, "file", None, [])]

            def parent(self): return self.stack[-1]

            def visit_ClassDef(self, node):
                parent_id, _, _, qual = self.parent()
                q = qual + [node.name]
                cid = f"{rel}::{'.'.join(q)}#cls@{node.lineno}"
                add_node(cid, "class", node.name, rel, node.lineno,
                         end_line=node.end_lineno, qualname=".".join(q), module=mod)
                edges.append({"src": parent_id, "dst": cid, "rel": "contains"})
                self.stack.append((cid, "class", node.name, q)); self.generic_visit(node); self.stack.pop()

            def _function(self, node):
                parent_id, parent_kind, parent_cls, qual = self.parent()
                q = qual + [node.name]
                kind = "method" if parent_kind == "class" else "function"
                fid = f"{rel}::{'.'.join(q)}#fn@{node.lineno}"
                start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                add_node(fid, kind, node.name, rel, node.lineno, end_line=node.end_lineno,
                         start_line=start, qualname=".".join(q), cls=parent_cls,
                         module=mod, is_async=isinstance(node, ast.AsyncFunctionDef))
                edges.append({"src": parent_id, "dst": fid, "rel": "contains"})
                defs_by_module[mod].setdefault(node.name, []).append(fid)
                if parent_kind == "class":
                    defs_by_class[(mod, parent_cls)].setdefault(node.name, []).append(fid)
                self.stack.append((fid, "function", parent_cls, q)); self.generic_visit(node); self.stack.pop()

            visit_FunctionDef = _function
            visit_AsyncFunctionDef = _function

            def visit_Call(self, node):
                caller, kind, cls, _ = self.parent()
                if kind == "function":
                    target = dotted_expr(node.func)
                    if target:
                        raw_calls.append({"caller": caller, "target": target,
                                          "file": rel, "module": mod, "class": cls,
                                          "line": node.lineno})
                self.generic_visit(node)

            def visit_Import(self, node):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".")[0]
                    imports[rel]["modules"][local] = alias.name
                    self._import_edge(alias.name, node.lineno)

            def visit_ImportFrom(self, node):
                level = node.level or 0
                package = mod.split(".") if rel.endswith("/__init__.py") or rel == "__init__.py" else mod.split(".")[:-1]
                prefix = package[:max(0, len(package) - level + 1)] if level else []
                target_mod = ".".join(prefix + ([node.module] if node.module else []))
                for alias in node.names:
                    if alias.name == "*": continue
                    imports[rel]["symbols"][alias.asname or alias.name] = (target_mod, alias.name)
                self._import_edge(target_mod, node.lineno)

            def _import_edge(self, target_mod, line):
                if not target_mod: return
                target_file = file_by_module.get(target_mod)
                if target_file:
                    dst = f"file:{target_file}"
                else:
                    dst = f"module:{target_mod}"
                    add_node(dst, "module", target_mod, "", line)
                edges.append({"src": file_id, "dst": dst, "rel": "imports"})

        Builder().visit(tree)

    def single(values): return values[0] if len(values) == 1 else None
    for call in raw_calls:
        target = call["target"]; parts = target.split("."); rel = call["file"]
        mod = call["module"]; cls = call["class"]; chosen = None; resolution = None
        if len(parts) == 1:
            imported = imports[rel]["symbols"].get(parts[0])
            if imported:
                chosen = single(defs_by_module.get(imported[0], {}).get(imported[1], [])); resolution = "from_import"
            if chosen is None:
                chosen = single(defs_by_module.get(mod, {}).get(parts[0], [])); resolution = "same_module"
        elif parts[0] in ("self", "cls") and cls:
            chosen = single(defs_by_class.get((mod, cls), {}).get(parts[-1], [])); resolution = "same_class"
        elif parts[0] in imports[rel]["modules"]:
            chosen = single(defs_by_module.get(imports[rel]["modules"][parts[0]], {}).get(parts[-1], [])); resolution = "module_import"
        else:
            chosen = single(defs_by_class.get((mod, parts[-2]), {}).get(parts[-1], [])); resolution = "class_qualified"
        if chosen is None and len(parts) == 1:
            chosen = single(defs_by_name.get(parts[0], [])); resolution = "unique_global"
        if chosen and chosen != call["caller"]:
            edges.append({"src": call["caller"], "dst": chosen, "rel": "calls",
                          "line": call["line"], "resolution": resolution})

    uniq = {}
    for edge in edges:
        key = (edge["src"], edge["dst"], edge["rel"])
        uniq.setdefault(key, edge)
    ir = {
        "tree_sha256": snap["tree_sha256"],
        "front_end": "stdlib-ast",
        "nodes": [nodes[k] for k in sorted(nodes)],
        "edges": [uniq[k] for k in sorted(uniq)],
        "counts": {"nodes": len(nodes), "edges": len(uniq),
                   "calls": sum(1 for _, _, r in uniq if r == "calls"),
                   "contains": sum(1 for _, _, r in uniq if r == "contains"),
                   "imports": sum(1 for _, _, r in uniq if r == "imports")},
    }
    cache.write(container_id, "semdag_ir.json", ir)
    cache.mark_stage(container_id, "semdag_ir", ir["counts"])
    return ir

if __name__ == "__main__":
    cid = sys.argv[1]
    ir = build(cid)
    print(json.dumps({"stage": "semdag_ir(ast)", **ir["counts"]}))
