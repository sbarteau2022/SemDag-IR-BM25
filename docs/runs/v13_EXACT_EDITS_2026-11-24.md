# v13 exact-fragment editing

E4B only; macOS Seatbelt plus official subprocess execution, no Docker. Fixed240s/40calls/60turns and16,384 output/4,096 thinking tokens. Local thinking-budget enforcement remains absent in vllm-metal; these are local development observations, not official scores.

## Cause and change

Recorded old edit calls supplied a function body for a whole-function lease. Four copies broke docstrings; the final copy compiled after deleting the def header. Outside verification caught the missing function before central apply. Instructions alone had not prevented this.

An editor-only scripts/replace.py now takes a current handle, one exact old fragment and replacement lines. Native code retains all surrounding source, including the header/docstring. Old text must match once inside the leased view, at most16 lines/2048 characters. Missing, overlapping or multiple matches fail unchanged. The program does not infer indentation, decode quotes, match flexibly or repair missing SDK fields. Existing locked compile/import/hash/scope/single-use checks and root outside/central verification remain. The root cannot execute this editor resource. Legacy full-view replacement is compatible but no longer recommended for a small change.

A BOM pressure test also exposed an AST-analysis encoding inconsistency: one leading UTF-8 encoding marker is now omitted only during AST analysis, matching Python source-byte interpretation; source bytes stay intact and embedded/double markers remain invalid.

## Verified capability

Both following change requests use the actual existing retriever.py source, without injecting a SWE bug. The driver prepares the assignment and invokes the real compiled root finalizer after the model edits. The actual compiled E4B editor must load its skill, read native status and execute its own exact old/new fragment. Host preparation/finalization is disclosed: this tests editing capability, not autonomous root policy or benchmark resolution.

| Component change request | E4B editing seconds | Patch bytes | Result |
|---|---:|---:|---|
| Treat None as empty token input; preserve string token outputs | 26.88 | 322 | Verified apply |
| Recognize Windows separators in test-path detection; preserve POSIX/ordinary behavior | 29.01 | 515 | Verified apply |

For both, actual events confirm a successful scripts/replace.py response marked exact_fragment. Independent outside and central checks pass; unchanged surrounding source is compared byte-for-byte. These are two observed successes, not a statistical reliability claim or a SWE score. The added None guard and separator normalization exist only in disposable capability workspaces; they are not silently merged into the product retriever.

Initial negatives are retained. Before the explicit native-call example, E4B returned a proposed code array without executing it. Two Windows launches were rejected before any model call because a host inspection/preparation process produced forbidden bytecode; generated files were removed and that diagnostic process was corrected. Those launches are excluded from model capability results. No task data/model traces were published or ingested into research memory.

## Regression and limits

337 host tests pass, zero errors/failures/skips. Actual SDK tests exercise both editor roles and root finalization, malformed/missing fields, root/sibling denial, stale and intervening views, zero/ambiguous/overlapping/outside fragments, quote/Unicode/CRLF/BOM/no-final-newline preservation and explicit deletion. A real retriever source replay reproduces the old compiled header loss and verifies the preserving counterpart. Official directory validation, role-asset equality and undefined-name lint pass.

The unchanged external Dask full-task run **completed the autonomous edit lifecycle**: root prepared at21.0s, editor executed one successful exact-fragment edit at157.2s, root finalized at172.0s, outside/central checks passed and applied at174.6s, and root explicitly submitted a498-byte patch at176.7s. Full task184.67s,5 counted tools,12 LLM calls, no harness error. No host prepared/edited/finalized/submitted this full-task run.

The independent task grader remains **0/1 resolved**, exit1,2 failures/43 passes. The patch preserved the function and changed one condition in the downstream update function; it did not solve the malformed-YAML loading requirements. This is genuine live edit/apply/submit proof, not task-resolution improvement. Remaining task work is causal localization/fix choice and broader policy qualification. Repeated development on one case is not a held-out estimate.

Local receipts: reports/v13_exact_edits_2026-11-24/, including source manifests, JUnit, real model events, actual patches, outside/central receipts, excluded launch errors and exact-endpoint evidence. Raw artifacts remain local. Design: ADR-015 and .10x/specs/2026-11-24-v13-edit-capability.md.

## Exact-path native timing gate

The preregistered variant exercises replace_text on the same real-source patch/check, using the original seven alternating pairs and <=10% overhead criterion. Baseline median0.184782291s; exact-fragment candidate0.219495708s: **+18.79% overhead**, identical output, modeled controls9->4. The gate **fails** and is retained; no speed promotion or threshold relaxation. The earlier3.59% whole-view/Git-read result applies to that earlier benchmark, not this exact path. Correct live execution and a passing regression suite do not erase this performance finding.

Conclusion: observed editing capability and autonomous lifecycle gates pass. Task-resolution and native timing gates do not. Keep the candidate experimental. Source manifests, actual events/patches, JUnit, official grading log, benchmark rows and cleanup receipts remain local.
