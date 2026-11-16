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
HERE = ROOT / "PaperTrack/phase3_silo"
prompts = {
    r["prompt_id"]: r for r in [json.loads(l) for l in (OUT / "prompts.jsonl").open()]
}
rows = [json.loads(l) for l in (OUT / "prompts.jsonl").open()]
base_scores = {
    json.loads(l)["prompt_id"]: json.loads(l)
    for l in (OUT / "base_scores.jsonl").open()
}  # not used

model, tok = mlx_lm.load(str(MODEL))
fit_ids_all = json.loads((OUT / "acts_fit_ids.json").read_text())
dev_ids_all = json.loads((OUT / "acts_dev_ids.json").read_text())
acts_fit = np.load(OUT / "acts_fit.npy")
acts_dev = np.load(OUT / "acts_dev.npy")
fid2idx = {pid: i for i, pid in enumerate(fit_ids_all)}
did2idx = {pid: i for i, pid in enumerate(dev_ids_all)}

ROLES = ["LOC", "ANA", "IMP", "VER"]
BANDS = {
    "early": list(range(6, 12)),
    "middle": list(range(18, 24)),
    "late": list(range(30, 36)),
}

# mu over fit task prompts
task_fit_ids = [pid for pid in fit_ids_all if prompts[pid]["kind"] == "task"]
mu_acts = (
    acts_fit[[fid2idx[pid] for pid in task_fit_ids]].mean(axis=0).astype(np.float64)
)  # [42,2560]
mu = mu_acts


# helper to svd top4
def top4(mat):
    # mat [n,2560] already centered
    if mat.shape[0] == 0:
        return np.zeros((2560, 4), dtype=np.float64)
    _, _, Vt = np.linalg.svd(mat, full_matrices=False)
    return Vt[:4].T.copy()


# role subspaces (fit task)
role_U = {r: np.zeros((42, 2560, 4), dtype=np.float32) for r in ROLES}
tmpl_U = {r: np.zeros((42, 2560, 4), dtype=np.float32) for r in ROLES}
for r in ROLES:
    r_task_ids = [pid for pid in task_fit_ids if prompts[pid]["role"] == r]
    r_tmpl_ids = [
        pid
        for pid in fit_ids_all
        if prompts[pid]["kind"] == "tmpl" and prompts[pid]["role"] == r
    ]
    for l in range(42):
        M = (
            acts_fit[[fid2idx[pid] for pid in r_task_ids], l, :].astype(np.float64)
            - mu[l]
        )
        role_U[r][l] = top4(M).astype(np.float32)
        M2 = (
            acts_fit[[fid2idx[pid] for pid in r_tmpl_ids], l, :].astype(np.float64)
            - mu[l]
        )
        tmpl_U[r][l] = top4(M2).astype(np.float32)

# rand subspaces
rand_U = {s: np.zeros((42, 2560, 4), dtype=np.float32) for s in range(5)}
# top-64 span of all fit task acts centered by mu
X = acts_fit[[fid2idx[pid] for pid in task_fit_ids]].astype(np.float64)  # [n,42,2560]
for l in range(42):
    Xc = X[:, l, :] - mu[l]  # [n,2560]
    _, _, Vt = np.linalg.svd(Xc, full_matrices=False)
    V64 = Vt[:64].T  # [2560,64]
    for seed in range(5):
        rng = np.random.default_rng(seed)
        coeffs = rng.normal(size=(64, 4))
        vecs = V64 @ coeffs  # [2560,4]
        Q, RR = np.linalg.qr(vecs)
        rand_U[seed][l] = Q[:, :4].astype(np.float32)

# save subspaces.npz
save = {}
save["mu"] = mu.astype(np.float32)
for r in ROLES:
    save[f"role_{r}"] = role_U[r]
    save[f"tmpl_{r}"] = tmpl_U[r]
for s in range(5):
    save[f"rand_{s}"] = rand_U[s]
np.savez(OUT / "subspaces.npz", **save)
fit_task_ids_list = [pid for pid in task_fit_ids]
(OUT / "fit_ids.json").write_text(json.dumps(fit_task_ids_list))

# intervene helpers
CAPTURE_ENERGY = None
CURRENT_U = None
CURRENT_MU = None
CURRENT_LAYERS = None
MODE_ABLATE = False

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
        Umx = mx.array(CURRENT_U[self.layer_idx].astype(np.float32))  # [2560,4]
        mux = mx.array(CURRENT_MU[self.layer_idx].astype(np.float32))
        diff = h - mux[None, None, :]
        coeff = diff @ Umx  # [b,s,4]
        proj = coeff @ Umx.T
        # removed energy per position
        removed = mx.sum(proj * proj, axis=-1)
        total = mx.sum(diff * diff, axis=-1)
        # mean over positions
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


def score_from_logits_and_prompt(r, full, prefix_ids, logits):
    if r["role"] == "IMP":
        return None  # handle separately
    last = logits[0, -1]
    logZ = float(mx.logsumexp(last))
    cand_lp = []
    for c in r["candidates"]:
        fullc = full + c
        base_ids = prefix_ids
        cids = tok.encode(fullc)
        tid = int(cids[-1])
        cand_lp.append(float(last[tid]) - logZ)
    arrc = np.array(cand_lp, dtype=np.float64)
    lse = float(np.log(np.exp(arrc - arrc.max()).sum()) + arrc.max())
    gi = r["candidates"].index(r["gold"])
    return float(cand_lp[gi] - lse), cand_lp


def score_imp_with_intervention(r):
    # returns score
    chat = apply_chat(r["user_text"])
    full = chat + r["assistant_prefix"]
    prefix_ids = tok.encode(full)
    gold = r["gold"]
    fullseq = full + gold
    full_ids = tok.encode(fullseq)
    arr = mx.array([full_ids])
    # energy accumulator
    global CAPTURE_ENERGY
    CAPTURE_ENERGY = {}
    logits = model(arr)  # intervention installed
    mx.eval(logits)
    # removed energy averaged over band layers
    re_vals = [CAPTURE_ENERGY[l] for l in CURRENT_LAYERS]
    removed_energy = float(np.mean(re_vals)) if re_vals else None
    # score
    n = len(full_ids) - len(prefix_ids)
    total = 0.0
    for k in range(n):
        pos = len(prefix_ids) - 1 + k
        gid = full_ids[len(prefix_ids) + k]
        lpos = logits[0, pos]
        lz = float(mx.logsumexp(lpos))
        total += float(lpos[gid]) - lz
    score = total / n if n else float("nan")
    return score, removed_energy


def score_simple_with_intervention(r):
    chat = apply_chat(r["user_text"])
    full = chat + r["assistant_prefix"]
    prefix_ids = tok.encode(full)
    arr = mx.array([prefix_ids])
    global CAPTURE_ENERGY
    CAPTURE_ENERGY = {}
    logits = model(arr)
    mx.eval(logits)
    re_vals = [CAPTURE_ENERGY[l] for l in CURRENT_LAYERS]
    removed_energy = float(np.mean(re_vals)) if re_vals else None
    sc, cand_lp = score_from_logits_and_prompt(r, full, prefix_ids, logits)
    return sc, removed_energy, cand_lp


# dev scores
dev_score_rows = []
# base rows for dev loaded below
# load base rows efficiently
base_rows_by_id = {}
for line in (OUT / "base_scores.jsonl").open():
    br = json.loads(line)
    if br["prompt_id"] in set(dev_ids_all):
        base_rows_by_id[br["prompt_id"]] = br

for pid in dev_ids_all:
    br = dict(base_rows_by_id[pid])
    br["band"] = None
    br["k"] = None
    dev_score_rows.append(br)

MODE_ABLATE = True
for band, layers in BANDS.items():
    CURRENT_LAYERS = set(layers)
    for r_name in ROLES:
        # set U/mu
        CURRENT_U = {l: role_U[r_name][l] for l in layers}
        CURRENT_MU = {l: mu[l] for l in layers}
        for pid in dev_ids_all:
            r = prompts[pid]
            if r["role"] == "IMP":
                sc, re = score_imp_with_intervention(r)
                cand_lp = None
            else:
                sc, re, cand_lp = score_simple_with_intervention(r)
            row = {
                "prompt_id": pid,
                "condition": f"role:{r_name}",
                "band": band,
                "k": 4,
                "score": sc,
                "cand_logprobs": cand_lp,
                "removed_energy": re,
                "run_id": None,  # will set after? dev has no single run_id requirement
            }
            dev_score_rows.append(row)
    print("band done", band, flush=True)

# assign run_ids? P3 doesn't require; leave None
with (OUT / "dev_scores.jsonl").open("w", encoding="utf-8") as fh:
    for row in dev_score_rows:
        fh.write(json.dumps(row) + "\n")

# band_choice provisional
(OUT / "band_choice.json").write_text(json.dumps({"band": "early", "k": 4}))
print("dev rows", len(dev_score_rows))
