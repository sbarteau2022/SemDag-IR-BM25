"""fork (the army script): give implementer k its own copy of the repository and a starting site.

args: ["<k>", "<the whole problem statement>"]

1. Runs the meta preflight once per task (cached: the second..fourth implementer get the cache).
2. Creates the git worktree <workspace>/.git/wt_<k> at the harness baseline. Git never tracks
   .git/, so nothing here can enter the submitted patch. read_file / edit_file accept the paths
   (".git/wt_<k>/<file>"), because they stay inside /workspace.
3. Assigns a different starting hypothesis to each implementer: k = 1..3 get the k-th ranked edit
   site with its exact current source; k = 4 gets the next-ranked sites and is told to re-check
   localization. Different starting points give real diversity instead of four copies of one guess.
Prints one JSON object; never raises.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ensemble as E  # noqa: E402
import impact  # noqa: E402
import meta  # noqa: E402

BUDGET = 5000


def fork(argv):
    args = [str(a) for a in argv]
    k = E.parse_k(args[:1]) or E.parse_k(args)
    if not k or k > E.K_MAX:
        return {"error": "first arg must be your implementer number 1-4",
                "hint": 'args: ["<k>", "<problem statement>"]'}
    issue_args = args[1:] if len(args) > 1 else []
    report = meta.preflight(issue_args)
    if report.get("error") and not report.get("cached"):
        return {"error": report["error"], "hint": 'args: ["<k>", "<problem statement>"]'}
    root = E.root()
    d = E.wt_dir(k)
    if not os.path.isdir(d):
        ref = impact.baseline_ref(root) or "HEAD"
        rc, _, err = E.git(root, "worktree", "add", "-q", "--detach", d, ref)
        if rc != 0:
            return {"error": f"git worktree add failed: {err.strip()[:200]}"}
    rel = E.wt_rel(k)
    sites = report.get("sites") or []
    out = {"k": k, "worktree": rel,
           "rule": f"Change code ONLY with edit.py args [\"{k}\", \"<file>\", \"<old>\", \"<new>\"] "
                   f"(it writes into {rel}). Read your copy with read_file('{rel}/<file>'). "
                   "Never edit the main workspace: the coordinator adopts the best copy."}
    if k <= len(sites) and k <= 3:
        s = dict(sites[k - 1])
        s["file"] = f"{rel}/{s['file']}"
        out["start_site"] = s
    else:
        out["start_sites"] = [f"{rel}/{x}" for x in (report.get("other_sites") or [])[:4]]
        out["note"] = ("You are the localization check: the top-ranked sites go to implementers "
                       "1-3. Confirm the real root cause; pick a different site if the issue "
                       "points elsewhere.")
    tests = report.get("tests_near_sites") or []
    run = f"cd /workspace/{rel} && PYTHONPATH=src:. "
    out["run_prefix"] = run
    if tests:
        out["test_cmd"] = run + meta.pytest_cmd(tests)
    bt = report.get("baseline_tests") or {}
    out["baseline_tests"] = {x: bt.get(x) for x in ("collected", "passed", "failed", "red_reason")}
    out["audit_args"] = ["--wt", str(k), "--repro", f"{run}python /tmp/repro_{k}.py"]
    out["next"] = (f"1) write /tmp/repro_{k}.py with run_command (heredoc) and run it with the "
                   f"run_prefix (it must fail now); 2) fix with edit.py [\"{k}\", file, old, new]; "
                   "3) run audit.py with audit_args; 4) end with one line: CANDIDATE <k> <decision>.")
    return out


def main(argv=None):
    try:
        out = fork(sys.argv[1:] if argv is None else argv)
        while len(E.dumps(out)) > BUDGET and out.get("start_site", {}).get("source"):
            src = out["start_site"]["source"]
            out["start_site"]["source"] = src[: len(src) * 3 // 4]
            out["start_site"]["source_truncated"] = True
    except Exception as ex:  # never hand the model a traceback
        out = {"error": f"{type(ex).__name__}: {ex}"[:300]}
    print(E.dumps(out))
    return out


if __name__ == "__main__":
    main()
