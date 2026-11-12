"""Phase 4c: an improved localizer on the rebuilt graph (SemDAG-L2).

Same gold definition and data handling as measure.py. `hints_text` and
`test_patch` are never read; `patch` is scoring only.

Fixed design choices (set before any score was read; none tuned on gold):
  - candidates: functions/methods outside test files (tests/ dirs, test_*.py,
    *_test.py, conftest.py)
  - N   name seeds: `Class.method` dotted mentions, bare function names, then
        methods of classes named in the issue, then functions of files named
        in the issue (path or module mention)
  - X   BM25 (k1=1.2, b=0.75) over function documents: identifier tokens of the
        body, with qualname and file-path tokens repeated 3x
  - G   Personalized PageRank (d=0.85, 40 iters) on the UNDIRECTED calls+contains
        graph, seeded by name seeds (1.0 each) plus the BM25 top-20 (normalised)
  - fusion: reciprocal rank fusion, k=60
Arms: N, X, NX = RRF(N,X), NXG = RRF(N,X,G).
Selection: the arm with the highest function Hit@5 on FastAPI+Requests+httpx.
Rich is held out and printed, not used to choose.
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure as m1  # noqa: E402

OUT = m1.OUT
ARMS = ("N", "X", "NX", "NXG", "XF", "EX", "D15", "D30", "D50", "D85", "DC85")
KS = (1, 5, 10)
DEPTH = 50
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
DOTTED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
PATHISH = re.compile(r"[A-Za-z0-9_\-./]+\.py")
CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
STOP = {"the", "and", "for", "that", "this", "with", "not", "but", "are", "was", "from", "have",
        "has", "when", "you", "can", "should", "would", "will", "use", "using", "def", "self",
        "return", "import", "none", "true", "false", "class", "if", "else", "in", "is", "of",
        "to", "it", "as", "on", "be", "or", "an", "at", "by", "we"}


def is_test_path(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    return (any(p in ("tests", "test", "testing") for p in parts[:-1])
            or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py")


def toks(text: str):
    out = []
    for ident in IDENT.findall(text):
        low = ident.lower()
        if len(low) >= 2 and low not in STOP:
            out.append(low)
        parts = [p.lower() for chunk in ident.split("_") for p in CAMEL.findall(chunk)]
        if len(parts) > 1:
            out.extend(p for p in parts if len(p) >= 2 and p not in STOP)
    return out


def rrf(lists, k=60):
    score = defaultdict(float)
    for lst in lists:
        for i, x in enumerate(lst):
            score[x] += 1.0 / (k + i + 1)
    return [x for x, _ in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))]


def run_task(task):
    iid = task["instance_id"]
    tmp = tempfile.mkdtemp(prefix=f"p4b_{iid}_", dir=os.environ["P4_SCRATCH"])
    repo = os.path.join(tmp, "repo")
    try:
        m1.extract_py(m1.DATA / "snapshots" / f"{iid}.tgz", repo)
        gold, gold_files, _, _ = m1.gold_sites(task["patch"], repo)
        issue = task["problem_statement"]

        # ---- function table straight from source (stdlib ast) ----
        funcs = []  # dict(key, file, qual, name, cls, start, end, doc_tokens)
        by_file = defaultdict(list)
        for root, _, names in os.walk(repo):
            for nm in sorted(names):
                if not nm.endswith(".py"):
                    continue
                fp = os.path.join(root, nm)
                rel = os.path.relpath(fp, repo)
                if is_test_path(rel) and not os.environ.get("P4_KEEP_TESTS"):
                    continue
                src = open(fp, errors="replace").read()
                lines = src.splitlines()
                for start, end, qual, defline, _async in m1.func_spans(src):
                    body = "\n".join(lines[start - 1:end])
                    head = " ".join([qual.replace(".", " "), rel.replace("/", " ").replace(".py", "")])
                    doc = toks(body) + toks(head) * 3
                    f = {"key": (rel, defline), "file": rel, "qual": qual,
                         "name": qual.rsplit(".", 1)[-1],
                         "cls": qual.rsplit(".", 1)[0] if "." in qual else None,
                         "start": start, "end": end, "doc": Counter(doc), "len": len(doc)}
                    by_file[rel].append(len(funcs)); funcs.append(f)
        n = len(funcs)
        if n == 0:
            return {"instance_id": iid, "repo": task["repo"], "error": "no functions"}
        by_name, by_qual_suffix, by_cls = defaultdict(list), defaultdict(list), defaultdict(list)
        for i, f in enumerate(funcs):
            by_name[f["name"]].append(i)
            parts = f["qual"].split(".")
            if len(parts) >= 2:
                by_qual_suffix[".".join(parts[-2:])].append(i)
                by_cls[parts[-2]].append(i)

        # ---- N: name seeds ----
        N, seen = [], set()

        def push(idxs):
            for i in idxs:
                if i not in seen:
                    seen.add(i); N.append(i)
        dotted = DOTTED.findall(issue)
        idents = list(dict.fromkeys(IDENT.findall(issue)))
        for d in dotted:
            parts = d.split(".")
            if len(parts) >= 2:
                push(by_qual_suffix.get(".".join(parts[-2:]), []))
        for w in idents:
            if len(w) >= 3 and len(by_name.get(w, [])) <= 20:
                push(by_name.get(w, []))
        for w in idents:
            if len(w) >= 3 and w[:1].isupper() and len(by_cls.get(w, [])) <= 60:
                push(by_cls.get(w, []))
        mentioned_files = set()
        for p in PATHISH.findall(issue):
            p = p.lstrip("./")
            for rel in by_file:
                if rel == p or rel.endswith("/" + p):
                    mentioned_files.add(rel)
        for d in dotted:
            p = d.replace(".", "/")
            for rel in by_file:
                stem = rel[:-3]
                if stem == p or stem.endswith("/" + p) or p.endswith("/" + stem.split("/")[-1]) and stem.endswith(p.split("/")[-2] + "/" + stem.split("/")[-1]) if "/" in p else False:
                    mentioned_files.add(rel)
        for rel in sorted(mentioned_files):
            push(by_file[rel])

        # ---- X: BM25 ----
        df = Counter()
        for f in funcs:
            df.update(f["doc"].keys())
        avg = sum(f["len"] for f in funcs) / n
        q = Counter(toks(issue))
        scores = [0.0] * n
        for term, qtf in q.items():
            d = df.get(term)
            if not d:
                continue
            idf = math.log(1 + (n - d + 0.5) / (d + 0.5))
            w = idf * min(qtf, 3)
            for i, f in enumerate(funcs):
                tf = f["doc"].get(term)
                if tf:
                    scores[i] += w * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * f["len"] / avg))
        order = sorted(range(n), key=lambda i: (-scores[i], funcs[i]["key"]))
        X = [i for i in order if scores[i] > 0][:200]

        # ---- G: PPR on undirected calls+contains ----
        adj = defaultdict(set)
        for idxs in by_cls.values():           # contains: methods of one class (same file)
            groups = defaultdict(list)
            for i in idxs:
                groups[(funcs[i]["file"], funcs[i]["cls"])].append(i)
            for g in groups.values():
                if len(g) <= 80:
                    for a in g:
                        adj[a].update(x for x in g if x != a)
        call_re = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")
        for i, f in enumerate(funcs):          # calls: uniquely resolvable bare names only
            for nm in set(f["doc"].keys()):
                pass
        # cheap call edges from the system's own IR resolution policy: unique global name
        name_unique = {nm: idxs[0] for nm, idxs in by_name.items() if len(idxs) == 1}
        src_cache = {}
        for i, f in enumerate(funcs):
            if f["file"] not in src_cache:
                src_cache[f["file"]] = open(os.path.join(repo, f["file"]), errors="replace").read().splitlines()
            body = "\n".join(src_cache[f["file"]][f["start"] - 1:f["end"]])
            for nm in set(call_re.findall(body)):
                j = name_unique.get(nm)
                if j is not None and j != i:
                    adj[i].add(j); adj[j].add(i)
        seed = defaultdict(float)
        for i in N[:50]:
            seed[i] += 1.0
        top = X[:20]
        if top:
            mx = scores[top[0]] or 1.0
            for i in top:
                seed[i] += scores[i] / mx
        G = []
        if seed:
            tot = sum(seed.values())
            p = {i: v / tot for i, v in seed.items()}
            r = dict(p)
            for _ in range(40):
                nxt = defaultdict(float)
                for i, v in r.items():
                    nb = adj.get(i)
                    if nb:
                        share = 0.85 * v / len(nb)
                        for j in nb:
                            nxt[j] += share
                    else:
                        for j, pv in p.items():
                            nxt[j] += 0.85 * v * pv
                for j, pv in p.items():
                    nxt[j] += 0.15 * pv
                r = nxt
            G = [i for i, _ in sorted(r.items(), key=lambda kv: (-kv[1], funcs[kv[0]]["key"]))][:200]

        # ---- XF: fuse function BM25 with a file-level BM25 ordering ----
        fdoc = {rel: Counter() for rel in by_file}
        for f in funcs:
            fdoc[f["file"]].update(f["doc"])
        fn_files = len(fdoc)
        fdf = Counter()
        for c in fdoc.values():
            fdf.update(c.keys())
        flen = {rel: sum(c.values()) for rel, c in fdoc.items()}
        favg = sum(flen.values()) / max(1, fn_files)
        fscore = defaultdict(float)
        for term, qtf in q.items():
            d = fdf.get(term)
            if not d:
                continue
            idf = math.log(1 + (fn_files - d + 0.5) / (d + 0.5))
            for rel, c in fdoc.items():
                tf = c.get(term)
                if tf:
                    fscore[rel] += idf * min(qtf, 3) * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * flen[rel] / favg))
        file_order = sorted(fdoc, key=lambda rel: (-fscore[rel], rel))
        frank = {rel: i for i, rel in enumerate(file_order)}
        FO = sorted(X, key=lambda i: (frank[funcs[i]["file"]], -scores[i], funcs[i]["key"]))
        XF = rrf([X, FO])

        # ---- EX: explicit code-style mentions first, then BM25 ----
        codeish = set(re.findall(r"`([^`\n]+)`", issue))
        ex_names = set()
        for c in codeish:
            ex_names.update(IDENT.findall(c))
        ex_names.update(re.findall(r"([A-Za-z_][A-Za-z0-9_]{2,})\s*\(", issue))
        ex_names.update(re.findall(r"\.([A-Za-z_][A-Za-z0-9_]{2,})", issue))
        E = [i for i in X if funcs[i]["name"] in ex_names and len(by_name[funcs[i]["name"]]) <= 3]
        eset = set(E)
        EX = E + [i for i in X if i not in eset]

        # ---- D: production retriever, shared byte-for-byte with repo_eval ----
        os.environ["SEMDAG_CACHE"] = os.path.join(tmp, "_cache")
        sys.path.insert(0, str(m1.PROD))
        import cache as _cache, snapshot as _snapshot, semdag_ir_ast as _irmod, retriever as _retriever
        _cache.init_container(iid, repo)
        snap = _snapshot.snapshot(iid, repo)
        ir = _irmod.build(iid)
        idx_of = {f["key"]: i for i, f in enumerate(funcs)}
        node_to_idx = {nd["id"]: idx_of[(nd["file"], nd["line"])] for nd in ir["nodes"]
                       if nd["kind"] in ("function", "method") and (nd["file"], nd["line"]) in idx_of}

        def production_order(damping, weights=None, direction="undirected"):
            result = _retriever.rank(ir, snap, issue, 200, damping=damping,
                                     include_tests=bool(os.environ.get("P4_KEEP_TESTS")),
                                     relation_weights=weights, direction=direction)
            return [node_to_idx[s["id"]] for s in result["top"] if s["id"] in node_to_idx], result

        shared_x, x_receipt = production_order(0.0)
        # With tests kept, the production snapshot omits files over 256 KB (large test modules),
        # so the candidate sets differ and the identity is only asserted in the default mode.
        if not os.environ.get("P4_KEEP_TESTS") and \
                [funcs[i]["key"] for i in shared_x] != [funcs[i]["key"] for i in X]:
            raise AssertionError("measurement BM25 diverged from production retriever")
        D, d_receipts = {}, {}
        for damping in (0.15, 0.30, 0.50, 0.85):
            name = f"D{int(damping * 100)}"
            D[name], d_receipts[name] = production_order(damping)
        D["DC85"], d_receipts["DC85"] = production_order(
            0.85, {"contains": 0.0, "calls": 1.0, "imports": 0.0}, "reverse_calls")

        lists = {"N": N, "X": X, "NX": rrf([N, X]), "NXG": rrf([N, X, G]), "XF": XF, "EX": EX, **D}

        # ---- control: the same BM25 over the SHIPPED graph's node texts ----
        shipped = None
        try:
            def is_func(text):
                for line in text.splitlines():
                    st = line.lstrip()
                    if not st or st.startswith("@"):
                        continue
                    return not st.startswith("class ")
                return True
            short = task["repo"].split("/")[-1]
            gp = m1.DATA / "graphs" / f"{short}_{task['base_commit']}.json"
            raw = json.loads(gp.read_text())
            snodes = [(nd["id"], nd.get("text") or "") for nd in raw["nodes"]]
            snodes = [(i, t) for i, t in snodes
                      if not (i.startswith(("tests.", "test.")) or ".tests." in i or ".test_" in i
                              or i.split(".")[-1].startswith("test_") or "conftest" in i)
                      and is_func(t)]
            sdocs = [Counter(toks(t) + toks(i.replace(".", " ")) * 3) for i, t in snodes]
            sn = len(sdocs)
            sdf = Counter()
            for c in sdocs:
                sdf.update(c.keys())
            slen = [sum(c.values()) for c in sdocs]
            savg = sum(slen) / max(1, sn)
            ssc = [0.0] * sn
            for term, qtf in q.items():
                d = sdf.get(term)
                if not d:
                    continue
                idf = math.log(1 + (sn - d + 0.5) / (d + 0.5))
                for j, c in enumerate(sdocs):
                    tf = c.get(term)
                    if tf:
                        ssc[j] += idf * min(qtf, 3) * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * slen[j] / savg))
            sorder = [j for j in sorted(range(sn), key=lambda j: (-ssc[j], snodes[j][0])) if ssc[j] > 0][:DEPTH]
            ids = [snodes[j][0] for j in sorder]
            gold_ids = set()
            for site in gold.values():
                dotted = site["file"][:-3].replace("/", ".") + "." + site["qual"]
                gold_ids.update(i for i, _ in snodes if i == dotted or (dotted.endswith("." + i) and i.endswith(site["qual"]) and "." in i))
            shipped = {"candidates": sn, "gold_ids": len(gold_ids),
                       "first_fn": next((r + 1 for r, i in enumerate(ids) if i in gold_ids), None)}
        except Exception as ex:
            shipped = {"error": repr(ex)}
        gkeys = set(gold)
        res = {}
        for name, lst in lists.items():
            lst = lst[:DEPTH]
            keys = [funcs[i]["key"] for i in lst]
            files, sf = [], set()
            for fkey, _ in keys:
                if fkey not in sf:
                    sf.add(fkey); files.append(fkey)
            res[name] = {"n": len(lst),
                         "first_fn": next((i + 1 for i, k in enumerate(keys) if k in gkeys), None),
                         "first_file": next((i + 1 for i, f in enumerate(files) if f in gold_files), None),
                         "top5": [f"{funcs[i]['file']}::{funcs[i]['qual']}" for i in lst[:5]]}
        cand_keys = {f["key"] for f in funcs}
        return {"instance_id": iid, "repo": task["repo"], "n_candidates": n,
                "gold_n": len(gkeys), "gold_in_candidates": sum(1 for k in gkeys if k in cand_keys),
                "gold_files": len(gold_files),
                "gold_test_only": bool(gkeys) and not any(k in cand_keys for k in gkeys),
                "async_gold": any(v["async"] for v in gold.values()),
                "dag": {"nodes": ir["counts"]["nodes"], "fn_nodes": len(node_to_idx),
                        "edges": {k: ir["counts"].get(k, 0) for k in ("contains", "calls", "imports")},
                        "production_receipts": {k: {"damping": v["damping"],
                                                     "relations_used": v["relations_used"]}
                                                for k, v in d_receipts.items()}},
                "shipped_bm25": shipped, "arms": res}
    except Exception as ex:
        import traceback
        return {"instance_id": iid, "repo": task["repo"], "error": repr(ex), "tb": traceback.format_exc()[-600:]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def hit(r, arm, k, level="fn"):
    return ((r["arms"][arm][f"first_{level}"] or 10 ** 6) <= k)


def table(rows, arms):
    ev = [r for r in rows if r["gold_n"]]
    evf = [r for r in rows if r["gold_files"]]
    out = {"fn_tasks": len(ev), "file_tasks": len(evf)}
    for a in arms:
        d = {}
        for k in KS:
            d[f"fn@{k}"] = sum(hit(r, a, k) for r in ev)
            d[f"file@{k}"] = sum(hit(r, a, k, "file") for r in evf)
        d["mrr_fn"] = round(sum(1.0 / r["arms"][a]["first_fn"] for r in ev if r["arms"][a]["first_fn"]) / max(1, len(ev)), 4)
        out[a] = d
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in open(m1.DATA / "tasks.jsonl")]
    for t in tasks:
        t.pop("hints_text", None); t.pop("test_patch", None)
    if len(sys.argv) > 1:
        tasks = [t for t in tasks if t["instance_id"] in sys.argv[1:]]
    with Pool(int(os.environ.get("P4_PROCS", "6"))) as pool:
        rows = pool.map(run_task, tasks, chunksize=1)
    with open(OUT / "v2_per_task.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    errs = [r for r in rows if "error" in r]
    ok = [r for r in rows if "error" not in r]
    # join the shipped-system arm A from measure.py for paired contrasts
    base = {}
    p1 = OUT / "per_task.jsonl"
    if p1.exists():
        for l in open(p1):
            r = json.loads(l)
            if "arms" in r:
                base[r["instance_id"]] = r["arms"]["A"]
    for r in ok:
        if r["instance_id"] in base:
            r["arms"]["A"] = base[r["instance_id"]]
    arms = ARMS + (("A",) if all("A" in r["arms"] for r in ok) else ())
    sel = [r for r in ok if not r["repo"].endswith("rich")]
    held = [r for r in ok if r["repo"].endswith("rich")]
    s = {"tasks": len(rows), "errors": [(r["instance_id"], r["error"]) for r in errs],
         "gold_fns": sum(r["gold_n"] for r in ok),
         "gold_in_candidates": sum(r["gold_in_candidates"] for r in ok),
         "tasks_gold_only_in_tests": sum(1 for r in ok if r["gold_test_only"]),
         "median_candidates": sorted(r["n_candidates"] for r in ok)[len(ok) // 2] if ok else 0,
         "selection": table(sel, arms), "heldout_rich": table(held, arms), "all": table(ok, arms)}
    def ship(pool):
        ev = [r for r in pool if r["gold_n"]]
        ok_ = [r for r in ev if r["shipped_bm25"] and "error" not in r["shipped_bm25"]]
        return {"tasks": len(ev), "scored": len(ok_),
                **{f"fn@{k}": sum(1 for r in ok_ if (r["shipped_bm25"]["first_fn"] or 10 ** 6) <= k) for k in KS}}
    s["shipped_bm25"] = {"selection": ship(sel), "heldout_rich": ship(held), "all": ship(ok)}
    asy = [r for r in ok if r.get("async_gold")]
    s["async_gold_tasks"] = {"n": len(asy), **{a: [sum(hit(r, a, k) for r in asy) for k in KS] for a in arms},
                             "shipped_bm25": [sum(1 for r in asy if r["shipped_bm25"] and (r["shipped_bm25"].get("first_fn") or 10 ** 6) <= k) for k in KS]}
    sel_ev = [r for r in sel if r["gold_n"]]
    s["winner"] = max(ARMS, key=lambda a: (sum(hit(r, a, 5) for r in sel_ev), -ARMS.index(a)))
    rng = random.Random(0)

    def boot(pool, x, y, k):
        ev = [r for r in pool if r["gold_n"]]
        if not ev or y not in ev[0]["arms"]:
            return None
        pt = sum(hit(r, x, k) - hit(r, y, k) for r in ev) / len(ev)
        ds = []
        for _ in range(4000):
            smp = [ev[rng.randrange(len(ev))] for _ in ev]
            ds.append(sum(hit(r, x, k) - hit(r, y, k) for r in smp) / len(smp))
        ds.sort()
        return {"diff": round(pt, 4), "ci95": [round(ds[100], 4), round(ds[3899], 4)]}
    w = s["winner"]
    best_d = max(("D15", "D30", "D50", "D85"), key=lambda a: (sum(hit(r, a, 5) for r in sel_ev), -int(a[1:])))
    s["best_dag_arm_on_selection"] = best_d
    s["dag_contrasts"] = {f"{best_d}-X fn@5 selection": boot(sel, best_d, "X", 5), f"{best_d}-X fn@5 heldout": boot(held, best_d, "X", 5),
                          f"{best_d}-X fn@10 heldout": boot(held, best_d, "X", 10), f"{best_d}-X fn@5 all": boot(ok, best_d, "X", 5),
                          f"{best_d}-X fn@1 all": boot(ok, best_d, "X", 1), f"{best_d}-X fn@10 all": boot(ok, best_d, "X", 10),
                          "DC85-X fn@5 all": boot(ok, "DC85", "X", 5)}
    s["contrasts"] = {f"{w}-A fn@5 all": boot(ok, w, "A", 5), f"{w}-A fn@10 all": boot(ok, w, "A", 10),
                      f"{w}-A fn@5 heldout": boot(held, w, "A", 5), f"{w}-A fn@10 heldout": boot(held, w, "A", 10),
                      f"{w}-X fn@5 all": boot(ok, w, "X", 5), f"{w}-N fn@5 all": boot(ok, w, "N", 5)}
    json.dump(s, open(OUT / "v2_summary.json", "w"), indent=1, sort_keys=True)
    print(json.dumps(s, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
