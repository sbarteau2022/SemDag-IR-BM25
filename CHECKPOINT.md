# CHECKPOINT: 2026-11-12, SemDAG repair

Resume point for the next session. Rules and layout are in [AGENTS.md](AGENTS.md).

## Current priority

- Paper draft: `PaperTrack/Paper_SemDAG.md`, rewritten around the corrected
  result: source retrieval supplies query relevance; a light typed SemDAG walk
  is statistically level at function localization and improves file context.
- Production candidate: `AgenticSubmission/v4_semdag/`. Directory validation,
  adversarial contracts, full 129-task offline localization, full-snapshot
  parity, and a real Requests snapshot smoke pass.
- Historical agent evidence remains `v0_baseline` versus `v2_bm25`; Axe 4 reads
  the real traces. No paired agent run of `v4_semdag` exists yet.
- No Kaggle submission has been made. The Paper Track deadline is today,
  November 12, 2026 at 11:59 PM UTC.

## Done
- Workspace folders created. Rules audited: `Rules/Overview/Competition_Audit.md`, `Evaluation_Rules_Full.md`, `Model_Choice.md`.
- Dataset downloaded (22 GB zip verified), extracted to `DataSets/public/data/` (129 tasks, snapshots, graphs, embeddings, 124 wheels).
- Docker image `swebench-sandbox:latest` built and smoke-tested (Python 3.13, git, pytest, shims, wheels).
- swegemma 0.2.11, adk_submission 0.2.13, adk_eval_core 0.1.0 installed in `.venv-harness`. `swegemma eval --help` works.
- Baseline submission `AgenticSubmission/v0_baseline/` (E4B, full official `system.md`, no adapters) passes `validate_directory`.
- CUDA checkpoint converted losslessly to MLX 4-bit: `~/models/gemma-4-e4b-it-qat-w4a16-mlx`. Generates correct code; tool calls parse.
- Local server `Tools/serve_e4b_mlx.sh` on `127.0.0.1:8123` (temp 0.2, top_p 0.95, max tokens 4096). Last seen running.
- Zed: provider `gemma4-e4b-mlx` and agent profile `gemma4-competition` (tools: terminal, read_file, edit_file, write_file; reasoning effort low). Settings backups sit beside `~/.config/zed/settings.json`.
- Memory notes saved in the Claude project memory folder (decisions, status, forum findings).

## Not done / blocked
- `v4_semdag` has not run through the model harness. Its present evidence is
  offline localization, parity, package validation, adversarial checks, and a
  direct real-snapshot runtime smoke.
- Thinking budget (4096) can't be enforced locally; `mlx-lm` has no equivalent. A small proxy was offered, not built.
- Paper Track: corrected measured draft exists at `PaperTrack/Paper_SemDAG.md`;
  public notebook URL and submission remain open.
- No LoRA adapter for E4B exists. Training must run on a Kaggle L4x4 notebook.
- Small Model Prize deadline unconfirmed.
- Chrome extension was not connected; the built-in browser (logged in to Kaggle) worked.

## Plan (go big)
1. Finalize the paper artifact and replace its public-notebook placeholder.
2. Run `v4_semdag` and `v2_bm25` on identical tasks, then analyze both with Axe 4.
3. Improve edit application and targeted behavioral verification, the current
   downstream bottlenecks.
4. Submit only after explicit user approval.

## Open questions for the user
- Whether to prioritize the Paper Track submission or a paired `v4_semdag`
  harness run before the deadline.
