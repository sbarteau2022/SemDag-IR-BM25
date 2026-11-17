# Lane runs: v7_brigade_lite per repository lane (loop 1)

Written 2026-11-17 before any v7 run. Evidence: **LIVE-MEASURED** (local MLX stand-in). Owner direction: small, independent runs per lane, so failures can be attributed per lane.

## Conditions

- **Arm:** `AgenticSubmission/v7_brigade_lite` (commit `1fbde53`). Submittable budget: 120 s per command, 40 calls, 5 min, 60 turns.
- **Runner:** `Tools/run_eval_seatbelt.sh` (no network), Docker Desktop, MLX on 8124 behind the telemetry proxy on 8125, concurrency 1.
- **Reference:** v6 / run_10, same tasks, same 5-minute budget, same harness. Paired per task.

## Lanes (frozen)

Each lane is 1 control (v6 resolved it) + 4 tasks covering run_10's failure classes.

| Lane | Ids file | Tasks (v6 class) |
|---|---|---|
| requests | `results/lane_requests_ids.txt` | requests_7427 (resolved), requests_7502 (right_function_wrong_fix), requests_7505 (right_file_wrong_function), requests_7433 (destructive_write), requests_6644 (wrong_file) |
| rich | `results/lane_rich_ids.txt` | rich_3468 (resolved), rich_3180 (right_function_wrong_fix), rich_3296 (right_file_wrong_function), rich_3043 (destructive_write), rich_3052 (right_function_wrong_fix) |
| httpx | `results/lane_httpx_ids.txt` | httpx_3672 (right_function_wrong_fix): the only public httpx task |
| fastapi | — | **Blocked locally.** The arm64 sandbox cannot import pydantic (run_11). Runs after the environment fix or on Kaggle. |

## What each lane run reports

- Per task: resolved, failure class, and the role where it broke:
  - planner: no PLAN, or the wrong site;
  - executor: edit errors, no repro, or the repro never went green;
  - auditor: submitted on red, or never submitted.
- Also per task: the audit decisions and strikes, the per-role seconds, tokens and peak context, compactions, and `edit_file` failure rate.

## Loop rules

- A lane run is diagnosis, not a gate. The Kaggle gate stays as recorded: ~18/23 target, 12–15 floor, clean exits.
- **Wiring falsifiers** (any one invalidates the run):
  - a role never runs;
  - the PLAN block is missing in more than half the rounds;
  - `meta.py` or `audit.py` returns `error`;
  - any task exceeds 32,768 prompt tokens.

## Amendment 2026-11-17 (before run_15)

- run_13: null (wiring, `top_k` float). run_14: null. 3 of 5 tasks were rejected by the harness because `__pycache__` was written into v7 by a test run during the lane; the 2 valid tasks are kept as diagnostics only. Both stay in the failure ledger.
- The requests lane is redone in full as **run_15** (same 5 tasks, v7 at commit `2c34a93`). Guards now in place: the tests never write bytecode, the official validator is run on every submission in the suite, and the runner refuses an invalid submission.
- The "ref" column is v6's earlier run_10 result on the same tasks; it is a reference, not a run of v6.

## Amendment 2026-11-17 (server change, before run_15)

- Local model server switched to **oMLX 0.7.0** (`SERVER=omlx`, runner default). Same checkpoint (symlink), equivalence 2/2, thinking honoured per request, 4-stream batching 2.3× (`results/server_bench/NOTES.md`). Single-stream speed is unchanged (~60 tok/s).
- Competition check: concurrent LLM calls via `ParallelAgent` are allowed (staff, 2026-10-11); parallel tool calls are not (staff, 2026-09-28); tasks run sequentially. Parallel-role arms are allowed and will be preregistered separately.
- The aborted run_15 attempt (stopped on the owner's pause, before any task finished) is discarded; run_15 starts fresh on oMLX.
