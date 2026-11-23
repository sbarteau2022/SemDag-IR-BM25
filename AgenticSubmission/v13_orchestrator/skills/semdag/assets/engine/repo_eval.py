"""repo_eval: type the issue, anchor it in the code graph, then gate the patch (v11).

  locate   args: [issue text]
           Parse the issue into a problem IR (identifiers, traceback frames, literals, paths; see
           task_ir.py), join it to the code IR by exact containment, and, on the anchor only, compute
           the loop locus. Prints about 400 characters of plain text, one action:
             edit <file>:<a>-<b> <qualname>  (anchor: traceback|literal|qualname|bm25: evidence)
             loop <kind> <lines> carries <names>  test: <condition>      (only when there is a locus)
             read <file> L<a>-<b>                                        (fix_edit's numbered view)
             check <one pytest node>
             forbid tests/, signature change[, the terminal raise ...]
             alt <two BM25 alternatives>                                 (only for a bm25 guess)
           The ranked list, hubs, walk paths, risk, fan-in and topo ranks go to eval.json only.
  verify   args: ["--verify"]
           Read the working-tree change from git (see impact.py). It blocks, not advises: when the
           anchor had a loop locus and no diff hunk touches it, or when the change deletes most of a
           file, `next` starts with "blocked:" and `clean` is false.
  flow     args: ["--flow", "Class.method"]  the recurrent structure of one function, as JSON.

The script never raises to the caller: every failure is a JSON object with `error` and `hint`.
It reads the repository only, and writes its cache under the temp directory so nothing enters
the patch. The repository is found from the harness wrapper's location (see wsroot.py), so the
script works in the docker backend (/workspace) and in the subprocess backend Kaggle uses.
"""
import ast
import hashlib
import json
import os
import re
import sys
import shlex

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wsroot  # noqa: E402
os.environ["SEMDAG_CACHE"] = wsroot.cache_root()
import cache, snapshot, semdag_ir_ast, retriever, vulnwalk, impact, flow, task_ir  # noqa: E402

DEFAULT_CONTAINER = "task"
VERIFY_BUDGET = 2600          # characters of JSON printed by verify
FLOW_BUDGET = 2200            # characters of JSON printed by flow
TOP_SITES = 10
READ_PAD = 15                 # lines shown around the edit span
READ_MAX = 90                 # fix_edit's numbered window (fix_edit.SHOW_LINES)
DESTRUCTIVE_MIN = 40          # a change deleting this many lines and ...
DESTRUCTIVE_SHARE = 0.5       # ... this share of the file is a rewrite, not a fix
ISSUE_KEYS = {"problem", "issue", "query", "text", "description", "problem_statement", "issue_text",
              "problem_description", "task", "q", "input", "prompt", "statement", "bug"}
USAGE = ("Pass args as a list with one string, the whole issue text, to get the edit span. "
         "Pass [\"--flow\", \"Class.method\"] to see a function's loops, recursion and callers. "
         "Pass [\"--verify\"] after editing to check the change.")


# ---------------------------------------------------------------- arguments
def _as_list(args):
    """One string that holds a stringified list becomes that list."""
    if len(args) == 1 and args[0].lstrip().startswith("[") and args[0].rstrip().endswith("]"):
        try:
            parsed = ast.literal_eval(args[0])
            if isinstance(parsed, (list, tuple)):
                return [str(x) for x in parsed]
        except (ValueError, SyntaxError):
            pass
    return args


def _flag(tok):
    m = re.fullmatch(r"--?([A-Za-z][A-Za-z0-9_-]*)", tok)
    return m.group(1).replace("-", "_").lower() if m else None


def parse_args(argv):
    """Tolerant parser for the shapes a small model emits through run_skill_script: a list with
    the issue text, a dict (the harness turns it into --key value pairs), flag-only calls, the
    legacy [container, repo, ...] form, and an issue split over several strings."""
    args = _as_list([str(a) for a in argv])
    if len(args) == 1 and re.match(r"\s*-{0,2}(flow|loops)\s+\S", args[0]):
        args = args[0].split(None, 1)  # "--flow Class.method" passed as one string
    opt = {"mode": "locate", "issue": [], "repo": None, "container": DEFAULT_CONTAINER,
           "problem_file": None, "top_n": TOP_SITES, "ref": None}
    bare = []
    i = 0
    while i < len(args):
        tok = args[i]
        key = _flag(tok)
        nxt = args[i + 1] if i + 1 < len(args) else None
        if key is None:
            bare.append(tok)
        elif key in ("verify", "check", "validate"):
            if nxt is None or nxt.strip().lower() not in ("false", "0", "no"):
                opt["mode"] = "verify"
            if nxt is not None and nxt.strip().lower() in ("true", "false", "1", "0", "yes", "no"):
                i += 1
        elif key in ("flow", "loops", "recurrence") and nxt is not None:
            opt["mode"], opt["ref"] = "flow", nxt.strip()
            i += 1
        elif key in ("problem_file", "file") and nxt is not None:
            opt["problem_file"] = nxt
            i += 1
        elif key in ("repo", "repo_dir", "workspace", "path") and nxt is not None:
            opt["repo"] = nxt
            i += 1
        elif key in ("top_n", "n", "k") and nxt is not None:
            try:
                opt["top_n"] = max(1, min(20, int(nxt)))
            except ValueError:
                pass
            i += 1
        elif key in ("container", "container_id") and nxt is not None:
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", nxt):
                opt["container"] = nxt
            i += 1
        elif nxt is not None:
            # --problem TEXT, --issue TEXT, and any unknown --key TEXT: the value is issue text
            if key in ISSUE_KEYS or len(nxt) > 3:
                opt["issue"].append(nxt)
            i += 1
        i += 1
    # legacy positional form: <container_id> <repo_dir> ...
    if len(bare) >= 2 and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", bare[0]) and (
            bare[1].rstrip("/") == wsroot.LITERAL or os.path.isdir(bare[1])):
        opt["container"], opt["repo"] = bare[0], opt["repo"] or bare[1]
        bare = bare[2:]
    if len(bare) == 1 and bare[0].strip().lower() in ("verify", "check"):
        opt["mode"], bare = "verify", []
    if len(bare) == 2 and bare[0].strip().lower() in ("flow", "loops"):
        opt["mode"], opt["ref"], bare = "flow", bare[1].strip(), []
    opt["issue"] = "\n".join(bare + opt["issue"]).strip()
    opt["repo"] = wsroot.workspace_root(opt["repo"])
    return opt


# ---------------------------------------------------------------- parity
def _recompute_tree(snap):
    h = hashlib.sha256()
    for rel in sorted(snap["files"]):
        h.update(rel.encode())
        h.update(snap["files"][rel]["sha256"].encode())
    return h.hexdigest()


def parity_check(snap, ir):
    """The graph must be a faithful derivation of the frozen bytes: same tree hash, no file
    node that is absent from the snapshot."""
    recomputed = _recompute_tree(snap)
    ir_files = {n["file"] for n in ir["nodes"] if n["kind"] == "file"}
    phantom = sorted(f for f in ir_files if f not in snap["files"])
    py = {r for r in snap["files"] if r.endswith(".py") and "content" in snap["files"][r]}
    ok = (recomputed == snap["tree_sha256"] == ir["tree_sha256"]) and not phantom
    return {"ok": ok, "tree_sha256": snap["tree_sha256"], "phantom_files": phantom,
            "py_files": len(py), "covered": len(ir_files & py),
            "uncovered_parseable": sorted(py - ir_files)[:20]}


def _dumps(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------- locate
def _test_node(test_file, name, text):
    """`file::test_fn` for the first test function in the file whose body names `name`, else the file."""
    if not text:
        return test_file
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return test_file
    rx = re.compile(r"\b" + re.escape(name) + r"\b")
    lines = text.splitlines()
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            body = "\n".join(lines[node.lineno - 1:node.end_lineno or node.lineno])
            if rx.search(body):
                found.append((node.lineno, node.name))
    if not found:
        return test_file
    owner = {}
    for cls in ast.walk(tree):
        if isinstance(cls, ast.ClassDef):
            for item in cls.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owner[item.lineno] = cls.name
    line, fn = min(found)
    return f"{test_file}::{owner[line]}::{fn}" if line in owner else f"{test_file}::{fn}"


def _span(a, b):
    return f"{a}-{b}" if b != a else str(a)


def check_for_site(ir, snap, repo, site):
    """Choose verification for the actual assigned site, including alternatives."""
    def read(path):
        return snap["files"].get(path, {}).get("content")
    rel = site["file"]
    targets = [(rel, site.get("qualname", site["name"]))]
    tests = [t["file"] for t in impact.rank_tests(ir, repo, targets, read)[:impact.MAX_TESTS]]
    if tests:
        node = _test_node(tests[0], site["name"], read(tests[0]))
        return f"python -m pytest {shlex.quote(node)} -q -x 2>&1 | tail -15"
    code = f"compile(open({rel!r}, 'rb').read(), {rel!r}, 'exec')"
    return "python -c " + shlex.quote(code)


def locate(opt):
    """v11 locate: problem IR -> anchor -> locus -> one action of about 400 characters.

    The ranked list, hubs, walk paths, risk, fan-in and topo ranks go to eval.json only."""
    repo, cid = opt["repo"], opt["container"]
    issue = opt["issue"]
    if opt["problem_file"]:
        try:
            with open(opt["problem_file"], errors="replace") as fh:
                issue = (issue + "\n" + fh.read()).strip()
        except OSError as ex:
            return {"error": f"cannot read problem file: {ex}", "hint": USAGE}
    if not issue:
        return {"error": "no issue text was passed", "hint": USAGE}
    if not os.path.isdir(repo):
        return {"error": f"repository directory not found: {repo}", "hint": USAGE}

    cache.init_container(cid, repo)
    snap = snapshot.snapshot(cid, repo)
    ir = semdag_ir_ast.build(cid)
    par = parity_check(snap, ir)
    if not par["ok"]:
        return {"mode": "locate", "parity_ok": False, "error": "graph does not match the snapshot",
                "hint": "Run the localizer again. If it repeats, search with run_command and grep."}

    pir = task_ir.problem_ir(issue)
    ranked = retriever.rank(ir, snap, issue, opt["top_n"])        # the v6 ranking: BM25 + light walk
    bm = {s["id"]: s["lexical_score"] for s in ranked["top"]}
    docs_scores = retriever.lexical_scores(ir, snap, issue)       # every function, for tie-breaks
    bm.update({k: v for k, v in docs_scores.items() if k not in bm})
    nodes = {n["id"]: n for n in ir["nodes"]}

    site, how, evidence = task_ir.anchor(ir, snap, pir, bm)
    alts = []
    if site is None:
        if not ranked["top"]:
            out_text = ("no anchor: no word of the issue occurs in the library source.\n"
                        "Search with run_command: grep -rn '<identifier from the issue>' --include=*.py . | head")
            cache.write(cid, "task_ir.json", {"problem": pir, "anchor": None, "locus": None})
            return {"mode": "locate", "text": out_text}
        site, how, evidence = nodes[ranked["top"][0]["id"]], "bm25", "rank 1, a guess"
        alts = [s for s in ranked["top"][1:3]]
    loc = task_ir.locus(ir, snap, site, pir) if how in ("traceback", "literal", "qualname") else None

    rel = site["file"]
    fstart, fend = site.get("start_line", site["line"]), site["end_line"]
    content = snap["files"].get(rel, {}).get("content") or ""
    total = len(content.splitlines())
    if loc:
        ea, eb = loc["start"], loc["end"]
    else:
        ea, eb = fstart, fend
    ra = max(1, (ea if loc else fstart) - READ_PAD)
    rb = min(total or eb, (eb if loc else fend) + READ_PAD)
    if rb - ra + 1 > READ_MAX:  # keep the read inside fix_edit's numbered window
        ra, rb = (max(1, ea - 5), min(total or eb, max(1, ea - 5) + READ_MAX - 1))

    check = check_for_site(ir, snap, repo, site)

    qual = site.get("qualname", site["name"])
    lines = [f"edit {rel}:{_span(ea, eb)} {qual}  (anchor: {how}: {evidence})"]
    if loc:
        lines.append(f"loop {loc['kind']} {_span(loc['loop_line'], loc['end'])} carries {','.join(loc['carried'][:4])}"
                     + (f"  test: {loc['test']}" if loc.get("test") else ""))
    lines.append(f'read fix_edit.py ["{rel} L{ra}-{rb}"]')
    lines.append(f"check {check}")
    forbid = "forbid tests/, signature change"
    tr = task_ir.terminal_raise(snap, site)
    if loc and tr:
        forbid += f", the terminal raise at L{tr} unless lines {_span(ea, eb)} are also in the diff"
    lines.append(forbid)
    if alts:
        lines.append("alt " + "; ".join(f"{a['qualname']} {a['file']}:{a['line']}-{a['end_line']}" for a in alts))
    text = "\n".join(lines)

    state = {"problem": pir, "anchor": {"file": rel, "qualname": qual, "line": site["line"],
                                        "start": fstart, "end": fend, "how": how, "evidence": evidence},
             "edit": {"file": rel, "start": ea, "end": eb}, "locus": loc, "read": [ra, rb],
             "check": check}
    cache.write(cid, "task_ir.json", state)

    # Everything else is for the paper, not the agent: ranked sites with risk, fan-in and topo
    # rank, hubs and walk paths of the vulnerability walk, and the flow view of the anchor.
    walk = vulnwalk.rank(ir, snap, issue, opt["top_n"])
    index = flow.Index(ir)
    full = []
    for i, s in enumerate(ranked["top"]):
        p = next((w for w in walk.get("top", []) if w["id"] == s["id"]), {})
        full.append({"rank": i + 1, "file": s["file"], "line": s["line"], "end_line": s["end_line"],
                     "qualname": s["qualname"], "risk": p.get("risk", 0), "fan_in": p.get("fan_in", 0),
                     "topo_rank": nodes[s["id"]].get("topo_rank"), **flow.site_flags(index, s["id"])})
    ctx = vulnwalk.compact(walk) if walk.get("top") else {"hubs": [], "walk_paths": []}
    cache.write(cid, "eval.json", {"repo": repo, "parity": par, "semdag": ir["counts"], "retrieval": ranked,
                                   "top_edit_sites": full, "hubs": ctx["hubs"], "walk_paths": ctx["walk_paths"],
                                   "flow": flow.describe(ir, f"{rel}::{qual}", rel, index=index),
                                   "task_ir": state, "stdout": text})
    cache.mark_stage(cid, "repo_eval", {"parity_ok": True, "anchor": how})
    return {"mode": "locate", "text": text}


# ---------------------------------------------------------------- flow
def _graph_for(opt):
    """The cached graph from locate, or a fresh one when flow or verify runs first."""
    repo, cid = opt["repo"], opt["container"]
    try:
        return cache.read(cid, "semdag_ir.json")
    except (OSError, ValueError):
        cache.init_container(cid, repo)
        snapshot.snapshot(cid, repo)
        return semdag_ir_ast.build(cid)


def flow_mode(opt):
    if not opt.get("ref"):
        return {"error": "no function was named", "hint": USAGE}
    if not os.path.isdir(opt["repo"]):
        return {"error": f"repository directory not found: {opt['repo']}", "hint": USAGE}
    ref, file = opt["ref"], None
    if "::" in ref:
        file = ref.split("::")[0]
    out = {"mode": "flow", **flow.describe(_graph_for(opt), ref, file)}
    while len(_dumps(out)) > FLOW_BUDGET:
        if len(out.get("loops", [])) > 2:
            out["loops"].pop()
        elif len(out.get("callers", [])) > 2:
            out["callers"].pop()
        elif len(out.get("calls", [])) > 2:
            out["calls"].pop()
        else:
            break
    return out


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)


def old_hunks(repo, rel):
    """Baseline-side line ranges touched by the working-tree change of one file."""
    ref = impact.baseline_ref(repo)
    if not ref:
        return None
    rc, text = impact._git(repo, "diff", "-U0", "--no-color", ref, "--", rel)
    if rc != 0:
        return None
    out = []
    for m in HUNK.finditer(text):
        a, n = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
        out.append((a, a + n - 1) if n else (a, a))   # pure insertion after line a
    return out


def destructive(repo, kept):
    """Files whose change deletes most of the file: a whole-file rewrite, never a fix."""
    ref = impact.baseline_ref(repo)
    if not ref:
        return []
    rc, text = impact._git(repo, "diff", "--numstat", ref, "--", *kept) if kept else (1, "")
    bad = []
    for line in (text.splitlines() if rc == 0 else []):
        bits = line.split("\t")
        if len(bits) != 3 or not bits[1].isdigit():
            continue
        deleted, rel = int(bits[1]), bits[2]
        old = impact.old_content(repo, ref, rel)
        total = len(old.splitlines()) if old else 0
        if total and deleted >= max(DESTRUCTIVE_MIN, DESTRUCTIVE_SHARE * total):
            bad.append({"file": rel, "deleted": deleted, "of": total})
    return bad


def gate(repo, cid, out):
    """v13: verify blocks empty patches, whole-file rewrites, undefined names, signature breaks, and missed loop loci."""
    if out.get("patch", {}).get("empty"):
        return ("blocked: patch is empty. Reproduce the failure first, then apply a minimal fix "
                "with fix_edit [\"<file>\", \"L<a>-<b>\", new_text], and verify again.")
    if out.get("undefined_names"):
        u = out["undefined_names"][0]
        return (f"blocked: undefined name '{u.get('name')}' at {u.get('file')}:{u.get('line')}. "
                f"Define or import it with fix_edit, then verify again.")
    if out.get("signature_breaks"):
        sb = out["signature_breaks"][0]
        return (f"blocked: signature change on {sb.get('qualname')} breaks callers ({sb.get('reason')}). "
                f"Restore the signature or update callers, then verify again.")
    kept = out.get("patch", {}).get("files", [])
    for d in destructive(repo, kept):
        return (f"blocked: the patch deletes {d['deleted']} of {d['of']} lines of {d['file']}. "
                f"Restore it with run_command `git checkout -- {d['file']}` and replace only the lines "
                f"you need with fix_edit [\"{d['file']}\", \"L<a>-<b>\", new_text].")
    try:
        state = cache.read(cid, "task_ir.json")
    except (OSError, ValueError):
        return None
    loc = state.get("locus")
    if not loc:
        return None
    rel, a, b = loc["file"], loc["start"], loc["end"]
    hunks = old_hunks(repo, rel) if rel in kept else []
    if hunks is None:
        return None
    if any(h0 <= b and h1 >= a - 1 for h0, h1 in hunks):
        return None
    names = ",".join(loc.get("carried", [])[:4])
    return (f"blocked: patch does not touch {loc['kind']} {a}-{b} carrying {names} in {rel}. "
            f"Edit inside that span: fix_edit [\"{rel}\", \"L{a}-{b}\", new_text], then verify again.")


# ---------------------------------------------------------------- verify
def verify(opt):
    repo, cid = opt["repo"], opt["container"]
    if not os.path.isdir(repo):
        return {"error": f"repository directory not found: {repo}", "hint": USAGE}
    ir = base_files = None
    try:
        ir = cache.read(cid, "semdag_ir.json")
    except (OSError, ValueError):
        ir = None
    has_git = impact.baseline_ref(repo) is not None
    if ir is None or not has_git:
        try:
            base_files = cache.read(cid, "snapshot.json")["files"]
        except (OSError, ValueError):
            base_files = None
    if ir is None:
        # verify was called before locate: build the graph from the tree as it is now
        if has_git:
            cache.init_container(cid, repo)
            snapshot.snapshot(cid, repo)
            ir = semdag_ir_ast.build(cid)
    out = impact.analyze(repo, ir=ir, base_files=None if has_git else base_files)
    if "patch" in out:
        reason = gate(repo, cid, out)
        if reason:
            out["blocked"] = True
            out["clean"] = False
            if not out.get("syntax_errors"):
                out["next"] = reason
            else:
                out["blocked_reason"] = reason
    try:
        cache.write(cid, "verify.json", out)
    except OSError:
        pass
    for key in ("changed_defs", "callers_to_check", "module_level_changed", "signature_breaks",
                "removed_still_used", "undefined_names"):
        if len(_dumps(out)) <= VERIFY_BUDGET:
            break
        if key == "callers_to_check" and key in out:
            out[key]["library"] = out[key]["library"][:2]
        elif isinstance(out.get(key), list):
            out[key] = out[key][:2]
    return out


def main(argv=None):
    try:
        opt = parse_args(sys.argv[1:] if argv is None else argv)
        mode = opt["mode"]
        out = verify(opt) if mode == "verify" else flow_mode(opt) if mode == "flow" else locate(opt)
    except Exception as ex:  # never hand the model a traceback
        out = {"error": f"{type(ex).__name__}: {ex}"[:300], "hint": USAGE}
    print(out["text"] if isinstance(out, dict) and "text" in out else _dumps(out))
    return out


if __name__ == "__main__":
    main()
