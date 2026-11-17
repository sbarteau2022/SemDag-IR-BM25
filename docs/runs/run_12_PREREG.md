# run_12: ROADMAP Phase 0 baseline, stock E4B LoopAgent, generous budget

Written 2026-11-17 before the run started. Evidence label: **LIVE-MEASURED** (local MLX stand-in). Owner instruction: "Raise eval_config to ~30 min / ~60 calls / 500 turns; run swegemma eval (stock E4B, current LoopAgent, NO adapter) over ~10–15 tasks, then the full 129 if stable. GATE: baseline resolution_rate recorded in results/."

## Arm

- `AgenticSubmission/v5_loop_e4b`: the sample LoopAgent (coder → verifier, `max_iterations: 4`), made runnable on E4B. All changes are listed in its README.
- No adapter. Stock competition sampling: temp 0.2, top_p 0.95, max_output 16384, thinking 4096.
- `eval_config` (**local-only, never zipped**): timeout 300 s, 60 tool calls, 30 min, 500 turns. Guarded by `tests/test_submission_budgets.py`.

## Conditions

Same as run_11:
- `Tools/run_eval_seatbelt.sh` (no network).
- Docker Desktop.
- `mlx_lm.server` on 8124 behind the telemetry proxy on 8125.
- Concurrency 1.
- Post-run ingest, report and image.

## Roster (frozen)

- 15 tasks: seeded draw (`random.Random(20261117)`) from `results/paired23_ids.txt`, written to `results/run_12_ids.txt`.
- These are requests/rich/httpx tasks, all gradable locally.
- Paired references on the same ids already exist: v0 (run_02/05), v2 (run_04/06), v6 (run_10).

## Gate

`results/run_12_v5_loop15/summary.json` exists with `resolution_rate` over the 15 tasks, and the telemetry falsifiers from run_11 hold:
- Proxy vs harness call counts within 5%.
- A trace for every task.
- Token agreement except calls cancelled by a timeout.

## "Stable" (decides whether to extend toward the 129)

All of: 0 harness errors, every task produced a trace, no task killed by the 4 GiB memory limit.

The full 129 is **not** a meaningful local measurement until the fastapi grading defect (run_11) is fixed: 67 tasks would be scored as failures whatever the agent does. If stable, the extension is the 62 gradable public tasks; fastapi waits for the environment fix.

## Known limits

- Local MLX: no thinking-budget enforcement, no events compaction.
- Docker installs test deps the scorer lacks.
- 15 tasks is a small sample.
