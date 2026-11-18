# MEMORY.md: project memory index

Durable facts for future sessions. One line per fact, newest last in each section. Update at the end of every session. Details live in the linked files, not here.

## Rules from the owner
- Every session starts by reading README.md (this folder and the GitHub repo). (2026-11-18)
- Budget is fixed: 4 min/task, 300 s command timeout, max_output 16384, thinking 4096. Do not ask to change. (2026-11-17)
- Never tune or train on the public competition tasks; results must generalize to the hidden set.
- v6_impact stays frozen as the reference; new work goes in new version folders.
- Never zip `v0_baseline` (1-minute eval_config).

## Competition facts
- Model: `gemma-4-e4b-it-qat-w4a16-ct` only. Rules acceptance Nov 25; finals and Small Model Bonus Dec 2, 23:59 UTC. Details: `competition-constraints/`, `docs/SCORER_PARITY.md`.
- Scorer runs patched vLLM 0.19.1 on 4x L4, one task at a time, about 120 tasks in 12 h.
- `.sh`, `.bak`, `.pyc` and extensionless files fail submission validation.
- Skill scripts must find the repo from the wrapper file location, not a literal `/workspace` (Kaggle subprocess sandbox). `AgenticSubmission/v6_impact` has the working pattern.

## State (2026-11-18)
- Best measured: v6_impact 7/23 on paired23 (local MLX). v7 tied it. v8_ensemble 0/5 and times out at 4 min locally. See README.md and `docs/runs/`.
- No Kaggle submission yet. Kaggle L4 timing notebook never run.
- This folder is a git repo with no remote. GitHub `sbarteau2022/SemDag-IR-BM25` has only the Nov 12 paper and v4 commits, plus open PR #1 (swe_traj_v1 dataset). `MetaSuperIntelligenceLabs-GlobalHack-A-thon-SoloDevTrack` is an unrelated project.
- Local environment: port 8123 is sometimes taken by a ClickHouse container; use 8124 (model) and 8125 (proxy). fastapi tasks cannot be graded locally (arm64 pydantic-core mismatch).

## Data and training
- `LoRAData/final` (6,874 rows) is demoted: 72% derived from public eval tasks. Replacement design: `Designs/FAILURE_DRIVEN_DATASET.md`.
- `swe_traj_v1`: 791 synthetic verified trajectories (648 train / 41 val / 102 test_ood), built from AST bug injection in permissive repos, excluding fastapi, requests, rich, httpx. In `DataSets/swe_traj_v1/`.

## Model backends
- Local server is **vllm-metal** (vLLM 0.33 on MLX, owner decision 2026-11-18), flag set matches the scorer's; it is the runner default and the only local server (oMLX uninstalled and removed from the project 2026-11-18). It rejects `thinking_token_budget`, so the proxy drops it: thinking budget not enforced locally. mlx_lm and oMLX were used for runs 10 to 23. Notes: `results/server_bench/vllm_metal/NOTES.md`.
- NVIDIA NIM (build.nvidia.com) hosts no Gemma 4 E4B, only `google/gemma-4-31b-it`; free tier is about 1,000 credits a month and about 40 requests a minute; trial terms allow testing and evaluation only. A relay exists in the cloud project files (`nim_backend/`) but is not on this Mac yet. It is a proxy for the scorer, never a match.
