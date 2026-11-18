# run_20 results: v8 ensemble smoke, rich lane (subprocess sandbox, oMLX)

Status: **LIVE-MEASURED** (local stand-in, smoke). Preregistration: `docs/runs/v8_PREREG.md`.

- Setup: `AgenticSubmission/v8_ensemble` at commit `644110a`; seatbelt + subprocess sandbox, no Docker; runner-started oMLX; parity on (thinking budget, top_k 64, compaction 14,336).
- Raw files: `results/run_20_v8_smoke/` (no image; subprocess mode). Finished 2026-11-18T06:04:39Z.
- 200 model calls, 0 proxy errors, 0 `finish_reason=length`. Mean TTFT 1.47 s (four streams queueing). Decode about 37 tok/s per call. Peak prompt 19,906 tokens.

## Outcome

**Resolved 0/5.** The loose reference, v7 in run_16 (Docker, other budgets, no parity), resolved 1/5 (rich_3468).

| task | result | implementers active (s) | main-workspace edits by implementers | patch bytes |
|---|---|---|---|---|
| rich_3180 | timeout 4.0 min | 13–234 | 6 (all 4 implementers) | 602 |
| rich_3468 | timeout | 5–213 | 2 | 554 |
| rich_3296 | **harness_error**: ADK `ValueError: No function call event found for function responses ids` inside ParallelAgent | 5–223 | 3 | 397 |
| rich_3043 | timeout | 14–237 | 4 | 348 |
| rich_3052 | timeout | 6–237 | 22 (all 4) | 1505 |

Grading itself works in the subprocess sandbox for rich. The test logs show real results: rich_3468 had 97 passed and 1 failed (`test_brokenpipeerror`); rich_3052 had 6 passed and 1 failed.

## Findings

1. **Stage 1 used the whole 4 minutes in 5/5 tasks.** No adversary, coordinator or final-implementer call happened in any task. Four implementers in parallel took 112–237 s: their tool calls run one at a time, and four oMLX streams share the Mac GPU. Each implementer used 6–18 tool calls against a prompt limit of 10. Locally the ensemble does not fit 4 minutes. The scorer's 4×L4 speed is still unmeasured, so this local timing does not settle the Kaggle case.
2. **Prompt-only isolation failed.** In 5/5 tasks implementers edited the shared workspace (`rich/...`) instead of `.git/wt_k/...`: 37 stray edits in total, even though `fork.py` returned the prefixed paths. The submitted patches came from these stray edits through the harness fallback, not from a chosen candidate.
3. **ADK ParallelAgent crashed one task** with an event-history inconsistency, a function response with no matching call. The ADK version comes from the competition wheelhouse, so this can happen on Kaggle. The cause (compaction vs interleaved parallel branches) is not yet isolated.

## Proposed next steps (not built)

- **Script-enforced isolation:** take `edit_file` away from implementers. Give them a skill `edit.py k <file> <old> <new>` that always writes into `.git/wt_k`, so the main workspace cannot be touched by an implementer.
- **Isolate the ADK crash:** rerun one task with `SWEGEMMA_PARITY=0` (compaction off) against compaction on.
- **Stage time:** fewer parallel implementers locally (2), or a deterministic hand-off. Decide only after measuring L4 throughput, because the local timing overstates the scorer's.

## Limitations

5 tasks, 1 seed, on a Mac stand-in in the subprocess sandbox. The comparison with run_16 is loose. Diagnostic only.
