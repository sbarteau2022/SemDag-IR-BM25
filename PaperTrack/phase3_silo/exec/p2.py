#!/usr/bin/env python3
import json
import time
from pathlib import Path

import mlx.core as mx
import mlx_lm
import numpy as np

ROOT = Path("/Users/stewartbarteau/Desktop/Gemma4DevAgentCompetitionKaggle")
MODEL = Path("/Users/stewartbarteau/models/gemma-4-e4b-it-qat-w4a16-mlx")
OUT = ROOT / "PaperTrack/phase3_silo/out"
rows = [json.loads(l) for l in (OUT / "prompts.jsonl").open()]
model, tok = mlx_lm.load(str(MODEL))
CAPTURE = None
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
    global CAPTURE
    if CAPTURE is not None:
        CAPTURE[self.layer_idx] = h[:, -1, :]
    return h, skv, off


gt.DecoderLayer.__call__ = patched


def apply_chat(user_text):
    msgs = [{"role": "user", "content": user_text}]
    return tok.apply_chat_template(
        msgs, add_generation_prompt=True, enable_thinking=False, tokenize=False
    )


base_rows = []
fit_ids = []
dev_ids = []
fit_acts = []
dev_acts = []

for ri, r in enumerate(rows):
    chat = apply_chat(r["user_text"])
    full = chat + r["assistant_prefix"]
    prefix_ids = tok.encode(full)
    # capture
    CAPTURE = [None] * 42
    arr = mx.array([prefix_ids])
    logits = model(arr)
    mx.eval(logits, *CAPTURE)
    acts = np.stack(
        [np.array(CAPTURE[l].astype(mx.float32)).reshape(2560) for l in range(42)],
        axis=0,
    ).astype(np.float32)
    CAPTURE = None
    # score
    if r["role"] == "IMP":
        gold = r["gold"]
        fullseq = full + gold
        full_ids = tok.encode(fullseq)
        # sanity: gold tokens
        assert full_ids[: len(prefix_ids)] == prefix_ids
        gold_ids = full_ids[len(prefix_ids) :]
        arr2 = mx.array([full_ids])
        logits2 = model(arr2)
        mx.eval(logits2)
        n = len(gold_ids)
        total = 0.0
        for k, gid in enumerate(gold_ids):
            pos = len(prefix_ids) - 1 + k
            lpos = logits2[0, pos]
            lz = float(mx.logsumexp(lpos))
            total += float(lpos[gid]) - lz
        score = total / n if n else float("nan")
        cand_lp = None
    else:
        last = logits[0, -1]
        logZ = float(mx.logsumexp(last))
        base_ids = prefix_ids
        cand_ids = []
        cand_lp = []
        for c in r["candidates"]:
            cids = tok.encode(full + c)
            assert len(cids) - len(base_ids) == 1, (
                r["prompt_id"],
                c,
                len(cids) - len(base_ids),
            )
            tid = int(cids[-1])
            cand_ids.append(tid)
            cand_lp.append(float(last[tid]) - logZ)
        gi = r["candidates"].index(r["gold"])
        # score
        arrc = np.array(cand_lp, dtype=np.float64)
        lse = float(np.log(np.exp(arrc - arrc.max()).sum()) + arrc.max())
        score = float(cand_lp[gi] - lse)
    row = {
        "prompt_id": r["prompt_id"],
        "condition": "base",
        "band": None,
        "k": None,
        "score": score,
        "cand_logprobs": cand_lp,
        "removed_energy": None,
        "run_id": None,
    }
    base_rows.append(row)
    if r["split"] == "fit":
        fit_ids.append(r["prompt_id"])
        fit_acts.append(acts)
    elif r["split"] == "dev":
        dev_ids.append(r["prompt_id"])
        dev_acts.append(acts)
    if ri % 50 == 0:
        print("done", ri, len(rows), flush=True)

# write base_scores
with (OUT / "base_scores.jsonl").open("w", encoding="utf-8") as fh:
    for row in base_rows:
        fh.write(json.dumps(row) + "\n")

fit_arr = np.stack(fit_acts, axis=0).astype(np.float32)
dev_arr = np.stack(dev_acts, axis=0).astype(np.float32)
np.save(OUT / "acts_fit.npy", fit_arr)
np.save(OUT / "acts_dev.npy", dev_arr)
(OUT / "acts_fit_ids.json").write_text(json.dumps(fit_ids))
(OUT / "acts_dev_ids.json").write_text(json.dumps(dev_ids))
print("fit", fit_arr.shape, len(fit_ids), "dev", dev_arr.shape, len(dev_ids))
