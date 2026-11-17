# run_12 results (PARTIAL, stopped by owner): E4B LoopAgent, 30-min local budget

Preregistration: `run_12_PREREG.md`. Evidence: **LIVE-MEASURED**, local MLX stand-in.

**Status: partial.** The owner stopped the run at 18:49 UTC after 10 of 15 tasks (harness exit 137), switching to short loops. It is recorded as a baseline reference only; per the preregistration it is **not admitted** to gate comparisons. Post-run ingest, report and image completed: `TELEMETRY.md`, `gemma4-e4b-telemetry:run-12-v5-loop`.

## Result on the 10 completed tasks

- **Resolved 3/10**: requests_7427, requests_7309, rich_3468.
- **v6 (run_10, 5-min budget) resolved exactly the same 3** of these 10, so the 30-min budget bought no extra solves.
- Failure classes: right_function_wrong_fix 4, wrong_file 2, right_file_wrong_function 1.

## Findings

- **Long budget breaks the context limit.** Peak prompt reached **157%** of 32,768 tokens (requests_7205) and 152% (requests_7309). Local MLX accepted that; the scorer's vLLM (`max_model_len 32768`) would not. A long single-context loop is unsafe at any budget.
- **Time per task:** up to 18 min, with up to 222 steps.
- `submit_patch` returned an error on 9 of 16 calls. The verifier keeps calling it after the patch was already submitted or while it is empty; this needs inspection before the next loop arm.
- **Model calls (506):**
  - TTFT p50 0.28 s;
  - decode p50 45.7 tok/s;
  - thinking per step p50 188, p90 534 tokens;
  - 1 of 391 steps over 4,096.
- **0 of 10 tasks reproduced before editing**, the same as every earlier run.
