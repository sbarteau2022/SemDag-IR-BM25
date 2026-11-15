"""Build verified SWE trajectories for one repo.

usage: python build.py <repo> <n_target> <out_dir> [seed]

Stages per repo:
  1. baseline: run the full suite once, keep tests that pass.
  2. screen:   inject candidate bugs, keep those that break 1..20 passing tests
               without breaking collection/imports.
  3. trajectory: in a fresh git workspace (bug committed as base), execute a
               scripted, observation-grounded agent with the harness tools.
  4. validate: apply the submitted patch to a fresh copy and run all
               fail-to-pass + pass-to-pass tests. Only passing samples are kept.
"""
import ast
import json
import os
import random
import re
import shutil
import subprocess
import sys
import textwrap
import time

import mutate
import phrases as P
from config import REPOS, REPOS_DIR, WORK
from core import Harness, PY, git_init, layout, make_env, make_workspace, run_tests, scrub

MAX_F2P = 20


# ------------------------------------------------------------------ baseline
def baseline(repo):
    cache = os.path.join(WORK, "baseline", repo + ".json")
    if os.path.exists(cache):
        return json.load(open(cache))
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    src_root, sources, tests = layout(os.path.join(REPOS_DIR, repo))
    ws = make_workspace(repo, "baseline")
    t0 = time.time()
    res = run_tests(ws, src_root, timeout=900) or {}
    dt = time.time() - t0
    shutil.rmtree(ws, ignore_errors=True)
    passed = sorted(k for k, v in res.items() if v == "passed")
    info = {"repo": repo, "src_root": src_root, "sources": sources, "tests": tests,
            "passed": passed, "collect_errors": sorted(k for k in res if k.startswith("__collect__")), "n_total": len(res), "seconds": round(dt, 1)}
    json.dump(info, open(cache, "w"))
    return info


def word_in(name, text):
    return re.search(r"\b%s\b" % re.escape(name), text) is not None


def select_targets(base, m, test_texts):
    if base["seconds"] <= 6:
        return None  # full suite is cheap
    stem = os.path.splitext(os.path.basename(m["file"]))[0]
    hits = [t for t, txt in test_texts.items() if word_in(m["func_name"], txt) or word_in(stem, txt)]
    return hits[:8] or ["__none__"]


# ------------------------------------------------------------------ test source helpers
def parse_nodeid(nid):
    parts = nid.split("::")
    f = parts[0]
    name = re.sub(r"\[.*\]$", "", parts[-1])
    cls = parts[1] if len(parts) == 3 else None
    return f, cls, name


def find_test_node(ws, nid):
    f, cls, name = parse_nodeid(nid)
    p = os.path.join(ws, f)
    if not os.path.exists(p):
        return None, None, None
    src = open(p, encoding="utf-8").read()
    tree = ast.parse(src)
    scope = tree.body
    if cls:
        c = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls]
        if not c:
            return None, None, src
        scope = c[0].body
    for n in scope:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n, tree, src
    return None, tree, src


def standalone_repro(ws, nid):
    """Turn a top-level, fixture-free, undecorated test into a script body."""
    node, tree, src = find_test_node(ws, nid)
    if node is None or parse_nodeid(nid)[1] or "[" in nid:
        return None
    if node.args.args or node.decorator_list or isinstance(node, ast.AsyncFunctionDef):
        return None
    lines = src.split("\n")
    body = lines[node.body[0].lineno - 1: node.end_lineno]
    if node.body and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant):
        body = lines[node.body[0].end_lineno: node.end_lineno]
    body_txt = textwrap.dedent("\n".join(body)).strip("\n")
    if not body_txt or len(body_txt.split("\n")) > 22 or re.search(r"\b(return|yield|self|await)\b", body_txt):
        return None
    if re.search(r"\b(tmp_path|tmpdir|monkeypatch|capsys|request)\b", body_txt):
        return None
    imports = []
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            if isinstance(n, ast.ImportFrom) and (n.level or (n.module or "").startswith(("tests", "test", "."))):
                continue
            if any(a.name == "*" for a in n.names):
                imports.append(f"from {n.module} import *")
                continue
            used = [a for a in n.names if word_in(a.asname or a.name.split(".")[0], body_txt)]
            if not used:
                continue
            parts = [a.name + (f" as {a.asname}" if a.asname else "") for a in used]
            if isinstance(n, ast.ImportFrom):
                imports.append(f"from {n.module} import " + ", ".join(parts))
            else:
                imports.append("import " + ", ".join(parts))
    return {"imports": "\n".join(imports), "body": body_txt}


def remove_tests(ws, nids):
    """Delete the given top-level test functions from their files (hide F2P tests)."""
    by_file = {}
    for nid in nids:
        f, cls, name = parse_nodeid(nid)
        if cls:
            return False
        by_file.setdefault(f, set()).add(name)
    for f, names in by_file.items():
        p = os.path.join(ws, f)
        src = open(p, encoding="utf-8").read()
        tree = ast.parse(src)
        lines = src.split("\n")
        spans = []
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names:
                s = min([d.lineno for d in n.decorator_list] + [n.lineno])
                spans.append((s, n.end_lineno))
        for s, e in sorted(spans, reverse=True):
            del lines[s - 1:e]
        new = "\n".join(lines)
        try:
            ast.parse(new)
        except SyntaxError:
            return False
        open(p, "w", encoding="utf-8").write(new)
    return True


# ------------------------------------------------------------------ static analysis
def func_defs(ws, sources):
    """name -> list of (file, start, end, body_text, qualname)."""
    out = {}
    for rel in sources:
        try:
            src = open(os.path.join(ws, rel), encoding="utf-8").read()
            tree = ast.parse(src)
        except Exception:
            continue
        lines = src.split("\n")

        def visit(node, stack):
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, ast.ClassDef):
                    visit(ch, stack + [ch.name])
                elif isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.setdefault(ch.name, []).append((rel, ch.lineno, ch.end_lineno,
                                                        "\n".join(lines[ch.lineno - 1:ch.end_lineno]),
                                                        ".".join(stack + [ch.name])))
                    visit(ch, stack + [ch.name])
                else:
                    visit(ch, stack)
        visit(tree, [])
    return out


def disambiguate(hits, file, line, qual, evidence):
    """Return a reason string if (file,line) can be justified among grep hits, else None."""
    if (file, line) not in hits:
        return None
    if len(hits) == 1:
        return ""
    parts = qual.split(".")
    if len(parts) >= 2 and word_in(parts[-2], evidence):
        return f" Several classes define `{parts[-1]}`; the code in question uses `{parts[-2]}`, so I want `{parts[-2]}.{parts[-1]}`."
    same = [h for h in hits if h[0] == file]
    if len(same) == 1 and word_in(os.path.splitext(os.path.basename(file))[0], evidence):
        return f" The other matches are in different modules; the report points at `{os.path.splitext(os.path.basename(file))[0]}`."
    return None


def called_names(text):
    return set(re.findall(r"(?:\.|\b)([A-Za-z_][A-Za-z0-9_]*)\s*\(", text))


TB_PY = re.compile(r'File "/workspace/([^"]+)", line (\d+), in (\S+)')
TB_PYTEST = re.compile(r"^(?!tests?/)([\w/.-]+\.py):(\d+): in (\S+)", re.M)


def frames(output, sources):
    fr = [(f, int(l), fn) for f, l, fn in TB_PY.findall(output)]
    fr += [(f, int(l), fn) for f, l, fn in TB_PYTEST.findall(output)]
    return [x for x in fr if x[0] in sources]


def short_err(output):
    lines = [l.rstrip() for l in output.strip().split("\n") if l.strip()]
    e_lines = [l[1:].strip() for l in lines if l.startswith("E ")]
    if e_lines:
        cand = e_lines[0]
    else:
        exc = [l for l in lines if re.match(r"^[A-Za-z_.]*(Error|Exception|Failed|Warning)\b", l)]
        cand = exc[-1] if exc else lines[-1]
    cand = cand.strip()
    if len(cand) > 160:
        cand = cand[:157] + "..."
    return "`" + cand.replace("`", "'") + "`"


def window(start, end, focus, size=60):
    if end - start + 1 <= size:
        return start, end
    if focus - start <= size - 12:
        return start, min(end, max(focus + 10, start + 40))
    s = max(start, focus - 30)
    return s, min(end, focus + 15)


# ------------------------------------------------------------------ issue text
ISSUE_SNIPPET_TITLES = [
    "`{api}` gives the wrong result", "Unexpected behaviour from `{api}`",
    "Bug: `{api}` doesn't behave as documented", "{exc} when using `{api}`",
]
ISSUE_CI_TITLES = [
    "Test failure: `{test}`", "`{test}` is failing on main", "CI red: {test}",
]


def make_issue(mode, repo, api, err_block, exc, snippet=None, test=None, hint=None, rng=random):
    if mode == "snippet":
        title = rng.choice(ISSUE_SNIPPET_TITLES).format(api=api, exc=exc)
        lead = rng.choice([
            "I ran into this with the current main branch of {repo}. Minimal reproduction:",
            "The following snippet should pass, but it fails:",
            "Here's a small example that shows the problem:",
            "Reproducer:",
        ]).format(repo=repo)
        tail = rng.choice([
            "I'd expect the assertions above to hold.",
            "Expected: no error, with the values shown in the asserts.",
            "This looks like a regression; the asserts reflect the documented behaviour.",
            "",
        ])
        body = f"{lead}\n\n```python\n{snippet}\n```\n\nActual output:\n\n```\n{err_block}\n```\n"
    else:
        title = rng.choice(ISSUE_CI_TITLES).format(test=test)
        lead = rng.choice([
            "The test `{test}` fails on the current code:",
            "Running `python -m pytest {test}` gives:",
            "This test started failing after a recent change:",
        ]).format(test=test)
        tail = rng.choice(["Please fix the library code. The test is correct.",
                           "The test reflects the intended behaviour.", ""])
        body = f"{lead}\n\n```\n{err_block}\n```\n"
    if hint:
        body += f"\n{hint}\n"
    if tail:
        body += f"\n{tail}\n"
    return f"{title}\n\n{body}".strip() + "\n"


def tail_block(output, n=14):
    lines = [l for l in output.rstrip().split("\n")]
    # keep traceback tail / pytest failure core, drop pytest summary noise
    lines = [l for l in lines if not re.match(r"^(=+|-+|\.+\s*\[|short test summary|FAILED |\d+ (failed|passed))", l)]
    return "\n".join(lines[-n:]).strip()


# ------------------------------------------------------------------ trajectory
class Traj:
    def __init__(self, h):
        self.h = h
        self.steps = []

    def call(self, thought, tool, **args):
        res = getattr(self.h, tool)(**args)
        self.steps.append({"thought": thought, "tool": tool, "args": args, "result": res})
        return res


def edit_args(h, file, m, rng):
    """Build edit_file args for reverting m in the mutated workspace; may produce a non-unique first attempt."""
    text = open(os.path.join(h.ws, file), encoding="utf-8").read()
    lines = text.split("\n")
    attempts = []
    if m["op"] == "drop_guard":
        a = m["start"] - 2  # 0-based index of anchor line (line before the removed guard)
        k = 0
        while True:
            old = "\n".join(lines[a - k:a + 1])
            if text.count(old) == 1 or k > 4:
                break
            k += 1
        new = old + "\n" + "\n".join(m["orig_lines"])
        attempts.append((old, new))
        return attempts
    i = m["start"] - 1
    line = lines[i]
    if text.count(line) > 1:
        attempts.append((line, m["orig_lines"][0]))  # will fail: non-unique (real error)
        for k in range(1, 5):
            old = "\n".join(lines[i - k:i + 1])
            if text.count(old) == 1:
                new = "\n".join(lines[i - k:i] + [m["orig_lines"][0]])
                attempts.append((old, new))
                break
        else:
            return None
    else:
        attempts.append((line, m["orig_lines"][0]))
    return attempts


def regression_file(base, m, f2p, test_texts, ws_tests_ok):
    files = sorted({parse_nodeid(t)[0] for t in f2p})
    stem = os.path.splitext(os.path.basename(m["file"]))[0]
    cands = [f for f in files] + [t for t in test_texts if stem in os.path.basename(t)]
    for f in cands:
        if f in ws_tests_ok:
            return f
    return cands[0] if cands else None


def build_one(repo, base, m, f2p, run_set, test_texts, rng, idx):
    src_root, sources = base["src_root"], base["sources"]
    # ---- choose mode
    snippet = None
    tops = [t for t in f2p if not parse_nodeid(t)[1] and "[" not in t]
    probe_ws = make_workspace(repo, f"probe{idx}")
    try:
        for t in sorted(tops, key=lambda x: rng.random()):
            s = standalone_repro(probe_ws, t)
            if s:
                snippet = (t, s)
                break
    finally:
        shutil.rmtree(probe_ws, ignore_errors=True)
    mode = "snippet" if snippet and len(tops) == len(f2p) and rng.random() < 0.8 else "ci"
    primary = snippet[0] if mode == "snippet" else sorted(f2p, key=lambda x: (len(x), x))[0]

    ws = make_workspace(repo, f"traj{idx}")
    mutate.apply(os.path.join(ws, m["file"]), m)
    if mode == "snippet":
        if not remove_tests(ws, f2p):
            mode, primary = "ci", sorted(f2p, key=len)[0]
            shutil.rmtree(ws)
            ws = make_workspace(repo, f"traj{idx}")
            mutate.apply(os.path.join(ws, m["file"]), m)
    git_init(ws)
    h = Harness(ws, src_root)
    tr = Traj(h)
    meta = {"mode": mode, "primary_test": primary}
    defs = func_defs(ws, sources)
    try:
        # ---------------- reproduce
        if mode == "snippet":
            sn = snippet[1]
            code = (sn["imports"] + "\n\n" if sn["imports"] else "") + sn["body"] + '\n\nprint("OK")'
            cmd = f"cat > /tmp/repro.py <<'EOF'\n{code}\nEOF\ntimeout 60 python /tmp/repro.py"
            # verify repro passes on the original code
            ok_ws = make_workspace(repo, f"ok{idx}")
            r_ok = subprocess.run(["/bin/bash", "-c", f"cat > /tmp/repro_ok_{idx}.py <<'EOF'\n{code}\nEOF\npython /tmp/repro_ok_{idx}.py"],
                                  cwd=ok_ws, env=make_env(ok_ws, src_root), capture_output=True, text=True, timeout=60)
            shutil.rmtree(ok_ws, ignore_errors=True)
            if r_ok.returncode != 0 or "OK" not in r_ok.stdout:
                return None, "repro_not_clean_on_original"
            r = tr.call(P.pick(P.PLAN_SNIPPET), "run_command", command=cmd)
            if r["exit_code"] == 0:
                return None, "repro_does_not_fail"
            out = r["output"]
            if r["exit_code"] == 124 or "Timeout" in out:
                return None, "hang"
            issue_snip = (sn["imports"] + "\n\n" if sn["imports"] else "") + sn["body"]
        else:
            cmd = f"timeout 90 python -m pytest {primary} -q --tb=short 2>&1 | tail -n 40"
            r = tr.call(P.pick(P.PLAN_CI, test=primary), "run_command", command=cmd)
            out = r["output"]
            if "Timeout" in out or "timed out" in out or not out.strip():
                return None, "hang"
            if "passed" in out and "failed" not in out and "error" not in out.lower():
                return None, "ci_test_passes"
        err = short_err(out)
        exc_m = re.search(r"\b([A-Z][A-Za-z]*(Error|Exception))\b", out)
        exc = exc_m.group(1) if exc_m else "Wrong result"
        meta["error"] = err
        fr = frames(out, sources)
        test_src = None
        if mode == "ci":
            node, _, tsrc = find_test_node(ws, primary)
            if node is None:
                return None, "test_node_missing"
            tsl = tsrc.split("\n")
            ts, te = min([d.lineno for d in node.decorator_list] + [node.lineno]), node.end_lineno
            te = min(te, ts + 59)
            test_src = "\n".join(tsl[ts - 1:te])
        else:
            test_src = snippet[1]["body"]

        # ---------------- localize
        mf, mfn = m["file"], m["func_name"]
        in_mut = lambda f, l: f == mf and m["func_start"] <= l <= m["func_end"]  # noqa: E731
        api = None
        route = None
        mut_frames = [x for x in fr if in_mut(x[0], x[1])]
        if mut_frames:
            route = "traceback"
        else:
            called = called_names(test_src)
            if mfn in called and not mfn.startswith("test"):
                route, api = "api_direct", mfn
            else:
                for c in sorted(called):
                    for (f, s, e, body, _q) in defs.get(c, []):
                        if f in sources and word_in(mfn, body) and mfn + "(" in body.replace(" (", "("):
                            route, api = "call_chain", c
                            break
                    if route:
                        break
        if not route:
            return None, "no_route"
        meta["route"] = route

        if mode == "ci":
            tr.call(P.pick(P.READ_TEST, err=err), "read_file", filepath=parse_nodeid(primary)[0],
                    start_line=ts, end_line=te)

        pkg_dir = os.path.dirname(mf) or "."
        search_root = (src_root or pkg_dir.split("/")[0]) if "/" in mf else "."

        def grep_def(name, prefer_file, thought):
            cmd = f"grep -rn \"def {name}\\b\" --include=*.py {search_root} | grep -v -E '(^|/)tests?/' | head -20"
            if search_root == ".":
                cmd = f"grep -rn \"def {name}\\b\" --include=*.py . | grep -v -E '(^|/)tests?/' | head -20"
            res = tr.call(thought, "run_command", command=cmd)
            hits = re.findall(r"^(?:\./)?([^:\n]+\.py):(\d+):", res["output"], re.M)
            hits = [(f, int(l)) for f, l in hits]
            mine = [x for x in hits if x[0] == prefer_file]
            return (mine[0] if mine else (hits[0] if hits else None)), hits

        mut_line = m["start"]
        diag_line = mut_line
        if route == "traceback":
            deepest = fr[-1]
            if not in_mut(deepest[0], deepest[1]) and rng.random() < 0.9:
                # read deepest frame first, then walk up to the mutated frame
                df, dl, dfn = deepest
                if mode == "ci":
                    th = f"The traceback's innermost library frame is `{dfn}` at {df}:{dl}. Reading there."
                else:
                    th = None
                ds, de = window(max(1, dl - 25), dl + 15, dl, 45)
                if th is None:
                    tr.steps[-1]["thought"] = tr.steps[-1]["thought"]
                    th = P.pick(P.SAW_TB, err=err, frame_func=dfn, frame_file=df, frame_line=dl)
                tr.call(th, "read_file", filepath=df, start_line=ds, end_line=de)
                mf_frame = mut_frames[-1]
                ws_, we_ = window(m["func_start"], m["func_end"], mut_line)
                tr.call(P.pick(P.WALK_UP, caller=mf_frame[2], file=mf, line=mf_frame[1]), "read_file",
                        filepath=mf, start_line=ws_, end_line=we_)
            else:
                f0 = mut_frames[-1]
                ws_, we_ = window(m["func_start"], m["func_end"], mut_line)
                th = (f"The traceback goes through `{f0[2]}` at {f0[0]}:{f0[1]}. Reading that function."
                      if mode == "ci" else P.pick(P.SAW_TB, err=err, frame_func=f0[2], frame_file=f0[0], frame_line=f0[1]))
                tr.call(th, "read_file", filepath=mf, start_line=ws_, end_line=we_)
        else:
            th0 = (P.pick(P.AFTER_TEST_READ, api=api) if mode == "ci" else P.pick(P.SAW_ASSERT, err=err, api=api))
            if route == "api_direct":
                hit, hits = grep_def(api, mf, th0)
                dl = [d[1] for d in defs.get(mfn, []) if d[0] == mf and d[4] == m["func"]]
                why = disambiguate(hits, mf, dl[0] if dl else -1, m["func"], test_src + out)
                if why is None:
                    return None, "ambiguous_def"
                ws_, we_ = window(m["func_start"], m["func_end"], mut_line)
                tr.call(P.pick(P.GREP_PICK, name=api, file=mf, line=dl[0], others="") + why, "read_file",
                        filepath=mf, start_line=ws_, end_line=we_)
            else:
                cands = [d for d in defs.get(api, []) if mfn + "(" in d[3].replace(" (", "(")]
                if not cands:
                    return None, "chain_miss"
                if len(cands) > 1:
                    return None, "ambiguous_api"
                af, astart, aend, _, aq = cands[0]
                hit, hits = grep_def(api, af, th0)
                why = disambiguate(hits, af, astart, aq, test_src + out)
                if why is None:
                    return None, "ambiguous_def"
                abody = cands[0][3].split("\n")
                call_off = next((i for i, l in enumerate(abody) if re.search(r"\b%s\s*\(" % re.escape(mfn), l)), None)
                if call_off is None:
                    return None, "chain_call_not_found"
                a_s, a_e = window(astart, aend, astart + call_off, 50)
                if not (a_s <= astart + call_off <= a_e):
                    return None, "chain_call_not_shown"
                tr.call(P.pick(P.GREP_PICK, name=api, file=af, line=astart, others="") + why, "read_file",
                        filepath=af, start_line=a_s, end_line=a_e)
                hit2, hits2 = grep_def(mfn, mf, P.pick(P.CHAIN, api=api, callee=mfn))
                dl = [d[1] for d in defs.get(mfn, []) if d[0] == mf and d[4] == m["func"]]
                why = disambiguate(hits2, mf, dl[0] if dl else -1, m["func"], test_src + out + af)
                if why is None:
                    return None, "ambiguous_def"
                ws_, we_ = window(m["func_start"], m["func_end"], mut_line)
                tr.call(f"`{mfn}` is at {mf}:{dl[0]}.{why} Reading it.", "read_file", filepath=mf,
                        start_line=ws_, end_line=we_)
            # make sure the mutated line was actually shown
        last_read = [s for s in tr.steps if s["tool"] == "read_file"][-1]["result"]
        if not (last_read.get("start_line", 1e9) <= mut_line <= last_read.get("end_line", -1)):
            if m["op"] != "drop_guard":
                return None, "mut_not_shown"

        # ---------------- edit
        attempts = edit_args(h, mf, m, rng)
        if not attempts:
            return None, "edit_not_unique"
        fam = m["family"]
        good = m["good"]
        diag = P.pick(P.DIAG[fam], line=diag_line, bad=m["bad"] or "(missing)", good=good.replace("\n", " "),
                      func=mfn, err=err, cond=m.get("guard_cond", ""))
        if m["op"] == "drop_guard":
            # guard must be inferable: its body tokens should appear in the test/error
            body_tokens = set(re.findall(r"[A-Za-z_]{4,}", " ".join(m["orig_lines"][1:] or m["orig_lines"])))
            body_tokens -= {"return", "raise", "None", "True", "False", "self", "continue", "break"}
            if body_tokens and not any(tk in (test_src + out) for tk in body_tokens):
                return None, "guard_not_inferable"
        if m["op"] == "return_none":
            mm = re.match(r"\s*return\s+(\w+)\s*$", m["orig_lines"][0])
            fsrc = "\n".join(open(os.path.join(ws, mf), encoding="utf-8").read().split("\n")[m["func_start"] - 1:m["start"] - 1])
            if not mm or not re.search(r"\b%s\b\s*(=|\+=|\|=)" % re.escape(mm.group(1)), fsrc):
                return None, "return_not_inferable"
        for k, (old, new) in enumerate(attempts):
            th = diag if k == 0 else P.pick(P.EDIT_RETRY)
            res = tr.call(th, "edit_file", filepath=mf, old_string=old, new_string=new)
            if k == len(attempts) - 1 and res.get("status") != "success":
                return None, "edit_failed"
        meta["edit_retry"] = len(attempts) > 1

        # ---------------- verify
        if mode == "snippet":
            r = tr.call(P.pick(P.VERIFY_REPRO), "run_command", command="timeout 60 python /tmp/repro.py")
            if r["exit_code"] != 0:
                return None, "repro_still_fails"
        else:
            r = tr.call(P.pick(P.VERIFY_TEST, test=primary), "run_command",
                        command=f"timeout 90 python -m pytest {primary} -q 2>&1 | tail -n 5")
            if "failed" in r["output"] or "error" in r["output"].lower():
                return None, "test_still_fails"
        tfile = parse_nodeid(primary)[0]
        r = tr.call(P.pick(P.REGRESS, tfile=tfile), "run_command",
                    command=f"timeout 120 python -m pytest {tfile} -q 2>&1 | tail -n 8")
        if re.search(r"\d+ (failed|error)", r["output"]):
            # pre-existing failures? compare against base outcomes in the run set
            base_ws = make_workspace(repo, f"pre{idx}")
            mutate.apply(os.path.join(base_ws, m["file"]), m)
            mutate.apply(os.path.join(base_ws, m["file"]), m, revert=True)
            if mode == "snippet":
                remove_tests(base_ws, f2p)
            pre = run_tests(base_ws, src_root, [tfile]) or {}
            shutil.rmtree(base_ws, ignore_errors=True)
            npre = sum(1 for v in pre.values() if v in ("failed", "error"))
            _unused = (re.findall(r"\d+", (re.search(r"(\d+) failed", r["output"]) or [None, "0"])[1] if re.search(r"(\d+) failed", r["output"]) else "0"))
            if npre == 0:
                return None, "regression"
            tr.steps[-1]["post_note"] = P.pick(P.REGRESS_PREEXIST, n=npre, func=mfn)
            meta["preexisting_failures"] = npre
        if rng.random() < 0.45:
            tr.call(P.pick(P.DIFF), "run_command", command="git diff")
        ncalls = h.calls
        sub = tr.call(P.pick(P.SUBMIT, calls=ncalls), "submit_patch")
        if sub["files_changed"] != 1 or "test" in re.findall(r"^diff --git a/(\S+)", sub["patch"], re.M)[0].split("/")[0]:
            return None, "bad_patch"
        where = f"`{mfn}` in {mf}"
        what = (f"`{m['bad']}` was changed to `{good}`." if m["op"] != "drop_guard"
                else f"Restored the missing `{m.get('guard_cond')}` guard.")
        final = P.pick(P.FINAL, where=where, what=what, tfile=tfile)

        # ---------------- issue text
        if mode == "snippet":
            err_block = tail_block(tr.steps[0]["result"]["output"]).replace("/tmp/repro.py", "repro.py")
            issue = make_issue("snippet", repo, api or mfn if route != "traceback" else (api or mfn), err_block, exc,
                               snippet=issue_snip, rng=rng)
        else:
            err_block = tail_block(tr.steps[0]["result"]["output"], 18)
            hint = None
            if rng.random() < 0.25:
                hint = rng.choice(["Possibly related to `{f}`.", "I suspect something in `{f}` but haven't dug in."]).format(f=mfn)
                meta["hint"] = True
            issue = make_issue("ci", repo, None, err_block, exc, test=primary, hint=hint, rng=rng)
        return {"issue": issue, "steps": tr.steps, "final": final, "meta": meta,
                "patch": sub["patch"]}, "ok"
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def validate(repo, base, m, patch, f2p, run_set, idx):
    ws = make_workspace(repo, f"val{idx}")
    try:
        mutate.apply(os.path.join(ws, m["file"]), m)
        git_init(ws)
        p = subprocess.run(["git", "apply", "-"], cwd=ws, input=patch, text=True, capture_output=True)
        if p.returncode != 0:
            return False, "apply_failed"
        res = run_tests(ws, base["src_root"], run_set) or {}
        bad_f2p = [t for t in f2p if res.get(t) != "passed"]
        passed = set(base["passed"])
        bad_p2p = [t for t, v in res.items() if t in passed and v != "passed"]
        if bad_f2p or bad_p2p:
            return False, f"f2p_fail={len(bad_f2p)} p2p_fail={len(bad_p2p)}"
        return True, sum(1 for t in res if t in passed)
    finally:
        shutil.rmtree(ws, ignore_errors=True)


# ------------------------------------------------------------------ main
def main(repo, n_target, out_dir, seed=0):
    rng = random.Random(f"{repo}-{seed}")
    P.R.seed(f"{repo}-{seed}-p")
    base = baseline(repo)
    passed = set(base["passed"])
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{repo}.jsonl")
    log_path = os.path.join(out_dir, f"{repo}.log")
    log = open(log_path, "a")
    if len(passed) < 20:
        print(f"{repo}: too few passing tests ({len(passed)})", file=log)
        return
    test_texts = {t: open(os.path.join(REPOS_DIR, repo, t), encoding="utf-8", errors="replace").read()
                  for t in base["tests"]}
    cands = []
    for rel in base["sources"]:
        cands += mutate.candidates(os.path.join(REPOS_DIR, repo, rel), rel, seed)
    by_op = {}
    for c in cands:
        by_op.setdefault(c["op"], []).append(c)
    for v in by_op.values():
        rng.shuffle(v)
    order = []
    ops = sorted(by_op)
    while any(by_op.values()):
        rng.shuffle(ops)
        for o in ops:
            if by_op[o]:
                order.append(by_op[o].pop())
    print(f"{repo}: {len(cands)} candidates, baseline {len(passed)} passing in {base['seconds']}s", file=log, flush=True)
    screen_ws = make_workspace(repo, f"screen{seed}")
    kept, tried, per_func = 0, 0, {}
    stats = {}
    t_start = time.time()
    with open(out_path, "a") as out:
        for i, m in enumerate(order):
            if kept >= n_target or tried >= n_target * 8 or time.time() - t_start > 60 * 40:
                break
            key = (m["file"], m["func"])
            if per_func.get(key, 0) >= 2:
                continue
            tried += 1
            fp = os.path.join(screen_ws, m["file"])
            try:
                mutate.apply(fp, m)
            except Exception:
                continue
            targets = select_targets(base, m, test_texts)
            if targets == ["__none__"]:
                mutate.apply(fp, m, revert=True)
                stats["no_tests"] = stats.get("no_tests", 0) + 1
                continue
            res = run_tests(screen_ws, base["src_root"], targets, timeout=300)
            mutate.apply(fp, m, revert=True)
            if res is None:
                stats["timeout"] = stats.get("timeout", 0) + 1
                continue
            if any(k.startswith("__collect__") and k not in set(base.get("collect_errors", [])) for k in res):
                stats["collect_error"] = stats.get("collect_error", 0) + 1
                continue
            f2p = sorted(t for t in passed if t in res and res[t] != "passed")
            if not (1 <= len(f2p) <= MAX_F2P):
                stats["f2p_out_of_range"] = stats.get("f2p_out_of_range", 0) + 1
                continue
            run_set = targets
            idx = f"{seed}_{i}"
            try:
                traj, why = build_one(repo, base, m, f2p, run_set, test_texts, rng, idx)
            except Exception as e:  # keep going on odd repos
                traj, why = None, "exception:" + type(e).__name__
            stats[why] = stats.get(why, 0) + 1
            if not traj:
                continue
            ok, info = validate(repo, base, m, traj["patch"], f2p, run_set, idx)
            if not ok:
                stats["validate:" + str(info)] = stats.get("validate:" + str(info), 0) + 1
                continue
            kept += 1
            per_func[key] = per_func.get(key, 0) + 1
            rec = {
                "id": f"{repo}__{m['op']}__{kept:04d}_{seed}",
                "repo": repo, "github": REPOS[repo][0], "license": REPOS[repo][1],
                "base_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=os.path.join(REPOS_DIR, repo),
                                              capture_output=True, text=True).stdout.strip(),
                "bug": {k: m[k] for k in ("file", "func", "op", "family", "start", "end", "orig_lines", "new_lines")},
                "fail_to_pass": f2p, "n_pass_to_pass": info,
                "issue": traj["issue"], "steps": traj["steps"], "final": traj["final"],
                "meta": traj["meta"], "patch": traj["patch"],
                "n_tool_calls": sum(1 for s in traj["steps"] if s["tool"] != "submit_patch"),
            }
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"kept {rec['id']} mode={traj['meta']['mode']} route={traj['meta']['route']} calls={rec['n_tool_calls']}", file=log, flush=True)
    shutil.rmtree(screen_ws, ignore_errors=True)
    print(f"{repo}: kept {kept}/{tried} stats={json.dumps(stats)}", file=log, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 0)
