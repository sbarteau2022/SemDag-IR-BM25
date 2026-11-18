"""gate: the coordinator's deterministic judgment over the 4 candidates, in one call.

args: []

For every non-empty candidate k (worktree .git/wt_<k>):
  static   - typecheck stand-in (the sandbox has no mypy/pyright/pyflakes): syntax errors,
             undefined names, removed-but-still-used names and signature breaks (repo_eval verify)
  review   - code-review rules on the diff: test/config edits (stripped by the harness), scratch
             files, debug leftovers (print/pdb/breakpoint), TODO/FIXME, bare except, size
  tests    - the nearest test files plus test files named after each edited module, run once in
             the candidate's own copy (its sources first on PYTHONPATH)
  repro    - the repro the implementer gave to its audit
  cex      - every saved adversarial counterexample for every candidate (a counterexample that
             fails on every candidate is treated as a broken counterexample and ignored)
Suites run two at a time (the sandbox has 2 vCPUs). Ranks candidates and prints the winner.
Prints one JSON object; never raises.
"""
import concurrent.futures as cf
import glob
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ensemble as E  # noqa: E402
import audit  # noqa: E402
import meta  # noqa: E402
import repo_eval  # noqa: E402

BUDGET = 3500
TEST_TIMEOUT = 75
CEX_TIMEOUT = 20
WORKERS = 2
TEST_FILE_CAP = 4
DEBUG = re.compile(r"^\+(?!\+\+).*\b(print\(|pdb\.set_trace|breakpoint\(\))", re.M)
TODO = re.compile(r"^\+(?!\+\+).*\b(TODO|FIXME|XXX)\b", re.M)
BARE = re.compile(r"^\+(?!\+\+)\s*except\s*:", re.M)


def review(diff, files):
    issues = []
    prot = [f for f in files if audit.impact.is_protected(f) or audit.impact.is_test_module(f)]
    if prot:
        issues.append("edits test/config files (stripped at grading): " + ", ".join(prot[:3]))
    scratch = [f for f in files if audit.SCRATCH.search(f)]
    if scratch:
        issues.append("scratch files in patch: " + ", ".join(scratch[:3]))
    if DEBUG.search(diff):
        issues.append("debug leftovers (print/pdb/breakpoint) added")
    if TODO.search(diff):
        issues.append("TODO/FIXME added")
    if BARE.search(diff):
        issues.append("bare except added")
    added = len(re.findall(r"^\+(?!\+\+)", diff, flags=re.M))
    if added > 150:
        issues.append(f"large change ({added} added lines) for a single issue")
    return issues, added


def static(k):
    ropt = repo_eval.parse_args(["--verify", "--repo", E.wt_dir(k),
                                 "--container", f"{E.MAIN_CID}_wt{k}"])
    v = repo_eval.verify(ropt)
    found = {x: v.get(x) for x in ("syntax_errors", "undefined_names", "removed_still_used",
                                   "signature_breaks") if v.get(x)}
    return [f"{x}: " + E.dumps(y)[:160] for x, y in found.items()]


def test_files_for(k, files, base_tests):
    root = E.wt_dir(k)
    out = list(base_tests)
    for f in files:
        mod = os.path.splitext(os.path.basename(f))[0]
        for t in glob.glob(os.path.join(root, "**", f"test_{mod}.py"), recursive=True):
            rel = os.path.relpath(t, root)
            if ".git" + os.sep not in rel and rel not in out:
                out.append(rel)
    return out[:TEST_FILE_CAP]


def run(cmd, cwd, env, timeout):
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                           timeout=timeout, shell=isinstance(cmd, str))
        tail = "\n".join(((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-3:])
        return p.returncode == 0, tail[-240:]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except OSError as ex:
        return False, str(ex)[:120]


def suite(k, files, base_tests, cex_files, main_root):
    d = E.wt_dir(k)
    env = meta.run_env(d)
    res = {"k": k}
    tf = test_files_for(k, files, base_tests)
    if tf:
        t = meta.run_pytest(d, tf, TEST_TIMEOUT)
        res["tests"] = {x: t.get(x) for x in ("collected", "passed", "failed", "errors",
                                               "red_reason")}
    aud = E.read_json(f"{E.MAIN_CID}_wt{k}", "audit.json", {}) or {}
    if aud.get("repro_cmd"):
        ok, tail = run(["bash", "-c", audit.rewrite_paths(aud["repro_cmd"], main_root)],
                       d, env, 30)
        res["repro"] = {"green": ok, "tail": tail}
    cres = {}
    for c in cex_files:
        ok, tail = run([sys.executable, c], d, env, CEX_TIMEOUT)
        cres[os.path.basename(c)] = ok
    res["cex"] = cres
    return res


def gate(_argv):
    t0 = time.time()
    main_root = E.root()
    m = E.read_json(E.MAIN_CID, "meta.json", {}) or {}
    base_tests = m.get("tests_near_sites") or []
    base_red = (m.get("baseline_tests") or {}).get("failed") or 0
    cex_files = sorted(glob.glob(os.path.join(E.cex_dir(), "k*_*.py")))
    cands, jobs = {}, {}
    for k in range(1, E.K_MAX + 1):
        diff = E.candidate_diff(k)
        if not diff.strip():
            cands[k] = {"k": k, "empty": True}
            continue
        files = E.diff_files(diff)
        issues, added = review(diff, files)
        cands[k] = {"k": k, "files": files[:4], "added": added, "review": issues,
                    "static": static(k)}
    live = [k for k, c in cands.items() if not c.get("empty")]
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for k in live:
            jobs[k] = ex.submit(suite, k, cands[k]["files"], base_tests, cex_files, main_root)
        for k, j in jobs.items():
            cands[k].update(j.result())
    # a counterexample every live candidate fails is more likely wrong than all candidates
    cex_names = {n for k in live for n in cands[k].get("cex", {})}
    broken_cex = sorted(n for n in cex_names
                        if all(not cands[k]["cex"].get(n, True) for k in live)) if len(live) > 1 else []
    for k in live:
        c = cands[k]
        valid = {n: ok for n, ok in c.get("cex", {}).items() if n not in broken_cex}
        t = c.get("tests") or {}
        tests_ok = (t.get("red_reason") is None and (t.get("collected") or 0) > 0) or (
            t.get("red_reason") in ("assertion", "test_failure")
            and (t.get("failed") or 0) <= base_red)
        c["score"] = [int(not c["static"]), int(bool(tests_ok)),
                      int(bool((c.get("repro") or {}).get("green"))),
                      sum(valid.values()) - len(valid), int(not c["review"]), -c["added"]]
        c["cex_failed"] = sorted(n for n, ok in valid.items() if not ok)
        c.pop("cex", None)
    ranked = sorted(live, key=lambda k: cands[k]["score"], reverse=True)
    out = {"mode": "gate", "ranking": ranked, "winner": ranked[0] if ranked else None,
           "ignored_cex": broken_cex, "secs": round(time.time() - t0, 1),
           "candidates": [cands[k] for k in range(1, E.K_MAX + 1)],
           "score_order": "static_clean, tests_ok, repro_green, -cex_failed, review_clean, -size"}
    out["next"] = (f"Winner: candidate {out['winner']}. Report it as: WINNER <k>, then list its "
                   "open problems (static, review, failed tests, failed counterexamples)."
                   if ranked else "No candidate changed anything. Report: WINNER none.")
    try:
        E.cache.write(E.MAIN_CID, "gate.json", out)
    except OSError:
        pass
    return out


def _trim(out):
    while len(E.dumps(out)) > BUDGET:
        cut = False
        for c in out["candidates"]:
            for key in ("repro",):
                if c.get(key, {}).get("tail"):
                    c[key]["tail"] = ""
                    cut = True
            if len(c.get("static") or []) > 1:
                c["static"] = c["static"][:1]
                cut = True
        if not cut:
            break
    return out


def main(argv=None):
    try:
        out = _trim(gate(sys.argv[1:] if argv is None else argv))
    except Exception as ex:  # never hand the model a traceback
        out = {"mode": "gate", "error": f"{type(ex).__name__}: {ex}"[:300]}
    print(E.dumps(out))
    return out


if __name__ == "__main__":
    main()
