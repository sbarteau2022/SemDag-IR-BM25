# Executor brief: parcels P0, P2, P3, P4

Read `PARCELS.md` first. It is the pre-registration; this brief only says how to produce the files it names. Do not change `build_dataset.py`, `validate.py`, `out/prompts.jsonl`, or `out/split.json`. If something in the protocol cannot be done as written, stop and report; do not improvise a substitute.

All outputs go in `PaperTrack/phase3_silo/out/`. Put your scripts in `PaperTrack/phase3_silo/exec/`. Use `.venv-mlx`. Do not restart or reconfigure the server on port 8123; load the model in your own process. Run Python with `PYTHONDONTWRITEBYTECODE=1`.

## Scoring one prompt

1. Build the chat with one user turn = `user_text`, apply the model's chat template with the generation prompt and **thinking disabled**, then append `assistant_prefix` verbatim.
2. LOC, ANA, VER: take the next-token log-probabilities at the last position. `cand_logprobs` = the raw log-prob of each string in `candidates`, in order. `score` = gold log-prob minus logsumexp over the candidates.
3. IMP: append `gold` after the prefix and teacher-force it. `score` = mean log-prob per gold token. `cand_logprobs` = null.
4. The capture position is the last token of the prefix (the position whose output is read in step 2, or that predicts the first gold token in step 3).

## P0 (time-box 45 minutes)

Write `p0_probe.json` with: `n_layers`, `d_model`, `model_sha256`, `tokenizer_sha256`, `thinking_disabled` (true), `candidate_token_ids` (map from each of `" A"`…`" H"`, `" Yes"`, `" No"` to its single token id after the `Answer:` prefix), `noop_max_abs_logit_diff`, `rerun_max_abs_logit_diff`, `ablation_max_abs_logit_diff`, `max_prompt_tokens` (true token count of the longest prompt), `seconds_per_forward` (median over 10 prompts).

If a candidate is not a single token after the prefix, stop and report: the prefix or candidates must change before the freeze, not after.

## P2

- `base_scores.jsonl`: one `base` row for every prompt in `prompts.jsonl` (all splits, both kinds).
- `acts_fit.npy` `[n,42,2560]` float32 with `acts_fit_ids.json` (prompt ids in row order) for every fit-split prompt, task and template-only. Same for dev: `acts_dev.npy`, `acts_dev_ids.json`.

## P3

- `mu[l]` = mean over all fit **task** activations at layer l (roles pooled).
- `role_<ROLE>[l]` = top-4 right singular vectors of that role's fit task activations minus `mu[l]`.
- `tmpl_<ROLE>[l]` = the same, from that role's template-only activations minus `mu[l]`.
- `rand_<seed>[l]` = 4 orthonormal vectors drawn with `numpy.random.default_rng(seed)` inside the top-64 principal span of all fit task activations minus `mu[l]` (Gaussian coefficients, then QR).
- Save all to `subspaces.npz` as `[42,2560,4]` arrays plus `mu`. Save `fit_ids.json` (the prompt ids used).
- Dev runs: for each band (early 6–11, middle 18–23, late 30–35), score every dev prompt under `role:LOC`, `role:ANA`, `role:IMP`, `role:VER`. Write `dev_scores.jsonl` including the dev `base` rows.
- Band choice: do not compute it yourself. Run `python3 validate.py p3` after writing a provisional `band_choice.json`; the validator recomputes the dev silo index per band and fails if your band is not the argmax. Fix `band_choice.json` to the band it reports, then rerun.

Ablation, exactly: at every layer in the band, on the block's output residual, at every token position, `h <- h - U (U^T (h - mu))`. Log `removed_energy` = mean over positions and band layers of `||U U^T (h - mu)||^2 / ||h - mu||^2`.

## P4

Only after `validate.py p3` passes. For every held-out prompt at the primary band, k = 4: `base`, four `role:`, four `tmpl:`, five `rand:` conditions. One `run_id` for all primary cells. Write `heldout_scores.jsonl`. Then the planned secondary cells (other bands; k = 1 and 16 with subspaces fitted the same way) appended with their own `run_id`.

## Receipts

After each parcel append one line to `out/receipts.jsonl`: parcel, command, start and end time, input and output SHA-256, row counts, status. Report failures and partial runs as they are. Do not rerun a held-out condition to get a different number; if a run crashed, say which cells are from the rerun.
