# run_23 preregistration: v9_recurrent vs frozen v6_impact, paired, held-out

Written 2026-11-18 before any run_23 task was started. Git HEAD 9e18b90 (main). Neither submission folder is edited, and nothing is tuned on these results.

## Question

Does v9_recurrent (v6 plus the hybrid recurrent SemDAG graph, loop/recursion fields on edit sites, the optional `--flow` call and the new `--verify` notes) resolve more held-out tasks than v6_impact?

## Task slice (`run_23_ids.txt`)

- Pool: non-fastapi tasks in `DataSets/public/data/tasks.jsonl` (62: rich 48, requests 13, httpx 1). fastapi cannot be graded locally.
- Excluded: every id that appears anywhere under `results/` (ids files, run folders, `telemetry.sqlite`), `docs/` or `Tools/local/`. That covers paired23 and runs 2 to 22. 42 of 62 were excluded.
- Left: 20 ids, all rich. Every requests and httpx id has been used before, so this slice is rich-only.
- Draw: `random.Random(20261118).sample(free, 20)`, sorted. The slice was first drawn at 12; the owner enlarged it to 20 before any task started, so the file was rewritten. With 20 free ids the draw is the whole unused pool, and no unused non-fastapi id is left after this run.
- Ids (20): rich_3486, rich_3506, rich_3518, rich_3521, rich_3535, rich_3675, rich_3676, rich_3772, rich_3782, rich_3882, rich_3894, rich_3930, rich_3935, rich_3938, rich_3944, rich_4006, rich_4070, rich_4075, rich_4076, rich_4077.

## Arms

| Arm | Folder | eval_config (as shipped, not changed) |
|---|---|---|
| v6_impact | `AgenticSubmission/v6_impact` | 120 s per command, 40 calls, **5 min**, 60 turns |
| v9_recurrent | `AgenticSubmission/v9_recurrent` | 300 s per command, 40 calls, **4 min**, 60 turns (owner budget) |

The budgets differ: v6 gets one more minute per task and a shorter command timeout. This favours v6 on time-limited tasks. It is reported and not corrected.

Order: v6 arm first, then v9, same ids, concurrency 1, Docker Desktop sandbox, no-network seatbelt.

## Server (deviation from the brief)

The brief asked for vllm-metal on 8124. Both arms send `thinking_token_budget` 4096 on every call, and vllm-metal 0.33 rejects that field with HTTP 400 (gate G2, `results/server_bench/vllm_metal/NOTES.md`). The proxy does not strip or emulate it yet. On vllm-metal both arms would fail every model call.

So both arms run on **oMLX 0.7.0** (`SERVER=omlx`, the runner default), which enforces the thinking budget through the proxy's `--thinking-budget-field thinking_budget`. The oMLX instance already listening on 8124 is reused (the same one run_22 reused); the runner records that in `model_server_provenance.txt`. Both arms see the same server, so the pairing holds.

## Metrics

- Primary: resolved count per arm (harness PASS/FAIL), and the per-task paired table (both, v6 only, v9 only, neither).
- Secondary: wall time per task; tool-call failures (by tool); failure class per unresolved task; for v9, how many tasks call `run_skill_script` with `--flow` and whether the new `loops`/`recursive`/`callers` fields appear in locate output.

## Decision rule

20 tasks is small. A difference of 1 or 2 resolved tasks is read as a tie. v9 is called better only if it resolves at least 3 more tasks than v6 with no task lost to a v9 crash. No tuning follows from this run.
