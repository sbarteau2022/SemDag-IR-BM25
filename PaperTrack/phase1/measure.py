#!/usr/bin/env python3
"""Phase 1 measurement. Rules below are frozen. Do not retune after reading recall.

Question
    The class node is an outline (stub body). The method node is the real body.
    Parent id is recoverable by splitting the symbol id. Call edges do not encode
    that link. Does the sibling/child closure, or cosine after subtracting the
    parent-outline vector, cover the gold edit more often than the named body
    or one call hop?

Predictor inputs
    problem_statement, graph nodes/edges, 256-d node embeddings.
    The patch is used only to score. hints_text and test_patch are not read.

Gold alignment
    A .py hunk is anchored to the smallest node whose text contains the old-side
    line window (context lines and deletions, in order) as consecutive lines.
    If that window is absent, the consecutive deletion block is tried.
    A one-line anchor that occurs in more than AMBIGUOUS_LINE_CAP nodes is
    unaligned. Lines with strip length < MIN_LINE_CHARS do not count.
    New files and non-.py hunks are unaligned and sit only in the "all lines"
    denominator.

Arms (union over seeds; embeddings exclude the seed itself)
    Z     seed nodes named by the issue
    P     children of a class seed, else siblings under the same parent id
    ZP    Z union P
    C     callers and callees, one hop, uncapped
    C50   the same neighborhood truncated at 50 names in edge order
    E     top-k other nodes by raw cosine, k = |P| or FIXED_K if P is empty
    R     top-k by cosine after subtracting the parent outline (else the graph mean)
    RAND  mean of RANDOM_DRAWS uniform draws of size k, seeds excluded

Seeds
    Identifiers from the issue: backtick spans, dotted names, tokens before
    '(', snake_case, CamelCase. Drop length < 3, keywords, and any short name
    shared by more than AMBIGUITY_CAP nodes. Match exact id, then id suffix.

Selection
    Winner is the highest micro line-recall on non-Rich tasks among
    Z, P, ZP, C, E, R. Rich is confirmatory and is not an input to that choice.
    Contrasts are task-resampled on the same split: ZP-Z, R-E, R-C, Z-C.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DataSets" / "public" / "data"
TASKS = DATA / "tasks.jsonl"
GRAPHS = DATA / "graphs"
EMBEDS = DATA / "embeddings"
OUT = Path(__file__).resolve().parent / "out"

AMBIGUITY_CAP = 20
AMBIGUOUS_LINE_CAP = 5
FIXED_K = 10
NEIGHBOR_CAP = 50
RANDOM_DRAWS = 50
RNG_SEED = 0
MIN_LINE_CHARS = 3
N_BOOT = 4000
WINNER_ARMS = ("Z", "P", "ZP", "C", "E", "R")
PRIMARY_ARMS = ("Z", "P", "ZP", "C", "C50", "E", "R", "RAND")

KEYWORDS = {
    "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "false", "finally", "for", "from",
    "global", "if", "import", "in", "is", "lambda", "none", "nonlocal", "not",
    "or", "pass", "raise", "return", "true", "try", "while", "with", "yield",
}

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
DOTTED_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
SNAKE_RE = re.compile(r"\b[a-z_][a-z0-9]*_[a-z0-9_]+\b")
CAMEL_RE = re.compile(r"\b[A-Z][a-zA-Z0-9]*[a-z][a-zA-Z0-9]*\b")
CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
TICK_RE = re.compile(r"`([^`\n]+)`")


def repo_short(repo: str) -> str:
    return repo.split("/")[-1]


def substantive(line: str) -> bool:
    return len(line.strip()) >= MIN_LINE_CHARS


def parse_hunks(patch: str) -> list[dict]:
    hunks: list[dict] = []
    old_path = None
    new_path = None
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        old_lines: list[str] = []
        deleted: list[str] = []
        added: list[str] = []
        for raw in buf:
            if raw.startswith("\\"):
                continue
            if raw.startswith("+"):
                added.append(raw[1:])
            elif raw.startswith("-"):
                deleted.append(raw[1:])
                old_lines.append(raw[1:])
            elif raw.startswith(" "):
                old_lines.append(raw[1:])
            else:
                old_lines.append(raw)
        path = new_path if old_path in (None, "/dev/null") else old_path
        hunks.append(
            {
                "path": path or "",
                "new_file": old_path in (None, "/dev/null"),
                "old_lines": old_lines,
                "deleted": deleted,
                "added": added,
            }
        )

    for line in patch.splitlines():
        if line.startswith("diff --git "):
            flush()
            buf = []
            old_path = None
            new_path = None
        elif line.startswith("--- "):
            old_path = line[4:].strip()
            if old_path.startswith("a/"):
                old_path = old_path[2:]
        elif line.startswith("+++ "):
            new_path = line[4:].strip()
            if new_path.startswith("b/"):
                new_path = new_path[2:]
        elif line.startswith("@@"):
            flush()
            buf = []
        elif old_path is not None or new_path is not None:
            if line.startswith(("+", "-", " ", "\\")):
                buf.append(line)
    flush()
    return hunks


def kind_of(text: str) -> str:
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("@"):
            continue
        if stripped.startswith("class "):
            return "class"
        return "func"
    return "func"


class Graph:
    def __init__(self, path: Path, embed_path: Path):
        raw = json.loads(path.read_text())
        self.ids: list[str] = []
        self.text: dict[str, str] = {}
        self.lines: dict[str, list[str]] = {}
        self.kind: dict[str, str] = {}
        self.nchars: dict[str, int] = {}
        for node in raw["nodes"]:
            ident = node["id"]
            body = node.get("text") or ""
            self.ids.append(ident)
            self.text[ident] = body
            self.lines[ident] = body.splitlines()
            self.kind[ident] = kind_of(body)
            self.nchars[ident] = len(body)
        self.idset = set(self.ids)
        self.parent: dict[str, str | None] = {}
        self.children: dict[str, list[str]] = defaultdict(list)
        for ident in self.ids:
            parent = ident.rsplit(".", 1)[0] if "." in ident else None
            if parent not in self.idset:
                parent = None
            self.parent[ident] = parent
            if parent is not None:
                self.children[parent].append(ident)
        self.short: dict[str, list[str]] = defaultdict(list)
        for ident in self.ids:
            self.short[ident.rsplit(".", 1)[-1]].append(ident)
        callers: dict[str, list[str]] = defaultdict(list)
        callees: dict[str, list[str]] = defaultdict(list)
        for edge in raw["edges"]:
            if edge.get("type") != "calls":
                continue
            src, dst = edge["source"], edge["target"]
            if src in self.idset and dst in self.idset and src != dst:
                callees[src].append(dst)
                callers[dst].append(src)
        self.callers = callers
        self.callees = callees
        self.first: dict[str, list[str]] = defaultdict(list)
        for ident, lines in self.lines.items():
            seen = set()
            for line in lines:
                if line in seen or not substantive(line):
                    continue
                seen.add(line)
                self.first[line].append(ident)
        archive = np.load(embed_path)
        rows = []
        ok = []
        self.emb_index: dict[str, int] = {}
        for ident in self.ids:
            if ident not in archive:
                continue
            vec = np.asarray(archive[ident], dtype=np.float64)
            if vec.shape != (256,):
                continue
            self.emb_index[ident] = len(rows)
            rows.append(vec)
            ok.append(ident)
        self.emb_ids = ok
        self.emb = np.vstack(rows) if rows else np.zeros((0, 256))
        self.mean = self.emb.mean(axis=0) if len(self.emb) else np.zeros(256)
        self.missing_emb = len(self.ids) - len(ok)
        archive.close()


def has_window(lines: list[str], seq: list[str]) -> bool:
    n = len(seq)
    if n == 0 or n > len(lines):
        return False
    first = seq[0]
    limit = len(lines) - n + 1
    start = 0
    while True:
        try:
            i = lines.index(first, start, limit)
        except ValueError:
            return False
        if lines[i : i + n] == seq:
            return True
        start = i + 1


def smallest_hit(graph: Graph, seq: list[str]) -> str | None:
    if not seq:
        return None
    # The line index stores substantive lines only. Windows often open on a
    # short token such as "):". Candidate nodes are those that contain the
    # first substantive line; the match is still the full consecutive window.
    key = next((line for line in seq if substantive(line)), None)
    if key is None:
        return None
    cands = graph.first.get(key, [])
    best = None
    best_len = None
    for ident in cands:
        if not has_window(graph.lines[ident], seq):
            continue
        nchars = graph.nchars[ident]
        if best is None or nchars < best_len or (nchars == best_len and ident < best):
            best = ident
            best_len = nchars
    return best


def line_support(graph: Graph, seq: list[str]) -> int:
    if len(seq) != 1:
        return 0
    return len(graph.first.get(seq[0], []))


def trim_ends(seq: list[str]) -> list[str]:
    start, end = 0, len(seq)
    while start < end and seq[start].strip() == "":
        start += 1
    while end > start and seq[end - 1].strip() == "":
        end -= 1
    return seq[start:end]


def usable_anchor(graph: Graph, seq: list[str]) -> bool:
    seq = trim_ends(seq)
    if not seq or not any(substantive(line) for line in seq):
        return False
    if len(seq) == 1 and line_support(graph, seq) > AMBIGUOUS_LINE_CAP:
        return False
    return True


def align_hunk(graph: Graph, hunk: dict) -> dict:
    deleted_w = [ln for ln in hunk["deleted"] if substantive(ln)]
    added_w = [ln for ln in hunk["added"] if substantive(ln)]
    path = hunk["path"]
    py = path.endswith(".py")
    weight = len(deleted_w) if deleted_w else len(added_w)
    if hunk["new_file"] or not py or weight == 0:
        return {
            "node": None,
            "weight": weight if py else len(deleted_w) + len(added_w),
            "how": "non_py" if not py else ("new_file" if hunk["new_file"] else "empty"),
            "py": py,
        }
    node = None
    how = "unaligned"
    window = trim_ends(hunk["old_lines"])
    if usable_anchor(graph, window):
        node = smallest_hit(graph, window)
        if node is not None:
            how = "old_window"
    if node is None and deleted_w:
        block = trim_ends(hunk["deleted"])
        if usable_anchor(graph, block):
            node = smallest_hit(graph, block)
            if node is not None:
                how = "deleted_block"
    return {"node": node, "weight": weight, "how": how if node else "unaligned", "py": True}


def issue_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for tick in TICK_RE.findall(text):
        tokens.update(IDENT_RE.findall(tick))
        tokens.update(DOTTED_RE.findall(tick))
    tokens.update(DOTTED_RE.findall(text))
    tokens.update(CALL_RE.findall(text))
    tokens.update(SNAKE_RE.findall(text))
    tokens.update(CAMEL_RE.findall(text))
    kept = set()
    for token in tokens:
        if len(token) < 3:
            continue
        if token.lower() in KEYWORDS:
            continue
        kept.add(token)
    return kept


def resolve_seeds(graph: Graph, text: str) -> list[str]:
    found: list[str] = []
    seen = set()
    for token in sorted(issue_tokens(text)):
        hits: list[str] = []
        if token in graph.idset:
            hits = [token]
        else:
            short = token.rsplit(".", 1)[-1]
            pool = graph.short.get(short, [])
            if token.startswith(short) and token == short:
                if len(pool) > AMBIGUITY_CAP:
                    continue
                hits = list(pool)
            else:
                suffix = "." + token
                hits = [ident for ident in graph.ids if ident == token or ident.endswith(suffix)]
                if len(hits) > AMBIGUITY_CAP:
                    continue
        for ident in hits:
            if ident not in seen:
                seen.add(ident)
                found.append(ident)
    return found


def unit(vec: np.ndarray) -> np.ndarray | None:
    norm = float(np.linalg.norm(vec))
    if norm < 1e-12:
        return None
    return vec / norm


def residual_matrix(graph: Graph) -> tuple[np.ndarray, np.ndarray]:
    """Return residual row-vectors (unnormalized) aligned to graph.emb_ids, and a mask of usable rows."""
    rows = np.zeros_like(graph.emb)
    usable = np.ones(len(graph.emb_ids), dtype=bool)
    for i, ident in enumerate(graph.emb_ids):
        parent = graph.parent[ident]
        if parent is not None and parent in graph.emb_index:
            rows[i] = graph.emb[i] - graph.emb[graph.emb_index[parent]]
        else:
            rows[i] = graph.emb[i] - graph.mean
        if float(np.linalg.norm(rows[i])) < 1e-12:
            usable[i] = False
    return rows, usable


def topk_from_queries(
    graph: Graph,
    queries: list[np.ndarray],
    matrix: np.ndarray,
    usable: np.ndarray,
    exclude: set[str],
    k: int,
) -> set[str]:
    if k <= 0 or not queries or len(graph.emb_ids) == 0:
        return set()
    q = np.vstack(queries)
    qn = np.linalg.norm(q, axis=1, keepdims=True)
    mn = np.linalg.norm(matrix, axis=1, keepdims=True)
    good_q = (qn[:, 0] >= 1e-12)
    if not np.any(good_q):
        return set()
    q = q[good_q]
    qn = qn[good_q]
    sims = (q @ matrix.T) / (qn * mn.T + 1e-12)
    sims = np.nan_to_num(sims, nan=-np.inf, posinf=-np.inf, neginf=-np.inf)
    sims[:, ~usable] = -np.inf
    for ident in exclude:
        idx = graph.emb_index.get(ident)
        if idx is not None:
            sims[:, idx] = -np.inf
    # Best cosine any query assigns to a node, then top k.
    best = sims.max(axis=0)
    if k >= len(best):
        order = np.argsort(-best)
    else:
        part = np.argpartition(-best, k)[:k]
        order = part[np.argsort(-best[part])]
    chosen = []
    for idx in order:
        if not np.isfinite(best[idx]):
            continue
        chosen.append(graph.emb_ids[int(idx)])
        if len(chosen) >= k:
            break
    return set(chosen)


def arm_sets(graph: Graph, seeds: list[str], resid: np.ndarray, usable: np.ndarray) -> dict[str, set[str]]:
    seed_set = set(seeds)
    children: set[str] = set()
    siblings: set[str] = set()
    for ident in seeds:
        if graph.kind[ident] == "class":
            children.update(graph.children.get(ident, []))
        else:
            parent = graph.parent[ident]
            if parent is not None:
                siblings.update(graph.children.get(parent, []))
    siblings -= seed_set
    pset = children | siblings
    call: list[str] = []
    seen_call = set()
    for ident in seeds:
        for other in graph.callees.get(ident, []) + graph.callers.get(ident, []):
            if other in seed_set or other in seen_call:
                continue
            seen_call.add(other)
            call.append(other)
    k = len(pset) if pset else FIXED_K
    raw_queries = []
    res_queries = []
    for ident in seeds:
        idx = graph.emb_index.get(ident)
        if idx is None:
            continue
        raw_queries.append(graph.emb[idx])
        res_queries.append(resid[idx])
    ones = np.ones(len(graph.emb_ids), dtype=bool)
    return {
        "Z": set(seeds),
        "P": set(pset),
        "ZP": set(seeds) | set(pset),
        "C": set(call),
        "C50": set(call[:NEIGHBOR_CAP]),
        "E": topk_from_queries(graph, raw_queries, graph.emb, ones, seed_set, k),
        "R": topk_from_queries(graph, res_queries, resid, usable, seed_set, k),
        "_k": k,
        "_call_list": call,
    }


def cover(nodes: set[str], anchors: list[dict]) -> tuple[int, int, int]:
    """Return covered weight, alignable weight, task-hit among alignable hunks."""
    covered = 0
    alignable = 0
    hit = 0
    total = 0
    for anchor in anchors:
        alignable += anchor["weight"] if anchor["node"] else 0
        total += anchor["weight"]
        if anchor["node"] and anchor["node"] in nodes:
            covered += anchor["weight"]
            hit += 1
    return covered, alignable, hit


def random_cover(graph: Graph, exclude: set[str], k: int, anchors: list[dict], instance_id: str) -> float:
    pool = [ident for ident in graph.ids if ident not in exclude]
    if k <= 0 or not pool:
        return 0.0
    digest = hashlib.sha256(instance_id.encode()).hexdigest()
    rng = np.random.default_rng([RNG_SEED, int(digest[:8], 16)])
    draw_n = min(k, len(pool))
    alignable_nodes = [(a["node"], a["weight"]) for a in anchors if a["node"]]
    if not alignable_nodes:
        return 0.0
    acc = 0.0
    for _ in range(RANDOM_DRAWS):
        pick = set(rng.choice(pool, size=draw_n, replace=False).tolist())
        acc += sum(w for node, w in alignable_nodes if node in pick)
    return acc / RANDOM_DRAWS


def exclusive_bin(anchor_node: str, arms: dict[str, set[str]]) -> str:
    if anchor_node in arms["Z"]:
        return "named_body"
    if anchor_node in arms["P"]:
        return "sibling_or_child"
    if anchor_node in arms["C"]:
        return "call"
    if anchor_node in arms["R"]:
        return "residual_only"
    if anchor_node in arms["E"]:
        return "raw_cosine_only"
    return "none"


def micro(rows: list[dict], arm: str) -> dict:
    covered = sum(r["covered"][arm] for r in rows)
    alignable = sum(r["alignable"] for r in rows)
    all_w = sum(r["all_weight"] for r in rows)
    hits = sum(1 for r in rows if r["alignable"] and r["covered"][arm] > 0)
    tasks = sum(1 for r in rows if r["alignable"])
    return {
        "covered": covered,
        "alignable": alignable,
        "recall": (covered / alignable) if alignable else None,
        "recall_all": (covered / all_w) if all_w else None,
        "task_hits": hits,
        "tasks_with_anchor": tasks,
        "task_hit_rate": (hits / tasks) if tasks else None,
        "mean_set_size": float(np.mean([r["size"][arm] for r in rows])) if rows else None,
    }


def boot_diff(rows: list[dict], left: str, right: str, rng: np.random.Generator) -> dict:
    n = len(rows)
    if n == 0:
        return {"diff": None, "lo": None, "hi": None}
    point_l = micro(rows, left)["recall"]
    point_r = micro(rows, right)["recall"]
    point = None if point_l is None or point_r is None else point_l - point_r
    diffs = np.empty(N_BOOT)
    for i in range(N_BOOT):
        sample = [rows[j] for j in rng.integers(0, n, n)]
        a = micro(sample, left)["recall"]
        b = micro(sample, right)["recall"]
        diffs[i] = np.nan if a is None or b is None else a - b
    finite = diffs[np.isfinite(diffs)]
    if point is None or len(finite) == 0:
        return {"diff": point, "lo": None, "hi": None}
    lo, hi = np.quantile(finite, [0.025, 0.975])
    return {"diff": point, "lo": float(lo), "hi": float(hi)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cache: dict[str, Graph] = {}
    rows = []
    missing_graph = []
    how_counts: dict[str, int] = defaultdict(int)
    for line in TASKS.read_text().splitlines():
        if not line.strip():
            continue
        task = json.loads(line)
        instance = task["instance_id"]
        short = repo_short(task["repo"])
        commit = task["base_commit"]
        gpath = GRAPHS / f"{short}_{commit}.json"
        epath = EMBEDS / f"{short}_{commit}.npz"
        if not gpath.exists() or not epath.exists():
            missing_graph.append(instance)
            continue
        key = str(gpath)
        if key not in cache:
            cache[key] = Graph(gpath, epath)
            print(f"loaded {gpath.name} nodes={len(cache[key].ids)} emb_missing={cache[key].missing_emb}", file=sys.stderr)
        graph = cache[key]
        anchors = [align_hunk(graph, hunk) for hunk in parse_hunks(task["patch"])]
        for anchor in anchors:
            how_counts[anchor["how"]] += 1
        seeds = resolve_seeds(graph, task["problem_statement"])
        resid, usable = residual_matrix(graph)
        arms = arm_sets(graph, seeds, resid, usable)
        k = arms.pop("_k")
        arms.pop("_call_list")
        rand_covered = random_cover(graph, set(seeds), k, anchors, instance)
        covered = {}
        sizes = {}
        for name in ("Z", "P", "ZP", "C", "C50", "E", "R"):
            c, alignable, _hit = cover(arms[name], anchors)
            covered[name] = c
            sizes[name] = len(arms[name])
        covered["RAND"] = rand_covered
        sizes["RAND"] = k
        _, alignable, _ = cover(arms["Z"], anchors)
        all_weight = sum(a["weight"] for a in anchors)
        bins = []
        for anchor in anchors:
            if not anchor["node"] or anchor["weight"] == 0:
                continue
            bins.append({"node": anchor["node"], "weight": anchor["weight"], "bin": exclusive_bin(anchor["node"], arms), "how": anchor["how"]})
        held = "rich" if short == "rich" else "dev"
        rows.append(
            {
                "instance_id": instance,
                "repo": short,
                "split": held,
                "n_seeds": len(seeds),
                "seeds": seeds[:40],
                "k": k,
                "alignable": alignable,
                "all_weight": all_weight,
                "covered": covered,
                "size": sizes,
                "n_nodes": len(graph.ids),
                "n_with_parent": sum(1 for ident in graph.ids if graph.parent[ident]),
                "bins": bins,
                "zero_seed": len(seeds) == 0,
            }
        )
        print(f"{instance} seeds={len(seeds)} alignable={alignable} Z={covered['Z']} P={covered['P']} C={covered['C']} E={covered['E']} R={covered['R']}", file=sys.stderr)

    if missing_graph:
        raise SystemExit(f"missing graphs: {missing_graph[:8]}")

    def pool(name: str) -> list[dict]:
        if name == "dev":
            return [r for r in rows if r["split"] == "dev"]
        if name == "rich":
            return [r for r in rows if r["split"] == "rich"]
        if name == "all":
            return rows
        return [r for r in rows if r["repo"] == name]

    summary_pools = {}
    for name in ("dev", "rich", "fastapi", "requests", "httpx", "all"):
        group = pool(name)
        summary_pools[name] = {
            "tasks": len(group),
            "zero_seed_tasks": sum(1 for r in group if r["zero_seed"]),
            "alignable_lines": sum(r["alignable"] for r in group),
            "all_lines": sum(r["all_weight"] for r in group),
            "arms": {arm: micro(group, arm) for arm in PRIMARY_ARMS},
        }

    dev = pool("dev")
    ranking = sorted(
        ((summary_pools["dev"]["arms"][arm]["recall"] or -1, arm) for arm in WINNER_ARMS),
        reverse=True,
    )
    winner = ranking[0][1]
    rng = np.random.default_rng(RNG_SEED)
    contrasts = {}
    for split in ("dev", "rich"):
        group = pool(split)
        contrasts[split] = {
            "ZP_minus_Z": boot_diff(group, "ZP", "Z", rng),
            "R_minus_E": boot_diff(group, "R", "E", rng),
            "R_minus_C": boot_diff(group, "R", "C", rng),
            "Z_minus_C": boot_diff(group, "Z", "C", rng),
            "P_minus_C": boot_diff(group, "P", "C", rng),
        }

    bin_weight = defaultdict(lambda: defaultdict(int))
    for row in rows:
        for item in row["bins"]:
            bin_weight[row["split"]][item["bin"]] += item["weight"]
            # Rich is both a split and a repo. Count that weight once.
            if row["repo"] != row["split"]:
                bin_weight[row["repo"]][item["bin"]] += item["weight"]

    payload = {
        "protocol": {
            "ambiguity_cap": AMBIGUITY_CAP,
            "ambiguous_line_cap": AMBIGUOUS_LINE_CAP,
            "fixed_k": FIXED_K,
            "neighbor_cap_secondary": NEIGHBOR_CAP,
            "random_draws": RANDOM_DRAWS,
            "rng_seed": RNG_SEED,
            "min_line_chars": MIN_LINE_CHARS,
            "n_boot": N_BOOT,
            "winner_arms": list(WINNER_ARMS),
            "winner_rule": "max micro line-recall on non-Rich among winner arms",
            "issue_fields": ["problem_statement"],
            "ignored_fields": ["hints_text", "test_patch"],
        },
        "alignment_hunks": dict(how_counts),
        "winner_on_dev": winner,
        "dev_ranking": [{"arm": arm, "recall": rec} for rec, arm in ranking],
        "pools": summary_pools,
        "contrasts": contrasts,
        "exclusive_bins": {k: dict(v) for k, v in bin_weight.items()},
        "graph_cache": len(cache),
    }
    (OUT / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    with (OUT / "per_task.jsonl").open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    print(f"\nWinner on non-Rich: {winner}")
    header = f"{'pool':<10} {'lines':>7} " + " ".join(f"{arm:>8}" for arm in PRIMARY_ARMS)
    print(header)
    for name in ("dev", "fastapi", "requests", "httpx", "rich", "all"):
        block = summary_pools[name]
        cells = []
        for arm in PRIMARY_ARMS:
            rec = block["arms"][arm]["recall"]
            cells.append(f"{rec:8.3f}" if rec is not None else f"{'—':>8}")
        print(f"{name:<10} {block['alignable_lines']:7d} " + " ".join(cells))
    print("\nContrasts are micro-recall differences. Intervals are task bootstrap 95%.")
    for split, table in contrasts.items():
        print(split)
        for name, est in table.items():
            print(f"  {name}: {est['diff']:.3f} [{est['lo']:.3f}, {est['hi']:.3f}]" if est["diff"] is not None else f"  {name}: none")
    print("exclusive bins", {k: dict(v) for k, v in bin_weight.items()})
    print("alignment", dict(how_counts))


if __name__ == "__main__":
    main()
