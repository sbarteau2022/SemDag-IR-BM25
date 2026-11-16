"""Independent audit of LoRAData/final: re-derives every invariant from the written files only."""

import collections
import json
import sys
from pathlib import Path

F = Path("/Users/stewartbarteau/Desktop/Gemma4DevAgentCompetitionKaggle/LoRAData/final")
rows = {
    sp: [json.loads(l) for l in open(F / f"{sp}.jsonl")]
    for sp in ("train", "dev", "test")
}
allr = [r for rs in rows.values() for r in rs]
print("rows:", {k: len(v) for k, v in rows.items()}, "total", len(allr))

# --- 1. unit cap: per (split, family, subtype, unit) <= 40, using the unit written on the row
viol = collections.Counter()
worst = (0, None)
for sp, rs in rows.items():
    g = collections.defaultdict(int)
    for r in rs:
        g[(r["family"], r["subtype"], r["unit"])] += 1
    for k, n in g.items():
        if n > worst[0]:
            worst = (n, (sp,) + k)
        if n > 40:
            viol[f"unit {k} -> {n}"] += 1
print("\nunit-cap violations (>40):", len(viol), list(viol)[:5] or "none")
print("largest unit group:", worst)

# --- 2. repo cap per split
for sp, rs in rows.items():
    c = collections.Counter(r["repo"] for r in rs)
    top = c.most_common(3)
    shares = {k: round(v / len(rs), 3) for k, v in top}
    over = {k: v for k, v in shares.items() if v > 0.60 + 1e-9}
    print(f"{sp}: n={len(rs)} top={shares} OVER CAP: {over or 'none'}")

# --- 3. task disjointness across splits (the split law)
tasks = collections.defaultdict(set)
for sp, rs in rows.items():
    for r in rs:
        tasks[r["task"]].add(sp)
leak = {t: sorted(s) for t, s in tasks.items() if len(s) > 1}
real_leak = {t: v for t, v in leak.items() if t != "synthetic"}
print("\nreal tasks spanning >1 split:", len(real_leak), list(real_leak)[:5] or "none")
print(
    "'synthetic' spans splits as expected (generated rows are split by rng seed, not a task):",
    "synthetic" in leak,
)

# --- 4. mask + record invariants on every row
viol = collections.Counter()
for r in allr:
    ids, labels = r["input_ids"], r["labels"]
    if len(ids) != len(labels):
        viol["len"] += 1
        continue
    if r["n_tokens"] != len(ids):
        viol["n_tokens_field"] += 1
    if r["n_targets"] != sum(1 for x in labels if x != -100):
        viol["n_targets_field"] += 1
    if not any(x != -100 for x in labels):
        viol["no_targets"] += 1
    if labels[0] != -100:
        viol["bos_not_masked"] += 1
    if r["n_tokens"] > 32768:
        viol["over_ceiling"] += 1
    if any(l != -100 and l != ids[k] for k, l in enumerate(labels)):
        viol["label_id_mismatch"] += 1
print("\nmask violations:", dict(viol) or "none")

# --- 5. id uniqueness + dedup
ids = collections.Counter(r["id"] for r in allr)
dups = {k: v for k, v in ids.items() if v > 1}
print("duplicate ids:", len(dups) or "none")
texts = collections.Counter(r["text"] for r in allr)
print("duplicate rendered texts:", sum(v - 1 for v in texts.values() if v > 1))

# --- 6. token-level check on a large sample: user turns and tool responses are masked
sys.path.insert(
    0, "/Users/stewartbarteau/Desktop/Gemma4DevAgentCompetitionKaggle/LoRAData/gen"
)
from render import TR_CLOSE, TR_OPEN, char_span
from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained(
    "/Users/stewartbarteau/Desktop/Gemma4DevAgentCompetitionKaggle/LoRAData/reference"
)
op_id = tok(TR_OPEN, add_special_tokens=False)["input_ids"][0]
cl_id = tok(TR_CLOSE, add_special_tokens=False)["input_ids"][0]
sample = allr if len(allr) <= 1500 else allr[:: len(allr) // 1500]
breach = 0
checked = 0
for r in sample:
    enc = tok(r["text"], add_special_tokens=False, return_offsets_mapping=True)
    ids = enc["input_ids"]
    labels = r["labels"]
    if ids != r["input_ids"]:
        breach += 1
        print("  TOKENIZER DRIFT on", r["id"])
        continue
    offs = enc["offset_mapping"]
    k, bad = 0, 0
    while k < len(ids):
        if ids[k] != op_id:
            k += 1
            continue
        j = k + 1
        while j < len(ids) and ids[j] != cl_id:
            j += 1
        if any(x != -100 for x in labels[k : j + 1]):
            bad += 1
        k = j + 1
    u = r["text"].index("<|turn>user\n")
    nxt = r["text"].find("<|turn>model\n")
    if nxt > u:
        a, b = char_span(offs, r["text"], u, nxt)
        if any(x != -100 for x in labels[a:b]):
            bad += 1
    breach += bad
    checked += 1
print(f"\nsampled {checked} rows: tool-response/user-turn mask breaches: {breach}")
print("AUDIT DONE")
