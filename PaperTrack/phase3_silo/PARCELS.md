# Phase 3: role-silo probe on frozen Gemma 4 E4B

Status: DRAFT pre-registration, written 2026-11-11 before any Phase 3 run. Freeze it (record its SHA-256 in `out/manifest.json`) before P2 starts. After the freeze, changes are appended as dated amendments, never edited in place.

Paper deadline: Nov 12, 23:59 UTC (5:59 PM Central). Working target 5:30 PM Central.

## Question

In the frozen base model, do the four agent roles (localization, analysis, implementation, verification) depend on causally separable residual-stream subspaces, or on one shared subspace?

This is the Phase 0 / H2 precondition named in `Designs/SharedLoRABank/design.md`. It decides whether role-specific sparse LoRA gates have anything separable to steer. No adapter is trained here and no adapter result may be claimed from it.

## What is measured

Four single-forward-pass probes built from the 129 public tasks. Each prompt has one scored readout, so no sampling and no generation.

| Role | Prompt content | Label source | Score (higher is better) |
|---|---|---|---|
| LOC | Issue text + 8 candidate file paths, lettered A–H | Gold = a non-test `.py` file changed by `patch`; 7 distractors drawn from the non-test `.py` files changed by other public tasks of the same repository (the graphs carry no file paths) | log-prob of the gold letter, normalised over the 8 letters |
| ANA | Source of function `f` + "does `f` directly call `g`?" | Positive = a `calls` edge in the task graph; negative = same-file non-neighbour | log-prob of the correct Yes/No, normalised over the two |
| IMP | Issue text + pre-patch hunk window | First substantive added line of `patch` (stripped length >= 3, same rule as Phase 1) | mean per-token log-prob of that line, teacher-forced |
| VER | Issue text + a diff + "does this diff address this issue?" | Positive = the task's own `patch`; negative = `patch` of another task in the same repo | log-prob of the correct Yes/No, normalised over the two |

Rules:
- `hints_text` and `test_patch` are never read. `patch` is used only as a probe label or probe content. Nothing here is agent input, and no probe prompt may be reused as training data for a scored adapter without a new split review.
- Two paraphrase templates per role, T1 and T2. Subspaces are fitted on T1; every reported effect is measured on T2.
- Per task: 1 LOC, 2 ANA (1 positive, 1 negative), 1 IMP, 2 VER (1 positive, 1 negative). A task that cannot supply an item is skipped for that role and listed in `skips.jsonl` with a reason. Skips are never silently dropped.
- Candidate order and distractor choice are seeded (seed 0). Gold letter position must be close to uniform.
- Prompt cap 5,000 characters (no tokenizer is used at build time). Issue text over 1,600 characters is cut from the middle; diffs over 2,600 characters are cut at a line boundary. The question is never cut. P0 reports the true token count of the longest prompt.
- Fit tasks get T1 prompts plus a template-only twin; dev and held-out tasks get T2 prompts only.
- Readout convention: chat template with thinking disabled, then an assistant prefix (`Answer:` for LOC, ANA, VER; a code fence for IMP). Candidates are scored as the next token after the prefix.

## Split (frozen before any model call)

- Fit: `fastapi/fastapi` (67 tasks). Inside it, a dev fold of 20 tasks chosen by sorted SHA-256 of `instance_id`; the other 47 fit the subspaces.
- Held-out: `Textualize/rich` (48), `psf/requests` (13), `encode/httpx` (1). httpx has no same-repo negative, so it is skipped for VER.
- The held-out split is read once, at P4, with everything else frozen.

## Capture and intervention

- Model: the local MLX 4-bit repack of `gemma-4-e4b-it-qat-w4a16-ct`. The paper names it as that repack, not as the CUDA checkpoint.
- Capture: residual stream after each of the 42 blocks at the readout position (last prompt token). Store float32, shape `[n_prompts, 42, 2560]`.
- Role subspace `U[r, l]`: top k = 4 principal directions of the role-r fit activations at layer l after subtracting the all-role mean `mu[l]`. k = 4 is primary; k = 1 and k = 16 are secondary and reported as such.
- Ablation: at every layer of one 6-layer band and at every token position, `h <- h - U U^T (h - mu)`.
- Band candidates: early 6–11, middle 18–23, late 30–35. The primary band is the one with the largest silo index on the dev fold. The other two are secondary.

## Controls

| Control | Construction | What it rules out |
|---|---|---|
| RAND | 5 random orthonormal k-subspaces (seeds 0–4) drawn inside the top-64 PCA span of all fit activations, same ablation | "Any rank-4 removal hurts this much" |
| TMPL | Subspace fitted the same way on template-only prompts: the role's T1 wording with the content block replaced by length-matched shuffled tokens | "The subspace is the instruction wording, not the operation" |
| Paraphrase + repo transfer | Fit on T1 / FastAPI, measure on T2 / other repos (this is the primary measurement) | Memorised template or repository |
| No-op hook | Hook installed, nothing removed | Hook itself changes logits |

Removed energy (`||U U^T (h - mu)||^2 / ||h - mu||^2`, averaged over positions) is logged for every condition so effect size can be read against how much was removed.

## Endpoint (fixed now)

- `D(s <- c)` = mean over held-out role-s prompts of `score_base - score_ablated(c)`, divided by the SD of the base score for role s.
- `N(s <- r)` = `D(s <- r)` minus the mean of `D(s <- RAND)` over the 5 seeds.
- **Silo index** `SI` = mean of the diagonal `N(r <- r)` minus mean of the off-diagonal `N(s <- r), r != s`.
- Uncertainty: paired bootstrap over tasks, 4,000 resamples, seed 0, 95% interval.

Claim rules:
1. "Siloed" only if the SI interval excludes 0 **and** the mean TMPL diagonal is under 50% of the mean role diagonal.
2. If the interval includes 0: report "no separable role subspaces detected at rank 4 in this band".
3. If TMPL reproduces the effect: report "lexical, not operational".
4. A role is "probed" only if, on held-out base runs, the share of its items that put more than chance probability on the gold answer (1/8 for LOC, 1/2 for ANA and VER) has a bootstrap lower bound above one half. Otherwise it is removed from both the rows and the columns of SI and reported as unprobed. IMP has no chance level; it is kept and its base score reported. The exact computation is `validate.py::stats`.
5. The full 4x4 matrix, every control, and every skip are published whatever the outcome.

## Parcels

Each parcel writes into `PaperTrack/phase3_silo/out/` and ends with a receipt line in `out/receipts.jsonl`: parcel id, command, input digests, output digests, counts, status. A parcel is not done until its gate passes.

| ID | Work | Needs model | Output | Gate (checked by the validator, not by the parcel's author) |
|---|---|---|---|---|
| P0 | Capture feasibility: hook the 42 blocks, capture 2 prompts, run a no-op hook and one ablation. Time-box 45 min. | yes | `p0_probe.json` | No-op logits equal base within 1e-4; two runs identical; ablation changes logits |
| P1 | Deterministic dataset build from `tasks.jsonl` + graphs | no | `prompts.jsonl`, `split.json`, `skips.jsonl` | Repo-disjoint split; counts match; no `hints_text` / `test_patch` text; label balance; gold-letter spread; cap respected; digest recorded |
| P2 | Base scores and captures for all prompts | yes | `base_scores.jsonl`, `acts_fit.npy`, `acts_dev.npy` | One row per prompt; no missing ids; chance comparison computed |
| P3 | Fit `mu`, `U` (roles, TMPL), RAND draws; choose band on dev | yes (dev ablations) | `subspaces.npz`, `dev_matrix.json`, `band_choice.json` | `U^T U = I` within 1e-5; fit ids are a subset of the 47; band chosen before P4 |
| P4 | Held-out ablations: base + 4 role + 4 TMPL + 5 RAND at the primary band, T2 templates | yes | `heldout_scores.jsonl` | Every (prompt, condition) cell present; removed energy logged; no fit or dev id present |
| P5 | Statistics and one figure (4x4 matrix with controls) | no | `stats.json`, `matrix.png` | Independent recomputation from `heldout_scores.jsonl` matches to 1e-9 |
| P6 | Standalone paper built on this probe (decision 2026-11-11: the Phase 1 and 2 record is not submitted) | no | Kaggle writeup | Every number maps to a file and digest; total under 3,000 words |

Fallback for P0: if MLX cannot hook this checkpoint inside the time-box, run P0–P4 with `transformers` on a Kaggle L4x4 notebook against the CUDA checkpoint and say so in the paper. If neither works by the freeze time below, Phase 3 is reported as a pre-registered design with no result.

Planned secondary analyses, run after the primary P4 cells are complete and labelled secondary in the paper: the other two bands at k = 4, and k = 1 and 16 at the primary band. Together they give a layer-by-rank map of where role damage concentrates.

Stretch, only if the result freeze allows: a small LoRA pilot on a Kaggle L4x4 notebook comparing an adapter restricted to the primary band with one restricted to a matched non-primary band. It needs its own short pre-registration before it starts.

## Schedule (Central time, Nov 12)

- P0 and P1 first, in parallel. P2–P3 follow overnight.
- P4 complete by 9:00 AM.
- Result freeze 11:00 AM: no new runs enter the paper after this.
- Draft complete 3:00 PM. Number audit 3:00–4:30 PM. Submit by 5:00 PM.

## Row formats

`prompts.jsonl`: `prompt_id, item_id, instance_id, repo, split (fit|dev|heldout), role, template (T1|T2), kind (task|tmpl), user_text, assistant_prefix, candidates, gold, neg_source, n_chars, n_tokens_est`.

`base_scores.jsonl`, `dev_scores.jsonl`, `heldout_scores.jsonl`: `prompt_id, condition (base|role:<ROLE>|tmpl:<ROLE>|rand:<seed>), band (early|middle|late, null for base), k (null for base), score, cand_logprobs (raw log-probs in candidate order; null for IMP), removed_energy (null for base), run_id`.

Other P2–P3 files: `acts_fit.npy` + `acts_fit_ids.json`, `acts_dev.npy` + `acts_dev_ids.json`, `subspaces.npz` (`mu` [42,2560]; `role_<ROLE>`, `tmpl_<ROLE>`, `rand_<seed>` each [42,2560,k]), `fit_ids.json`, `band_choice.json` (`band`, `k`).

`out/manifest.json`: SHA-256 of this file, `tasks.jsonl`, the model weights, tokenizer, and every script, plus the frozen seeds.

## Build record

- 2026-11-11: P1 built by `build_dataset.py` and passed `validate.py p1`. 1,042 prompts, 11 skips. Held-out usable items: LOC 59, ANA 124, IMP 58, VER 122. Digests are in `out/split.json`.
- Known limits to state in the paper: an ANA positive can often be answered by finding the callee's name in the shown source; 7 of 122 IMP gold lines already occur somewhere in their prompt; LOC distractors are files touched by other public tasks, so they are plausible but not exhaustive.
