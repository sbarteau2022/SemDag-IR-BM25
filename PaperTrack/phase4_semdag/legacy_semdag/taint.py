"""Stage 3.5 — Taint seeding: a lightweight, deterministic data-flow overlay on
the SemDAG that marks where untrusted input enters (sources) and where danger
happens (sinks), then finds taint-sink intersections — sinks reachable from a
source over the call-flow DAG — and emits a Personalized PageRank seed vector.

This is node-granularity taint (not full def-use): a function is a SOURCE if it
or its outgoing calls match source patterns, a SINK if they match sink patterns.
A sink is TAINT-REACHABLE if some source can reach it via `calls` edges. Those
intersections get the heaviest seed mass, so the downstream PPR walk targets
SQLi / unsafe-deserialization / command-exec / memory-safety surface first.

Writes taint.json. Usage: python taint.py <container_id>
"""
import sys, json, re
from collections import defaultdict
import cache

# substring patterns (lowercased) matched against a node's name and the names of
# its outgoing extern/ambiguous callees + imported modules in its file.
SOURCE_PATTERNS = [
    "__source_",
    "request", "req.", "query", "params", "getquery", "formvalue", "body",
    "argv", "args", "clap", "getopt", "env::var", "getenv", "environ", "std::env",
    "stdin", "readline", "input(", "read_to_string", "fs::read", "readfile",
    "fopen", "open(", "recv", "socket", "accept", "deserialize", "from_str",
    "from_slice", "pickle.load", "json.load", "serde_json::from", "unmarshal",
]
SINK_PATTERNS = [
    # command / code execution
    "exec", "eval", "system(", "popen", "subprocess", "command::new", "spawn",
    "os.system", "child_process", "shell",
    # SQL
    "execute", "executemany", "query(", "raw_query", "prepare", "cursor.execute",
    "sqlx::query", "rusqlite", "format!(\"select", "\"select ", "\"insert ",
    "\"update ", "\"delete ",
    # deserialization (untrusted)
    "pickle.loads", "yaml.load", "marshal.loads", "deserialize", "from_reader",
    "serde_json::from", "bincode::deserialize",
    # memory safety / unsafe
    "unsafe", "transmute", "from_raw", "memcpy", "strcpy", "get_unchecked",
    "as_mut_ptr", "set_len", "slice::from_raw",
]

def classify(text: str, patterns) -> list:
    t = text.lower()
    return sorted({p for p in patterns if p in t})

def reachable(adj, start):
    seen, stack = set(), list(adj.get(start, ()))
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n); stack.extend(adj.get(n, ()))
    seen.discard(start)
    return seen

def build(container_id: str) -> dict:
    ir = cache.read(container_id, "semdag_ir.json")
    meta = {n["id"]: n for n in ir["nodes"]}

    # per-function "signal text": its own name + names of callees (extern/ambiguous/internal)
    sig = defaultdict(list)
    fwd = defaultdict(set)   # caller -> callees (calls)
    imports_by_file = defaultdict(list)
    for n in ir["nodes"]:
        if n["kind"] == "module":
            imports_by_file[n["file"]].append(n["name"])
    for e in ir["edges"]:
        if e["rel"] == "calls":
            fwd[e["src"]].add(e["dst"])
            sig[e["src"]].append(meta.get(e["dst"], {}).get("name", ""))

    funcs = [n for n in ir["nodes"] if n["kind"] in ("function", "method")]
    sources, sinks = {}, {}
    for n in funcs:
        nid = n["id"]
        text = " ".join([n["name"]] + sig.get(nid, []) + imports_by_file.get(n["file"], []))
        sm = classify(text, SOURCE_PATTERNS)
        km = classify(text, SINK_PATTERNS)
        if sm:
            sources[nid] = sm
        if km:
            sinks[nid] = km

    # taint-sink intersection: a sink reachable from some source via calls flow
    src_reach = {}
    for s in sources:
        src_reach[s] = reachable(fwd, s)
    taint_sinks = {}
    for k in sinks:
        feeders = [s for s in sources if k in src_reach.get(s, ()) or k == s]
        if feeders:
            taint_sinks[k] = {"patterns": sinks[k], "fed_by": sorted(feeders)[:8]}

    # Personalized PageRank seed vector:
    #   taint-reachable sink = 1.0 (the bug gathers here)
    #   plain sink           = 0.5
    #   source               = 0.25 (entry surface)
    seed = defaultdict(float)
    for nid in sinks:
        seed[nid] += 1.0 if nid in taint_sinks else 0.5
    for nid in sources:
        seed[nid] += 0.25
    tot = sum(seed.values()) or 1.0
    seed = {k: round(v / tot, 8) for k, v in seed.items()}

    out = {
        "tree_sha256": ir["tree_sha256"],
        "counts": {"sources": len(sources), "sinks": len(sinks),
                   "taint_sinks": len(taint_sinks), "seed_nodes": len(seed)},
        "sources": sources, "sinks": sinks, "taint_sinks": taint_sinks,
        "seed": seed,
    }
    cache.write(container_id, "taint.json", out)
    cache.mark_stage(container_id, "taint", out["counts"])
    return out

if __name__ == "__main__":
    cid = sys.argv[1]
    o = build(cid)
    print(json.dumps({"stage": "taint", **o["counts"]}))
