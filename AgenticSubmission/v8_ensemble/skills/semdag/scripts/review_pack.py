"""review_pack: what adversarial reviewer k needs, in one call.

args: ["<k>"]   (the candidate number you were assigned)

Prints candidate k's diff (as the harness would extract it), the files it touches, its own
audit verdict, and the repro it claimed. Read-only. Prints one JSON object; never raises.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ensemble as E  # noqa: E402

DIFF_CHARS = 3500


def pack(argv):
    k = E.parse_k([str(a) for a in argv])
    if not k or k > E.K_MAX:
        return {"error": "args: [\"<candidate number 1-4>\"]"}
    diff = E.candidate_diff(k)
    out = {"candidate": k, "worktree": E.wt_rel(k)}
    if not diff.strip():
        out["empty"] = True
        out["next"] = f"Candidate {k} changed nothing. Reply: NONE {k} (empty candidate)."
        return out
    out["files"] = E.diff_files(diff)
    out["diff"] = diff[:DIFF_CHARS] + ("\n... [diff truncated]" if len(diff) > DIFF_CHARS else "")
    aud = E.read_json(f"{E.MAIN_CID}_wt{k}", "audit.json", {}) or {}
    out["self_audit"] = {x: aud.get(x) for x in ("decision", "green", "reasons", "gaps")}
    if aud.get("repro_cmd"):
        out["claimed_repro"] = aud["repro_cmd"][:300]
    out["next"] = ("Find an input where this change still gives the wrong result, or breaks "
                   "behaviour that worked before. Save it with save_cex.py; it must import "
                   "the package and assert the CORRECT behaviour described in the issue.")
    return out


def main(argv=None):
    try:
        out = pack(E.normalize(sys.argv[1:] if argv is None else argv))
    except Exception as ex:  # never hand the model a traceback
        out = {"error": f"{type(ex).__name__}: {ex}"[:300]}
    print(E.dumps(out))
    return out


if __name__ == "__main__":
    main()
