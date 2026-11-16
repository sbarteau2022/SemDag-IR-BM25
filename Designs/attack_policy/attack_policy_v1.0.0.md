# How to Attack: task policy for the Gemma 4 E4B dev agent

Version 1.0.0 · 2026-11-12 · Owner: Stewart Barteau · Status: **candidate, not yet measured as a whole**

## Assumptions

- **What this is.** A precedence-ordered action policy for one agent resolving one repository issue inside the `swegemma` sandbox. It is not a content-safety policy. I used the Nemotron policy generator's artifact shape (assumptions, rules with scope and carve-outs, real examples, edge cases, JSON, drop-in prompt) and none of its taxonomy. It will not run on a Nemotron safety model.
- **Model and runtime.** `gemma-4-e4b-it-qat-w4a16-ct`, nine harness tools plus the `locate` skill, 32k context, per-task budget in `eval_config.yaml` (5 min, 40 tool calls).
- **Scoring.** Resolution rate. A wrong patch and an empty patch both score zero, so abstaining never beats attempting. This reverses the "abstain gate" in `LORA_TRAINING_DESIGN.md` for this metric.
- **Evidence rule.** Every rule cites a measurement from 2026-11-12 or is marked **unmeasured**. Examples are real traces under `results/`. Nothing is invented.
- **Evidence base.** 23 baseline and 23 skill-arm task runs (Requests, httpx, Rich) in Docker, and the 129-task CPU localization study. Small, public-repo, single-sample.

## Design basis (six questions, answered before writing rules)

1. **Context.** A bounded batch job: one issue, one sandbox, hard caps on time, calls and context. Failure is silent (a zero), so the policy must prevent quiet failure, not handle errors.
2. **State and invariants.** The only state that scores is the working tree diff at submit. Invariants: the diff is non-empty; it touches no test file, `pytest.ini` or `conftest.py`; scratch lives in `/tmp`; the last successful edit is the one submitted.
3. **Failure modes, measured.** Of the baseline's 19 failures: 13 edited a gold file and wrote the wrong fix, 4 edited the wrong file, 2 submitted nothing. `edit_file` rejected 25 of 55 calls (45%); the skill arm 18 of 48. Every empty submission followed repeated `old_string not found` errors.
4. **Authority.** The agent may read anything in `/workspace`, edit source only, and submit once. The harness strips diffs to protected files, so editing them wastes calls.
5. **Replay and concurrency.** One agent, no concurrency. Replay is the hazard: repeating a failed action. 7 baseline and 10 skill-arm edits were retried after a failure with no read in between.
6. **Observability.** The harness trace already records every call. `Tools/trace_report.py` and `results/reports/edit_failures.json` are the instruments; each rule below names the field that shows whether it was followed.

## Rules, highest precedence first

### R1. Never submit an empty diff
- **Definition.** `submit_patch` is allowed only after an `edit_file` or `write_file` call has returned `status: ok` on a source file. If `submit_patch` returns `patch_size: 0`, the task is not done.
- **In scope.** Ending the session; the final answer.
- **Out of scope.** Whether the edit is correct (R5).
- **Evidence.** 3 baseline and 2 skill-arm tasks submitted `patch_size: 0`. All five followed failed edits. None was a real fix.
- **Real example.** `requests_7205` (baseline): three `edit_file` errors, then `submit_patch` → `patch_size: 0`, one more failed edit, then a second empty submit.
- **Edge case.** `requests_7427` passed with an empty patch in the baseline. Its tests pass with no change, so it tells you nothing. Do not learn "empty can pass" from it.
- **Trace field.** `tasks_with_empty_submit`.

### R2. When an edit is rejected, read the exact lines before trying again
- **Definition.** After `old_string not found`, the next call is `read_file` on that file with a line range around the target. Copy `old_string` from that output verbatim, as few lines as identify the spot. Never retry an edit from memory.
- **In scope.** Every `edit_file` error.
- **Out of scope.** Edits that succeed.
- **Evidence.** 45% of baseline edits and 38% of skill-arm edits were rejected. Tasks with any rejected edit resolved 1 of 8 (baseline, the empty-patch pass) and 0 of 4 (skill arm); tasks with none resolved 3 of 15 and 7 of 19. 17 rejected edits were retried with no read in between.
- **Real example.** `rich_3043` (skill arm): four consecutive rejected edits to `rich/_export_format.py`, no read between them, then an empty submit.
- **Edge case.** If two reads and two retries still fail, replace the whole function with `write_file` only if the file is small; otherwise make a smaller edit on one unique line. **Unmeasured.**
- **Trace field.** `failed_edit_retried_without_reading`, `edit_errors`.

### R3. Locate once, first
- **Definition.** The first call is the `locate` skill with the issue text. Read the first candidates before any other search.
- **In scope.** The opening of every task.
- **Out of scope.** Later searches once a candidate has been read and rejected.
- **Evidence.** Offline, the same retrieval puts a gold function in its top 5 on 58 of 116 tasks and a gold file in its top 10 on 108 of 128. In agent runs it was called on 15 of 23 tasks; its candidates held a gold file 12 times and a gold function 10. Wrong-file failures went from 4 (baseline) to 3. The skill arm resolved 7 of 23 against 4, with three wins and no losses; three discordant tasks is not significant.
- **Real example.** `rich_2725`: baseline spent 327 s in the analyzer sub-agent, had three edits rejected and submitted nothing; the skill arm located, edited once and passed in 7 calls.
- **Edge case.** `requests_6644`: candidates held no gold file. If the first three candidates do not mention what the issue describes, fall back to `grep` on an identifier from the issue. **Fallback unmeasured.**
- **Trace field.** `locate_called_first`, `locate_candidates_had_gold_file`.

### R4. One small edit at the located site
- **Definition.** Change the fewest lines that implement the issue, in the function you read. Do not refactor, rename, or touch a second file unless the issue names it.
- **In scope.** All source edits.
- **Out of scope.** Adding a new function the issue asks for.
- **Evidence.** The dominant failure is right file, wrong fix: 13 of 19 baseline failures and 11 of 16 skill-arm failures. **Whether smaller edits fix this is unmeasured.** It is the largest open question in this policy.
- **Real example.** `httpx_3672` (skill arm): located a gold function, then submitted a 4,260-byte patch against the baseline's 1,222; both failed.
- **Edge case.** Overloaded functions (`rich_3052` has three `PromptBase.ask` definitions): the signature change must be applied to each.
- **Trace field.** `agent_patch_size`, `edited_gold_file`.

### R5. Run the tests for the module you changed, and believe them
- **Definition.** After a successful edit, run the test file that covers the edited module. A test that fails and mentions the edited function is yours to fix. Submit when it passes, or when the budget in R6 says to.
- **In scope.** Verification before submit.
- **Out of scope.** Failures in unrelated test files; the hidden tests, which the agent never sees.
- **Evidence.** The agent ran a command in 21 of 23 baseline tasks and nearly every skill-arm task, and still failed 19 and 16. In the first smoke run it saw failures, called them unrelated, and submitted. The syntax-only gate rejected 0 of 11 model patches. **A test-keyed gate has not been measured.**
- **Real example.** `requests_6589` (baseline): ran `pytest tests/test_utils.py`, attributed the failures to another test, submitted, failed.
- **Edge case.** Test dependencies may be missing in the scored sandbox. If the test command errors on import, do not spend more than one call on it.
- **Trace field.** `calls.run_command`; a future field for "red test before submit".

### R6. Spend the budget on the edit, and leave a diff before it runs out
- **Definition.** By the 20th tool call, or 3 minutes, a successful edit must exist in the tree. From then on, only verify or correct it. Never start a new line of investigation in the last minute.
- **In scope.** Pacing.
- **Out of scope.** Tasks that finish early.
- **Evidence.** Passing skill-arm tasks used a mean of 9 calls. `rich_3061` (baseline) hit the 8-minute cap after 23 calls. The harness records a non-empty tree even without `submit_patch`, so a timed-out task with an edit can still score. **The 20-call threshold is a judgment, unmeasured.**
- **Edge case.** The scored L4 hardware is faster per token than the laptop; call counts transfer, seconds do not.
- **Trace field.** `tool_calls`, `duration_seconds`, `error`.

### R7. Do not delegate localization after `locate` has answered
- **Definition.** Use the analyzer sub-agent only when `locate` and one `grep` have both failed.
- **Evidence.** One trace (`rich_2725` baseline, 327 s in the analyzer, no patch). **Anecdotal.**
- **Trace field.** `calls.code_analyzer_agent`.

## Harness law (always in force, not ranked)

- Never edit test files, `/workspace/pytest.ini` or `conftest.py`.
- Scratch files go in `/tmp`.
- One model, nine tools plus declared skills. No network.

## Verdict at submit (recorded, not gating)

| Verdict | Meaning | Action |
|---|---|---|
| `verified` | Edit succeeded and the module's tests pass | Submit |
| `unverified` | Edit succeeded; tests fail, error, or were not run | Submit |
| `no_edit` | No successful edit exists | Do not submit; return to R2 or R3 |

Only `no_edit` blocks, because a wrong patch costs nothing under this metric.

## What would change this policy

1. A paired run of this prompt against `v2_bm25` on the same 23 tasks. Until then it is a candidate.
2. A measured test-keyed gate (R5) with a positive and a negative control.
3. Any evidence on what turns "right file, wrong fix" into a pass (R4).
