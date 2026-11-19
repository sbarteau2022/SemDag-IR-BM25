"""repo_eval: localize an issue in /workspace, then check a change before it is submitted.

Two modes, one compact JSON line on stdout each. Standard library only, offline.

  locate   args: [issue text]
           Snapshot the repository, build the typed graph, check byte parity, rank edit
           sites, and list hub context and the tests nearest to the top sites.
  verify   args: ["--verify"]
           Read the working-tree change from git and report what the submitted patch will
           contain, what the change breaks, and which existing test to run (see impact.py).

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wsroot  # noqa: E402
os.environ["SEMDAG_CACHE"] = wsroot.cache_root()
import cache, snapshot, semdag_ir_ast, retriever, vulnwalk, impact, flow  # noqa: E402

DEFAULT_CONTAINER = "task"
LOCATE_BUDGET = 3600          # characters of JSON printed by locate
VERIFY_BUDGET = 2600          # characters of JSON printed by verify
FLOW_BUDGET = 2200            # characters of JSON printed by flow
# locate also carries the flow of its top sites. The harness cuts skill stdout at 5,000 characters
# (swegemma/budget.py max_stdout_chars), so locate's own part keeps LOCATE_BUDGET and the flow part
# gets FLOW_IN_LOCATE (inside FLOW_BUDGET): 3,600 + 1,300 = 4,900.
FLOW_IN_LOCATE = 1300
FLOW_SITES = 2
TOP_SITES = 10
HUBS_SHOWN = 3
SHORT_QUERY_CHARS = 80
ISSUE_KEYS = {"problem", "issue", "query", "text", "description", "problem_statement", "issue_text",
              "problem_description", "task", "q", "input", "prompt", "statement", "bug"}
USAGE = ("Pass args as a list with one string, the issue text, to rank edit sites. "
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
def site_flow(index, ir, site):
    """Compact flow of one ranked site: loops (lines, carried names, exits, calls), recursion
    and callers. Sites with nothing recurrent and no callers get no entry."""
    d = flow.describe(ir, f"{site['file']}::{site['qualname']}", site["file"], index=index)
    if d.get("error"):
        return None
    out = {"site": f"{site['file']}::{site['qualname']}"}   # file too: two packages can share a qualname
    if d.get("loops"):
        out["loops"] = [{k: l[k] for k in ("at", "kind", "carried", "exits", "calls") if l.get(k)}
                        for l in d["loops"]]
    if d.get("recursion"):
        out["recursion"] = d["recursion"]
    if d.get("callers"):
        out["callers"] = d["callers"][:3]
        if d.get("callers_total", 0) > 3:
            out["callers_total"] = d["callers_total"]
    return out if len(out) > 1 else None


def trim_flow(entries, budget):
    """Shrink flow entries deterministically until they fit: callers, then loop calls, then
    later loops, then the second site."""
    def size():
        return len(_dumps(entries))
    while entries and size() > budget:
        last = entries[-1]
        if len(last.get("callers", [])) > 1:
            last["callers"].pop()
        elif any(l.get("calls") for l in last.get("loops", [])):
            next(l for l in reversed(last["loops"]) if l.get("calls")).pop("calls")
        elif len(last.get("loops", [])) > 1:
            last["loops"].pop()
        elif last.get("recursion", {}).get("with"):
            last["recursion"].pop("with")
        elif len(entries) > 1:
            entries.pop()
        elif len(last) > 1:
            last.pop(next(k for k in reversed(list(last)) if k != "site"))
        else:
            entries.pop()
    return entries


def locate(opt):
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

    # Edit sites: BM25 over live function source, consolidated by a damped walk. This is the
    # ranking that held up on held-out tasks. The vulnerability walk adds context only.
    ranked = retriever.rank(ir, snap, issue, opt["top_n"])
    walk = vulnwalk.rank(ir, snap, issue, opt["top_n"])
    parts = {s["id"]: s for s in walk.get("top", [])}
    _scores, all_parts, _meta = ({}, {}, {})
    if any(s["id"] not in parts for s in ranked["top"]):
        _scores, all_parts, _meta = vulnwalk.score_nodes(ir, snap, issue, False, vulnwalk.DAMPING)
    index = flow.Index(ir)
    sites = []
    for i, s in enumerate(ranked["top"]):
        p = parts.get(s["id"]) or all_parts.get(s["id"]) or {}
        sites.append({"rank": i + 1, "file": s["file"], "line": s["line"], "end_line": s["end_line"],
                      "qualname": s["qualname"], "risk": p.get("risk", 0), "fan_in": p.get("fan_in", 0),
                      **flow.site_flags(index, s["id"])})

    ctx = vulnwalk.compact(walk) if walk.get("top") else {"hubs": [], "walk_paths": []}
    hubs = ctx["hubs"][:HUBS_SHOWN]
    paths = ctx["walk_paths"][:HUBS_SHOWN]

    def read(rel):
        return snap["files"].get(rel, {}).get("content")
    targets = [(s["file"], s["qualname"]) for s in sites[:3]]
    tests = [t["file"] for t in impact.rank_tests(ir, repo, targets, read)[:impact.MAX_TESTS]] if targets else []

    out = {"mode": "locate", "files": par["py_files"], "matched": ranked["matched_candidates"],
           "top_edit_sites": sites, "tests_near_sites": tests, "hubs": hubs, "walk_paths": paths}
    if not sites:
        out["note"] = ("No word of the query occurs in the library source. Pass the issue's own "
                       "identifiers, file names and error text.")
    elif len(issue) < SHORT_QUERY_CHARS:
        out["note"] = ("Short query. Ranking improves when you pass the whole issue text, with its "
                       "identifiers and error messages.")

    flows = [f for f in (site_flow(index, ir, s) for s in sites[:FLOW_SITES]) if f]
    flows = trim_flow(flows, FLOW_IN_LOCATE)

    cache.write(cid, "eval.json", {"repo": repo, "parity": par, "semdag": ir["counts"],
                                   "retrieval": ranked, "locate": out, "flow": flows})
    cache.mark_stage(cid, "repo_eval", {"parity_ok": True, "localized": len(sites)})

    # trim deterministically to the budget: walk steps, then paths, then hubs, then low sites
    while len(_dumps(out)) > LOCATE_BUDGET:
        longest = max(out["walk_paths"], key=lambda p: len(p["reach"]), default=None)
        if longest and len(longest["reach"]) > 2:
            longest["reach"].pop()
        elif out["walk_paths"]:
            out["walk_paths"].pop()
        elif out["hubs"]:
            out["hubs"].pop()
        elif any("callers" in s for s in out["top_edit_sites"]):
            next(s for s in reversed(out["top_edit_sites"]) if "callers" in s).pop("callers")
        elif len(out["top_edit_sites"]) > 5:
            out["top_edit_sites"].pop()
        else:
            break
    if flows:
        out["flow"] = flows
    return out


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


def recurrence_notes(ir, changed_defs, limit=3):
    """What the change touches in the recurrent structure: cycles and loops."""
    index = flow.Index(ir)
    notes = []
    for d in changed_defs:
        if d.endswith(" (new)") or "::" not in d:
            continue
        rel, q = d.split("::", 1)
        ids = index.find(f"{rel}::{q}")
        if not ids:
            continue
        n = index.nodes[ids[0]]
        if n.get("recursive"):
            others = [index.nodes[m].get("qualname") for m in index.nodes[n["scc"]]["members"] if m != ids[0]]
            notes.append(f"{q} is recursive" + (f" with {', '.join(others[:3])}" if others else "")
                         + ": check the base case and that every path still terminates.")
        loops = index.loops_of(ids[0])
        carried = sorted({c for l in loops for c in index.nodes[l].get("carried", [])})
        if loops:
            notes.append(f"{q} has {len(loops)} loop(s)" + (f" carrying {', '.join(carried[:5])}" if carried else "")
                         + ": check the first and last iteration and the empty case.")
        if len(notes) >= limit:
            break
    return notes[:limit]


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
    if ir is not None and out.get("changed_defs"):
        notes = recurrence_notes(ir, out["changed_defs"])
        if notes:
            out["recurrence"] = notes
    try:
        cache.write(cid, "verify.json", out)
    except OSError:
        pass
    for key in ("changed_defs", "callers_to_check", "module_level_changed", "signature_breaks",
                "removed_still_used", "undefined_names", "recurrence"):
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
    print(_dumps(out))
    return out


if __name__ == "__main__":
    main()
