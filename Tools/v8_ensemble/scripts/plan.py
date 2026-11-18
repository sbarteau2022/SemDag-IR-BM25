"""plan: the lead's one call before anyone else starts (testing script + code-review material + copies).

args: ["<the whole problem statement>"]

1. Testing script: the meta preflight runs the nearest tests once at baseline (counts and the
   reason for any red) and ranks edit sites with their exact current source.
2. Code-review material: the top sites with their exact source and the next-ranked sites, so
   the lead can judge where the bug really is before assigning work.
3. Creates the four implementer copies .git/wt_1 .. .git/wt_4 at the harness baseline, so
   implementers start with an assignment and a copy and never have to set themselves up.
Prints one JSON object; never raises.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ensemble as E  # noqa: E402
import impact  # noqa: E402
import meta  # noqa: E402

BUDGET = 6500


def plan(argv):
    report = meta.preflight([a for a in argv if a.strip()])
    if report.get("error") and not report.get("cached"):
        return {"error": report["error"], "hint": 'args: ["<the whole problem statement>"]'}
    root = E.root()
    ref = impact.baseline_ref(root) or "HEAD"
    made = []
    for k in range(1, E.K_MAX + 1):
        d = E.wt_dir(k)
        if not os.path.isdir(d):
            rc, _, err = E.git(root, "worktree", "add", "-q", "--detach", d, ref)
            if rc != 0:
                return {"error": f"git worktree add failed for wt_{k}: {err.strip()[:200]}"}
        made.append(E.wt_rel(k))
    out = {"mode": "plan", "copies": made,
           "baseline_tests": {x: (report.get("baseline_tests") or {}).get(x)
                              for x in ("cmd", "collected", "passed", "failed", "red_reason", "tail")},
           "sites": report.get("sites") or [], "other_sites": report.get("other_sites") or [],
           "tests_near_sites": report.get("tests_near_sites") or []}
    out["next"] = ("Review the sites and the failing tests, then write exactly four lines "
                   "'ASSIGN <k>: <file> <function> - <what to change and why>', k = 1..4, each a "
                   "different hypothesis (different site, or a different fix at the same site).")
    return out


def _trim(out):
    while len(E.dumps(out)) > BUDGET:
        if out.get("other_sites"):
            out["other_sites"].pop()
            continue
        srcs = [s for s in out.get("sites", []) if len(s.get("source", "")) > 300]
        if srcs:
            s = max(srcs, key=lambda x: len(x["source"]))
            s["source"] = s["source"][: len(s["source"]) * 3 // 4]
            s["source_truncated"] = True
            continue
        if out["baseline_tests"].get("tail"):
            out["baseline_tests"]["tail"] = ""
            continue
        break
    return out


def main(argv=None):
    try:
        out = _trim(plan(E.normalize(sys.argv[1:] if argv is None else argv)))
    except Exception as ex:  # never hand the model a traceback
        out = {"error": f"{type(ex).__name__}: {ex}"[:300]}
    print(E.dumps(out))
    return out


if __name__ == "__main__":
    main()
