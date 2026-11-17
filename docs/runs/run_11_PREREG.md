# run_11: v6.1 on 25 unseen public tasks, local MLX, no-network seatbelt

Written 2026-11-17 before the run started. Evidence label for results: **LIVE-MEASURED** (local MLX stand-in, not the scorer's L4/vLLM).

## Purpose

1. Baseline failure picture for v6 on tasks it has never seen, under the new telemetry, to drive the failure-based E4B dataset.
2. Prove the telemetry path end to end: proxy TTFT, per-step thinking vs budget, tool pass/fail, steps per task and inside tool calls, SQLite store, baked Docker image.

This is a measurement run, not a tuning run. Nothing is changed in response to its results before the run ends.

## Fixed conditions

- Arm **v6.1** = `AgenticSubmission/v6_1_budget` = `v6_impact` plus one change: `max_output_tokens` 16384 → 8192 (see the file header for the evidence). v6_impact stays frozen.
- Budget from the arm's `eval_config.yaml`: timeout 120 s, 40 tool calls, 5 min, 60 turns.
- Model: `~/models/gemma-4-e4b-it-qat-w4a16-mlx` via `mlx_lm.server` 0.32.2 on 127.0.0.1:8124, `--temp 0.2 --top-p 0.95`, thinking on. The client's sampling config overrides server defaults.
- Telemetry proxy on 8125 (`Tools/telemetry/llm_proxy.py`), store `results/telemetry.sqlite`.
- Harness: `swegemma 0.2.11`, Docker sandbox in **Docker Desktop** (not Colima), concurrency 1.
- Seatbelt: model server, proxy and harness all run under `Tools/seatbelt/no_network.sb` (loopback + Unix sockets only). Task containers run with `network_disabled=True`.
- Runner: `Tools/run_eval_seatbelt.sh AgenticSubmission/v6_1_budget results/run_11_v6_1_seatbelt25 results/run_11_ids.txt run_11_v6_1 v6.1`.

## Task roster (frozen)

Seeded draw (`random.Random(20261117)`) from the 106 public tasks that no previous run has touched, stratified by repo: 16 of 67 fastapi, 9 of 39 rich. List: `results/run_11_ids.txt`.

The remaining 81 never-run tasks stay reserved for the held-out set in `docs/frontier-loop/GOAL.md`.

## Metrics (all from the store; definitions in `Tools/telemetry/ingest.py`)

resolved; failure class; duration; steps per task; agent steps; tool calls and pass/fail per tool and per skill script; nested steps inside agent_tool calls; prompt/completion/cached tokens; peak context fraction of 32,768; thinking tokens per model step vs the 4,096 budget; TTFT, time to first action and decode tok/s per model call; first-edit time; ran tests; repro before edit; test environment missing deps.

## Known limits

- Local MLX does not enforce `thinking_budget` and local `swegemma eval` does not configure the scorer's events compaction (14,336 tokens). Both are measured, not reproduced.
- Docker installs test deps that the scorer's subprocess sandbox lacks, so the local pass rate is an upper bound.
- fastapi has never been run through the agent; no prior per-repo baseline exists for it.
- Public tasks are not the hidden set (which comes from private repos). Results describe failure modes, not a leaderboard estimate.

## Falsifiers for the telemetry

The telemetry is rejected if any of: proxy call count differs from the harness's `total_llm_calls` sum by more than 5%; any task's trace is missing; per-call proxy `completion_tokens` disagree with trace step metrics on matched calls; the external-network probe succeeds under the seatbelt.
