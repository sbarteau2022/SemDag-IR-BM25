"""Agentic families in the real Gemma tool-call format: edit_file mechanics drills and skill-use trajectories.
Tool outputs are emulated from real snapshot files; presubmit/snapshot skill scripts are executed for real in a throwaway git repo.
Tool-output tokens are masked from the loss at render time; deliberately wrong turns carry train=False."""
import ast, difflib, json, os, re, subprocess, sys, tempfile
from pathlib import Path
from common import *
from tools import tools

SKILLS = ROOT.parent / "AgenticSubmission" / "v1_brigade" / "skills"
PY = os.environ.get("LORA_PY") or sys.executable
ALL = tools("run_command","read_file","edit_file","write_file","get_status","submit_patch","get_code_neighbors","search_similar_code","get_code_subgraph","load_skill","load_skill_resource","run_skill_script")
J = json.dumps
TAIL = ("\n\n## Task Budget (Session terminates when any budget is exhausted)\n- Time allowance: 60.0 minutes\n- Tool calls allowance: 100 calls\n- Max loop iterations: 500 turns\n\n"
        "## Execution Environment Rules\n- Single command timeout: 300 seconds\n- Command output limit: 5000 characters\n- File view limit: 150 lines per read_file call\n"
        "- Environment is offline. All repository and test dependencies are ALREADY pre-installed.\n\n"
        "Work under /workspace, verify your change, call submit_patch once when complete, then reply with a short summary.")

CMP = re.compile(r"(?<![<>=!:\-])(<=|>=|==|!=|<|>)(?![=>])")
CMP_PAIR = {"<": "<=", "<=": "<", ">": ">=", ">=": ">", "==": "!=", "!=": "=="}

def sig(tree):
    ops = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare): ops.append(tuple(type(o).__name__ for o in n.ops))
        elif isinstance(n, ast.BoolOp): ops.append(type(n.op).__name__)
        elif isinstance(n, ast.BinOp): ops.append(type(n.op).__name__)
        elif isinstance(n, ast.Constant): ops.append(("c", repr(n.value)))
    return ops

def line_mutations(line):
    out = []
    for m in CMP.finditer(line):
        out.append((line[:m.start()] + CMP_PAIR[m.group(1)] + line[m.end():], CMP_PAIR[m.group(1)], m.group(1), "comparison operator"))
    for a, b in ((" and ", " or "), (" or ", " and "), (" is not None", " is None"), (" is None", " is not None"), (" + ", " - "), (" - ", " + ")):
        i = line.find(a)
        if i >= 0: out.append((line[:i] + b + line[i + len(a):], b.strip(), a.strip(), "operator"))
    return out

def enclosing(tree, lineno):
    best = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= lineno <= n.end_lineno:
            if best is None or n.lineno >= best.lineno: best = n
    return best.name if best else None

def find_drill(srcs, rng):
    paths = [p for p in sorted(srcs) if not is_test_path(p) and not p.startswith(("docs", "scripts", "benchmarks", "examples")) and "docs_src" not in p and 40 <= len(srcs[p].splitlines()) <= 600]
    rng.shuffle(paths)
    for p in paths[:12]:
        text = srcs[p]; lines = text.splitlines()
        try: orig_tree = ast.parse(text)
        except SyntaxError: continue
        idxs = list(range(len(lines))); rng.shuffle(idxs)
        for i in idxs[:80]:
            ln = lines[i]
            if ln.lstrip().startswith(("#", '"', "'")) or len(ln) > 110 or not ln.strip(): continue
            fn = enclosing(orig_tree, i + 1)
            if not fn: continue
            muts = line_mutations(ln); rng.shuffle(muts)
            for bad, good_tok, bad_tok, kind in muts:
                new_lines = lines[:i] + [bad] + lines[i + 1:]; new_text = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
                try: t2 = ast.parse(new_text)
                except SyntaxError: continue
                a, b = sig(orig_tree), sig(t2)
                if a == b or [x for x in a if isinstance(x, tuple) and x[0] == "c"] != [x for x in b if isinstance(x, tuple) and x[0] == "c"]: continue
                return {"path": p, "fn": fn, "idx": i, "orig_line": ln, "bad_line": bad, "good_tok": good_tok, "bad_tok": bad_tok, "kind": kind,
                        "orig_text": text, "bad_text": new_text}
    return None

def unique_old(bad_text, lines, i):
    """Smallest block of consecutive lines ending at line i (extending upward) that occurs exactly once."""
    for k in range(0, 4):
        blk = "\n".join(lines[max(0, i - k): i + 1])
        if bad_text.count(blk) == 1: return blk, k
    return None, None

def udiff(path, old, new):
    d = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{path}", f"b/{path}", n=3))
    return d if d.endswith("\n") or not d else d + "\n"

def tc(name, **args): return {"type": "function", "function": {"name": name, "arguments": args}}
def tr(name, obj): return {"role": "tool", "name": name, "content": J(obj)}
def asst(think, calls=None, content=None, train=True):
    m = {"role": "assistant", "reasoning_content": think}
    if calls: m["tool_calls"] = calls
    if content is not None: m["content"] = content
    if not train: m["train"] = False
    return m

def skill_load(name):
    txt = (SKILLS / name / "SKILL.md").read_text()
    _, fm, body = txt.split("---", 2)
    meta = dict(l.split(": ", 1) for l in fm.strip().splitlines())
    return {"skill_name": name, "instructions": body.strip(), "frontmatter": meta}

def run_skill(name, argv, root, extra_files=None):
    code = (SKILLS / name / "scripts" / "check.py").read_text().replace('"/workspace"', J(str(root)))
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=os.path.dirname(str(root))) as f:
        f.write(code); sp = f.name
    try:
        r = subprocess.run([PY, "-I", sp, *argv], cwd=root, capture_output=True, text=True, timeout=30,
                           env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(root), "GIT_CONFIG_NOSYSTEM": "1"})
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    finally:
        os.unlink(sp)

def skill_result(name, rc, out, err):
    return {"skill_name": name, "file_path": "scripts/check.py", "stdout": out, "stderr": err, "status": "success" if rc == 0 else "error"}

def mk_workspace(d, bad_text):
    root = tempfile.mkdtemp(prefix="ws_")
    p = Path(root) / d["path"]; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(bad_text)
    g = lambda *a: subprocess.run(["git", *a], cwd=root, capture_output=True, env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": root, "GIT_AUTHOR_NAME": "a", "GIT_AUTHOR_EMAIL": "a@b", "GIT_COMMITTER_NAME": "a", "GIT_COMMITTER_EMAIL": "a@b"})
    g("init", "-q"); g("add", "-A"); g("commit", "-qm", "baseline")
    return root

def build_row(t, d, flow, rng, split):
    path, fn, i = d["path"], d["fn"], d["idx"]
    lines = d["bad_text"].splitlines(); total = len(lines)
    lo, hi = max(1, i + 1 - 10), min(total, i + 1 + 10)
    window = "\n".join(lines[lo - 1: hi])
    old, k = unique_old(d["bad_text"], lines, i)
    if old is None: return None
    new = "\n".join(d["orig_text"].splitlines()[max(0, i - k): i + 1])
    snippet_count = d["bad_text"].count(d["bad_line"].strip())
    stmt = (f"In `{path}`, function `{fn}`: the line `{d['bad_line'].strip()}` is wrong. The {d['kind']} `{d['bad_tok']}` must be `{d['good_tok']}`. "
            f"Fix this line and nothing else.")
    user = f"You are evaluating a software engineering task for repository {t['repo']}.\n\nProblem Statement:\n{stmt}" + TAIL
    msgs = [{"role": "user", "content": user}]
    root = None
    th = f"The task points at `{fn}` in `{path}`. I need the exact current text before editing, so I'll read the lines around it."
    msgs += [asst(th, [tc("read_file", end_line=hi, filepath=path, start_line=lo)]),
             tr("read_file", {"status": "ok", "filepath": path, "content": window, "start_line": lo, "end_line": hi, "total_lines": total, "is_truncated": False})]
    if flow == "skill_snap":
        msgs += [asst("Before editing, I'll hash the exact range with the snapshot-check skill so I know the text I saw is the text on disk.", [tc("load_skill", skill_name="snapshot-check")]),
                 tr("load_skill", skill_load("snapshot-check"))]
        root = mk_workspace(d, d["bad_text"])
        rc, out, err = run_skill("snapshot-check", [path, str(lo), str(hi)], root)
        msgs += [asst("Run it on the range I just read.", [tc("run_skill_script", args=[path, str(lo), str(hi)], file_path="scripts/check.py", skill_name="snapshot-check")]),
                 tr("run_skill_script", skill_result("snapshot-check", rc, out, err))]
        if rc != 0: return None
    if flow == "recover" and snippet_count >= 2:
        first = d["bad_line"].strip()
        msgs += [asst(f"Line {i + 1} reads `{first}`. I'll try that text as old_string.", [tc("edit_file", filepath=path, new_string=d["orig_line"].strip(), old_string=first)], train=False),
                 tr("edit_file", {"status": "error", "error_type": "FileEditError", "error_message": f"old_string matches {snippet_count} locations in {path}; add surrounding lines to make it unique or set allow_multiple=true.", "details": {"occurrences": snippet_count}})]
        th2 = f"The same text appears {snippet_count} times, so the edit was rejected. I'll include the line above" + (" and more context" if k > 1 else "") + " to make old_string unique, keeping exact indentation."
    else:
        th2 = (f"Line {i + 1} has the wrong {d['kind']}: `{d['bad_tok']}` should be `{d['good_tok']}`. " +
               (f"The line text occurs {snippet_count} times in the file, so I'll add the line{'s' if k > 1 else ''} above to make old_string unique." if k else "The line is unique in the file, so it is a safe old_string. I'll copy it exactly, including indentation."))
    msgs += [asst(th2, [tc("edit_file", filepath=path, new_string=new, old_string=old)])]
    fixed = d["bad_text"].replace(old, new, 1)
    if fixed != d["orig_text"]: return None
    diff = udiff(path, d["bad_text"], fixed)
    msgs += [tr("edit_file", {"status": "ok", "filepath": path, "occurrences": 1, "strategy": "exact", "diff": diff, "is_truncated": False})]
    if flow in ("skill_snap", "skill_ok", "skill_fail"):
        if root is None: root = mk_workspace(d, d["bad_text"])
        Path(root, path).write_text(fixed)
        msgs += [asst("The diff shows only the intended change. Before submitting I'll run the presubmit-check skill on the changed paths.", [tc("load_skill", skill_name="presubmit-check")]),
                 tr("load_skill", skill_load("presubmit-check"))]
        if flow == "skill_fail":
            scratch = f"tests/test_{fn.strip('_')}_check.py"
            Path(root, "tests").mkdir(exist_ok=True); Path(root, scratch).write_text("def test_x():\n    assert True\n")
            msgs += [asst("I'll drop a quick regression test into tests/ first.", [tc("write_file", content="def test_x():\n    assert True\n", filepath=scratch)], train=False),
                     tr("write_file", {"status": "ok", "filepath": scratch, "size": 33})]
        rc, out, err = run_skill("presubmit-check", [path], root)
        msgs += [asst("Run the check with the one source path I changed as the allowlist.", [tc("run_skill_script", args=[path], file_path="scripts/check.py", skill_name="presubmit-check")]),
                 tr("run_skill_script", skill_result("presubmit-check", rc, out, err))]
        if flow == "skill_fail":
            if rc == 0: return None
            msgs += [asst("The check rejected a path outside the allowlist: the test file I added. Tests must not be part of the patch, so I'll remove it and re-run.", [tc("run_command", command=f"rm {scratch}")]),
                     tr("run_command", {"status": "ok", "stdout": "", "stderr": "", "exit_code": 0})]
            os.unlink(Path(root, scratch)); rc, out, err = run_skill("presubmit-check", [path], root)
            msgs += [asst("Re-run the check.", [tc("run_skill_script", args=[path], file_path="scripts/check.py", skill_name="presubmit-check")]),
                     tr("run_skill_script", skill_result("presubmit-check", rc, out, err))]
        if rc != 0: return None
    msgs += [asst("The change is minimal and checks pass. Submitting the patch.", [tc("submit_patch")]),
             tr("submit_patch", {"status": "ok", "patch_size": len(diff), "files_changed": 1}),
             asst("The patch is submitted.", None, f"Fixed `{fn}` in `{path}`: changed `{d['bad_tok']}` to `{d['good_tok']}` on line {i + 1}.")]
    return {"family": "agent", "subtype": f"edit_{flow}", "split": split, "source": {"task": t["instance_id"], "repo": t["repo"], "path": path, "line": i + 1},
            "thinking": True, "tools": ALL, "messages": msgs,
            "verifier": {"kind": "edit_traj", "path": path, "bad_text": d["bad_text"], "orig_text": d["orig_text"], "edits": [{"old": old, "new": new}]}}

FLOWS = ["plain"] * 9 + ["recover"] * 4 + ["skill_ok"] * 4 + ["skill_snap"] * 2 + ["skill_fail"] * 3
def make_rows(tasks, per_task=4):
    rows, seen = [], set()
    for t in tasks:
        try: srcs = load_src(t["instance_id"])
        except FileNotFoundError: continue
        made = 0
        for attempt in range(per_task * 4):
            rng = rng_for("agent", t["instance_id"], attempt)
            d = find_drill(srcs, rng)
            if not d: continue
            key = sha(d["path"] + str(d["idx"]) + d["bad_line"] + sha(d["orig_text"]))
            if key in seen: continue
            flow = FLOWS[int(sha(key, 6), 16) % len(FLOWS)]
            split = "train" if int(sha("fn|" + key, 8), 16) % 10 < 8 else ("dev" if int(sha("fn|" + key, 8), 16) % 10 == 8 else "test")
            r = build_row(t, d, flow, rng, split)
            if r is None: continue
            seen.add(key); rows.append(r); made += 1
            if made >= per_task: break
    return rows
