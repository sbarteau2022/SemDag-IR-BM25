# run_16 results: v7 brigade-lite, rich lane (oMLX)

Status: **LIVE-MEASURED** (local stand-in). Preregistration: `docs/runs/lanes_PREREG.md` plus its 2026-11-17 amendments. Setup is the same as run_15 (oMLX 0.7.0, seatbelt, 120 s / 40 calls / 5 min / 60 turns).
Raw files: `results/run_16_v7_lane_rich/`. Image: `gemma4-e4b-telemetry:run-16-v7-rich`. Finished 2026-11-17T21:31:51Z. 114 model calls, 0 proxy errors. TTFT averaged 0.63 s; decode, aggregated over all calls, was 57.5 tok/s.

## Outcome

**Resolved 1/5. v6 (run_10) also resolved 1/5 on the same tasks (rich_3468 in both).** No change in the score. 3 of the 5 tasks hit the 5-minute timeout.

| task | v7 class | broke at | evidence |
|---|---|---|---|
| rich_3468 | resolved | none | |
| rich_3043 | timeout | executor (planner poisoned it) | **Degenerate repetition.** The planner (temp 1.0) wrote `from rich.console import Console; ... Segment; ... TerminalTheme;` on repeat until it hit max_tokens 6144 (28,931 chars). The executor's reasoning (4096, the cap) and the auditor's output (1024, the cap) then repeated the same loop. 0 edits |
| rich_3052 | timeout | auditor | 3/3 edits applied, audit said revise, then the time ran out |
| rich_3180 | timeout | auditor | 2/2 edits applied, audit said revise, then the time ran out |
| rich_3296 | right_file_wrong_function | verify | audit said revise; the task was submitted on round 3 |

Time share by role: planner 33%, executor 63%, auditor 4%.

## Findings

1. **Repetition collapse spreads through the roles.** The planner's text reaches the executor and auditor through `{plan?}` and the shared conversation, and both copied the loop. All 3 `finish_reason=length` calls in run_16 came from this one task. run_15 had 0 such calls.
   - ADK forwards both penalties: `google/adk/models/lite_llm.py` passes `presence_penalty` and `frequency_penalty` through to LiteLLM. oMLX 0.7.0 accepts both per request (`omlx/server.py:1711-1714`).
   - **Local fidelity gap.** oMLX applies them through mlx_lm `make_logits_processors`, whose `presence_context_size` and `frequency_context_size` default to **20 tokens** (`mlx_lm/sample_utils.py:76-82, 309`). The loop period here is about 20 tokens or more, so the local penalty barely sees one repeat. vLLM counts penalties over all generated tokens, so the scorer's planner should be less prone to this loop.
   - This is inferred from source code; no live check on the scorer has been run. Local runs therefore overstate repetition collapse. A cheap safeguard that holds on both servers: lower the planner's `max_output_tokens` (6144 now) so that a loop costs less.
2. **Revise rounds do not fit the 5-minute task cap.** In 3052 and 3180 the edits went through and audit asked for a revision, but the timer ran out before a second executor pass. Combined with run_15, 5 of 10 lane tasks timed out.
3. As in run_15, the repro counter (`/tmp` only) shows 0, and context is not the limit (peak 15–61%).

## Limitations

5 tasks, 1 seed, on a Mac stand-in. The 1/5 tie shows neither a gain nor a regression. These results are diagnostic only.
