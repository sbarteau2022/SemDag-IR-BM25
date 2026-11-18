"""edit: implementer k's only way to change code. Always writes into its own copy .git/wt_<k>.

args: ["<k>", "<file path as in the repository, e.g. rich/console.py>", "<old text>", "<new text>"]
      ["<k>", "<file>", "@1", "<new text>"]      (replace a block fix_edit offered)
      ["<k>", "<file>", "L120-126", "<new text>"] (replace a line range)

The path is taken relative to the repository; a leading /workspace/ or .git/wt_<n>/ is dropped,
so the edit lands in .git/wt_<k> whatever prefix the model wrote. The main workspace is never
touched (run_20: prompt-only isolation failed, 37 stray edits in 5 tasks). Matching, rescue
references, test-file refusal and the parse guard are fix_edit's. Prints one JSON object.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ensemble as E  # noqa: E402
import fix_edit  # noqa: E402

PREFIX = re.compile(r"^(?:/workspace/)?(?:\.git/wt_\d+/)?")


def edit(argv):
    args = [str(a) for a in argv]
    k = E.parse_k(args[:1])
    if not k or k > E.K_MAX:
        return {"ok": False, "error": "first arg must be your implementer number 1-4",
                "hint": 'args: ["<k>", "<file>", "<old text>", "<new text>"]'}
    d = E.wt_dir(k)
    if not os.path.isdir(d):
        return {"ok": False, "error": f"no copy .git/wt_{k} yet: call fork.py first"}
    filepath, old, new = fix_edit.parse_args(args[1:])
    filepath = PREFIX.sub("", (filepath or "").strip())
    out = fix_edit.run(filepath, old, new, repo=d)
    out["copy"] = E.wt_rel(k)
    return out


def main(argv=None):
    try:
        out = edit(sys.argv[1:] if argv is None else argv)
    except Exception as ex:  # never hand the model a traceback
        out = {"ok": False, "error": f"{type(ex).__name__}: {ex}"[:300]}
    print(E.dumps(out))
    return out


if __name__ == "__main__":
    main()
