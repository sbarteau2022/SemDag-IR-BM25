"""Shared helpers for the LoRA dataset builders. Deterministic; no network; stdlib + numpy only."""
import ast, hashlib, json, random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # LoRAData/
PUB = ROOT.parent / "DataSets" / "public"
DATA = PUB / "data"
CACHE = ROOT / "cache"
OUT = ROOT / "out"
SPLITS = ("train", "dev", "test")

def sha(s, n=16):
    if isinstance(s, str):
        s = s.encode("utf-8", "surrogatepass")
    return hashlib.sha256(s).hexdigest()[:n]

def rng_for(*parts):
    return random.Random(int(sha("|".join(map(str, parts)), 12), 16))

def load_tasks(keep_patch=False):
    """Never expose test_patch / hints_text to any generator."""
    rows = []
    for line in open(DATA / "tasks.jsonl"):
        t = json.loads(line)
        for k in ("test_patch", "hints_text"):
            t.pop(k, None)
        if not keep_patch:
            t.pop("patch", None)
        rows.append(t)
    return rows

def split_map(tasks):
    """Task-level split, stratified by repo, decided by sha of instance_id only."""
    by = {}
    for t in tasks:
        by.setdefault(t["repo"], []).append(t["instance_id"])
    out = {}
    for repo, ids in by.items():
        ids = sorted(ids, key=lambda i: sha("split|" + i))
        n = len(ids)
        ntr, ndev = (n, 0) if n < 4 else (round(0.6 * n), max(1, round(0.15 * n)))
        for k, i in enumerate(ids):
            out[i] = "train" if k < ntr else ("dev" if k < ntr + ndev else "test")
    return out

def graph_file(t):
    name = t["repo"].split("/")[1].lower()
    p = DATA / "graphs" / f"{name}_{t['base_commit']}.json"
    return p if p.exists() else None

def load_graph(t):
    p = graph_file(t)
    if not p:
        return None
    g = json.loads(p.read_text())
    nodes = {n["id"]: n for n in g["nodes"]}
    edges = sorted({(e["source"], e["target"]) for e in g["edges"] if e.get("type") == "calls"})
    return nodes, edges

def load_src(instance_id):
    """path -> source text for the task's snapshot (from cache/index + blobs)."""
    idx = json.loads((CACHE / "index" / f"{instance_id}.json").read_text())
    return {p: (CACHE / "blobs" / h).read_text("utf-8", "replace") for p, h in idx.items()}

def is_test_path(p):
    parts = p.split("/")
    b = parts[-1]
    return (any(x in ("tests", "test", "testing") for x in parts[:-1]) or b.startswith("test_")
            or b.endswith("_test.py") or b == "conftest.py")

def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
