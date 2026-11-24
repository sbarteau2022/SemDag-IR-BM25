# Protocol diagnosis
ADR-004 governs read-only local request capture and raw/chat/parser probes. No scored-runtime changes or hidden model-output repair. Fixed-call probes pass; full context still needed. Public parser/template text was verified and ingested locally; task/model content is not ingested or published.

ADR-005 adds strict typed positional grammar, with the same roles/actions and backward-compatible flags; actual SDK fixtures and full tests pass. ADR-006 aligns model-facing discovery with the SDK instruction and fixes role-aware unprepared status feedback. No SDK load-precondition enforcement claim. Greedy probes do not repair wrong-skill routing, so sampling unchanged. Short-case original reference grading fails and is excluded. Final same-case live SDK-aligned trial follows the sealed source.

ADR-008 repairs observed BM25 over-narrowing, mutable shared verification metadata, Python compilation-context validation and safe unchanged-assignment liveness. Per-assignment caches and durable handle markers are tested; pending candidates are not discarded. 296 host tests/official validation pass. Updated native timing +15.44% fails the original 10% secondary gate and is retained, not relaxed. Same-case live trial follows; no performance promotion.

ADR-009 moves optional prepare clock calculation into native code using the harness baseline tag and adds explicit edit_lines plus safe current-assignment read selectors. No SDK field inference or packed-write repair. Actual compiled SDK positive/negative cases and full regression suite pass; fixed same-case E4B verification follows.

ADR-010 repairs participant-native source stdout formatting and exit status. Metadata header/raw source avoids duplicate source escaping; failures emit structured stderr and nonzero exit. Internal data dictionaries stay stable. Python physical LF line handling preserves Unicode separators. Actual SDK integration and undefined-name lint pass; full suite precedes the next unchanged-case smoke. No model-output cleanup or role expansion.

ADR-011 separates same-assigned-file context reading from write lease creation, adds exact location/module-global joins and rejects ambiguous location lists. Existing roles/write bounds and no-callback/no-harness-modification constraints remain. Native source/selector integration and full regressions precede unchanged-case E4B validation. No claim of hard child-loop cancellation.

ADR-012 adds state-derived continuation data and a root-only fixed finalizer accepting one actual handle. No status mutation or generic malformed-call inference. Failure recommendations route to the candidate owner with the same one retry count. All 313 host tests, actual SDK continuation/denial cases and undefined-name lint pass; live finalizer trial follows the frozen source.

Prefer an explicit per-operation baseline object over module-global memoization or monkeypatching Git. Freeze labels to commit IDs for coherent old-side reads. Preserve existing optional call signatures and current-working-tree visibility. Resource tests use real Git, not synthetic model output.
