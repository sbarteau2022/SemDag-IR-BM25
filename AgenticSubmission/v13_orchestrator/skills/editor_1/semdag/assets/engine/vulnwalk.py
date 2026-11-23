"""Vulnerability walk: score every node of the typed SemDAG, then walk outward.

Stage 1 reuses the v4 source signal: BM25 over live function source is the
restart distribution of a damped walk over contains / calls / imports edges.
Unlike v4, every node the walk reaches is scored (function, method, class,
file), not only the BM25-matched functions.

Stage 2 turns walk mass into a hub score.  Mass says "the issue flows here";
fan-in says "many things depend on this place", so one hop from it reaches
many consumers.  Only LIBRARY callers and importers count: code under tests,
docs_src, examples, scripts and similar is excluded, because a public helper
called from hundreds of tutorial snippets is not more likely to need an edit.
The boost is capped, so structure can at most triple relevance:

    boost(v) = min(3, (1 + ln(1 + fan_in_lib(v))) * (1 + ln(1 + importers_lib(v))))
    h(v)     = mass(v) * boost(v)

Stage 3 adds a small per-function risk prior read from the AST (broad except,
unguarded raise, unchecked subscript parameter, string-built path, subprocess
or eval, mutable default):

    score(v) = h_norm(v) * (1 + 0.5 * min(1, risk_count(v) / 3))

Stage 4 expands the top seeds with a hop depth chosen by relative score
(3 / 2 / 1) and stops a path when its strength falls below a fraction of the
seed's score.

Every constant below is fixed by design.  None is fitted to benchmark tasks.
The module is stdlib-only, offline and deterministic: ties break on
(file, line, id) and floats are rounded only at output.
"""
import ast
import json
import math
from collections import Counter, defaultdict

import retriever

DAMPING = retriever.DEFAULT_DAMPING            # 0.15, same as v4
RISK_WEIGHT = 0.5
RISK_SATURATION = 3
SEED_COUNT = 5
DEPTH_HIGH, DEPTH_MID = 0.66, 0.33             # relative-score cut points
HOP_LIMITS = (4, 3, 2)                          # neighbours kept at hop 1, 2, 3
PATH_FLOOR = 0.1                                # of the seed's score
WALK_WEIGHTS = {"contains": 1.0, "calls": 1.0, "imports": 1.0}
OUTPUT_BUDGET = 4800                            # chars; tool output cap is 5000
NODE_KINDS = ("file", "class", "function", "method")
BOOST_CAP = 3.0                                 # hub boost never exceeds 3x relevance mass
# Directory names whose code is a consumer of the library, not part of it.
NON_LIBRARY_DIRS = {"docs_src", "docs", "doc", "examples", "example", "scripts", "benchmarks",
                    "bench", "tutorial", "tutorials", "demo", "demos", "samples", "sample"}


def is_library_path(rel):
    """True for library code: not a test file and not under a consumer directory."""
    parts = rel.split("/")
    return not retriever.is_test_path(rel) and not any(p in NON_LIBRARY_DIRS for p in parts[:-1])


# ---------------------------------------------------------------- risk prior
_PROC = {"os.system", "os.popen", "eval", "exec"}
_PATH_SINKS = {"open", "Path", "os.path.join", "os.remove", "os.makedirs", "os.listdir"}


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _string_built(arg):
    if isinstance(arg, ast.JoinedStr):
        return True
    if isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Add, ast.Mod)):
        return True
    return (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute)
            and arg.func.attr == "format")


def risk_count(fn):
    """Count risk signals inside one FunctionDef / AsyncFunctionDef."""
    args = fn.args
    params = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs} - {"self", "cls"}
    count = 0
    for default in args.defaults + [d for d in args.kw_defaults if d is not None]:
        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
            count += 1
        elif isinstance(default, ast.Call) and _dotted(default.func) in ("list", "dict", "set"):
            count += 1
    guarded, subscripted = set(), set()
    covered = set()                              # raise nodes inside a try body
    for node in ast.walk(fn):
        if isinstance(node, ast.Try) and node.handlers:
            for stmt in node.body:
                covered.update(id(n) for n in ast.walk(stmt))
    for node in ast.walk(fn):
        if isinstance(node, ast.ExceptHandler):
            t = node.type
            if t is None or (isinstance(t, ast.Name) and t.id in ("Exception", "BaseException")):
                count += 1
        elif isinstance(node, ast.Raise) and node.exc is not None and id(node) not in covered:
            count += 1
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
                and node.value.id in params:
            subscripted.add(node.value.id)
        elif isinstance(node, (ast.If, ast.IfExp, ast.While, ast.Assert)):
            guarded.update(n.id for n in ast.walk(node.test) if isinstance(n, ast.Name))
        elif isinstance(node, ast.Call):
            name = _dotted(node.func) or ""
            if name.startswith("subprocess.") or name in _PROC:
                count += 1
            elif name in _PATH_SINKS and node.args and _string_built(node.args[0]):
                count += 1
    return count + len(subscripted - guarded)


def _risk_by_node(ir, snap, ids):
    """risk_count per function/method id, parsing each file once."""
    wanted = defaultdict(list)
    nodes = {n["id"]: n for n in ir["nodes"]}
    for nid in ids:
        n = nodes[nid]
        wanted[n["file"]].append(n)
    out = {}
    for rel, group in wanted.items():
        content = snap["files"].get(rel, {}).get("content")
        if content is None:
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        by_line = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                by_line[(node.lineno, node.name)] = node
        for n in group:
            fn = by_line.get((n["line"], n["name"]))
            if fn is not None:
                out[n["id"]] = risk_count(fn)
    return out


# ------------------------------------------------------------- structure
def _structure(ir, keep):
    """fan_in (distinct library callers) and importers (library files importing the node's file)."""
    callers = defaultdict(set)
    importers = defaultdict(set)
    contains = defaultdict(list)
    files = {n["id"]: n["file"] for n in ir["nodes"]}
    for e in ir["edges"]:
        if e["src"] not in keep or e["dst"] not in keep:
            continue
        lib_src = is_library_path(files.get(e["src"], ""))
        if e["rel"] == "calls":
            if lib_src and e["src"] != e["dst"]:  # recursion is not fan-in
                callers[e["dst"]].add(e["src"])
        elif e["rel"] == "imports":
            if lib_src:
                importers[e["dst"]].add(e["src"])
        elif e["rel"] == "contains":
            contains[e["src"]].append(e["dst"])
    return callers, importers, contains


def _subtree_fan_in(nid, callers, contains, memo):
    if nid in memo:
        return memo[nid]
    total = len(callers.get(nid, ()))
    for child in contains.get(nid, ()):
        total += _subtree_fan_in(child, callers, contains, memo)
    memo[nid] = total
    return total


def score_nodes(ir, snap, issue, include_tests=False, damping=DAMPING):
    """Return (scores, parts, meta).  scores maps node id -> final score in [0, 1.5]."""
    docs = retriever._documents(ir, snap, include_tests=include_tests)
    bm = retriever._bm25(docs, issue)
    positive = [i for i, s in enumerate(bm) if s > 0]
    meta = {"candidates": len(docs), "matched": len(positive)}
    if not positive:
        return {}, {}, meta
    total = sum(bm[i] for i in positive)
    restart = {docs[i]["node"]["id"]: bm[i] / total for i in positive}
    mass, used = retriever._walk(ir, restart, damping, WALK_WEIGHTS, include_tests)
    meta["relations_used"] = dict(used)
    meta["mass_total"] = sum(mass.values())
    meta["lexical"] = {docs[i]["node"]["id"]: (bm[i], r + 1) for r, i in enumerate(
        sorted(positive, key=lambda i: (-bm[i], docs[i]["node"]["file"], docs[i]["node"]["line"])))}

    nodes = {n["id"]: n for n in ir["nodes"]}
    keep = {nid for nid, n in nodes.items() if n["kind"] in NODE_KINDS
            and retriever.is_candidate_path(n.get("file", ""), include_tests)}
    callers, importers, contains = _structure(ir, keep)
    memo = {}
    parts, raw = {}, {}
    for nid, m in mass.items():
        if nid not in keep or m <= 0:
            continue
        n = nodes[nid]
        fan_in = _subtree_fan_in(nid, callers, contains, memo)
        file_id = f"file:{n['file']}"
        imp = len(importers.get(file_id, ()))
        boost = min(BOOST_CAP, (1 + math.log(1 + fan_in)) * (1 + math.log(1 + imp)))
        raw[nid] = m * boost
        parts[nid] = {"mass": m, "fan_in": fan_in, "importers": imp}
    top_raw = max(raw.values(), default=0.0) or 1.0
    fn_ids = [nid for nid in raw if nodes[nid]["kind"] in ("function", "method")]
    risks = _risk_by_node(ir, snap, fn_ids)
    scores = {}
    for nid, r in raw.items():
        h = r / top_raw                                     # hub score in [0, 1]
        rc = risks.get(nid, 0)
        scores[nid] = h * (1 + RISK_WEIGHT * min(1.0, rc / RISK_SATURATION))
        parts[nid].update({"hub": h, "risk": rc})
    return scores, parts, meta


# ------------------------------------------------------------------ walk
def depth_for(rel_score):
    if rel_score >= DEPTH_HIGH:
        return 3
    if rel_score >= DEPTH_MID:
        return 2
    return 1


def _adjacency(ir, keep):
    adj = defaultdict(dict)
    for e in ir["edges"]:
        w = WALK_WEIGHTS.get(e["rel"], 0.0)
        if w <= 0 or e["src"] not in keep or e["dst"] not in keep:
            continue
        for a, b in ((e["src"], e["dst"]), (e["dst"], e["src"])):
            if w > adj[a].get(b, (0.0, ""))[0]:
                adj[a][b] = (w, e["rel"])
    return adj


def expand(ir, scores, order, nodes, include_tests=False):
    """Walk outward from the top seeds with dynamic depth. Returns path records."""
    keep = {nid for nid in nodes if nodes[nid]["kind"] in NODE_KINDS
            and retriever.is_candidate_path(nodes[nid].get("file", ""), include_tests)}
    adj = _adjacency(ir, keep)
    seeds = order[:SEED_COUNT]
    top = scores[seeds[0]] if seeds else 0.0
    out = []
    for seed in seeds:
        rel_score = scores[seed] / top if top else 0.0
        depth = depth_for(rel_score)
        floor = PATH_FLOOR * scores[seed]
        seen = {seed}
        frontier = [(seed, 1.0)]
        reached = []
        for hop in range(1, depth + 1):
            nxt = []
            for node, strength in frontier:
                cands = []
                for nb, (w, rel) in adj.get(node, {}).items():
                    if nb in seen:
                        continue
                    s = scores.get(nb, 0.0)
                    if s * strength * w < floor or s <= 0:
                        continue
                    cands.append((-s * w, nodes[nb]["file"], nodes[nb]["line"], nb, rel, w))
                cands.sort()
                for negv, _f, _l, nb, rel, w in cands[:HOP_LIMITS[hop - 1]]:
                    if nb in seen:
                        continue
                    seen.add(nb)
                    reached.append({"hop": hop, "from": node, "id": nb, "via": rel})
                    nxt.append((nb, strength * w))
            frontier = nxt
        out.append({"seed": seed, "depth": depth, "rel_score": rel_score, "reached": reached})
    return out


# ------------------------------------------------------------------ output
def _label(n):
    q = n.get("qualname", n["name"])
    return f"{n['file']}::{q}" if n["kind"] != "file" else n["file"]


def rank(ir, snap, issue, top_n=10, damping=DAMPING, include_tests=False):
    scores, parts, meta = score_nodes(ir, snap, issue, include_tests, damping)
    base = {"method": "vulnerability_walk", "damping": damping, **{
        k: meta[k] for k in ("candidates", "matched", "relations_used") if k in meta}}
    if not scores:
        return {**base, "top": [], "hubs": [], "walk_paths": []}
    nodes = {n["id"]: n for n in ir["nodes"]}
    order = sorted(scores, key=lambda i: (-scores[i], nodes[i]["file"], nodes[i]["line"], i))
    lex = meta["lexical"]

    def rec(nid):
        n, p = nodes[nid], parts[nid]
        r = {"id": nid, "kind": n["kind"], "name": n["name"],
             "qualname": n.get("qualname", n["name"]), "file": n["file"], "line": n["line"],
             "end_line": n.get("end_line"), "score": scores[nid], "hub": p["hub"],
             "mass": p["mass"], "fan_in": p["fan_in"], "importers": p["importers"],
             "risk": p["risk"]}
        if nid in lex:
            r["lexical_score"], r["lexical_rank"] = lex[nid]
        return r

    top = [rec(i) for i in order if nodes[i]["kind"] in ("function", "method")][:top_n]
    hubs = [rec(i) for i in order[:SEED_COUNT]]
    paths = []
    for p in expand(ir, scores, order, nodes, include_tests):
        paths.append({"seed": p["seed"], "depth": p["depth"], "rel_score": p["rel_score"],
                      "reached": [{**r, "score": scores[r["id"]]} for r in p["reached"]]})
    return {**base, "mass_total": meta["mass_total"], "top": top, "hubs": hubs,
            "walk_paths": paths, "_nodes": nodes}


def compact(result, ndigits=4):
    """Agent-facing JSON, trimmed deterministically to OUTPUT_BUDGET chars."""
    nodes = result.get("_nodes", {})

    def r(x):
        return round(x, ndigits)

    sites = [{"rank": i + 1, "file": s["file"], "line": s["line"], "end_line": s["end_line"],
              "qualname": s["qualname"], "score": r(s["score"]), "risk": s["risk"],
              "fan_in": s["fan_in"], "lexical_rank": s.get("lexical_rank")}
             for i, s in enumerate(result["top"])]
    hubs = [{"kind": h["kind"], "at": f"{h['file']}:{h['line']}", "name": h["qualname"],
             "hub": r(h["hub"]), "fan_in": h["fan_in"], "importers": h["importers"]}
            for h in result["hubs"]]
    paths = []
    for p in result["walk_paths"]:
        seed = nodes[p["seed"]]
        steps = [f"h{x['hop']} {x['via']} {_label(nodes[x['id']])}:{nodes[x['id']]['line']}"
                 for x in p["reached"]]
        paths.append({"seed": _label(seed), "depth": p["depth"], "reach": steps})
    out = {"method": result["method"], "candidates": result.get("candidates"),
           "matched": result.get("matched"), "top_edit_sites": sites, "hubs": hubs,
           "walk_paths": paths}
    # Trim in a fixed order until the JSON fits the tool-output cap.
    def size():
        return len(json.dumps(out, separators=(",", ":")))
    while size() > OUTPUT_BUDGET:
        longest = max(paths, key=lambda p: len(p["reach"]), default=None)
        if longest and len(longest["reach"]) > 1:
            longest["reach"].pop()
        elif len(out["top_edit_sites"]) > 5:
            out["top_edit_sites"].pop()
        elif paths:
            paths.pop()
        else:
            break
    return out
