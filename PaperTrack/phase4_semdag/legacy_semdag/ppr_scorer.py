"""PurePythonPPRScorer — zero-dependency vulnerability-hub scorer.

Stdlib only (collections). No pip, no native compilation, no tree-sitter at
call time: it consumes the cached SemDAG-IR (+ optional taint seed) and runs
Personalized PageRank on the reversed call graph. Because tree-sitter already
produced and cached the IR, this scorer runs instantly inside any offline
sandbox container.

Typical use: a test fails or an issue is filed -> extract the traceback frame's
FUNCTION NAME -> `scorer.score_by_names([name])` -> top vulnerability hubs,
instantly. The seed can be function names, explicit node ids, or a raw weight
vector (e.g. the taint seed), and bias vectors can be layered in.
"""
from collections import defaultdict

D = 0.85
ITERS = 80


class PurePythonPPRScorer:
    def __init__(self, ir: dict, taint: dict | None = None):
        self.meta = {n["id"]: n for n in ir["nodes"]}
        self.kind = {n["id"]: n["kind"] for n in ir["nodes"]}
        self.fwd = defaultdict(set)     # caller -> callees
        self.rev = defaultdict(set)     # callee -> callers
        self.radj = defaultdict(list)   # PPR propagation: callee -> [callers]
        self.extern_out = defaultdict(int)
        self.resolved_out = defaultdict(int)
        self.by_name = defaultdict(list)
        nodes = set(self.meta)
        for n in ir["nodes"]:
            if n["kind"] in ("function", "method"):
                self.by_name[n["name"]].append(n["id"])
        for e in ir["edges"]:
            if e["rel"] != "calls":
                continue
            s, d = e["src"], e["dst"]
            self.fwd[s].add(d); self.rev[d].add(s); self.radj[d].append(s)
            nodes.add(s); nodes.add(d)
            if self.kind.get(d) in ("extern", "ambiguous"):
                self.extern_out[s] += 1
            else:
                self.resolved_out[s] += 1
        self.nodes = sorted(nodes)
        self.out_edges = {k: sorted(set(v)) for k, v in self.radj.items()}
        self.taint = taint or {}
        t = self.taint
        self.sources, self.sinks, self.tsinks = (t.get("sources", {}),
                                                 t.get("sinks", {}), t.get("taint_sinks", {}))

    # ---- seeds ----
    def names_to_nodes(self, names):
        out = []
        for nm in names:
            out.extend(self.by_name.get(nm, []))
        return out

    def _reach(self, adj, start):
        seen, stack = set(), list(adj.get(start, ()))
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n); stack.extend(adj.get(n, ()))
        seen.discard(start)
        return seen

    def _ppr(self, pvec):
        n = len(self.nodes)
        r = {nid: pvec.get(nid, 0.0) for nid in self.nodes}
        if sum(r.values()) == 0:
            r = {nid: 1.0 / n for nid in self.nodes}
        for _ in range(ITERS):
            nxt = {nid: (1.0 - D) * pvec.get(nid, 0.0) for nid in self.nodes}
            dangling = 0.0
            for v in self.nodes:
                tv = self.out_edges.get(v, ())
                if not tv:
                    dangling += r[v]; continue
                share = D * r[v] / len(tv)
                for tt in tv:
                    nxt[tt] += share
            if dangling:
                for nid in self.nodes:
                    nxt[nid] += D * dangling * pvec.get(nid, 0.0)
            s = sum(nxt.values()) or 1.0
            r = {k: v / s for k, v in nxt.items()}
        return r

    # ---- scoring ----
    def score(self, seed: dict, top_n: int = 15) -> list:
        tot = sum(seed.values()) or 1.0
        pvec = {k: v / tot for k, v in seed.items()}
        ppr = self._ppr(pvec)
        rows = []
        for nid in (n for n in self.nodes if self.kind.get(n) in ("function", "method")):
            ro, eo = self.resolved_out.get(nid, 0), self.extern_out.get(nid, 0)
            m = self.meta[nid]
            rows.append({
                "id": nid, "name": m["name"], "file": m["file"], "line": m["line"],
                "fan_in": len(self.rev.get(nid, ())), "fan_out": len(self.fwd.get(nid, ())),
                "downstream": len(self._reach(self.fwd, nid)),
                "upstream": len(self._reach(self.rev, nid)),
                "coherence": round((ro / (ro + eo)) if (ro + eo) else 0.5, 4),
                "is_sink": nid in self.sinks, "taint_sink": nid in self.tsinks,
                "taint_patterns": self.sinks.get(nid, []) or self.sources.get(nid, []),
                "ppr": ppr.get(nid, 0.0),
            })
        tp = sum(x["ppr"] for x in rows) or 1.0
        for x in rows:
            x["prob"] = round(x["ppr"] / tp, 6); del x["ppr"]
        rows.sort(key=lambda x: (-x["prob"], x["id"]))
        for i, x in enumerate(rows):
            x["rank"] = i + 1
        return rows[:top_n]

    def score_by_names(self, names, top_n: int = 15, blend_taint: bool = True) -> list:
        """Seed from traceback/issue function NAMES; optionally blend the taint
        seed so the walk still favors taint-reachable sinks near the frame."""
        seed = defaultdict(float)
        for nid in self.names_to_nodes(names):
            seed[nid] += 1.0
        if blend_taint:
            for nid, w in self.taint.get("seed", {}).items():
                seed[nid] += 0.25 * w
        if not seed:  # unknown name -> fall back to taint-only
            seed = dict(self.taint.get("seed", {}))
        return self.score(dict(seed), top_n)


if __name__ == "__main__":
    import sys, json, cache
    cid = sys.argv[1]
    names = [a for a in sys.argv[2:] if not a.isdigit()]
    top_n = next((int(a) for a in sys.argv[2:] if a.isdigit()), 10)
    ir = cache.read(cid, "semdag_ir.json")
    try:
        taint = cache.read(cid, "taint.json")
    except FileNotFoundError:
        taint = None
    scorer = PurePythonPPRScorer(ir, taint)
    hubs = scorer.score_by_names(names, top_n)
    print(json.dumps({"seed_names": names, "candidates_ranked": len(hubs),
        "top": [{k: h[k] for k in ("rank","name","file","line","prob","is_sink",
                 "taint_sink","downstream","taint_patterns")} for h in hubs]}, indent=2))
