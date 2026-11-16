"""Real-graph families: dag (graph-query reading) and systems (structural reasoning). Labels computed from the edge list in the prompt."""
import collections, json
from common import *
from tools import tools

BAD_TOP = {"tests", "test", "docs_src", "docs", "scripts", "benchmarks", "examples", "tutorial", "tools"}
PKG = {"fastapi/fastapi": {"fastapi"}, "psf/requests": {"requests"}, "Textualize/rich": {"rich"}, "encode/httpx": {"httpx"}}
def keep(i, repo):
    return i.split(".")[0] in PKG.get(repo, set())

def node_split(x):
    v = int(sha("node|" + x, 8), 16) % 10
    return "train" if v < 8 else ("dev" if v == 8 else "test")

def adjs(edges):
    out, inn = collections.defaultdict(set), collections.defaultdict(set)
    for a, b in edges:
        out[a].add(b); inn[b].add(a)
    return out, inn

def neighborhood(edges, seed, cap):
    und = collections.defaultdict(set)
    for a, b in edges:
        und[a].add(b); und[b].add(a)
    seen, frontier, order = {seed}, [seed], [seed]
    while frontier and len(order) < cap:
        nxt = []
        for n in frontier:
            for m in sorted(und[n]):
                if m not in seen and len(order) < cap:
                    seen.add(m); order.append(m); nxt.append(m)
        frontier = nxt
    ns = set(order)
    return sorted(ns), sorted((a, b) for a, b in edges if a in ns and b in ns)

def bfs(adj, s, maxd=99):
    dist, q = {s: 0}, collections.deque([s])
    while q:
        n = q.popleft()
        if dist[n] >= maxd: continue
        for m in sorted(adj.get(n, ())):
            if m not in dist:
                dist[m] = dist[n] + 1; q.append(m)
    return dist

def sccs(nodes, out):
    idx, low, st, on, res, c = {}, {}, [], set(), [], [0]
    def sc(v):
        idx[v] = low[v] = c[0]; c[0] += 1; st.append(v); on.add(v)
        for w in sorted(out.get(v, ())):
            if w not in idx: sc(w); low[v] = min(low[v], low[w])
            elif w in on: low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            comp = []
            while True:
                w = st.pop(); on.discard(w); comp.append(w)
                if w == v: break
            res.append(sorted(comp))
    for v in nodes:
        if v not in idx: sc(v)
    return sorted(res)

def kahn(nodes, out):
    indeg = {n: 0 for n in nodes}
    for a in nodes:
        for b in out.get(a, ()): indeg[b] += 1
    ready, order, trace = sorted(n for n in nodes if indeg[n] == 0), [], []
    while ready:
        n = ready.pop(0); order.append(n)
        for b in sorted(out.get(n, ())):
            indeg[b] -= 1
            if indeg[b] == 0: ready.append(b)
        ready.sort()
        trace.append((n, list(ready)))
    return (order if len(order) == len(nodes) else None), trace

def short(n, repo_prefix):  # display helper only
    return n

def fmt(v): return json.dumps(v, separators=(",", ":"), sort_keys=True)

def subgraph_json(nodes, edges):
    return {"status": "ok", "nodes": nodes, "edges": [{"from": a, "to": b, "type": "calls"} for a, b in edges],
            "node_count": len(nodes), "edge_count": len(edges), "is_truncated": False}

PHR = {
 "callees": ["Which symbols does `{x}` directly call?", "List the direct callees of `{x}` in this graph.", "What does `{x}` call directly?"],
 "callers": ["Which symbols directly call `{x}`?", "List the direct callers of `{x}` in this graph.", "Who calls `{x}` directly?"],
 "reach": ["Which symbols can `{x}` reach within {k} call hop(s)? Exclude `{x}` itself.", "List everything reachable from `{x}` in at most {k} call hop(s), excluding `{x}`."],
 "impact": ["If `{x}` changes, which symbols may be affected? Count callers up to {k} hop(s) away and group them by hop distance.", "Blast radius of changing `{x}`: group its transitive callers (up to {k} hops) by hop distance."],
 "path": ["Give the shortest call path from `{x}` to `{y}`. If several shortest paths exist, pick the alphabetically earliest. Use null if there is none.", "Is `{y}` reachable from `{x}`? Return the shortest call path (alphabetically earliest on ties) or null."],
 "cycles": ["Which symbols form call cycles (strongly connected groups of 2 or more) in this graph? Also list symbols that call themselves.", "Find the feedback loops: groups of symbols that can all reach each other, plus any self-calls."],
 "topo": ["Order all symbols so every caller appears before the symbols it calls. When several are available, pick the alphabetically earliest.", "Give a call-order (callers first) listing of all symbols; alphabetical tie-break."],
 "hub": ["Which symbol has the most direct callers in this graph? Break ties alphabetically. Give its in-degree.", "Find the most depended-upon symbol (highest number of direct callers) and its in-degree; alphabetical tie-break."],
 "spof": ["Ignoring call direction, which single symbols (other than `{x}` and `{y}`) would disconnect `{x}` from `{y}` if removed? Return a sorted list, empty if none.", "Treat the graph as undirected. Which symbols (not `{x}` or `{y}`) are single points of failure between `{x}` and `{y}`? Sorted list."],
 "layers": ["Assign layers: layer 0 = symbols that call nothing; otherwise 1 + the highest layer among the symbols it calls. Group symbols by layer.", "Compute the dependency layering of this acyclic graph (leaves are layer 0, each symbol sits one above its highest callee)."],
}

def solve(q, nodes, edges, a):
    out, inn = adjs(edges)
    x, y, k = a.get("x"), a.get("y"), a.get("k", 2)
    if q == "callees": return sorted(out[x])
    if q == "callers": return sorted(inn[x])
    if q == "reach":
        d = bfs(out, x, k); return sorted(n for n, h in d.items() if 1 <= h <= k)
    if q == "impact":
        d = bfs(inn, x, k); r = collections.defaultdict(list)
        for n, h in d.items():
            if h >= 1: r[str(h)].append(n)
        return {h: sorted(v) for h, v in sorted(r.items())}
    if q == "path":
        d = bfs(out, x)
        if y not in d: return None
        best = None
        def rec(path):
            nonlocal best
            n = path[-1]
            if n == y:
                if best is None or path < best: best = list(path)
                return
            for m in out[n]:
                if d.get(m) == len(path) and m not in path: rec(path + [m])
        rec([x]); return best
    if q == "cycles":
        return {"cycles": [c for c in sccs(nodes, out) if len(c) > 1], "self_calls": sorted(n for n in nodes if n in out[n])}
    if q == "topo":
        o, _ = kahn(nodes, out); return o
    if q == "hub":
        m = max(len(inn[n]) for n in nodes); n = sorted(n for n in nodes if len(inn[n]) == m)[0]
        return {"in_degree": m, "node": n}
    if q == "spof":
        und = collections.defaultdict(set)
        for s, t in edges: und[s].add(t); und[t].add(s)
        res = []
        for n in nodes:
            if n in (x, y): continue
            seen, st = {x}, [x]
            while st:
                u = st.pop()
                for w in und[u]:
                    if w != n and w not in seen: seen.add(w); st.append(w)
            if y not in seen: res.append(n)
        return sorted(res)
    if q == "layers":
        o, _ = kahn(nodes, out); lay = {}
        for n in reversed(o):
            lay[n] = 0 if not out[n] else 1 + max(lay[m] for m in out[n])
        r = collections.defaultdict(list)
        for n, l in lay.items(): r[str(l)].append(n)
        return {l: sorted(v) for l, v in sorted(r.items(), key=lambda kv: int(kv[0]))}

def derive(q, nodes, edges, a, val):
    """Plain-text derivation computed from the same edges (the model's thinking)."""
    out, inn = adjs(edges); x, y, k = a.get("x"), a.get("y"), a.get("k", 2)
    L = []
    if q == "callees":
        L.append(f"Edges whose source is {x}: " + (", ".join(f"{x}->{b}" for b in sorted(out[x])) or "none") + ".")
    elif q == "callers":
        L.append(f"Edges whose target is {x}: " + (", ".join(f"{b}->{x}" for b in sorted(inn[x])) or "none") + ".")
    elif q in ("reach", "impact"):
        adj = out if q == "reach" else inn; d = bfs(adj, x, k)
        for h in range(1, k + 1):
            fr = sorted(n for n, dd in d.items() if dd == h)
            L.append(f"Hop {h}: {', '.join(fr) if fr else 'nothing new'}.")
    elif q == "path":
        d = bfs(out, x)
        if y not in d: L.append(f"Breadth-first search from {x} never reaches {y}; it visits {len(d)} symbol(s).")
        else: L.append(f"{y} is {d[y]} hop(s) from {x}; taking the alphabetically earliest shortest path.")
    elif q == "cycles":
        for c in sccs(nodes, out):
            if len(c) > 1: L.append("Mutually reachable: " + ", ".join(c) + ".")
        sc = sorted(n for n in nodes if n in out[n])
        L.append("Self-calls: " + (", ".join(sc) if sc else "none") + ".")
        if len(L) == 1 and not sc: L.insert(0, "No group of two or more symbols can reach each other.")
    elif q == "topo":
        o, tr = kahn(nodes, out)
        for n, rdy in tr: L.append(f"Take {n}; still ready: {', '.join(rdy) if rdy else 'none'}.")
    elif q == "hub":
        L.append("Direct caller counts: " + ", ".join(f"{n}={len(inn[n])}" for n in nodes if inn[n]) + ".")
    elif q == "spof":
        L.append(f"Remove each symbol other than {x} and {y} and test whether {y} is still connected to {x}.")
    elif q == "layers":
        o, _ = kahn(nodes, out)
        L.append("Callees-first order: " + ", ".join(reversed(o)) + ".")
    L.append("Result: " + fmt(val) + ".")
    return " ".join(L)

def sowhat(q, nodes, edges, a, val):
    out, inn = adjs(edges)
    if q == "hub": return f" {val['node']} is the structural hub here: {val['in_degree']} direct caller(s), so a change to it has the widest first-order reach."
    if q == "spof": return (" Removing " + ", ".join(val) + " would split them, so changes there are high risk.") if val else " No single symbol separates them, so there is redundancy between the two."
    if q == "cycles" and val["cycles"]: return " Cycles mean there is no clean bottom-up order for these symbols; they must change together."
    if q == "impact":
        n = sum(len(v) for v in val.values()); return f" {n} symbol(s) sit upstream within {a['k']} hop(s)."
    return ""

def pick_args(q, nodes, edges, seed, rng):
    out, inn = adjs(edges); a = {"x": seed}
    if q in ("reach", "impact"): a["k"] = rng.choice([1, 2, 3])
    if q == "path" or q == "spof":
        und = collections.defaultdict(set)
        for s, t in edges: und[s].add(t); und[t].add(s)
        d = bfs(out, seed) if q == "path" else bfs(und, seed)
        far = sorted(n for n, h in d.items() if h >= 2)
        if q == "path" and (not far or rng.random() < 0.3):
            un = sorted(n for n in nodes if n not in d)
            if not un: return None
            a["y"] = rng.choice(un)
        else:
            if not far: return None
            a["y"] = rng.choice(far)
    if q in ("topo", "layers"):
        o, _ = kahn(nodes, out)
        if o is None: return None
    return a

def make_rows(tasks, smap, per_type=3, cap_lo=7, cap_hi=14):
    rows, seen = [], set()
    for t in tasks:
        g = load_graph(t)
        if not g: continue
        gn, ge = g
        edges = [(a, b) for a, b in ge if keep(a, t["repo"]) and keep(b, t["repo"]) and a in gn and b in gn]
        deg = collections.Counter()
        for a, b in edges: deg[a] += 1; deg[b] += 1
        cand = sorted(n for n, d in deg.items() if d >= 3)
        if not cand: continue
        for q in PHR:
            rng = rng_for("dag", t["instance_id"], q)
            seeds = sorted(cand, key=lambda n: sha(f"{t['instance_id']}|{q}|{n}"))[:per_type * 3]
            made = 0
            for seed in seeds:
                if made >= per_type: break
                nodes, sub = neighborhood(edges, seed, rng.randint(cap_lo, cap_hi))
                if len(sub) < 4: continue
                a = pick_args(q, nodes, sub, seed, rng)
                if a is None: continue
                key = sha(fmt([q, a, sub]))
                if key in seen: continue
                seen.add(key); made += 1
                val = solve(q, nodes, sub, a)
                fam = "systems" if q in ("hub", "spof", "layers", "cycles", "impact") else "dag"
                tmpl = rng.choice(PHR[q]).format(**{**{"k": 2}, **a})
                think = derive(q, nodes, sub, a, val) + sowhat(q, nodes, sub, a, val)
                ans = "ANSWER: " + fmt(val)
                sg = subgraph_json(nodes, sub)
                via_tool = rng.random() < 0.35
                if via_tool:
                    msgs = [{"role": "user", "content": f"Repository: {t['repo']}. Symbols of interest: {json.dumps(nodes)}.\n\n{tmpl}\nEnd with a line `ANSWER: <json>`."},
                            {"role": "assistant", "reasoning_content": "I need the call edges among these symbols before I can answer, so I will fetch the induced subgraph.",
                             "tool_calls": [{"type": "function", "function": {"name": "get_code_subgraph", "arguments": {"nodes": nodes}}}]},
                            {"role": "tool", "name": "get_code_subgraph", "content": json.dumps(sg, separators=(",", ":"))},
                            {"role": "assistant", "reasoning_content": think, "content": ans}]
                    tl = tools("get_code_subgraph")
                else:
                    msgs = [{"role": "user", "content": f"Call graph neighborhood from a Python repository ({t['repo']}), as returned by get_code_subgraph:\n{json.dumps(sg, separators=(',', ':'))}\n\n{tmpl}\nEnd with a line `ANSWER: <json>`."},
                            {"role": "assistant", "reasoning_content": think, "content": ans}]
                    tl = None
                rows.append({"family": fam, "subtype": q, "split": node_split(seed), "source": {"task": t["instance_id"], "repo": t["repo"], "seed": seed},
                             "thinking": True, "tools": tl, "messages": msgs,
                             "verifier": {"kind": "graph", "q": q, "nodes": nodes, "edges": sub, "args": a, "answer": val}})
    return rows
