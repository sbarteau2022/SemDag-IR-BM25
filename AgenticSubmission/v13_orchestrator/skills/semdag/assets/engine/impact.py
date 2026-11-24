"""impact: what the current working-tree change does, read from git and the AST.

The harness builds the submitted patch with `git diff` against the tag `_swegemma_baseline`
and then removes every test and runner-config file from it. This module answers, before
`submit_patch`, the questions that decide whether a patch can score:

  1. patch preview   which files the patch will carry, which the harness will strip, whether
                     the patch is empty after stripping.
  2. change checks   syntax errors, names that became undefined, definitions that were removed
                     while other files still import or call them, and signature changes that
                     break existing callers.
  3. callers         library callers of every changed function (from the repository graph).
  4. tests_to_run    the existing test files most likely to exercise the change, ranked by
                     resolved test-to-source calls, name mentions, imports and path affinity.

Standard library only. It never writes inside the repository and never mutates the git index.
"""
import ast
import builtins
import os
import re
import subprocess

import retriever
import snapshot

# ---------------------------------------------------------------- constants (fixed by design)
BASELINE_REFS = ("_swegemma_baseline", "HEAD")
PROTECTED_NAMES = {"conftest.py", "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg", ".pytest.ini",
                   "sitecustomize.py", "usercustomize.py", "_swegemma_stubs.py"}
TEST_DIRS = {"tests", "test", "testing"}
W_CALL, W_MENTION, W_IMPORT, W_STEM, W_PATH, W_REACH = 3.0, 2.0, 1.0, 3.0, 1.5, 2.0
REACH_DEPTH, REACH_FRONTIER = 4, 400
MENTION_CAP = 3
MIN_NAME_LEN = 4
GENERIC_PATH_TOKENS = {"src", "lib", "python", "init", "main", "base", "core", "utils", "util", "common",
                       "helpers", "py", "tutorial", "docs"}
MAX_TESTS, MAX_CALLERS, MAX_LIST = 3, 6, 8
GREP_FILE_LIMIT = 40
TEST_CMD = "python -m pytest {files} -q -x 2>&1 | tail -30"


# ---------------------------------------------------------------- paths
def is_protected(rel: str) -> bool:
    """Mirror of the harness rule: these paths are removed from the submitted patch."""
    parts = rel.replace("\\", "/").split("/")
    name = parts[-1]
    if name in PROTECTED_NAMES or name.endswith(".pth"):
        return True
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py"):
        return True
    return bool(TEST_DIRS & {p.lower() for p in parts[:-1]}) and name.endswith(".py")


def is_test_module(rel: str) -> bool:
    name = rel.split("/")[-1]
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


# ---------------------------------------------------------------- git
def _git(repo, *args, timeout=30):
    try:
        p = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", *args],
                           capture_output=True, text=True, errors="replace", timeout=timeout)
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


AUTO_BASELINE = object()


class GitBaseline:
    """One verification's old-side reads, pinned to an immutable Git object."""
    def __init__(self, repo, label, oid):
        self.repo, self.label, self.oid = os.path.realpath(repo), label, oid
        self._contents = {}

    def check_repo(self, repo):
        if os.path.realpath(repo) != self.repo:
            raise ValueError("Git baseline belongs to another repository")

    def old_content(self, rel):
        if rel not in self._contents:
            rc, text = _git(self.repo, "show", f"{self.oid}:{rel}")
            if rc:
                return None
            self._contents[rel] = text
        return self._contents[rel]


def resolve_baseline(repo):
    for ref in BASELINE_REFS:
        rc, oid = _git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
        if rc == 0 and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", oid.strip()):
            return GitBaseline(repo, ref, oid.strip())
    return None


def baseline_ref(repo):
    baseline = resolve_baseline(repo)
    return baseline.label if baseline else None


def changed_paths(repo, ref):
    """{path: 'modified'|'added'|'deleted'} for the working tree against ref, as the harness
    patch will see it: tracked changes plus untracked files that are not ignored."""
    out = {}
    rc, text = _git(repo, "diff", "--name-status", "--no-renames", ref)
    if rc == 0:
        for line in text.splitlines():
            bits = line.split("\t")
            if len(bits) >= 2:
                out[bits[-1]] = {"M": "modified", "A": "added", "D": "deleted"}.get(bits[0][:1], "modified")
    rc, text = _git(repo, "ls-files", "--others", "--exclude-standard")
    if rc == 0:
        for rel in text.splitlines():
            if rel:
                out.setdefault(rel, "added")
    return {p: s for p, s in out.items() if not snapshot.is_harness_temp(p.split("/")[-1])}


def old_content(repo, ref, rel):
    rc, text = _git(repo, "show", f"{ref}:{rel}")
    return text if rc == 0 else None


def changed_paths_from_snapshot(repo, base_files):
    """Fallback when the workspace is not a git repository: diff against the cached snapshot."""
    out, seen = {}, set()
    import cache
    for root, dirs, names in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in snapshot.SKIP_DIRS)
        for name in sorted(names):
            if snapshot.is_harness_temp(name):
                continue
            fp = os.path.join(root, name)
            if not os.path.isfile(fp):
                continue
            rel = os.path.relpath(fp, repo)
            seen.add(rel)
            try:
                sha = cache.sha256_file(fp)
            except OSError:
                continue
            if rel not in base_files:
                out[rel] = "added"
            elif base_files[rel]["sha256"] != sha:
                out[rel] = "modified"
    for rel in base_files:
        if rel not in seen:
            out[rel] = "deleted"
    return out


# ---------------------------------------------------------------- AST facts
def _parse(text, rel):
    # CPython accepts a single UTF-8 BOM in source bytes; preserve file bytes,
    # but omit the decoded encoding marker from AST analysis.
    if text is not None:
        text = text.removeprefix('\ufeff')
    try:
        return ast.parse(text, filename=rel), None
    except SyntaxError as ex:
        return None, {"file": rel, "line": ex.lineno, "msg": str(ex.msg)}
    except (ValueError, RecursionError) as ex:
        return None, {"file": rel, "line": None, "msg": str(ex)}


def definitions(tree):
    """{qualname: node} for module-level functions and classes and for class members."""
    out = {}

    def visit(body, prefix):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[prefix + node.name] = node
            elif isinstance(node, ast.ClassDef):
                out[prefix + node.name] = node
                visit(node.body, prefix + node.name + ".")
            elif isinstance(node, (ast.If, ast.Try)):
                visit(node.body, prefix)
                for extra in getattr(node, "orelse", []), getattr(node, "finalbody", []):
                    visit(extra, prefix)
                for handler in getattr(node, "handlers", []):
                    visit(handler.body, prefix)
    visit(tree.body, "")
    return out


def _own_dump(node):
    """Dump that ignores positions. For a class, ignore its member definitions: a class counts
    as changed only when its bases, decorators or class-level statements changed."""
    if isinstance(node, ast.ClassDef):
        body = [ast.dump(n) for n in node.body
                if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        return "|".join(
            [ast.dump(b) for b in node.bases] + [ast.dump(k) for k in node.keywords]
            + [ast.dump(d) for d in node.decorator_list] + body)
    return ast.dump(node)


def _module_level_dump(tree):
    return "|".join(ast.dump(n) for n in tree.body
                    if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))


def signature(fn):
    a = fn.args
    pos = [x.arg for x in a.posonlyargs + a.args]
    required = len(pos) - len(a.defaults)
    kwonly = {x.arg: d is not None for x, d in zip(a.kwonlyargs, a.kw_defaults)}
    return {"pos": pos, "required": required, "kwonly": kwonly,
            "vararg": a.vararg is not None, "kwarg": a.kwarg is not None}


def signature_breaks(old_fn, new_fn):
    """Reasons an existing call site written for old_fn can fail against new_fn."""
    o, n = signature(old_fn), signature(new_fn)
    drop = 1 if o["pos"][:1] in (["self"], ["cls"]) and n["pos"][:1] == o["pos"][:1] else 0
    op, np_ = o["pos"][drop:], n["pos"][drop:]
    o_req, n_req = max(0, o["required"] - drop), max(0, n["required"] - drop)
    why = []
    absorbs = n["vararg"] and n["kwarg"]
    for name in op:
        if name not in np_ and name not in n["kwonly"] and not absorbs:
            why.append(f"parameter '{name}' was removed")
    common_old = [x for x in op if x in np_]
    common_new = [x for x in np_ if x in op]
    if common_old != common_new:
        why.append("positional parameters were reordered")
    for i, name in enumerate(np_):
        if name in op:
            if i < n_req and op.index(name) >= o_req:
                why.append(f"parameter '{name}' lost its default")
            continue
        if name in o["kwonly"]:
            continue
        if i < n_req:
            why.append(f"new required parameter '{name}'")
        elif any(later in op for later in np_[i + 1:]):
            why.append(f"parameter '{name}' was inserted before existing ones")
    for name, has_default in o["kwonly"].items():
        if name not in n["kwonly"] and name not in np_ and not n["kwarg"]:
            why.append(f"keyword parameter '{name}' was removed")
    for name, has_default in n["kwonly"].items():
        if not has_default and name not in o["kwonly"] and name not in op:
            why.append(f"new required keyword parameter '{name}'")
    return why


_BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__builtins__", "__spec__", "__loader__",
                                  "__package__", "__path__", "__class__", "__debug__", "__annotations__",
                                  "__dict__", "__qualname__", "__module__", "reveal_type", "__all__"}


def unbound_names(tree):
    """{name: first line} for names that are read but bound nowhere in the file.

    Scope-insensitive on purpose: a name counts as bound if any scope of the file binds it. That
    misses some real errors and reports almost no false ones. Files with a star import are skipped."""
    bound, loads = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
            return {}
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
            for tp in getattr(node, "type_params", []) or []:
                bound.add(tp.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                loads.setdefault(node.id, node.lineno)
            else:
                bound.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bound.add(node.rest)
        elif node.__class__.__name__ == "TypeAlias":
            if isinstance(node.name, ast.Name):
                bound.add(node.name.id)
            for tp in getattr(node, "type_params", []) or []:
                bound.add(tp.name)
    return {name: line for name, line in loads.items() if name not in bound and name not in _BUILTINS}


# ---------------------------------------------------------------- references to removed names
def _module_tail(rel):
    stem = rel[:-3] if rel.endswith(".py") else rel
    parts = stem.split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return parts[-1] if parts else ""


def references_to(repo, rel, name, new_tree):
    """Places that still use a top-level name removed from rel. High precision: an import of the
    name from a module with the same tail, an attribute access on that module, or a read of the
    name inside rel itself."""
    refs = []
    if new_tree is not None:
        for node in ast.walk(new_tree):
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load):
                refs.append(f"{rel}:{node.lineno}")
                break
    tail = _module_tail(rel)
    rc, text = _git(repo, "grep", "-l", "-w", "-F", "--untracked", "-e", name, "--", "*.py")
    files = [f for f in text.splitlines() if f and f != rel][:GREP_FILE_LIMIT] if rc == 0 else []
    for other in files:
        try:
            with open(os.path.join(repo, other), errors="replace") as fh:
                tree, _ = _parse(fh.read(), other)
        except OSError:
            continue
        if tree is None:
            continue
        for node in ast.walk(tree):
            hit = None
            if isinstance(node, ast.ImportFrom) and any(a.name == name for a in node.names):
                mod = (node.module or "").split(".")[-1]
                if mod == tail or (node.level and not node.module):
                    hit = node.lineno
            elif (isinstance(node, ast.Attribute) and node.attr == name
                  and isinstance(node.value, ast.Name) and node.value.id == tail):
                hit = node.lineno
            if hit:
                refs.append(f"{other}:{hit}")
                break
    return refs


# ---------------------------------------------------------------- graph look-ups
def _graph(ir):
    nodes = {n["id"]: n for n in ir["nodes"]}
    by_key = {}
    for n in ir["nodes"]:
        if n["kind"] in ("function", "method", "class"):
            by_key.setdefault((n["file"], n.get("qualname", n["name"])), n["id"])
    callers, imports = {}, {}
    for e in ir["edges"]:
        if e["rel"] in ("calls", "instantiates") and e["src"] != e["dst"]:  # recursion is not a caller
            callers.setdefault(e["dst"], set()).add(e["src"])
        elif e["rel"] == "imports":
            imports.setdefault(e["src"], set()).add(e["dst"])
    return nodes, by_key, callers, imports


def _path_tokens(rel, strip_test_prefix=False):
    """Discriminating tokens of a path. The top-level directory (the package or `tests`) is shared
    by nearly every file, so it is left out."""
    out = set()
    stem = rel[:-3] if rel.endswith(".py") else rel
    parts = stem.split("/")
    if parts[0] == "src" and len(parts) > 2:
        parts = parts[1:]
    if len(parts) > 1:
        parts = parts[1:]
    for part in parts:
        if strip_test_prefix:
            part = re.sub(r"^test_|_test$", "", part)
        for tok in re.split(r"[^A-Za-z0-9]+|_", part):
            tok = tok.lower()
            if len(tok) >= 3 and tok not in GENERIC_PATH_TOKENS and tok not in TEST_DIRS:
                out.add(tok)
    return out


def rank_tests(ir, repo, targets, read=None):
    """Rank existing test modules for a set of target definitions.

    targets: list of (file, qualname). Score per test module (weights fixed by design):
      3.0  per distinct target that a function in the test module calls (resolved edge)
      2.0  per distinct target name the module's text mentions as a whole word (at most 3)
      1.0  if the module imports a target's file
      3.0  if the module is named test_<stem>.py or <stem>_test.py for a target's file
      1.5  per path token shared with a target's file (directories and stem)
    """
    nodes, by_key, callers, imports = _graph(ir)
    files = sorted({f for f, _ in targets})
    target_ids = {by_key[k] for k in targets if k in by_key}
    names = set()
    for _f, q in targets:
        for part in q.split("."):
            if len(part) >= MIN_NAME_LEN and not (part.startswith("__") and part.endswith("__")):
                names.add(part)
    name_res = {n: re.compile(r"\b" + re.escape(n) + r"\b") for n in sorted(names)}
    file_ids = {f"file:{f}" for f in files}
    stems = {_module_tail(f) for f in files} - {""}
    tokens = set().union(*[_path_tokens(f) for f in files]) if files else set()

    called_by_file = {}
    for tid in target_ids:
        for src in callers.get(tid, ()):
            n = nodes.get(src)
            if n and is_test_module(n["file"]):
                called_by_file.setdefault(n["file"], set()).add(tid)

    # Reach: walk the inverse call edges from the targets through library code; the first test
    # function met on each path gives its file a score that falls with the number of hops.
    reach, frontier, seen = {}, set(target_ids), set(target_ids)
    for depth in range(1, REACH_DEPTH + 1):
        nxt = set()
        for nid in sorted(frontier):
            for src in callers.get(nid, ()):
                if src in seen:
                    continue
                seen.add(src)
                f = nodes[src]["file"]
                if is_test_module(f):
                    reach.setdefault(f, depth)
                elif not retriever.is_test_path(f):
                    nxt.add(src)
        frontier = set(sorted(nxt)[:REACH_FRONTIER])
        if not frontier:
            break

    scored = []
    for n in ir["nodes"]:
        if n["kind"] != "file" or not is_test_module(n["file"]):
            continue
        rel = n["file"]
        if not os.path.isfile(os.path.join(repo, rel)):
            continue
        why, score = [], 0.0
        calls = len(called_by_file.get(rel, ()))
        if calls:
            score += W_CALL * calls
            why.append(f"calls {calls}")
        elif rel in reach:
            score += W_REACH / reach[rel]
            why.append(f"reaches in {reach[rel]}")
        text = read(rel) if read else None
        if text is None:
            try:
                with open(os.path.join(repo, rel), errors="replace") as fh:
                    text = fh.read()
            except OSError:
                text = ""
        mentions = sum(1 for rx in name_res.values() if rx.search(text))
        if mentions:
            score += W_MENTION * min(MENTION_CAP, mentions)
            why.append(f"mentions {mentions}")
        if imports.get(n["id"], set()) & file_ids:
            score += W_IMPORT
            why.append("imports")
        stem = re.sub(r"^test_|_test$", "", rel.split("/")[-1][:-3])
        if stem in stems:
            score += W_STEM
            why.append("name")
        shared = len(tokens & _path_tokens(rel, strip_test_prefix=True))
        if shared:
            score += W_PATH * shared
            why.append(f"path {shared}")
        if score > 0:
            scored.append((-score, rel, ", ".join(why)))
    scored.sort()
    return [{"file": rel, "score": round(-neg, 1), "why": why} for neg, rel, why in scored]


def callers_of(ir, targets, limit=MAX_CALLERS):
    nodes, by_key, callers, _imports = _graph(ir)
    lib, tests = [], 0
    seen = set()
    for key in targets:
        tid = by_key.get(key)
        for src in sorted(callers.get(tid, ())) if tid else ():
            n = nodes.get(src)
            if not n or src in seen:
                continue
            seen.add(src)
            if retriever.is_test_path(n["file"]):
                tests += 1
            else:
                lib.append(f"{n['file']}:{n['line']} {n.get('qualname', n['name'])}")
    return {"library": lib[:limit], "library_total": len(lib), "test_callers": tests}


# ---------------------------------------------------------------- main analysis
def analyze(repo, ir=None, base_files=None, read=None, baseline=AUTO_BASELINE):
    """Full verdict for the working tree. ir: repository graph (baseline or current).
    base_files: cached snapshot files, used only when the workspace has no git history."""
    if baseline is AUTO_BASELINE:
        baseline = resolve_baseline(repo)
    if baseline is not None:
        baseline.check_repo(repo)
    ref = baseline.oid if baseline else None
    if ref:
        paths = changed_paths(repo, ref)
        base = baseline.label
    elif base_files is not None:
        paths = changed_paths_from_snapshot(repo, base_files)
        base = "snapshot"
    else:
        return {"mode": "verify", "error": "no git history and no cached snapshot",
                "next": "Run the localizer once first, then verify again."}

    kept = sorted(p for p in paths if not is_protected(p))
    stripped = sorted(p for p in paths if is_protected(p))
    new_files = [p for p in kept if paths[p] == "added"]

    syntax, undefined, breaks, removed_used = [], [], [], []
    changed_defs, targets, module_level = [], [], []
    for rel in kept:
        if not rel.endswith(".py") or paths[rel] == "deleted":
            continue
        try:
            with open(os.path.join(repo, rel), errors="replace") as fh:
                new_text = fh.read()
        except OSError:
            continue
        new_tree, err = _parse(new_text, rel)
        if err:
            syntax.append(err)
            continue
        if paths[rel] == "added":
            old_text = None
        elif ref:
            old_text = baseline.old_content(rel)
        else:
            old_text = (base_files.get(rel) or {}).get("content")
        old_tree = _parse(old_text, rel)[0] if old_text is not None else None

        new_unbound = unbound_names(new_tree)
        old_unbound = unbound_names(old_tree) if old_tree is not None else {}
        for name, line in sorted(new_unbound.items(), key=lambda kv: kv[1]):
            if name not in old_unbound:
                undefined.append({"file": rel, "name": name, "line": line})

        new_defs = definitions(new_tree)
        if old_tree is None:
            for q, node in new_defs.items():
                if not isinstance(node, ast.ClassDef):
                    changed_defs.append(f"{rel}::{q} (new)")
            continue
        old_defs = definitions(old_tree)
        if _module_level_dump(old_tree) != _module_level_dump(new_tree):
            module_level.append(rel)
        for q, node in new_defs.items():
            old = old_defs.get(q)
            if old is None:
                if not isinstance(node, ast.ClassDef):
                    changed_defs.append(f"{rel}::{q} (new)")
                    targets.append((rel, q))
                continue
            if _own_dump(old) == _own_dump(node):
                continue
            changed_defs.append(f"{rel}::{q}")
            targets.append((rel, q))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                    isinstance(old, (ast.FunctionDef, ast.AsyncFunctionDef)):
                why = signature_breaks(old, node)
                if why:
                    entry = {"def": f"{rel}::{q}", "why": why[:3]}
                    if ir is not None:
                        c = callers_of(ir, [(rel, q)])
                        entry["callers"] = c["library_total"] + c["test_callers"]
                    breaks.append(entry)
        for q in old_defs:
            if q in new_defs or any(q.startswith(p + ".") and p not in new_defs for p in old_defs):
                continue
            if "." in q:
                if ir is None:
                    continue
                c = callers_of(ir, [(rel, q)])
                live = []
                for site in c["library"]:
                    caller_file = site.split(":")[0]
                    try:
                        with open(os.path.join(repo, caller_file), errors="replace") as fh:
                            if re.search(r"\b" + re.escape(q.split(".")[-1]) + r"\s*\(", fh.read()):
                                live.append(site.split(" ")[0])
                    except OSError:
                        pass
                if live:
                    removed_used.append({"def": f"{rel}::{q}", "refs": live[:3]})
            else:
                refs = references_to(repo, rel, q, new_tree) if ref else []
                if refs:
                    removed_used.append({"def": f"{rel}::{q}", "refs": refs[:3]})

    out = {"mode": "verify", "base": base,
           "patch": {"files": kept[:MAX_LIST], "n_files": len(kept), "new_files": new_files[:MAX_LIST],
                     "stripped": stripped[:MAX_LIST], "empty": not kept},
           "syntax_errors": syntax[:5], "undefined_names": undefined[:MAX_LIST],
           "signature_breaks": breaks[:4], "removed_still_used": removed_used[:4],
           "changed_defs": changed_defs[:MAX_LIST]}
    if module_level:
        out["module_level_changed"] = module_level[:4]

    tests = []
    if ir is not None:
        focus = targets or [(rel, "") for rel in kept if rel.endswith(".py")]
        if targets:
            priority = [(b["def"].split("::")[0], b["def"].split("::")[1]) for b in breaks]
            ordered = priority + [t for t in targets if t not in priority]
            c = callers_of(ir, ordered)
            if c["library_total"] or c["test_callers"]:
                out["callers_to_check"] = c
        tests = rank_tests(ir, repo, focus, read)[:MAX_TESTS]
    out["tests_to_run"] = tests
    if tests:
        out["test_cmd"] = TEST_CMD.format(files=tests[0]["file"])

    out["clean"] = not (syntax or undefined or removed_used or not kept)
    out["next"] = advise(out)
    return out


def advise(v):
    """One deterministic next step, most severe finding first."""
    p = v["patch"]
    if v["syntax_errors"]:
        e = v["syntax_errors"][0]
        return f"Fix the syntax error in {e['file']} line {e['line']}: {e['msg']}."
    if p["empty"]:
        if p["stripped"]:
            return ("The patch would be EMPTY: you changed only test or config files, which are removed "
                    "from the patch. Fix the library source instead.")
        return "The patch would be EMPTY: no file changed yet. Make the edit before submitting."
    if v["undefined_names"]:
        u = v["undefined_names"][0]
        return f"'{u['name']}' is used in {u['file']} line {u['line']} but never defined or imported. Add the import or fix the name."
    if v["removed_still_used"]:
        r = v["removed_still_used"][0]
        return f"{r['def']} was removed or renamed but is still used at {r['refs'][0]}. Keep the old name or update that use."
    if v["signature_breaks"]:
        b = v["signature_breaks"][0]
        return (f"{b['def']}: {b['why'][0]}. Existing callers may break "
                f"({b.get('callers', '?')} known). Give the parameter a default or update the callers.")
    scratch = [f for f in p["new_files"] if not f.endswith(".py") or "/" not in f]
    if scratch:
        return f"New file {scratch[0]} will be part of the patch. Delete it if it is a scratch file."
    if v.get("test_cmd"):
        return "Run: " + v["test_cmd"] + "  Then submit_patch."
    return "No problem found. Run a targeted test if one exists, then submit_patch."
