"""save_cex: store an adversarial counterexample for candidate k.

args: ["<k>", "<python code>"]

The code must be a standalone script that imports the package and asserts the CORRECT
behaviour from the issue; it passes (exit 0) only if the candidate is right on that input.
It is checked for syntax and saved outside the repository (temp cache). The coordinator's
gate runs every saved counterexample against every candidate. Prints one JSON object.
"""
import ast
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ensemble as E  # noqa: E402

MAX_CHARS = 4000
MAX_PER_K = 3


def save(argv):
    args = [str(a) for a in argv]
    if len(args) < 2:
        return {"error": 'args: ["<k>", "<python code>"]'}
    k = E.parse_k(args[:1])
    if not k or k > E.K_MAX:
        return {"error": "first arg must be the candidate number 1-4"}
    code = "\n".join(args[1:]).strip()
    if code.startswith("```"):
        code = code.strip("`")
        code = code[code.find("\n") + 1:] if code.lower().startswith("python") else code
    if len(code) > MAX_CHARS:
        return {"error": f"too long ({len(code)} chars); keep it under {MAX_CHARS}"}
    try:
        tree = ast.parse(code, f"cex_{k}.py")
    except SyntaxError as ex:
        return {"error": f"SyntaxError: {ex.msg} (line {ex.lineno})"}
    if not any(isinstance(n, (ast.Assert, ast.Raise)) for n in ast.walk(tree)):
        return {"error": "the counterexample must assert the correct behaviour (an assert statement)"}
    d = E.cex_dir()
    have = sorted(glob.glob(os.path.join(d, f"k{k}_*.py")))
    if len(have) >= MAX_PER_K:
        return {"error": f"candidate {k} already has {MAX_PER_K} counterexamples"}
    path = os.path.join(d, f"k{k}_{len(have) + 1}.py")
    with open(path, "w") as fh:
        fh.write(code + "\n")
    return {"saved": True, "candidate": k, "id": os.path.basename(path),
            "next": f"Reply with one line: CEX {k} saved."}


def main(argv=None):
    try:
        out = save(E.normalize(sys.argv[1:] if argv is None else argv, unquote_upto=1))
    except Exception as ex:  # never hand the model a traceback
        out = {"error": f"{type(ex).__name__}: {ex}"[:300]}
    print(E.dumps(out))
    return out


if __name__ == "__main__":
    main()
