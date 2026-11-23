"""Lexical retrieval followed by a light walk over the typed SemDAG IR.

The issue queries live function source with BM25.  Those scores become the
restart distribution for a deterministic walk over resolved calls, lexical
containment, and repository imports.  A small damping value keeps source
evidence primary while allowing structure to consolidate file-level context.
"""
from collections import Counter, defaultdict
import math
import re

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
STOP = {"the", "and", "for", "that", "this", "with", "not", "but", "are", "was", "from",
        "have", "has", "when", "you", "can", "should", "would", "will", "use", "using",
        "def", "self", "return", "import", "none", "true", "false", "class", "if", "else",
        "in", "is", "of", "to", "it", "as", "on", "be", "or", "an", "at", "by", "we"}
DEFAULT_DAMPING = 0.15
DEFAULT_RELATION_WEIGHTS = {
    "calls": 1.5,
    "loop_calls": 1.4,
    "recurses": 1.3,
    "instantiates": 1.0,
    "inherits": 0.8,
    "member_of": 0.6,
    "contains": 0.35,
    "imports": 0.25,
}
WALK_NODE_KINDS = ("file", "class", "function", "method", "loop", "recursion")


def is_test_path(rel):
    parts = rel.split("/"); name = parts[-1]
    return (any(p in ("tests", "test", "testing") for p in parts[:-1])
            or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py")


def is_tool_path(rel):
    """Submission/harness implementation files are never task edit sites."""
    name = rel.split("/")[-1]
    return rel.startswith("semdag/") or name.startswith(".adk_exec_")


def is_candidate_path(rel, include_tests=False):
    return not is_tool_path(rel) and (include_tests or not is_test_path(rel))


def tokens(text):
    out = []
    for ident in IDENT.findall(text):
        low = ident.lower()
        if len(low) >= 2 and low not in STOP:
            out.append(low)
        parts = [p.lower() for chunk in ident.split("_") for p in CAMEL.findall(chunk)]
        if len(parts) > 1:
            out.extend(p for p in parts if len(p) >= 2 and p not in STOP)
    return out


def _documents(ir, snap, include_tests=False):
    docs = []
    for node in ir["nodes"]:
        if node["kind"] not in ("function", "method") or not is_candidate_path(node["file"], include_tests):
            continue
        content = snap["files"].get(node["file"], {}).get("content")
        if content is None or not node.get("end_line"):
            continue
        lines = content.splitlines()
        start = node.get("start_line", node["line"])
        body = "\n".join(lines[start - 1:node["end_line"]])
        head = f"{node.get('qualname', node['name']).replace('.', ' ')} {node['file'].replace('/', ' ').replace('.py', '')}"
        terms = tokens(body) + tokens(head) * 3
        docs.append({"node": node, "terms": Counter(terms), "length": len(terms)})
    return docs


def _bm25(docs, query):
    n = len(docs); df = Counter()
    for doc in docs: df.update(doc["terms"].keys())
    avg = sum(d["length"] for d in docs) / max(1, n)
    scores = [0.0] * n
    for term, qtf in Counter(tokens(query)).items():
        freq = df.get(term)
        if not freq: continue
        weight = math.log(1 + (n - freq + 0.5) / (freq + 0.5)) * min(qtf, 3)
        for i, doc in enumerate(docs):
            tf = doc["terms"].get(term)
            if tf:
                scores[i] += weight * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * doc["length"] / avg))
    return scores


def _walk(ir, restart, damping, weights, include_tests=False, direction="undirected"):
    keep = {n["id"] for n in ir["nodes"] if n["kind"] in WALK_NODE_KINDS
            and is_candidate_path(n.get("file", ""), include_tests)}
    adj = defaultdict(lambda: defaultdict(float)); used = Counter()
    for edge in ir["edges"]:
        rel = edge["rel"]; weight = weights.get(rel, 0.0)
        if weight <= 0 or edge["src"] not in keep or edge["dst"] not in keep: continue
        if direction == "reverse_calls" and rel == "calls":
            adj[edge["dst"]][edge["src"]] += weight
        else:
            adj[edge["src"]][edge["dst"]] += weight
            adj[edge["dst"]][edge["src"]] += weight
        used[rel] += 1
    rank = dict(restart)
    for _ in range(30):
        nxt = defaultdict(float); lost = 0.0
        for node, mass in rank.items():
            neighbors = adj.get(node); total = sum(neighbors.values()) if neighbors else 0.0
            if not total:
                lost += damping * mass; continue
            for target, weight in neighbors.items():
                nxt[target] += damping * mass * weight / total
        for node, mass in restart.items():
            nxt[node] += (1.0 - damping + lost) * mass
        rank = nxt
    return rank, used


def lexical_scores(ir, snap, issue, include_tests=False):
    """BM25 score of every candidate function (node id -> score); zero scores omitted."""
    docs = _documents(ir, snap, include_tests=include_tests)
    return {d["node"]["id"]: s for d, s in zip(docs, _bm25(docs, issue)) if s > 0}


def rank(ir, snap, issue, top_n=10, damping=DEFAULT_DAMPING, include_tests=False,
         relation_weights=None, direction="undirected"):
    """Return ranked function sites plus auditable lexical/structural evidence."""
    docs = _documents(ir, snap, include_tests=include_tests)
    scores = _bm25(docs, issue)
    positive = [i for i, score in enumerate(scores) if score > 0]
    total = sum(scores[i] for i in positive) or 1.0
    restart = {docs[i]["node"]["id"]: scores[i] / total for i in positive}
    weights = dict(DEFAULT_RELATION_WEIGHTS if relation_weights is None else relation_weights)
    graph, used = _walk(ir, restart, damping, weights, include_tests, direction) if restart and damping else (restart, Counter())
    lexical_order = sorted(positive, key=lambda i: (-scores[i], docs[i]["node"]["file"], docs[i]["node"]["line"]))
    lexical_rank = {i: pos + 1 for pos, i in enumerate(lexical_order)}
    eligible = [i for i, doc in enumerate(docs) if graph.get(doc["node"]["id"], 0.0) > 0.0]
    order = sorted(eligible, key=lambda i: (-graph.get(docs[i]["node"]["id"], 0.0),
                                            docs[i]["node"]["file"], docs[i]["node"]["line"]))
    top = []
    for i in order[:top_n]:
        node = docs[i]["node"]
        top.append({"id": node["id"], "name": node["name"], "qualname": node.get("qualname", node["name"]),
                    "file": node["file"], "line": node["line"], "end_line": node["end_line"],
                    "lexical_rank": lexical_rank.get(i), "lexical_score": scores[i],
                    "structural_score": graph.get(node["id"], 0.0)})
    return {"method": "bm25_typed_semdag", "damping": damping, "direction": direction,
            "candidates": len(docs),
            "matched_candidates": len(positive), "relations_used": dict(used), "top": top}
