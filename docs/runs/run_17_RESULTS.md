# run_17 results: v7 brigade-lite, httpx lane (oMLX)

Status: **LIVE-MEASURED** (local stand-in). Same preregistration and setup as run_15 and run_16. Raw files: `results/run_17_v7_lane_httpx/`. Image: `gemma4-e4b-telemetry:run-17-v7-httpx`. Finished 2026-11-17T21:44:29Z. 26 model calls, 0 proxy errors, 0 `finish_reason=length`.

**Resolved 0/1. v6 (run_10) also resolved 0/1 on this task.**

| task | v7 class | broke at | evidence |
|---|---|---|---|
| httpx_3672 | timeout | auditor never reached | The planner took 25 s. The executor applied 1/1 edits, then ran **9 repro commands** over 274 s and hit the 5 min cap before the audit ran |

This matches run_15 task 6644. The executor keeps re-running checks after its edit instead of handing over to the audit, so the auditor never runs.

## Three lanes combined (run_15 to run_17, 11 tasks)

- **v7 2/11, v6 2/11** on the same tasks. No gain.
- **6/11 tasks timed out.** The executor used 63–69% of each lane's time. The auditor used 3–4%.
- Where tasks broke: auditor 5 (gate never reached in 6644, 3052, 3180, 3672; skipped in 7505), executor 2 (7502 edit failures; 3043 poisoned by the planner's loop), verify 2 (7433, 3296), resolved 2.

## Limitations

1 task. Diagnostic only.
