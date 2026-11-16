"""Phase 4: SemDAG (in-sandbox rebuilt graph) vs the shipped graph, CPU only.

For each public task: extract the snapshot's .py files, build the SemDAG IR with
the UNMODIFIED semdag modules, and score repo_eval's localization ranking
against the gold edit functions of `patch`. `hints_text` and `test_patch` are
never read. `patch` is used for scoring only.

Gold edit site: the innermost function/method (pre-patch source, stdlib ast)
containing a deleted line; for pure-insertion hunks, the innermost function
containing BOTH old-side neighbours of the insertion. Anything else (new files,
module/class-level inserts, non-.py) is file-level gold only.

Arms (all ranked lists of SemDAG function/method nodes):
  A  repo_eval as shipped: PPR on the reversed call graph, seeded by issue
     symbols, taint seed blended at 0.25
  B  same, taint blend off
  S  seed nodes only, issue order
  SC seeds, then containment closure (methods of a class named in the issue;
     siblings of a seeded method)
Shipped graph (sets, not ranked): Z seeds, ZP seeds+outline, C one call hop.
"""
from __future__ import annotations

import ast
import json
import os
import random
import shutil
import sys
import tarfile
import tempfile
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = Path(os.environ.get("P4_DATA", ROOT / "DataSets/public/data"))
# SEMDAG: the graph-first system exactly as first shipped (frozen copy, audited in the paper).
# PROD: the repaired production code, the same files the v4_semdag skill ships.
SEMDAG = Path(os.environ.get("P4_SEMDAG_LEGACY", HERE / "legacy_semdag"))
PROD = Path(os.environ.get("P4_SEMDAG", ROOT / "AgenticSubmission/v4_semdag/skills/semdag/scripts"))
PHASE1 = Path(os.environ.get("P4_PHASE1", HERE.parent / "phase1"))
OUT = Path(os.environ.get("P4_OUT", HERE / "out"))
os.environ.setdefault("P4_SCRATCH", tempfile.gettempdir())
KS = (1, 5, 10)
DEPTH = 50
SKIP_PARTS = {".git", "node_modules", ".venv", "venv", "__pycache__", "site-packages"}


def is_test_path(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    return (any(p in ("tests", "test", "testing") for p in parts[:-1])
            or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py")


def parse_patch(patch: str):
    """Yield (path, is_new_file, hunks); hunk = list of (tag, old_lineno)."""
    files, cur, old = [], None, 0
    lines = patch.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("--- "):
            a = ln[4:].strip()
            b = lines[i + 1][4:].strip() if i + 1 < len(lines) else ""
            path = b[2:] if b.startswith("b/") else b
            cur = {"path": path, "new": a == "/dev/null", "hunks": []}
            files.append(cur)
            i += 2
            continue
        if ln.startswith("@@") and cur is not None:
            try:
                old = int(ln.split()[1].split(",")[0][1:])
            except Exception:
                old = 1
            cur["hunks"].append([])
        elif cur is not None and cur["hunks"]:
            if ln.startswith("-"):
                cur["hunks"][-1].append(("-", old)); old += 1
            elif ln.startswith("+"):
                cur["hunks"][-1].append(("+", old))  # old = line AFTER the insert point
            elif ln.startswith(" ") or ln == "":
                cur["hunks"][-1].append((" ", old)); old += 1
        i += 1
    return files


def func_spans(src: str):
    """[(start, end, qualname, def_lineno, is_async)] for every def."""
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, ast.ClassDef):
                walk(ch, prefix + [ch.name])
            elif isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([ch.lineno] + [d.lineno for d in ch.decorator_list])
                out.append((start, ch.end_lineno, ".".join(prefix + [ch.name]),
                            ch.lineno, isinstance(ch, ast.AsyncFunctionDef)))
                walk(ch, prefix + [ch.name])
            else:
                walk(ch, prefix)
    walk(tree, [])
    return out


def innermost(spans, line):
    best = None
    for s in spans:
        if s[0] <= line <= s[1] and (best is None or s[0] >= best[0]):
            best = s
    return best


def gold_sites(patch: str, repo_dir: str):
    gold, gold_files, n_hunks, n_aligned = {}, set(), 0, 0
    for f in parse_patch(patch):
        if not f["path"].endswith(".py"):
            continue
        fp = os.path.join(repo_dir, f["path"])
        if f["new"] or not os.path.isfile(fp):
            n_hunks += len(f["hunks"])
            continue
        gold_files.add(f["path"])
        spans = func_spans(open(fp, errors="replace").read())
        for h in f["hunks"]:
            n_hunks += 1
            dels = [o for t, o in h if t == "-"]
            hit = set()
            if dels:
                for o in dels:
                    s = innermost(spans, o)
                    if s:
                        hit.add(s)
            else:
                for o in {o for t, o in h if t == "+"}:
                    a, b = innermost(spans, o - 1), innermost(spans, o)
                    if a and b and a == b:
                        hit.add(a)
            if hit:
                n_aligned += 1
            for s in hit:
                gold[(f["path"], s[3])] = {"file": f["path"], "qual": s[2],
                                           "line": s[3], "async": s[4]}
    return gold, gold_files, n_hunks, n_aligned


def extract_py(tgz: Path, dest: str):
    with tarfile.open(tgz) as tf:
        members = []
        for m in tf:
            if not m.isfile() or not m.name.endswith(".py"):
                continue
            parts = Path(m.name).parts
            if any(p in SKIP_PARTS for p in parts):
                continue
            members.append(m)
        tf.extractall(dest, members=members, filter="data")


def shipped_arms(task, gold):
    """Set-based arms on the shipped graph, via the Phase 1 loader."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("phase1_measure", PHASE1 / "measure.py")
    p1 = importlib.util.module_from_spec(spec); sys.modules["phase1_measure"] = p1; spec.loader.exec_module(p1)
    short = task["repo"].split("/")[-1]
    gp = DATA / "graphs" / f"{short}_{task['base_commit']}.json"
    ep = DATA / "embeddings" / f"{short}_{task['base_commit']}.npz"
    if not gp.exists() or gp.stat().st_size == 0:
        return None
    g = p1.Graph(gp, ep)

    def to_ids(site):
        dotted = site["file"][:-3].replace("/", ".") + "." + site["qual"]
        return {i for i in g.ids if i == dotted or dotted.endswith("." + i) and i.count(".") >= 1
                and i.endswith(site["qual"])}
    gold_ids = {k: to_ids(v) for k, v in gold.items()}
    seeds = p1.resolve_seeds(g, task["problem_statement"])
    z = set(seeds)
    p = set()
    for s in seeds:
        if g.kind[s] == "class":
            p.update(g.children.get(s, []))
        elif g.parent.get(s):
            p.update(g.children.get(g.parent[s], []))
    p -= z
    c = set()
    for s in seeds:
        c.update(g.callers.get(s, [])); c.update(g.callees.get(s, []))

    def hit(nodes):
        return any(ids & nodes for ids in gold_ids.values())
    return {"nodes": len(g.ids),
            "gold_present": sum(1 for ids in gold_ids.values() if ids),
            "gold_present_async": sum(1 for k, ids in gold_ids.items() if ids and gold[k]["async"]),
            "Z": {"hit": hit(z), "size": len(z)},
            "ZP": {"hit": hit(z | p), "size": len(z | p)},
            "C": {"hit": hit(c), "size": len(c)}}


def run_task(task):
    iid = task["instance_id"]
    tmp = tempfile.mkdtemp(prefix=f"p4_{iid}_", dir=os.environ["P4_SCRATCH"])
    os.environ["SEMDAG_CACHE"] = os.path.join(tmp, "_cache")
    repo = os.path.join(tmp, "repo")
    try:
        extract_py(DATA / "snapshots" / f"{iid}.tgz", repo)
        gold, gold_files, n_hunks, n_aligned = gold_sites(task["patch"], repo)

        sys.path.insert(0, str(SEMDAG))
        import cache, snapshot, semdag_ir_ast, taint, repo_eval
        from ppr_scorer import PurePythonPPRScorer
        cache.init_container(iid, repo)
        snap = snapshot.snapshot(iid, repo)
        ir = semdag_ir_ast.build(iid)
        par = repo_eval.parity_check(iid, snap, ir)
        tnt = taint.build(iid)
        sc = PurePythonPPRScorer(ir, tnt)
        syms = repo_eval.problem_symbols(task["problem_statement"])

        funcs = [n for n in sc.nodes if sc.kind.get(n) in ("function", "method")]
        key = {n: (sc.meta[n]["file"], sc.meta[n]["line"]) for n in funcs}
        node_keys = set(key.values())

        nontest = {n for n in funcs if not is_test_path(sc.meta[n]["file"])}
        diag = {}

        def ppr_rank(seed, tag=None):
            """Same ordering as PurePythonPPRScorer.score, without evidence columns.
            Returns (as shipped: all functions, same ranking restricted to non-test functions)."""
            tot = sum(seed.values()) or 1.0
            ppr = sc._ppr({k: v / tot for k, v in seed.items()})
            tp = sum(ppr.get(n, 0.0) for n in funcs) or 1.0
            rows = sorted(((-round(ppr.get(n, 0.0) / tp, 6), n) for n in funcs))
            if tag:
                allmass = sum(ppr.values()) or 1.0
                diag[tag] = {"mass_on_functions": round(tp / allmass, 4),
                             "mass_on_test_functions": round(sum(ppr.get(n, 0.0) for n in funcs if n not in nontest) / allmass, 4),
                             "mass_on_extern_or_ambiguous": round(sum(v for n, v in ppr.items() if sc.kind.get(n) in ("extern", "ambiguous")) / allmass, 4),
                             "test_fns_in_top10": sum(1 for _, n in rows[:10] if n not in nontest),
                             "test_fns_in_top5": sum(1 for _, n in rows[:5] if n not in nontest),
                             "tied_at_rank5": bool(len(rows) > 5 and rows[4][0] == rows[5][0])}
            return [n for _, n in rows[:DEPTH]], [n for _, n in rows if n in nontest][:DEPTH]

        seed_nodes = sc.names_to_nodes(syms)
        tseed = tnt.get("seed", {})
        sa = defaultdict(float)
        for n in seed_nodes:
            sa[n] += 1.0
        for n, w in tseed.items():
            sa[n] += 0.25 * w
        if not sa:
            sa = dict(tseed)
        sb = defaultdict(float)
        for n in seed_nodes:
            sb[n] += 1.0

        # containment from the IR's `contains` edges
        kids, parent = defaultdict(list), {}
        for e in ir["edges"]:
            if e["rel"] == "contains":
                kids[e["src"]].append(e["dst"]); parent[e["dst"]] = e["src"]
        cls_by_name = defaultdict(list)
        for n in ir["nodes"]:
            if n["kind"] == "class":
                cls_by_name[n["name"]].append(n["id"])
        s_list, seen = [], set()
        for n in seed_nodes:
            if n not in seen:
                seen.add(n); s_list.append(n)
        sc_list = list(s_list); seen2 = set(sc_list)
        for sym in syms:
            for cid in cls_by_name.get(sym, []):
                for k in kids.get(cid, []):
                    if k in key and k not in seen2:
                        seen2.add(k); sc_list.append(k)
        for n in s_list:
            p = parent.get(n)
            if p and sc.kind.get(p) == "class":
                for k in kids.get(p, []):
                    if k in key and k not in seen2:
                        seen2.add(k); sc_list.append(k)

        a_all, a_nt = ppr_rank(dict(sa), "A") if sa else ([], [])
        b_all, b_nt = ppr_rank(dict(sb), "B") if sb else ([], [])
        arms = {"A": a_all, "B": b_all, "S": s_list, "SC": sc_list,
                "Af": a_nt, "Bf": b_nt,
                "Sf": [n for n in s_list if n in nontest], "SCf": [n for n in sc_list if n in nontest]}
        n_edges = Counter(e["rel"] for e in ir["edges"])
        gkeys = set(gold)
        res = {}
        for name, lst in arms.items():
            keys = [key[n] for n in lst]
            files, sf = [], set()
            for f, _ in keys:
                if f not in sf:
                    sf.add(f); files.append(f)
            first = next((i + 1 for i, k in enumerate(keys) if k in gkeys), None)
            ffirst = next((i + 1 for i, f in enumerate(files) if f in gold_files), None)
            res[name] = {"n": len(lst), "first_fn": first, "first_file": ffirst}
        row = {"instance_id": iid, "repo": task["repo"], "parity_ok": par["ok"],
               "ir": ir["counts"], "n_funcs": len(funcs), "n_syms": len(syms),
               "n_seed_nodes": len(s_list), "n_seed_nodes_nontest": sum(1 for n in s_list if n in nontest),
               "n_funcs_nontest": len(nontest), "ppr_diag": diag, "ir_edges_by_rel": dict(n_edges),
               "hunks": n_hunks, "hunks_aligned": n_aligned,
               "gold": list(gold.values()), "gold_files": sorted(gold_files),
               "gold_in_semdag": sum(1 for k in gkeys if k in node_keys),
               "gold_async": sum(1 for v in gold.values() if v["async"]),
               "arms": res}
        try:
            row["shipped"] = shipped_arms(task, gold)
        except Exception as ex:  # report, never hide
            row["shipped"] = {"error": repr(ex)}
        return row
    except Exception as ex:
        return {"instance_id": iid, "repo": task["repo"], "error": repr(ex)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def summarize(rows):
    ok = [r for r in rows if "error" not in r]
    ev = [r for r in ok if r["gold"]]            # function-level evaluable
    evf = [r for r in ok if r["gold_files"]]     # file-level evaluable
    out = {"tasks": len(rows), "errors": [r["instance_id"] for r in rows if "error" in r],
           "parity_ok": sum(r["parity_ok"] for r in ok),
           "fn_evaluable": len(ev), "file_evaluable": len(evf),
           "hunks": sum(r["hunks"] for r in ok), "hunks_aligned": sum(r["hunks_aligned"] for r in ok),
           "gold_fns": sum(len(r["gold"]) for r in ev),
           "gold_in_semdag": sum(r["gold_in_semdag"] for r in ev),
           "gold_async": sum(r["gold_async"] for r in ev),
           "tasks_with_async_gold": sum(1 for r in ev if r["gold_async"]),
           "no_seed_tasks": sum(1 for r in ev if r["n_seed_nodes"] == 0)}
    sh = [r for r in ev if r.get("shipped") and "error" not in r["shipped"]]
    out["shipped"] = {"tasks": len(sh),
                      "gold_fns": sum(len(r["gold"]) for r in sh),
                      "gold_present": sum(r["shipped"]["gold_present"] for r in sh),
                      "gold_async": sum(r["gold_async"] for r in sh),
                      "gold_present_async": sum(r["shipped"]["gold_present_async"] for r in sh)}
    for a in ("Z", "ZP", "C"):
        out["shipped"][a] = {"hit": sum(r["shipped"][a]["hit"] for r in sh),
                             "mean_size": round(sum(r["shipped"][a]["size"] for r in sh) / max(1, len(sh)), 2)}
    out["arms"] = {}
    for a in ("A", "B", "S", "SC", "Af", "Bf", "Sf", "SCf"):
        d = {"mean_len": round(sum(r["arms"][a]["n"] for r in ev) / max(1, len(ev)), 2)}
        for k in KS:
            d[f"fn_hit@{k}"] = sum(1 for r in ev if (r["arms"][a]["first_fn"] or 99) <= k)
            d[f"file_hit@{k}"] = sum(1 for r in evf if (r["arms"][a]["first_file"] or 99) <= k)
        d["fn_hit@any"] = sum(1 for r in ev if r["arms"][a]["first_fn"])
        out["arms"][a] = d
    rng = random.Random(0)

    def boot(x, y, k=5):
        diffs = []
        for _ in range(4000):
            s = [ev[rng.randrange(len(ev))] for _ in ev]
            diffs.append(sum(((r["arms"][x]["first_fn"] or 99) <= k) - ((r["arms"][y]["first_fn"] or 99) <= k)
                             for r in s) / len(s))
        diffs.sort()
        pt = sum(((r["arms"][x]["first_fn"] or 99) <= k) - ((r["arms"][y]["first_fn"] or 99) <= k)
                 for r in ev) / len(ev)
        return {"diff": round(pt, 4), "ci95": [round(diffs[100], 4), round(diffs[3899], 4)]}
    if ev:
        out["contrasts_fn_hit@5"] = {"B-A": boot("B", "A"), "S-A": boot("S", "A"),
                                     "SC-S": boot("SC", "S"), "SC-B": boot("SC", "B")}
    by = defaultdict(list)
    for r in ev:
        by[r["repo"]].append(r)
    out["by_repo"] = {repo: {"n": len(rs), **{a: sum(1 for r in rs if (r["arms"][a]["first_fn"] or 99) <= 5)
                                              for a in ("A", "B", "S", "SC")}} for repo, rs in by.items()}
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in open(DATA / "tasks.jsonl")]
    for t in tasks:
        t.pop("hints_text", None); t.pop("test_patch", None)
    if len(sys.argv) > 1:
        tasks = [t for t in tasks if t["instance_id"] in sys.argv[1:]]
    with Pool(int(os.environ.get("P4_PROCS", "6"))) as pool:
        rows = pool.map(run_task, tasks, chunksize=1)
    with open(OUT / "per_task.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    s = summarize(rows)
    json.dump(s, open(OUT / "summary.json", "w"), indent=1, sort_keys=True)
    print(json.dumps(s, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
