# v3_attack: v2_bm25 with the how-to-attack policy prompt (Designs/attack_policy v1.0.0)

- Base model: `gemma-4-e4b-it-qat-w4a16-ct`, one model for the root agent and its analyzer sub-agent. No adapter.
- Tools: the nine harness tools, unchanged from `v0_baseline`.
- Added: one ADK skill, `skills/locate`. `scripts/locate.py` parses every non-test Python file under `/workspace` with the standard library, scores each function against the issue text with BM25, and prints the top candidates as `path:start-end qualified.name`. It reads files only.
- Prompt: the official system prompt plus the seven-rule attack policy. Candidate: not yet shown to beat v2_bm25.
- Budgets: `eval_config.yaml` (5 min, 40 tool calls, 60 turns per task).

Measured (see `PaperTrack/Paper_SemDAG.md`): on the 129 public tasks the same retrieval puts a gold edit function in the top 5 on 58 of 116 tasks. Agent-level results are in `results/`.

Not done: no run on the scored CUDA checkpoint, no Kaggle submission.
