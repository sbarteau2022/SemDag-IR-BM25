# ADR-008: Bind verification to the assignment; permit safe unmodified reassignment

Status: Accepted as a native correctness/liveness repair within owner-authorized edit/tool policy work. No new model, role, tool or budget.

Live evidence: compact-query E4B prepares both slots and editor 1 attempts a guarded edit. A BM25 guess narrowed the assignment to a single list-comprehension line 32 in Dask path initialization, not the function. The edit is correctly refused as invalid syntax. Slot 2 has another function. Inspection finds all prepare calls and final verify share the mutable task cache, so loop/anchor metadata can describe a different slot than the candidate being verified.

Decision: each preparation gets a separate cache namespace carried in its transaction state, with selected-assignment metadata/check derived for the actual candidate. A BM25 guess is not evidence to force a narrow loop locus; keep its whole function. Trusted exact anchors retain the loop-locus gate. Verification uses the state's own cache, never the latest other slot's metadata.

Root prepare may supersede only an unmodified prepared assignment, under the same lock after version/tree checks. Pending edits are never discarded. New preparation/handles invalidate old ones. A durable marker stores the current issued handle before atomic ephemeral JSON state, so restoring an older metadata checkpoint cannot revive a revoked read-only view or assignment. Lost/mismatched state fails closed. Locks coordinate helpers, not arbitrary external shell writers; full containment is not claimed.

Tests: BM25 whole-function versus trusted exact locus, separate slot caches and selected metadata/checks, stale-handle invalidation, old checkpoint replay, refusing pending edits, and unrelated cache contamination. Then full suite, official validation, same-case E4B smoke. Gates remain actual managed edit plus outside-verified apply and independent hidden-test resolution. Preserve all prior failures; no evaluation/test weakening or task-specific routing rules.

Additional observed defect: editor 2 produced a module-level return accepted by ast.parse but rejected by Python compilation during outside verification. Compile candidate ASTs without executing them, retain line/error context, and test return/break/continue/nonlocal cases. Verification rejection was correct; candidate acceptance must catch these earlier.
