# run_15 results: v7 brigade-lite, requests lane (oMLX)

Status: **LIVE-MEASURED** (local stand-in). Preregistration: `docs/runs/lanes_PREREG.md` and its amendments dated 2026-11-17.

- Submission `AgenticSubmission/v7_brigade_lite`. Server oMLX 0.7.0, same MLX checkpoint. Runs under seatbelt with no network. Docker Desktop, concurrency 1.
- Budget: 120 s per command, 40 tool calls, 5 min, 60 turns per task.
- Raw files: `results/run_15_v7_lane_requests/` (LANE_REPORT.md, TELEMETRY.md, traces). Image `gemma4-e4b-telemetry:run-15-v7-requests`.
- Finished 2026-11-17T21:01:33Z. 95 model calls, 0 proxy errors, all HTTP 200.

## Outcome

**Resolved 1/5. v6 (run_10) also resolved 1/5 on the same tasks (requests_7427 in both).** No change in the score.

| task | v7 class | broke at | evidence |
|---|---|---|---|
| requests_7427 | resolved | none | |
| requests_6644 | timeout | auditor never reached | 1 good edit, then 4 full-suite `run_command` pytest reruns (each red) until the 5 min cap |
| requests_7502 | timeout | executor | 5/5 `edit_file` failed with `old_string not found` (F3 edit recovery) |
| requests_7433 | right_function_wrong_fix | verify | audit said revise, then submit_best ×3; `submit_patch` called 4 times. The session did not end after the first call |
| requests_7505 | right_file_wrong_function | auditor gate skipped | auditor called `submit_patch` without running `audit.py` |

Time share by role: planner 29%, executor 69%, auditor 3%. Peak context was 15–28%, so context is no longer the limit for v7.

## Findings (each tied to the rows above)

1. **Executor time sink.** Repeated full-suite pytest runs (6644) and edit retries that keep failing (7502) caused both timeouts. Candidate fix: the executor runs only `test_cmd` from meta (the nearest tests), and after 2 `edit_file` failures it must re-read the exact lines before trying again.
2. **`submit_patch` does not end the LoopAgent locally.** In 7433 the auditor submitted 4 times in a row and the loop kept going. This wastes time. Check whether the scorer behaves the same before relying on either behaviour.
3. **The audit gate can be skipped.** In 7505 the auditor submitted without calling `audit.py`. The prompt alone does not enforce the gate.
4. **Repro counter undercounts.** `lane_report.repro_runs` only counts commands that touch `/tmp`. 6644 ran an inline `python -c` repro. The column is a lower bound.

## Measurement notes

- Local oMLX speed for this run: TTFT averaged 0.39 s (max 1.6 s). Decode, aggregated over all calls, was 57.5 tok/s (72,288 completion tokens).
- The per-call column `llm_calls.decode_tok_per_s` averaged 3,898. That is an artifact: oMLX streams in large chunks (61 chunks per 761 tokens on average), so `total_s - ttft_s` is near zero on some calls. Use the aggregate. Do not average that column for oMLX runs.

## Limitations

5 tasks, 1 seed, on a Mac stand-in, not the L4/vLLM scorer. A tie at 1/5 shows neither a gain nor a regression. The lane result is diagnostic only. It is not admitted to any final comparison.
