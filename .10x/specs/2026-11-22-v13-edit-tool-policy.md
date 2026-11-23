# v13 edit execution, tool calls, then subagent policy

Status: PROPOSED; owner design review required before implementation. User scope: optimize edit execution and tool calls, then refine subagent policy. E4B only; macOS Seatbelt/subprocess; no Docker; unchanged four-minute/default-token limits. No official harness patches, new runtime model APIs or hidden model-output rewrites.

## Evidence and limits

Previous real E4B development run: 7 skill calls, 9 shell calls, 1 skill load, 2 editor dispatches, 1 submit; no valid slot and no patch. The later valid run completed one malformed skill call then timed out. No live successful edit exists to benchmark yet. These are failure traces, not a representative performance baseline.

New host component reproductions on real v13 retriever source, in disposable directories:
- A slot assigned lines 1-5 accepted a line-18 edit.
- apply_ws accepted that unverified change and lost a concurrent central-file change.
- Reading NON_LIB_DIRS at line 38, shifting the file, then replacing the old coordinate succeeded but inserted a duplicate assignment at the wrong location.
Receipts: reports/v13_edit_policy_design_2026-11-22/baseline_probes.json and stale_line_probe.json. These are controlled component probes, not SWE resolution results.

## Alternatives

| Approach | Benefit | Cost / limitation |
|---|---|---|
| Native edit transactions and fused lifecycle operations (recommended) | Reduces coordinate replay and glue calls; checks state before writes | More state/rollback logic; must preserve observable errors |
| Prompt/manual changes alone | Small change | Does not prevent stale edits or unverified apply; prior manual repair did not yield task success |
| Host correction of malformed model tool calls | May conceal errors | Rejected: changes scorer behavior and fabricates model intent |

## Stage 1: Native edit execution and tool-call reduction

1. At prepare/read, persist a task/slot-specific assignment: allowed source file and span, central base SHA256, slot SHA256, numbered view, generation and opaque edit handle. The model edits with handle + replacement, rather than regenerating paths and coordinates. Resolve all fields in the sandbox; unknown, cross-task, cross-slot, stale or already-used handles fail explicitly. Correct existing call forms remain available during comparison; they must receive the same assignment/staleness protections when editing managed slots.
2. Edit commit: validate assigned span, current bytes and new Python syntax/imports; reject out-of-range endpoints instead of clamping. Atomically replace only after guards pass. Preserve file permissions and supported encodings/newlines; unsupported encodings fail without changing bytes. A successful edit returns a fresh handle/view and compact diff. Errors return bounded actionable evidence. Missing skill_name/file_path remains an official tool error: native scripts cannot run until the caller supplies a valid envelope.
3. Coalesce preparation (locate, baseline check, spawn, assignment) behind one skill-script action, reusing recorded results. Coalesce finalization (collect, scope/staleness checks, outside test, apply and verify) behind another. This is ordinary deterministic code, not an LLM orchestrator hidden in Python. Keep detailed receipts outside the patch.
4. Finalization must recheck the central base and candidate hashes, reject protected/off-assignment changes, and preserve test exit codes. Capture output then truncate it; never turn pytest failure into a passing tail pipeline. Respect the remaining task deadline, with cleanup/rollback on failure. Reject stale apply rather than overwriting central updates. Test in a separate disposable verification copy before central apply; retain a final central verification check and restore only this transaction's files if it fails and their hashes still match the applied candidate. Do not overwrite intervening external changes during rollback.
5. Scope warning: these scripts can guard their own edit/apply paths. Existing run_command still permits direct filesystem writes, and agent_tool remains callable by the model. Do not describe the design as an unbypassable sandbox or claim script policy prevents all model dispatches. Removing/bounding those broader capabilities requires a separate supported-ADK design.

## Stage 1 preregistered gates

- Zero mutations for stale/cross-slot/unknown handles, off-span edits, invalid syntax/imports, protected paths, changed central source, verification timeout/failure and malformed inputs. Include concurrent edits, duplicate requests, CRLF, no final newline, Unicode, file modes and rollback interference.
- Replay the three measured component failures: they must now refuse with central/sibling bytes preserved. Valid in-scope edits must collect, verify and apply with exact expected bytes.
- On fixed identical source/patch/check inputs, compare old/new deterministic lifecycles. Target at least three fewer successful control calls, identical accepted output and test outcome, no suppressed failures, no >10% median native execution-time regression across seven alternating repetitions. If the gate fails, retain the negative result; do not change thresholds afterward. Count model-level calls separately.
- Official package validation, unchanged E4B and budgets, comprehensive host regression suite, adversarial review, then real E4B development smoke on the qualified external Dask task. Require a successful managed edit and outside-verified apply to claim live edit-path improvement. Report task resolution independently; no held-out gain from a same-task retry.

## Stage 2: Subagent policy — design after Stage 1 measurements

Do not tune dispatch and edit execution in the same comparison. Start from explicit policy states: unprepared -> prepared -> editor_running -> candidate_ready -> verified -> applied -> submitted (or failed). Missing preparation must prevent native edits/finalization; never trust PATCH_READY prose as verification.

Compare one editor by default against a second editor only for an evidence-backed distinct alternate locus. Separate a genuinely different hypothesis from a repeated failed tool call. Dispatch consumes the shared four-minute budget; reserve verification/submission time. Set concrete dispatch/retry thresholds after observing successful editor and verification durations, before policy experiments. Do not invent timing estimates from the failed runs.

Policy review questions: What information must the editor receive? Which tools/paths does each role actually need? What state permits a retry? How does root choose a patch on measured tests rather than eloquent summaries? How do failed or timed-out editors release resources? What supported declarative ADK structure can restrict dispatch, versus what remains only instruction? No runtime access to host research memory.

Measure valid-call rate, wrong-route/format calls, successful prepared edits, stale/off-scope rejections, verified apply, duplicate dispatches, task resolves, wall time and model tokens. Freeze external development/held-out case selection and policy gates before comparison; do not train/tune on competition public tasks or optimize against gold patches. Model-generation changes need repetition to distinguish noise. No promotion without genuine task-resolution evidence under identical budgets.

## Delivery

Preserve current v13 as a hashed reference before implementation. Implement Stage 1 in a reversible candidate or isolated branch, update README/session memory and .10x decisions, run required gates, then present Stage 2 policy with measured timing. No Kaggle submission, training, budget changes, other models or delegated host agents are authorized by this design.
