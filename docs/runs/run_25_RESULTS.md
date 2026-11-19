# run_25: v10_edit_rescue smoke (3 tasks, vllm-metal, subprocess sandbox)

Date: 2026-11-19. Arm: `AgenticSubmission/v10_edit_rescue` (audit and changes: `docs/audit_2026-11-19.md`,
`AgenticSubmission/v10_edit_rescue/README.md`). Raw outputs: `results/run_25_v10_smoke/`.

Setup, from `results/run_25_v10_smoke/run_meta.json`: `sandbox: subprocess` (no Docker), `server: vllm_metal`,
seatbelt no-network profile, budget 300 s / 40 calls / 4 min / 60 turns, max_output 16384, thinking 4096
(not enforced locally: vllm-metal rejects `thinking_token_budget`, the proxy drops it). `git_head 1703270`,
`git_dirty: true` (v10 was uncommitted), `submission_sha256 db62f4ed…`.
Tasks: `rich_3506` (also in run_24, so it is paired with v9), `requests_7315`, `httpx_3672` (not seen before
this session). Public tasks were used only to evaluate; nothing was tuned on them.

The submission was changed twice after this run, both generic and both tested: the flow `site` label now
includes the file, and `fix_edit.py` cleans two copy artifacts (doubled backslashes, a pasted read_file JSON
tail). run_25 does not measure those two changes.

## Result (grader output, `results/run_25_v10_smoke/summary.json` and `test_outputs/`)

**1 of 3 resolved.**

| task | resolved | grader | wall s | tool calls | edit_file ok/total | fix_edit calls | flow in locate | class (TELEMETRY.md) |
|---|---|---|---|---|---|---|---|---|
| requests_7315 | **yes** | `1 passed in 0.01s`, exit 0 | 108 | 5 | 1/1 | 0 | yes | resolved |
| httpx_3672 | no | collection error: `AttributeError: module 'httpx' has no attribute 'Stream'` | 243 (timeout) | 12 | 3/4 | 0 | yes | timeout |
| rich_3506 | no | `FAILED tests/test_segment.py::test_split_cells_mixed`, 1 failed 51 passed | 206 | 5 | 1/1 | 0 | yes | right_function_wrong_fix |

Edit success: **5 of 6 edit_file calls (83%)**, against 3 of 9 (33%) in run_24 (v9, rich_3486 and rich_3506).
The code_editor sub-agent was not called (it is now a last resort; in run_24 it cost 68 s).
Two of three tasks finished inside the budget; both run_24 tasks timed out.

## Where each task broke

- **requests_7315**: locate -> read -> one edit -> `--verify` -> `pytest tests/test_adapters.py` -> submit.
  The edit path worked first time.
- **rich_3506**: not an edit failure. Localization was right (`Segment._split_cells`, rank 2, with its `while`
  loop carrying `cell_pos` and `pos` in the new `flow` field). The fix was wrong: the model replaced
  `raise AssertionError("Will never reach here")` with a fallback return and never changed the loop's
  `cell_pos > cut` branch. Its own check ran `tests/test_segment.py` (49 passed) and it submitted; the hidden
  test `test_split_cells_mixed` fails. 172 s passed between its first read (9 s) and its only edit (181 s):
  two model turns of thinking, 7,851 thinking tokens in the task (unbounded locally).
- **httpx_3672**: one edit failed (step 12). Cause, by replay against the snapshot: a 30-line `old_string`
  with two copy errors, `b"\\r\\n"` where the file has `b"\r\n"`, and the read_file JSON tail
  (`", "start_line": 325, "end_line": 360, "total_lines": 515, "is_truncated": false`) pasted onto its last line.
  The model did **not** call fix_edit as the prompt now requires; it re-read and succeeded with a shorter anchor
  (step 14). It then timed out at 243 s with a 2,606-byte patch; the hidden tests need a `httpx.Stream`
  attribute the patch never added. After this run, fix_edit cleans both copy errors: the replayed step-12 call
  now matches the block and is then refused only because the model's own new_string would not parse (line 371,
  `unexpected indent`).

## Was the flow output used?

It was present in all three locate results (3,768 to 3,966 characters, under the 5,000-character stdout cap).
There is no evidence the model acted on it: no agent message cites `flow` or `carried`; rich_3506's messages
name `cell_pos` but that also appears in the code it read.

## What this smoke shows, and what it does not

- Shows: the edit path is no longer the dominant failure on these tasks (6/9 failed before, 1/6 now; the one
  failure was a new kind, now handled in fix_edit). The subprocess sandbox grades requests, rich and httpx.
- Does not show: a pass-rate gain over v6 (7/23 on paired23). Three tasks are a smoke, not a measurement, and
  rich_3506 failed on reasoning, not tooling. The prompt rule "next call is fix_edit" was not followed in the
  one case it applied (1 of 1).

## Larger model: what the rules say

Facts, quoted from files in this repository:

1. **Larger Gemma variants are allowed.** `Rules/Verbatim/model-selection-budget-harness-rules.md:5-9`:
   "At present, we only support the following ... `gemma-4-31b-it-qat-w4a16-ct`, `gemma-4-12b-it-qat-w4a16-ct`,
   `gemma-4-e4b-it-qat-w4a16-ct`, `gemma-4-e2b-it-qat-w4a16-ct`".
2. **One model per submission.** Same file, line 11: "Every agent and subagent in your submission must use the
   same model." Staff confirmed (`Rules/Verbatim/forum-staff-posts.md:319`): "no main 31b agent and 12b
   subagent, for instance".
3. **Two finals, and the bonus needs E2B/E4B as one of them.** `Rules/Verbatim/rules.md:35`: "You may select up
   to two (2) Final Submissions for judging." `Rules/Verbatim/prizes.md:24`: "Submissions must explicitly use
   either Gemma E2B or Gemma E4B as the base model. For a submission to be eligible it must be one of the team's
   two selected final submissions." So one final can be E4B (bonus-eligible) and the other a 31B or 12B
   submission competing on the main leaderboard. The E4B-only rule in `CLAUDE.md` is a project decision, not a
   competition rule.
4. **Hardware and time.** `Rules/Verbatim/upgraded-accelerators.md:3`: L4x4 machines "offer 96GB of GPU memory
   enabling submissions with much larger models". `Rules/Verbatim/evaluation.md:35`: "a limit of 12 hours to
   submit patches for all tasks, inclusive of sandbox setup time". `Rules/Verbatim/forum-staff-posts.md:185`:
   "~120 tasks in the test set". Overrunning 12 h errors the whole submission (`Rules/Verbatim/forum-findings.md:46-49`).
5. **LoRA cost.** `Rules/Verbatim/forum-staff-posts.md:226`: with LoRA enabled the 4xL4 KV cache shrank to about
   7.6k tokens and long requests hung (staff said they would patch it).

What this implies, as inference, not measurement: 12 h / 120 tasks is 6.0 min per task gross, before vLLM
start-up and sandbox setup, the same budget for any model. A 31B model decodes more slowly than E4B on the same
GPUs, so the 4-minute per-task cap would cut more 31B tasks short unless the cap is raised (the owner fixed it at
4 min). We have no measured L4 throughput for any model (`docs/SCORER_PARITY.md:75`, "not measured by us"), so
the first step before deciding is the long-pending Kaggle L4 timing notebook, run once for E4B and once for 31B.
The submission's model was not changed.
