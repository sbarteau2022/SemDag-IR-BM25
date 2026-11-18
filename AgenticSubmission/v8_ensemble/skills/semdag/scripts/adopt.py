"""adopt: apply candidate k's change to the main workspace and audit it there.

args: ["<k>"]

The main /workspace stays at the baseline until this call: implementers only edit their own
worktrees. adopt.py resets the main workspace's tracked files to the baseline (so a second
adopt replaces, never stacks), applies candidate k's diff, then runs the normal audit with the
candidate's own repro. After it, fix anything left directly in /workspace (not in .git/wt_*),
re-run audit.py, and call submit_patch. Prints one JSON object; never raises.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ensemble as E  # noqa: E402
import audit  # noqa: E402
import impact  # noqa: E402


def adopt(argv):
    k = E.parse_k([str(a) for a in argv])
    if not k or k > E.K_MAX:
        return {"error": 'args: ["<candidate number 1-4>"]'}
    diff = E.candidate_diff(k)
    if not diff.strip():
        return {"error": f"candidate {k} is empty; adopt the next one in the gate ranking"}
    root = E.root()
    ref = impact.baseline_ref(root) or "HEAD"
    # back to the baseline for tracked files; remove untracked non-ignored files a previous
    # adopt created (never touches .git/ or ignored caches)
    E.git(root, "checkout", "-q", ref, "--", ".")
    E.git(root, "clean", "-fdq", "-e", ".git")
    rc, _, err = E.git(root, "apply", "--whitespace=nowarn", "-", stdin=diff)
    if rc != 0:
        rc, _, err = E.git(root, "apply", "--3way", "--whitespace=nowarn", "-", stdin=diff)
    if rc != 0:
        return {"error": f"could not apply candidate {k}: {err.strip()[:200]}"}
    aud = E.read_json(f"{E.MAIN_CID}_wt{k}", "audit.json", {}) or {}
    repro = aud.get("repro_cmd") or ""
    # the candidate's repro ran inside its worktree; in the main workspace run it from the root
    repro = repro.replace(f"/workspace/.git/wt_{k}", "/workspace")
    res = audit.audit(["--repro", repro] if repro else [])
    res = audit._trim(res)
    res["adopted"] = k
    res["files"] = E.diff_files(diff)[:6]
    return res


def main(argv=None):
    try:
        out = adopt(sys.argv[1:] if argv is None else argv)
    except Exception as ex:  # never hand the model a traceback
        out = {"error": f"{type(ex).__name__}: {ex}"[:300]}
    print(E.dumps(out))
    return out


if __name__ == "__main__":
    main()
