"""repo_eval — deterministic repo-state automaton (the external verifier).

Turns a whole repo into ONE compact eval.json the agent reads instead of
spinning sub-agents. Stdlib-only, offline, reproducible. The agent calls this
via run_command, reads the summary, edits, and calls it again to verify — the
compiler + the repo's own tests are the non-driftable oracle.

Stages (cheap/deterministic by default; build+test are opt-in to protect the
per-task compute budget):

  1. snapshot        — freeze repo bytes (snapshot.json: per-file sha256 + tree hash)
  2. semIR DAG       — parse to nodes/edges (stdlib `ast`)
  3. PARITY CHECK    — prove the DAG is a faithful, non-drifted derivation of the
                       frozen snapshot: recompute the tree hash from snapshot
                       files, require it == snapshot.tree_sha256 == ir.tree_sha256,
                       and require every IR file-node to exist in the snapshot
                       (no phantom/drifted files). Hard gate: parity.ok.
  4. localization    — BM25 over live function source supplies restart mass to
                       a light typed walk over contains/calls/imports.
  5. syntax          — py_compile every touched .py (always available).
  6. typecheck       — mypy/pyright on changed files IF present (else skipped).
  7. build  (--build "<cmd>")  — run it; report rc + log tail.
  8. tests  (--test  "<cmd>")  — run the repo's OWN tests; report pass/fail +
                       failing nodeids/file:line/trace. NEVER the hidden test_patch.

Usage:
  python repo_eval.py <container_id> <repo_dir> [--problem-file F | --problem "..."]
      [--changed f1.py,f2.py] [--typecheck] [--build "pip install -e ."]
      [--test "python -m pytest -q"] [--top-n N]
"""
import os, sys, re, json, hashlib, subprocess, argparse
# Run as an ADK skill script: sibling modules live beside this file, and the
# cache must stay out of /workspace so it never enters the submitted diff.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SEMDAG_CACHE", "/tmp/semdag-cache")
import cache, snapshot, semdag_ir_ast, retriever

GUARDRAIL = "repo_eval never reads held-out/hidden tests (test_patch); test signal uses the repo's own tests only."

def _recompute_tree(snap: dict) -> str:
    h = hashlib.sha256()
    for rel in sorted(snap["files"]):
        h.update(rel.encode()); h.update(snap["files"][rel]["sha256"].encode())
    return h.hexdigest()

def parity_check(container_id: str, snap: dict, ir: dict) -> dict:
    recomputed = _recompute_tree(snap)
    snap_tree = snap["tree_sha256"]; ir_tree = ir["tree_sha256"]
    ir_files = {n["file"] for n in ir["nodes"] if n["kind"] == "file"}
    phantom = sorted(f for f in ir_files if f not in snap["files"])  # drift: IR file not in snapshot
    py_in_snap = {r for r in snap["files"] if r.endswith(".py") and "content" in snap["files"][r]}
    covered = sorted(ir_files & py_in_snap)
    uncovered = sorted(py_in_snap - ir_files)  # parseable files the IR missed
    ok = (recomputed == snap_tree == ir_tree) and not phantom
    return {"ok": ok, "tree_sha256": snap_tree,
            "recomputed_matches_snapshot": recomputed == snap_tree,
            "ir_matches_snapshot": ir_tree == snap_tree,
            "phantom_files": phantom, "py_files": len(py_in_snap),
            "covered": len(covered), "uncovered_parseable": uncovered[:20]}

_SYM = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
def problem_symbols(text: str):
    if not text:
        return []
    # prefer backtick/quoted tokens, then dotted.attrs, then bare identifiers
    toks = re.findall(r"`([^`]+)`|'([^']+)'|\"([^\"]+)\"", text)
    flat = [t for grp in toks for t in grp if t]
    for m in re.findall(r"[A-Za-z_][\w\.]+", text):
        flat.append(m.split(".")[-1])
    seen, out = set(), []
    for t in flat:
        for w in _SYM.findall(t):
            if w not in seen:
                seen.add(w); out.append(w)
    return out[:40]

def py_compile_errors(snap: dict, changed=None):
    import ast as _ast
    errs = []
    targets = changed or [r for r in snap["files"] if r.endswith(".py") and "content" in snap["files"][r]]
    for rel in targets:
        e = snap["files"].get(rel, {})
        if "content" not in e:
            continue
        try:
            _ast.parse(e["content"], filename=rel)
        except SyntaxError as ex:
            errs.append({"file": rel, "line": ex.lineno, "msg": str(ex.msg)})
    return errs

def typecheck(repo: str, changed):
    import shutil
    tool = next((t for t in ("mypy", "pyright") if shutil.which(t)), None)
    if not tool or not changed:
        return {"ran": False, "tool": tool, "errors": []}
    try:
        p = subprocess.run([tool, *changed], cwd=repo, capture_output=True, text=True, timeout=120)
        errs = [l for l in p.stdout.splitlines() if ": error" in l][:50]
        return {"ran": True, "tool": tool, "errors": errs}
    except Exception as ex:
        return {"ran": False, "tool": tool, "error": str(ex)}

_PYTEST_FAIL = re.compile(r"^(FAILED|ERROR)\s+(?P<node>\S+)", re.M)
def run_cmd(repo, cmd, timeout):
    try:
        p = subprocess.run(cmd, cwd=repo, shell=True, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + "\n" + p.stderr)
    except Exception as ex:
        return 1, f"runner error: {ex}"

def verify_delta(container_id: str, repo: str, test_cmd=None):
    """Persistent incremental verify: diff the working tree against the FROZEN
    baseline snapshot (set on the first full run), re-check only changed files,
    and return a clean/regressed verdict. Cheap enough to run after every edit."""
    base = cache.read(container_id, "snapshot.json")   # the frozen baseline
    bfiles = base["files"]
    changed, added, removed = [], [], []
    seen = set()
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in snapshot.SKIP_DIRS]
        for name in sorted(names):
            fp = os.path.join(root, name)
            if not os.path.isfile(fp):
                continue
            rel = os.path.relpath(fp, repo); seen.add(rel)
            try:
                sha = cache.sha256_file(fp)
            except OSError:
                continue
            if rel not in bfiles:
                added.append(rel)
            elif bfiles[rel]["sha256"] != sha:
                changed.append(rel)
    removed = [r for r in bfiles if r not in seen]
    touched = sorted(set(changed + added))
    # re-parse + syntax only the touched .py (incremental; baseline stays frozen)
    import ast as _ast
    syntax = []
    for rel in touched:
        if not rel.endswith(".py"):
            continue
        fp = os.path.join(repo, rel)
        try:
            _ast.parse(open(fp, errors="replace").read(), filename=rel)
        except SyntaxError as ex:
            syntax.append({"file": rel, "line": ex.lineno, "msg": str(ex.msg)})
    tests = None
    if test_cmd:
        rc, log = run_cmd(repo, test_cmd, 600)
        fails = [{"node": m.group("node")} for m in _PYTEST_FAIL.finditer(log)][:50]
        tests = {"cmd": test_cmd, "rc": rc, "passed": rc == 0, "failures": fails,
                 "log_tail": log.strip().splitlines()[-12:]}
    clean = (not syntax) and (tests is None or tests["passed"])
    verdict = {"mode": "verify", "guardrail": GUARDRAIL,
               "baseline_tree_sha256": base["tree_sha256"][:12],
               "changed": changed, "added": added, "removed": removed,
               "syntax_errors": syntax, "tests": tests, "clean": clean}
    cache.write(container_id, "verify.json", verdict)
    cache.mark_stage(container_id, "verify",
                     {"clean": clean, "touched": len(touched), "syntax_errors": len(syntax)})
    print(json.dumps({"clean": clean, "changed": changed, "added": added,
        "removed": removed, "syntax_errors": syntax[:5],
        "tests": (tests and {"passed": tests["passed"], "failures": len(tests["failures"])})},
        indent=2))
    return verdict

def _normalize_argv(argv):
    """Accept the forms a small model actually emits through run_skill_script:
    one string holding the issue text, or one string holding a stringified list."""
    args = list(argv[1:])
    if len(args) == 1 and args[0].lstrip().startswith("["):
        try:
            import ast as _ast
            parsed = _ast.literal_eval(args[0])
            if isinstance(parsed, (list, tuple)):
                args = [str(x) for x in parsed]
        except (ValueError, SyntaxError):
            pass
    if len(args) == 1 and not args[0].startswith("--"):
        args = ["task", "/workspace", "--problem", args[0]]
    return [argv[0]] + args


def main():
    sys.argv = _normalize_argv(sys.argv)
    ap = argparse.ArgumentParser()
    ap.add_argument("container_id"); ap.add_argument("repo_dir")
    ap.add_argument("--problem"); ap.add_argument("--problem-file")
    ap.add_argument("--changed"); ap.add_argument("--typecheck", action="store_true")
    ap.add_argument("--build"); ap.add_argument("--test")
    ap.add_argument("--top-n", type=int, default=10)
    ap.add_argument("--verify", action="store_true",
                    help="incremental verify vs the frozen baseline (run after each edit)")
    a = ap.parse_args()
    if a.verify:
        verify_delta(a.container_id, os.path.abspath(a.repo_dir), a.test)
        return
    repo = os.path.abspath(a.repo_dir)
    problem = a.problem or (open(a.problem_file).read() if a.problem_file else "")
    changed = [c.strip() for c in a.changed.split(",")] if a.changed else None

    cache.init_container(a.container_id, repo)
    snap = snapshot.snapshot(a.container_id, repo)
    ir = semdag_ir_ast.build(a.container_id)
    par = parity_check(a.container_id, snap, ir)

    # Localization uses the issue against live function source, then performs a
    # light walk over the typed SemDAG.  Source evidence remains dominant.
    localization = []
    retrieval = None
    if par["ok"]:
        retrieval = retriever.rank(ir, snap, problem, a.top_n)
        localization = [
            {"rank": i + 1, **{k: site[k] for k in ("name", "qualname", "file", "line", "end_line",
                                                       "lexical_rank", "lexical_score", "structural_score")}}
            for i, site in enumerate(retrieval["top"])
        ]

    syntax = py_compile_errors(snap, changed)
    types = typecheck(repo, changed) if a.typecheck else {"ran": False}
    build = None
    if a.build:
        rc, log = run_cmd(repo, a.build, 600)
        build = {"cmd": a.build, "rc": rc, "ok": rc == 0, "log_tail": log.strip().splitlines()[-15:]}
    tests = None
    if a.test:
        rc, log = run_cmd(repo, a.test, 600)
        fails = [{"node": m.group("node")} for m in _PYTEST_FAIL.finditer(log)][:50]
        tests = {"cmd": a.test, "rc": rc, "passed": rc == 0,
                 "failures": fails, "log_tail": log.strip().splitlines()[-15:]}

    out = {"guardrail": GUARDRAIL, "repo": repo, "parity": par,
           "semdag": ir["counts"], "retrieval": retrieval,
           "localization": localization, "syntax_errors": syntax,
           "typecheck": types, "build": build, "tests": tests}
    cache.write(a.container_id, "eval.json", out)
    cache.mark_stage(a.container_id, "repo_eval",
                     {"parity_ok": par["ok"], "syntax_errors": len(syntax),
                      "localized": len(localization)})
    # agent-facing compact summary
    print(json.dumps({"parity_ok": par["ok"], "tree_sha256": par["tree_sha256"][:12],
        "files": par["py_files"], "covered": par["covered"], "phantom": par["phantom_files"],
        "semdag": ir["counts"],
        "localizer": (retrieval and {k: retrieval[k] for k in ("method", "damping", "candidates",
                                                                 "matched_candidates", "relations_used")}),
        "top_edit_sites": localization[:6],
        "syntax_errors": syntax[:5],
        "build": (build and {"ok": build["ok"]}),
        "tests": (tests and {"passed": tests["passed"], "failures": len(tests["failures"])})},
        indent=2))

if __name__ == "__main__":
    main()
