"""Shared helpers for the v8 ensemble scripts (fork, review_pack, save_cex, suites, adopt).

Each solver k works in its own git worktree at <workspace>/.git/wt_<k>, checked out at the
harness baseline. Git never tracks anything under .git/, so a worktree can never enter the
submitted patch; edit_file and read_file accept the paths because they stay inside /workspace.
"""
import ast
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wsroot  # noqa: E402
os.environ["SEMDAG_CACHE"] = wsroot.cache_root()
import cache  # noqa: E402
import impact  # noqa: E402

MAIN_CID = "task"
K_MAX = 4


_TOKEN = re.compile(r"[\w./@:+-]+")


def _unquote(s):
    """Strip literal quotes only around a single token (a number, path, flag or name), never
    around code: old/new text for edits must reach fix_edit byte for byte."""
    t = s.strip()
    while len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" and _TOKEN.fullmatch(t[1:-1].strip()):
        t = t[1:-1].strip()
    return t if t != s.strip() else s


def normalize(argv, unquote_upto=None):
    """Undo the argument shapes a small model emits through run_skill_script (run_21): nested
    lists, a stringified list, and values wrapped in literal quotes ('"3"', '"semdag"')."""
    out = []

    def add(x):
        if isinstance(x, (list, tuple)):
            for y in x:
                add(y)
            return
        s = str(x)
        st = s.strip()
        if st.startswith("[") and st.endswith("]"):
            try:
                v = ast.literal_eval(st)
                if isinstance(v, (list, tuple)):
                    add(list(v))
                    return
            except (ValueError, SyntaxError):
                pass
        out.append(s)

    add(list(argv))
    return [s if (unquote_upto is not None and i >= unquote_upto) else _unquote(s)
            for i, s in enumerate(out)]


def dumps(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def root():
    return wsroot.workspace_root(None)


def wt_rel(k):
    return f".git/wt_{k}"


def wt_dir(k):
    return os.path.join(root(), ".git", f"wt_{k}")


def parse_k(argv, default=None):
    for a in argv:
        m = re.search(r"(?:^|\D)([1-9])\s*$", str(a).strip("[]'\" "))
        if m and 1 <= int(m.group(1)) <= 8:
            return int(m.group(1))
    return default


def git(cwd, *args, timeout=60, stdin=None):
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, input=stdin)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as ex:
        return 1, "", str(ex)


def candidate_diff(k):
    """The solver's change, as the harness would extract it (intent-to-add new files)."""
    d = wt_dir(k)
    if not os.path.isdir(d):
        return ""
    ref = impact.baseline_ref(d) or "HEAD"
    git(d, "add", "-N", ".")
    rc, out, _ = git(d, "diff", "--binary", ref)
    return out if rc == 0 else ""


def diff_files(diff):
    return re.findall(r"^\+\+\+ b/(\S+)", diff, flags=re.M)


def read_json(cid, name, default=None):
    try:
        return cache.read(cid, name)
    except (OSError, ValueError):
        return default


def cex_dir():
    d = os.path.join(cache.container_dir(MAIN_CID), "cex")
    os.makedirs(d, exist_ok=True)
    return d
