#!/usr/bin/env python3
"""Structural IR for Python repos: deterministic, stdlib-only, offline.

Subcommands:
  snapshot    byte-for-byte memory-allocated box + index (no context dump)
  analyze     confidence-ranked issue scan + compact flag count key
  decompose   IR -> context-relational DAG (files/modules/classes/functions)
  context     reachability-conditioned vulnerability probability

Every subcommand prints exactly one compact JSON receipt line and writes full
artefacts to <repo>/<out_dir>/, keeping the context window free of repo bytes.
Stdlib only: pathlib, hashlib, json, ast, re, collections. No third-party deps.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    "dist",
    "build",
}
MITIGATOR_WORDS = {
    "validate",
    "sanitize",
    "escape",
    "check",
    "auth",
    "permission",
    "verify",
    "authorize",
    "whitelist",
    "clean",
    "guard",
}
SOURCE_NAME_PARTS = (
    "handle",
    "view",
    "route",
    "api",
    "endpoint",
    "controller",
    "main",
    "parse",
    "deserialize",
    "read",
    "fetch",
    "process",
    "run",
    "serve",
    "request",
)
SOURCE_PARAM_PARTS = (
    "request",
    "payload",
    "data",
    "input",
    "body",
    "raw",
    "query",
    "param",
)
PREFIX = {
    "type_issue": "TYPE",
    "mutdef": "MUTDEF",
    "assert": "ASSERT",
    "eval": "EVAL",
    "shell": "SHELL",
    "pickle": "PICKLE",
    "yaml": "YAML",
    "secret": "SECRET",
    "broad": "BROAD",
    "sqli": "SQLI",
}
SECRET_RE = re.compile(
    r"(api_key|secret|password|passwd|token|access_key)"
    r"""\s*[:=]\s*["'][^"'\s]{6,}["']""",
    re.IGNORECASE,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_skipped(rel: Path) -> bool:
    return any(part in SKIP_DIRS for part in rel.parts)


def collect_files(root: Path, out_dir: Path | None = None) -> list[Path]:
    """All regular files under root, minus skip dirs and the tool's own output dir.

    Excluding the output dir is required for correctness: a snapshot must not
    ingest a previous run's snapshot.box / *.json artefacts.
    """
    excluded: Path | None = None
    if out_dir is not None:
        excluded = out_dir if out_dir.is_absolute() else root / out_dir
        excluded = excluded.resolve()
    out = []
    for path in root.rglob("*"):
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if is_skipped(rel):
            continue
        if excluded is not None and path.resolve() == excluded:
            continue
        # skip anything inside the output directory tree
        if excluded is not None:
            try:
                if path.resolve().is_relative_to(excluded):
                    continue
            except (OSError, ValueError):
                pass
        out.append(path)
    return sorted(out)


def relpath(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def parse_py(path: Path):
    """Return (tree, source). tree is None when the file does not parse."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, ""
    try:
        return ast.parse(source, filename=str(path)), source
    except (SyntaxError, ValueError, RecursionError):
        return None, source


def dotted_root(name: str | None) -> str:
    if not name:
        return ""
    return name.split(".", 1)[0]


# ---------------------------------------------------------------- snapshot


def cmd_snapshot(root: Path, out_dir: Path) -> None:
    out = out_dir if out_dir.is_absolute() else root / out_dir
    out.mkdir(parents=True, exist_ok=True)

    files = collect_files(root, out_dir)
    staged: list[tuple[Path, bytes]] = []
    total = 0
    for path in files:
        try:
            blob = path.read_bytes()
        except OSError:
            blob = b""
        staged.append((path, blob))
        total += len(blob)

    # memory-allocated box: one contiguous bytearray for the whole snapshot
    box = bytearray(total)
    entries = []
    offset = 0
    for path, blob in staged:
        box[offset : offset + len(blob)] = blob
        entries.append(
            {
                "path": relpath(root, path),
                "size": len(blob),
                "offset": offset,
                "sha256": sha256_bytes(blob),
            }
        )
        offset += len(blob)

    box_path = out / "snapshot.box"
    box_path.write_bytes(bytes(box))
    index = {
        "root": str(root),
        "files": len(entries),
        "total_bytes": total,
        "box_sha256": sha256_bytes(bytes(box)),
        "entries": entries,
    }
    index_path = out / "snapshot.index.json"
    index_path.write_text(json.dumps(index, indent=2))

    receipt = {
        "ok": True,
        "command": "snapshot",
        "files": len(entries),
        "total_bytes": total,
        "box_sha256": index["box_sha256"],
        "box_path": str(box_path),
        "index_path": str(index_path),
    }
    print(json.dumps(receipt, separators=(",", ":")))


# ---------------------------------------------------------------- analyze


def mutable_default(node: ast.AST) -> bool:
    """True if any default value is a list/dict/set literal or comprehension."""
    mutable = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)
    for field in ("defaults", "kw_defaults"):
        for default in getattr(node.args, field, []) or []:
            if isinstance(default, mutable):
                return True
    for arg in (
        list(getattr(node.args, "posonlyargs", []))
        + list(node.args.args)
        + list(node.args.kwonlyargs)
    ):
        if arg.annotation and isinstance(arg.annotation, mutable):
            return True
    return False


def call_name(node: ast.Call) -> str:
    """Dotted callee text, e.g. 'subprocess.run' / 'eval' / 'x.load'."""
    parts = []
    cur = node.func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def kw_is_true(node: ast.Call, name: str) -> bool:
    for kw in node.keywords:
        if (
            kw.arg == name
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
        ):
            return True
    return False


def arg_is_dangerous_string(arg: ast.AST) -> bool:
    if isinstance(arg, ast.JoinedStr):  # f-string
        return True
    if isinstance(arg, ast.BinOp):  # "a" % x  or  "a" + x
        return True
    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
        return arg.func.attr in ("format", "join")
    return False


def files_scanned_flags(root: Path, files: list[Path]):
    """Single pass over .py files -> (per-file trees, flags, counts)."""
    trees: dict[str, tuple[ast.AST, str]] = {}
    flags: list[dict] = []

    def add(kind: str, confidence: float, file: str, line: int, evidence: str) -> None:
        prefix = PREFIX[kind]
        flags.append(
            {
                "id": f"{prefix}-{len(flags) + 1}",
                "kind": kind,
                "file": file,
                "line": line,
                "confidence": confidence,
                "evidence": evidence,
            }
        )

    for path in files:
        rel = relpath(root, path)
        tree, source = parse_py(path)
        if tree is None:
            continue
        trees[rel] = (tree, source)
        is_test = "test" in rel.lower()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if not name.startswith("_") and node.returns is None:
                    add(
                        "type_issue",
                        0.4,
                        rel,
                        node.lineno,
                        f"public function `{name}` lacks return annotation",
                    )
                if mutable_default(node):
                    add(
                        "mutdef",
                        0.75,
                        rel,
                        node.lineno,
                        f"mutable default argument in `{name}`",
                    )
            elif isinstance(node, ast.Assert) and not is_test:
                add("assert", 0.5, rel, node.lineno, "assert in non-test code")
            elif isinstance(node, ast.ExceptHandler):
                names = set()
                if node.type is not None:
                    for sub in ast.walk(node.type):
                        if isinstance(sub, ast.Name):
                            names.add(sub.id)
                        elif isinstance(sub, ast.Attribute):
                            names.add(sub.attr)
                if names & {"Exception", "BaseException"}:
                    add("broad", 0.6, rel, node.lineno, "broad exception handler")
            elif isinstance(node, ast.Call):
                callee = call_name(node)
                simple = callee.rsplit(".", 1)[-1]
                if simple in ("eval", "exec") and "." not in callee:
                    add("eval", 0.95, rel, node.lineno, "eval/exec usage")
                elif callee in ("os.system", "os.popen") or (
                    simple in ("run", "call", "check_call", "check_output", "Popen")
                    and callee.startswith("subprocess.")
                    and kw_is_true(node, "shell")
                ):
                    add("shell", 0.95, rel, node.lineno, "shell execution")
                elif simple in ("load", "loads") and (
                    callee.startswith("pickle.")
                    or callee.startswith("cPickle.")
                    or callee.startswith("_pickle.")
                ):
                    add(
                        "pickle", 0.8, rel, node.lineno, "unsafe pickle deserialization"
                    )
                elif simple == "load" and callee.startswith("yaml."):
                    loader_ok = any(
                        kw.arg == "Loader" and "Safe" in ast.dump(kw.value)
                        for kw in node.keywords
                    )
                    if not loader_ok:
                        add(
                            "yaml",
                            0.8,
                            rel,
                            node.lineno,
                            "yaml.load without SafeLoader",
                        )
                elif simple in ("execute", "executemany", "raw") and any(
                    arg_is_dangerous_string(arg) for arg in node.args
                ):
                    add(
                        "sqli",
                        0.7,
                        rel,
                        node.lineno,
                        "possible SQL injection via string construction",
                    )

        for lineno, line in enumerate(source.splitlines(), start=1):
            if SECRET_RE.search(line):
                add("secret", 0.9, rel, lineno, "possible hardcoded secret")

    return trees, flags


def cmd_analyze(root: Path, out_dir: Path) -> None:
    out = out_dir if out_dir.is_absolute() else root / out_dir
    out.mkdir(parents=True, exist_ok=True)
    py_files = [p for p in collect_files(root, out_dir) if p.suffix == ".py"]

    trees, flags = files_scanned_flags(root, py_files)
    deps, functions, classes = set(), 0, 0
    for tree, _ in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_name = dotted_root(alias.name)
                    if root_name:
                        deps.add(root_name)
            elif isinstance(node, ast.ImportFrom):
                # only absolute imports count as external dependencies;
                # relative imports (level > 0) are intra-repo structure
                if node.level == 0:
                    root_name = dotted_root(node.module)
                    if root_name:
                        deps.add(root_name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions += 1
            elif isinstance(node, ast.ClassDef):
                classes += 1

    key = {
        "files": len(py_files),
        "functions": functions,
        "classes": classes,
        "dependencies": len(deps),
        "type_issues": sum(1 for f in flags if f["kind"] == "type_issue"),
        "vuln_flags": sum(1 for f in flags if f["kind"] != "type_issue"),
        "total_flags": len(flags),
    }
    payload = {
        "root": str(root),
        "files_scanned": len(py_files),
        "flag_count_key": key,
        "flags": flags,
        "dependencies": sorted(deps),
    }
    path = out / "analyze.json"
    path.write_text(json.dumps(payload, indent=2))

    receipt = {
        "ok": True,
        "command": "analyze",
        "files_scanned": len(py_files),
        "flag_count_key": key,
        "out": str(path),
    }
    print(json.dumps(receipt, separators=(",", ":")))


# ---------------------------------------------------------------- decompose


class GraphBuilder:
    """Builds the two-tier (macro/micro) context-relational DAG from Python AST."""

    def __init__(self) -> None:
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self._seen_nodes: set[str] = set()
        self._seen_edges: set[tuple[str, str, str, int]] = set()
        self.functions: list[dict] = []  # function nodes only, for call graphs
        self.func_index: dict[str, str] = {}  # simple name -> node id (last wins)

    def add_node(
        self, node_id: str, kind: str, path: str, start: int, end: int, name: str | None
    ) -> None:
        if node_id in self._seen_nodes:
            return
        self._seen_nodes.add(node_id)
        self.nodes.append(
            {
                "id": node_id,
                "kind": kind,
                "path": path,
                "start_line": start,
                "end_line": end,
                "name": name,
            }
        )
        if kind == "function":
            self.functions.append(
                {"id": node_id, "path": path, "start_line": start, "end_line": end}
            )
        if kind == "function" and name:
            self.func_index[name] = node_id

    def add_edge(self, src: str, dst: str, kind: str, line: int) -> None:
        key = (src, dst, kind, line)
        if key in self._seen_edges or src == dst:
            return
        self._seen_edges.add(key)
        self.edges.append({"from": src, "to": dst, "kind": kind, "line": line})

    def visit(
        self,
        node: ast.AST,
        file_id: str,
        path: str,
        container: str,
        stack: list[tuple[str, str]],
    ) -> None:
        """stack = [(name, id)] of enclosing function scopes for call attribution."""
        if isinstance(node, ast.ClassDef):
            node_id = f"{file_id}::{node.name}"
            self.add_node(
                node_id,
                "class",
                path,
                node.lineno,
                getattr(node, "end_lineno", node.lineno),
                node.name,
            )
            self.add_edge(container, node_id, "contains", node.lineno)
            for child in ast.iter_child_nodes(node):
                self.visit(child, file_id, path, node_id, stack)
            return

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node_id = (
                f"{file_id}::{node.name}"
                if not stack
                else f"{stack[-1][1]}::{node.name}"
            )
            if stack:
                node_id = f"{stack[-1][1]}::{node.name}"
            self.add_node(
                node_id,
                "function",
                path,
                node.lineno,
                getattr(node, "end_lineno", node.lineno),
                node.name,
            )
            self.add_edge(container, node_id, "contains", node.lineno)
            child_stack = stack + [(node.name, node_id)]
            for child in ast.iter_child_nodes(node):
                self.visit(child, file_id, path, node_id, child_stack)
            return

        if isinstance(node, ast.Call) and stack:
            callee = call_name(node)
            simple = callee.rsplit(".", 1)[-1]
            target = self.func_index.get(simple)
            if target:
                self.add_edge(stack[-1][1], target, "calls", node.lineno)

        for child in ast.iter_child_nodes(node):
            self.visit(child, file_id, path, container, stack)


def build_graph(root: Path, py_files: list[Path], trees) -> GraphBuilder:
    graph = GraphBuilder()
    modules: set[str] = set()

    # pass 1: nodes + contains + imports (needs full func_index, so ids are stable)
    for path in py_files:
        rel = relpath(root, path)
        tree = trees.get(rel, (None, ""))[0]
        if tree is None:
            continue
        file_id = f"file:{rel}"
        graph.add_node(
            file_id, "file", rel, 1, len(trees[rel][1].splitlines()) or 1, rel
        )
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # relative imports are intra-repo structure, not external modules
                if isinstance(node, ast.ImportFrom) and node.level > 0:
                    continue
                targets = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module]
                )
                for name in targets:
                    root_name = dotted_root(name)
                    if not root_name:
                        continue
                    mod_id = f"module:{root_name}"
                    if mod_id not in modules:
                        modules.add(mod_id)
                        graph.add_node(mod_id, "module", rel, 0, 0, root_name)
                    graph.add_edge(file_id, mod_id, "imports", node.lineno)
        graph.visit(tree, file_id, rel, file_id, [])

    return graph


def cmd_decompose(root: Path, out_dir: Path) -> None:
    out = out_dir if out_dir.is_absolute() else root / out_dir
    out.mkdir(parents=True, exist_ok=True)
    py_files = [p for p in collect_files(root, out_dir) if p.suffix == ".py"]
    trees, _ = files_scanned_flags(root, py_files)
    graph = build_graph(root, py_files, trees)

    payload = {"root": str(root), "nodes": graph.nodes, "edges": graph.edges}
    path = out / "decompose.json"
    path.write_text(json.dumps(payload))
    receipt = {
        "ok": True,
        "command": "decompose",
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "out": str(path),
    }
    print(json.dumps(receipt, separators=(",", ":")))


# ---------------------------------------------------------------- context


def is_source(name: str, path: str, params: str) -> bool:
    hay = f"{name} {path} {params}".lower()
    if any(part in hay for part in SOURCE_NAME_PARTS):
        return True
    if any(part in params.lower() for part in SOURCE_PARAM_PARTS):
        return True
    low = path.lower()
    return any(tag in low for tag in ("route", "view", "api", "controller", "handler"))


def is_mitigator(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in MITIGATOR_WORDS)


def build_call_graph(trees, py_files, root) -> tuple[list[dict], list[tuple[str, str]]]:
    functions: list[dict] = []
    edges: list[tuple[str, str]] = []
    index_by_simple: dict[str, str] = {}

    for path in py_files:
        rel = relpath(root, path)
        tree, _ = trees.get(rel, (None, ""))
        if tree is None:
            continue
        file_id = f"file:{rel}"

        def walk(node, stack):
            if isinstance(node, ast.ClassDef):
                for child in ast.iter_child_nodes(node):
                    walk(child, stack)
                return
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                node_id = (
                    f"{stack[-1][1]}::{node.name}"
                    if stack
                    else f"{file_id}::{node.name}"
                )
                functions.append(
                    {
                        "id": node_id,
                        "file": rel,
                        "name": node.name,
                        "class": None,
                        "start_line": node.lineno,
                        "end_line": getattr(node, "end_lineno", node.lineno),
                        "params": ast.unparse(node.args),
                        "source_like": is_source(
                            node.name, rel, ast.unparse(node.args)
                        ),
                    }
                )
                index_by_simple.setdefault(node.name, node_id)
                child_stack = stack + [(node.name, node_id)]
                for child in ast.iter_child_nodes(node):
                    walk(child, child_stack)
                return
            if isinstance(node, ast.Call) and stack:
                simple = call_name(node).rsplit(".", 1)[-1]
                target = index_by_simple.get(simple)
                if target:
                    edges.append((stack[-1][1], target))
            for child in ast.iter_child_nodes(node):
                walk(child, stack)

        walk(tree, [])

    # class attribute: rebuild quickly by re-walking with class context
    return functions, edges


def functions_with_class(trees, py_files, root):
    """Function records that know their enclosing class (for containment edges)."""
    records: list[dict] = []
    simple_index: dict[str, str] = {}

    def class_of(node) -> str | None:
        cur = node
        while cur is not None:
            if isinstance(cur, ast.ClassDef):
                return cur.name
            cur = getattr(cur, "parent", None)
        return None

    for path in py_files:
        rel = relpath(root, path)
        tree, _ = trees.get(rel, (None, ""))
        if tree is None:
            continue
        file_id = f"file:{rel}"
        # attach parents for container lookup
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        tree.parent = None

        def walk(node, stack):
            if isinstance(node, ast.ClassDef):
                for child in ast.iter_child_nodes(node):
                    walk(child, stack)
                return
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cname = class_of(node)
                node_id = (
                    f"{file_id}::{cname}::{node.name}"
                    if cname
                    else f"{file_id}::{node.name}"
                )
                params = ast.unparse(node.args)
                records.append(
                    {
                        "id": node_id,
                        "file": rel,
                        "name": node.name,
                        "class": cname,
                        "start_line": node.lineno,
                        "end_line": getattr(node, "end_lineno", node.lineno),
                        "params": params,
                        "source_like": is_source(node.name, rel, params),
                    }
                )
                simple_index.setdefault(node.name, node_id)
                child_stack = stack + [(node.name, node_id)]
                for child in ast.iter_child_nodes(node):
                    walk(child, child_stack)
                return
            if isinstance(node, ast.Call) and stack:
                simple = call_name(node).rsplit(".", 1)[-1]
                target = simple_index.get(simple)
                if target:
                    records.append({"_edge": (stack[-1][1], target)})
            for child in ast.iter_child_nodes(node):
                walk(child, stack)

        walk(tree, [])

    return records


def cmd_context(root: Path, out_dir: Path) -> None:
    out = out_dir if out_dir.is_absolute() else root / out_dir
    out.mkdir(parents=True, exist_ok=True)
    py_files = [p for p in collect_files(root, out_dir) if p.suffix == ".py"]
    trees, flags = files_scanned_flags(root, py_files)
    records = functions_with_class(trees, py_files, root)

    fn_nodes = [r for r in records if "_edge" not in r]
    call_edges = sorted({r["_edge"] for r in records if "_edge" in r})

    # id already encodes containment; container id for reverse lookups
    id_of_record = {r["id"]: r for r in fn_nodes}

    # in-degree -> source selection (roots) plus heuristic entry names
    indeg: dict[str, int] = {r["id"]: 0 for r in fn_nodes}
    for _, dst in call_edges:
        indeg[dst] = indeg.get(dst, 0) + 1
    sources = [
        r["id"] for r in fn_nodes if r["source_like"] or indeg.get(r["id"], 0) == 0
    ]

    reverse: dict[str, list[str]] = {}
    for src, dst in call_edges:
        reverse.setdefault(dst, []).append(src)

    # map flags to enclosing function nodes
    fn_by_file: dict[str, list[dict]] = {}
    for record in fn_nodes:
        fn_by_file.setdefault(record["file"], []).append(record)

    def flag_node(flag) -> str | None:
        for record in fn_by_file.get(flag["file"], []):
            if record["start_line"] <= flag["line"] <= record["end_line"]:
                return record["id"]
        same = fn_by_file.get(flag["file"], [])
        return same[0]["id"] if same else None

    path_cache: dict[str, list[list[str]]] = {}

    def reverse_paths(target: str) -> list[list[str]]:
        if target in path_cache:
            return path_cache[target]
        parent: dict[str, str | None] = {target: None}
        queue = deque([target])
        while queue:
            cur = queue.popleft()
            for pred in reverse.get(cur, ()):
                if pred not in parent:
                    parent[pred] = cur
                    queue.append(pred)
        paths = []
        for src in sources:
            if src not in parent:
                continue
            chain, cur = [], src
            while cur is not None:
                chain.append(cur)
                cur = parent[cur]
            paths.append(chain)
        path_cache[target] = paths
        return paths

    risky_nodes: set[str] = set()
    vulns = []
    for flag in flags:
        node = flag_node(flag)
        paths = reverse_paths(node) if node else []
        for chain in paths:
            risky_nodes.update(chain)

        closures = []
        for chain in paths:
            for node_id in chain:
                record = id_of_record.get(node_id)
                if record and not is_mitigator(record["name"]):
                    closures.append(
                        f"Add input validation / authorization gate at {node_id} "
                        f"({record['file']}:{record['start_line']})"
                    )
        deduped: list[str] = []
        seen_closures: set[str] = set()
        for closure in closures:
            if closure not in seen_closures:
                seen_closures.add(closure)
                deduped.append(closure)
        closures = deduped

        any_mit = any(
            is_mitigator(id_of_record[n]["name"])
            for chain in paths
            for n in chain
            if n in id_of_record
        )
        prob = flag["confidence"]
        if paths:
            prob = min(prob * 1.25, 0.999)
            if not any_mit:
                prob = min(prob * 1.1, 0.999)
        else:
            prob *= 0.5

        vulns.append(
            {
                **flag,
                "function_node": node,
                "reachable_from_source": bool(paths),
                "reachability_paths": paths,
                "contextual_probability": round(prob, 3),
                "needed_closures": closures,
            }
        )

    # related holes: flags that share a node already on a reachable vuln path
    by_node: dict[str, list[str]] = {}
    for flag, entry in zip(flags, vulns):
        if entry["function_node"]:
            by_node.setdefault(entry["function_node"], []).append(flag["id"])
    for entry in vulns:
        related = (
            {
                fid
                for node in entry["reachability_paths"][0]
                for fid in by_node.get(node, [])
            }
            if entry["reachability_paths"]
            else set()
        )
        related.discard(entry["id"])
        entry["related_holes"] = sorted(related)

    key = {
        "functions": len(fn_nodes),
        "sources": len(sources),
        "vuln_flags": len(vulns),
        "reachable_vulns": sum(1 for v in vulns if v["reachable_from_source"]),
        "needed_closures": sum(len(v["needed_closures"]) for v in vulns),
    }
    payload = {
        "root": str(root),
        "sources": sources,
        "nodes": len(fn_nodes),
        "vulnerable_flags": vulns,
        "contextual_flag_count_key": key,
    }
    path = out / "context_prob.json"
    path.write_text(json.dumps(payload, indent=2))
    receipt = {
        "ok": True,
        "command": "context",
        "nodes": len(fn_nodes),
        "sources": len(sources),
        "vulns": len(vulns),
        "reachable_vulns": key["reachable_vulns"],
        "out": str(path),
    }
    print(json.dumps(receipt, separators=(",", ":")))


# ---------------------------------------------------------------- cli


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="structural_ir",
        description="Deterministic structural IR for Python repos (stdlib only).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(".ir"),
        help="output directory, relative to repo root or absolute",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("snapshot", "analyze", "decompose", "context"):
        sp = sub.add_parser(name)
        sp.add_argument("root", type=Path)

    args = parser.parse_args()
    table = {
        "snapshot": cmd_snapshot,
        "analyze": cmd_analyze,
        "decompose": cmd_decompose,
        "context": cmd_context,
    }
    table[args.cmd](args.root, args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
