#!/usr/bin/env python3
import json
import time
import uuid
from pathlib import Path

import mlx.core as mx
import mlx_lm
import numpy as np

ROOT = Path("/Users/stewartbarteau/Desktop/Gemma4DevAgentCompetitionKaggle")
MODEL = Path("/Users/stewartbarteau/models/gemma-4-e4b-it-qat-w4a16-mlx")
OUT = ROOT / "PaperTrack/phase3_silo/out"
prompts = {
    r["prompt_id"]: r for r in [json.loads(l) for l in (OUT / "prompts.jsonl").open()]
}
heldout_ids = [
    r["prompt_id"]
    for r in [json.loads(l) for l in (OUT / "prompts.jsonl").open()]
    if r["split"] == "heldout"
]

model, tok = mlx_lm.load(str(MODEL))

# load subspaces
z = np.load(OUT / "subspaces.npz")
mu = z["mu"].astype(np.float64)
role_U = {r: z[f"role_{r}"] for r in ["LOC", "ANA", "IMP", "VER"]}
tmpl_U = {r: z[f"tmpl_{r}"] for r in ["LOC", "ANA", "IMP", "VER"]}
rand_U = {s: z[f"rand_{s}"] for s in range(5)}

ROLES = ["LOC", "ANA", "IMP", "VER"]
primary = json.loads((OUT / "band_choice.json").read_text())["band"]
BANDS = {
    "early": list(range(6, 12)),
    "middle": list(range(18, 24)),
    "late": list(range(30, 36)),
}
primary_layers = set(BANDS[primary])

# intervene state
MODE_ABLATE = True
CURRENT_U = None
CURRENT_MU = None
CURRENT_LAYERS = primary_layers
CAPTURE_ENERGY = None
import mlx_lm.models.gemma4_text as gt

orig_call = gt.DecoderLayer.__call__


def patched(
    self, x, mask=None, cache=None, per_layer_input=None, shared_kv=None, offset=None
):
    h, skv, off = orig_call(
        self,
        x,
        mask=mask,
        cache=cache,
        per_layer_input=per_layer_input,
        shared_kv=shared_kv,
        offset=offset,
    )
    global CAPTURE_ENERGY
    if MODE_ABLATE and self.layer_idx in CURRENT_LAYERS:
        Umx = mx.array(CURRENT_U[self.layer_idx].astype(np.float32))
        mux = mx.array(CURRENT_MU[self.layer_idx].astype(np.float32))
        diff = h - mux[None, None, :]
        coeff = diff @ Umx
        proj = coeff @ Umx.T
        removed = mx.sum(proj * proj, axis=-1)
        total = mx.sum(diff * diff, axis=-1)
        ratio = float(mx.mean(removed / (total + 1e-12)))
        if CAPTURE_ENERGY is not None:
            CAPTURE_ENERGY[self.layer_idx] = ratio
        h = h - proj
    return h, skv, off


gt.DecoderLayer.__call__ = patched


def apply_chat(user_text):
    msgs = [{"role": "user", "content": user_text}]
    return tok.apply_chat_template(
        msgs, add_generation_prompt=True, enable_thinking=False, tokenize=False
    )


def set_U(Ufull):
    global CURRENT_U, CURRENT_MU
    CURRENT_U = {l: Ufull[l] for l in primary_layers}
    CURRENT_MU = {l: mu[l] for l in primary_layers}


base_rows_by_id = {}
for line in (OUT / "base_scores.jsonl").open():
    br = json.loads(line)
    if br["prompt_id"] in set(heldout_ids):
        base_rows_by_id[br["prompt_id"]] = br

out_path = OUT / "heldout_scores.jsonl"
existing = []
if out_path.exists():
    existing = [json.loads(l) for l in out_path.open() if l.strip()]
run_ids = {r.get("run_id") for r in existing if r.get("run_id")}
run_id = sorted(run_ids)[0] if run_ids else str(uuid.uuid4())

# base rows (write once)
has_base = any(r.get("condition") == "base" for r in existing)
if not has_base:
    with out_path.open("a", encoding="utf-8") as fh:
        for pid in heldout_ids:
            br = dict(base_rows_by_id[pid])
            br["band"] = None
            br["k"] = None
            br["run_id"] = run_id
            fh.write(json.dumps(br) + "\n")
            fh.flush()

# completed prompts = those with all 13 ablated conditions
from collections import defaultdict

by = defaultdict(set)
for r in existing:
    if r.get("condition") != "base":
        by[r["prompt_id"]].add(r["condition"])
completed = {pid for pid in heldout_ids if len(by[pid]) == 13}
# remove partial ablated rows for incomplete prompts
if existing:
    keep = [
        r
        for r in existing
        if r.get("condition") == "base" or r["prompt_id"] in completed
    ]
    with out_path.open("w", encoding="utf-8") as fh:
        for r in keep:
            fh.write(json.dumps(r) + "\n")
pending = [pid for pid in heldout_ids if pid not in completed]
print(
    "completed", len(completed), "pending", len(pending), "run_id", run_id, flush=True
)


# helper to score one prompt given Ufull and band layers
def score_with_U(r, Ufull):
    global CAPTURE_ENERGY
    set_U(Ufull)
    chat = apply_chat(r["user_text"])
    full = chat + r["assistant_prefix"]
    prefix_ids = tok.encode(full)
    if r["role"] == "IMP":
        gold = r["gold"]
        fullseq = full + gold
        full_ids = tok.encode(fullseq)
        arr = mx.array([full_ids])
        CAPTURE_ENERGY = {}
        logits = model(arr)
        mx.eval(logits)
        re_vals = [CAPTURE_ENERGY[l] for l in primary_layers]
        removed_energy = float(np.mean(re_vals))
        n = len(full_ids) - len(prefix_ids)
        total = 0.0
        for k in range(n):
            pos = len(prefix_ids) - 1 + k
            gid = full_ids[len(prefix_ids) + k]
            lpos = logits[0, pos]
            lz = float(mx.logsumexp(lpos))
            total += float(lpos[gid]) - lz
        sc = total / n if n else float("nan")
        return sc, removed_energy, None
    else:
        arr = mx.array([prefix_ids])
        CAPTURE_ENERGY = {}
        logits = model(arr)
        mx.eval(logits)
        re_vals = [CAPTURE_ENERGY[l] for l in primary_layers]
        removed_energy = float(np.mean(re_vals))
        last = logits[0, -1]
        logZ = float(mx.logsumexp(last))
        cand_lp = []
        for c in r["candidates"]:
            cids = tok.encode(full + c)
            tid = int(cids[-1])
            cand_lp.append(float(last[tid]) - logZ)
        arrc = np.array(cand_lp, dtype=np.float64)
        lse = float(np.log(np.exp(arrc - arrc.max()).sum()) + arrc.max())
        gi = r["candidates"].index(r["gold"])
        sc = float(cand_lp[gi] - lse)
        return sc, removed_energy, cand_lp


# ablated conditions for pending prompts, appended incrementally
for idx, pid in enumerate(pending):
    r = prompts[pid]
    rows_to_write = []
    # role
    for role in ROLES:
        sc, re, clp = score_with_U(r, role_U[role])
        rows_to_write.append(
            {
                "prompt_id": pid,
                "condition": f"role:{role}",
                "band": primary,
                "k": 4,
                "score": sc,
                "cand_logprobs": clp,
                "removed_energy": re,
                "run_id": run_id,
            }
        )
    # tmpl
    for role in ROLES:
        sc, re, clp = score_with_U(r, tmpl_U[role])
        rows_to_write.append(
            {
                "prompt_id": pid,
                "condition": f"tmpl:{role}",
                "band": primary,
                "k": 4,
                "score": sc,
                "cand_logprobs": clp,
                "removed_energy": re,
                "run_id": run_id,
            }
        )
    # rand
    for s in range(5):
        sc, re, clp = score_with_U(r, rand_U[s])
        rows_to_write.append(
            {
                "prompt_id": pid,
                "condition": f"rand:{s}",
                "band": primary,
                "k": 4,
                "score": sc,
                "cand_logprobs": clp,
                "removed_energy": re,
                "run_id": run_id,
            }
        )
    with out_path.open("a", encoding="utf-8") as fh:
        for row in rows_to_write:
            fh.write(json.dumps(row) + "\n")
        fh.flush()
    if (idx + 1) % 5 == 0 or idx == len(pending) - 1:
        print(
            "completed prompts",
            len(completed) + idx + 1,
            "of",
            len(heldout_ids),
            flush=True,
        )
print("primary done", "run_id", run_id)
