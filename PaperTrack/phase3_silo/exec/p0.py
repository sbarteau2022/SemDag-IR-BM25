#!/usr/bin/env python3
import hashlib
import json
import statistics
import time
from pathlib import Path

import mlx.core as mx
import mlx_lm
import numpy as np

ROOT = Path("/Users/stewartbarteau/Desktop/Gemma4DevAgentCompetitionKaggle")
MODEL = Path("/Users/stewartbarteau/models/gemma-4-e4b-it-qat-w4a16-mlx")
OUT = ROOT / "PaperTrack/phase3_silo/out"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


model, tok = mlx_lm.load(str(MODEL))

# candidate token ids after Answer: prefix
rows = [json.loads(l) for l in (OUT / "prompts.jsonl").open()]
loc = [r for r in rows if r["role"] == "LOC"][0]
messages = [{"role": "user", "content": loc["user_text"]}]
chat = tok.apply_chat_template(
    messages, add_generation_prompt=True, enable_thinking=False, tokenize=False
)
full = chat + loc["assistant_prefix"]
cand_ids = {}
for c in [" A", " B", " C", " D", " E", " F", " G", " H", " Yes", " No"]:
    ids = tok.encode(full + c)
    base = tok.encode(full)
    assert len(ids) - len(base) == 1, (c, len(ids) - len(base))
    cand_ids[c] = int(ids[-1])

# max prompt tokens (true)
max_pt = 0
for r in rows:
    msgs = [{"role": "user", "content": r["user_text"]}]
    ch = tok.apply_chat_template(
        msgs, add_generation_prompt=True, enable_thinking=False, tokenize=False
    )
    fullp = ch + r["assistant_prefix"]
    n = len(tok.encode(fullp))
    if n > max_pt:
        max_pt = n

# no-op / rerun / ablation on first prompt
r = rows[0]
msgs = [{"role": "user", "content": r["user_text"]}]
chat = tok.apply_chat_template(
    msgs, add_generation_prompt=True, enable_thinking=False, tokenize=False
)
full = chat + r["assistant_prefix"]
ids = tok.encode(full)
arr = mx.array([ids])


def forward(a):
    logits = model(a)
    mx.eval(logits)
    return logits


# warm
l0 = forward(arr)

# rerun
l1 = forward(arr)
rerun = float(mx.max(mx.abs(l1 - l0)))

# no-op hook: monkeypatch layer identity
import mlx_lm.models.gemma4_text as gt

orig = gt.DecoderLayer.__call__


def noop(self, *a, **k):
    h, skv, off = orig(self, *a, **k)
    return h, skv, off


gt.DecoderLayer.__call__ = noop
ln = forward(arr)
gt.DecoderLayer.__call__ = orig
noop_diff = float(mx.max(mx.abs(ln - l0)))

# ablation: transform first 4 dims of hidden at every layer in early band
rng = np.random.default_rng(0)
U, _, _ = np.linalg.svd(rng.normal(size=(2560, 4)), full_matrices=False)
# U shape (4,2560)? use columns
Umat = np.zeros((2560, 4), dtype=np.float32)
# orthonormal via QR
A = rng.normal(size=(2560, 4)).astype(np.float32)
Q, R = np.linalg.qr(A)
Umat = Q[:, :4].astype(np.float32)
mu = np.zeros((2560,), dtype=np.float32)
Umx = mx.array(Umat)
mux = mx.array(mu)
orig2 = gt.DecoderLayer.__call__


def abl(
    self, x, mask=None, cache=None, per_layer_input=None, shared_kv=None, offset=None
):
    h, skv, off = orig2(
        self,
        x,
        mask=mask,
        cache=cache,
        per_layer_input=per_layer_input,
        shared_kv=shared_kv,
        offset=offset,
    )
    if self.layer_idx in set(range(6, 12)):
        diff = h - mux[None, None, :]
        coeff = diff @ Umx
        proj = coeff @ Umx.T
        h = h - proj
    return h, skv, off


gt.DecoderLayer.__call__ = abl
la = forward(arr)
gt.DecoderLayer.__call__ = orig2
abl_diff = float(mx.max(mx.abs(la - l0)))

# seconds per forward over 10 prompts
times = []
for r2 in rows[:10]:
    msgs = [{"role": "user", "content": r2["user_text"]}]
    ch = tok.apply_chat_template(
        msgs, add_generation_prompt=True, enable_thinking=False, tokenize=False
    )
    full2 = ch + r2["assistant_prefix"]
    a2 = mx.array([tok.encode(full2)])
    t0 = time.perf_counter()
    l = forward(a2)
    times.append(time.perf_counter() - t0)
sec_med = float(statistics.median(times))

out = {
    "n_layers": 42,
    "d_model": 2560,
    "model_sha256": sha_file(MODEL / "model.safetensors"),
    "tokenizer_sha256": sha_file(MODEL / "tokenizer.json"),
    "thinking_disabled": True,
    "candidate_token_ids": cand_ids,
    "noop_max_abs_logit_diff": noop_diff,
    "rerun_max_abs_logit_diff": rerun,
    "ablation_max_abs_logit_diff": abl_diff,
    "max_prompt_tokens": int(max_pt),
    "seconds_per_forward": sec_med,
}
(OUT / "p0_probe.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
