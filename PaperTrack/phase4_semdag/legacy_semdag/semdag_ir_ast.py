"""Stage 3 (stdlib) — SemDAG-IR via Python's built-in `ast`. No tree-sitter, no
network, no compile: usable in a fully offline sandbox. Produces the SAME
semdag_ir.json schema the rest of the pipeline consumes:

  nodes: file / class / function|method  (+ extern:/ambiguous:/module:)
  edges: contains / calls / imports

Reads file contents from the cached snapshot (deterministic, context-preserving)
and applies identical scope-qualified call resolution (same-file wins, unique
global, self.-method -> same-class, else one ambiguous sink; extern if no def).

Covers Python targets. For multi-language repos where tree-sitter IS available
(pre-vendored), semdag_ir_flow.py remains the richer path; this is the
zero-dependency default.

Usage: python semdag_ir_ast.py <container_id>
"""
import os, sys, json, ast
import cache

def build(container_id: str) -> dict:
    snap = cache.read(container_id, "snapshot.json")
    nodes = {}
    edges = []
    defs_by_name = {}
    raw_calls = []  # (caller_id, name, rel, is_method, receiver)

    def add_node(nid, kind, name, file, line, cls=None):
        if nid not in nodes:
            n = {"id": nid, "kind": kind, "name": name, "file": file, "line": line}
            if cls is not None:
                n["cls"] = cls
            nodes[nid] = n
            if kind in ("function", "method"):
                defs_by_name.setdefault(name, []).append(nid)

    for rel, entry in sorted(snap["files"].items()):
        if "content" not in entry or not rel.endswith(".py"):
            continue
        try:
            tree = ast.parse(entry["content"])
        except SyntaxError:
            continue
        file_id = f"file:{rel}"
        add_node(file_id, "file", rel, rel, 1)

        def callee(node):
            """(name, is_method, receiver) for an ast.Call."""
            f = node.func
            if isinstance(f, ast.Attribute):
                recv = f.value.id if isinstance(f.value, ast.Name) else None
                return f.attr, True, recv
            if isinstance(f, ast.Name):
                return f.id, False, None
            # e.g. chained call()(); dig for the last attribute/name
            cur = f
            while isinstance(cur, (ast.Call, ast.Subscript)):
                cur = cur.func if isinstance(cur, ast.Call) else cur.value
            if isinstance(cur, ast.Attribute):
                return cur.attr, True, None
            if isinstance(cur, ast.Name):
                return cur.id, False, None
            return None, False, None

        def walk(node, scope_id, scope_cls):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    cid = f"{rel}::{child.name}#cls@{child.lineno}"
                    add_node(cid, "class", child.name, rel, child.lineno)
                    edges.append({"src": scope_id, "dst": cid, "rel": "contains"})
                    walk(child, cid, child.name)
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    kind = "method" if scope_cls is not None else "function"
                    fid = f"{rel}::{child.name}#fn@{child.lineno}"
                    add_node(fid, kind, child.name, rel, child.lineno, cls=scope_cls)
                    edges.append({"src": scope_id, "dst": fid, "rel": "contains"})
                    walk(child, fid, None)  # nested defs/calls attributed to this fn
                elif isinstance(child, (ast.Attribute, ast.Subscript, ast.Name)):
                    _ids = [n.id for n in ast.walk(child) if isinstance(n, ast.Name)]
                    for _src in ("request", "argv", "environ", "stdin", "params", "form", "body"):
                        if _src in _ids and scope_id != file_id:
                            raw_calls.append((scope_id, "__source_" + _src, rel, False, None))
                    walk(child, scope_id, scope_cls)
                elif isinstance(child, ast.Call):
                    nm, is_m, recv = callee(child)
                    if nm:
                        raw_calls.append((scope_id, nm, rel, is_m, recv))
                    walk(child, scope_id, scope_cls)
                elif isinstance(child, ast.Import):
                    for a in child.names:
                        mid = f"module:{a.name}"
                        add_node(mid, "module", a.name, rel, child.lineno)
                        edges.append({"src": file_id, "dst": mid, "rel": "imports"})
                elif isinstance(child, ast.ImportFrom):
                    mod = child.module or "."
                    mid = f"module:{mod}"
                    add_node(mid, "module", mod, rel, child.lineno)
                    edges.append({"src": file_id, "dst": mid, "rel": "imports"})
                    walk(child, scope_id, scope_cls)
                else:
                    walk(child, scope_id, scope_cls)

        walk(tree, file_id, None)

    # scope/type-qualified call resolution (identical policy to the TS front end)
    def meta_of(nid): return nodes.get(nid, {})
    for caller, name, caller_rel, is_method, receiver in raw_calls:
        cands = defs_by_name.get(name, [])
        chosen = None
        if not cands:
            dst = f"extern:{name}"; add_node(dst, "extern", name, "", 0); chosen = [dst]
        else:
            same = [c for c in cands if meta_of(c).get("file") == caller_rel]
            if len(same) == 1:
                chosen = same
            elif len(cands) == 1:
                chosen = cands
            elif is_method and receiver in ("self", "cls"):
                cc = meta_of(caller).get("cls")
                inclass = [c for c in cands
                           if meta_of(c).get("cls") == cc and meta_of(c).get("file") == caller_rel]
                chosen = inclass if len(inclass) == 1 else None
            if chosen is None:
                dst = f"ambiguous:{name}"; add_node(dst, "ambiguous", name, "", 0); chosen = [dst]
        for t in chosen:
            if t != caller:
                edges.append({"src": caller, "dst": t, "rel": "calls"})

    uniq = sorted({(e["src"], e["dst"], e["rel"]) for e in edges})
    ir = {
        "tree_sha256": snap["tree_sha256"],
        "front_end": "stdlib-ast",
        "nodes": [nodes[k] for k in sorted(nodes)],
        "edges": [{"src": s, "dst": d, "rel": r} for s, d, r in uniq],
        "counts": {"nodes": len(nodes), "edges": len(uniq),
                   "calls": sum(1 for _, _, r in uniq if r == "calls")},
    }
    cache.write(container_id, "semdag_ir.json", ir)
    cache.mark_stage(container_id, "semdag_ir", ir["counts"])
    return ir

if __name__ == "__main__":
    cid = sys.argv[1]
    ir = build(cid)
    print(json.dumps({"stage": "semdag_ir(ast)", **ir["counts"]}))
