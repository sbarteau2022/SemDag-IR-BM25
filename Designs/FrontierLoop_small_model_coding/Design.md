# Design: Small-Model Coding Agent Improvement (Frontier Loop)

Goal metric: dev-task solve rate on the 129-task SWE-style set, single E4B base model.

## Key audit finding

On paired v4/v5/v6 evidence, edit failure, not localization, is the bottleneck: 0 of 4 tasks solved when an edit failed vs 7 of 19 when none failed. Structural tools improve localization by exposure but 4B conversion remains ~0.24 (pre-registered study, Gemma 4 E2B-12B / Qwen3).

## Preprint-backed leverage

1. Edit-interface decomposition (SWE-Edit, arXiv:2604.26102v2): Viewer + Editor subagents +12.5pp edit success via GRPO edit-format selection.
2. Collaborative small components (Co-PatcheR, arXiv:2505.18955v2): 3 x 14B specialized components beat monolithic 70B.
3. Dense repair rewards (TaPR, arXiv:2608.00494v1): +2.44pp pooled, +3.31pp 7/8B.
4. Workflow alignment (SEAlign, arXiv:2503.18455v1), live scaffolds (Live-SWE-agent), history-guided collection (SWE-Trail).

## Proposed scaffold change

- Keep v6 localization/verify unchanged.
- Add Viewer->Editor decomposition and edit-format decision (find-replace vs whole-file vs rescue @-blocks).
- Train (Kaggle CUDA): LoRA GRPO on E4B using PR-Edit-style edit-success reward + dense per-turn test-pass reward.

## Hardening items 1-3

1. Edit conversion:
   - Viewer/Editor decomposition (already wired in agent.yaml + prompts).
   - Build PR-Edit eval: 274 mechanical corruptions x 3 edit formats; reward edit success exact-byte match after edit/fix_edit.
   - Train GRPO on E4B in Kaggle with format reward; expected +5-12pp (SWE-Edit +12.5 on 8B).

2. Repair reward density (TaPR):
   - Define multi-turn trajectory log (tool calls, test pass ratio per turn).
   - Replace single-shot reward with per-turn test-pass-ratio + final solve.
   - Reward hypothesis-support read actions with small positive weight.

3. Alignment target (SEAlign):
   - Build task bundles from real SWE dev issues, not competitive-programming data.
   - MCTS-style preference pairs over workflow steps: localize, read callers, edit, verify.
   - Train LoRA on E4B (rank >= 16) with EWC against coding baseline.

## Success criterion

Dev-set solve rate +5pp over v6 baseline in paired run before any Kaggle submission.
