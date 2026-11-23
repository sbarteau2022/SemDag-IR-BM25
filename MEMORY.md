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
- v9_recurrent run_24 vllm-metal smoke resolved 0/2; both tasks timed out at about 244-245 seconds. Full host suite: 147 passed, 3 warnings. (2026-11-18)
- run_24 edit failures were never whitespace: 4/6 stale text from before the model's own successful edit, 2/6 hallucinated anchors from the code_editor sub-agent (which had no skill access). Audit: `docs/audit_2026-11-19.md`. (2026-11-19)
- v10_edit_rescue run_25 smoke: 1/3 resolved (requests_7315), edit_file 5/6 ok; rich_3506 failed on a wrong fix, httpx_3672 timed out. Full host suite 163 passed. (2026-11-19)
- v11_task_ir (2026-11-20): the issue is typed (frames, literals, qualnames) and anchored before BM25; fix_edit line ranges are the only edit path. E4B needed fix_edit to accept one packed string and escaped `\n`, and could not count lines from read_file (removed). Smoke run_28: 1/3, and that one resolve is an empty patch. Results: `docs/runs/run_26_28_RESULTS.md`.
- Rules allow 31B and 12B; one model per submission; the Small Model Bonus needs E2B/E4B as one of the two finals, so the other final may use a larger model. E4B-only is a project choice. Quotes: `docs/runs/run_25_RESULTS.md`. (2026-11-19)
- The project is published to `sbarteau2022/SemDag-IR-BM25`; local `main` tracks the remote interview-review branch until the owner changes the default branch. (2026-11-18)

## Data and training
- `LoRAData/final` (6,874 rows) is demoted: 72% derived from public eval tasks. Replacement design: `Designs/FAILURE_DRIVEN_DATASET.md`.
- `swe_traj_v1`: 791 synthetic verified trajectories (648 train / 41 val / 102 test_ood), built from AST bug injection in permissive repos, excluding fastapi, requests, rich, httpx. In `DataSets/swe_traj_v1/`.

## Model backends
- Local server is **vllm-metal** (vLLM 0.33 on MLX, owner decision 2026-11-18), flag set matches the scorer's; it is the runner default and the only local server (oMLX uninstalled and removed from the project 2026-11-18). It rejects `thinking_token_budget`, so the proxy drops it: thinking budget not enforced locally. mlx_lm and oMLX were used for runs 10 to 23. Notes: `results/server_bench/vllm_metal/NOTES.md`.
- NVIDIA NIM (build.nvidia.com) hosts no Gemma 4 E4B, only `google/gemma-4-31b-it`; free tier is about 1,000 credits a month and about 40 requests a minute; trial terms allow testing and evaluation only. A relay exists in the cloud project files (`nim_backend/`) but is not on this Mac yet. It is a proxy for the scorer, never a match.

- v13_orchestrator qualified/tested 2026-11-22 with E4B only, no Docker, macOS Seatbelt/subprocess. Fixed hardlink cross-slot/central mutation, explicit slot paths, owner editor budgets, packed workspace args and skill docs. Host suite 217 passed; external Dask empty/reference gate verified (2 fail/43 pass vs 45 pass). Two valid same-task runs 0/1 each with empty patches, latter timed out at 241.44s; auth-only attempt excluded. No task-resolution gain or promotion. See docs/runs/v13_QUALIFICATION_2026-11-22.md.

- v13 edit/tool/policy follow-up (2026-11-22): component probes accepted off-span edit, stale central overwrite and stale-coordinate duplicate insertion. Native transaction/fused lifecycle design proposed in .10x/specs/2026-11-22-v13-edit-tool-policy.md; awaiting approval before implementation. Subagent-policy thresholds must follow successful-edit timings; missing official tool-envelope keys cannot be repaired inside an uncalled skill script.
