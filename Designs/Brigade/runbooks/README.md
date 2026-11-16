# Lane Runbooks

These are draft operating procedures. `Governing_law.md` and machine contracts take precedence.

Each lane must:

1. Confirm dependency receipts.
2. Read only declared inputs.
3. Stay inside its time and tool budget.
4. Write only its unique output key/file.
5. Label every claim and cite C7 where required.
6. Return an explicit status, including partial, empty, malformed, stale, or budget-exhausted.
7. Never self-approve.

Runbooks exist per lane because responsibilities, tool surfaces, and stop conditions differ. Shared prose alone is too ambiguous for deterministic admission.

## Binding handoff protocol

Each lane starts only after the controller verifies every dependency artifact's schema, content digest, task ID, and gate receipt. The lane receives the exact artifact hashes in `input_digests`; C3, C5, and C6 receive the same frozen C7 digest. A missing, stale, or mismatched input blocks the lane and produces a failure receipt. No lane repairs another lane's artifact in place.

The producer writes one temporary file under its declared `/tmp/gemma-brigade/current/` name, validates it, then atomically renames it to the committed lane path. A correction is a new attempt with a supersedes reference in the controller ledger. A lane cannot call `submit_patch` except F, and no lane may write repository source except I. The controller preserves a per-lane call count, monotonic start/deadline, and exact status response; prose promises do not enforce budgets.

| Lane | Required input | Committed output | Failure handoff |
|---|---|---|---|
| C1 | Issue and task manifest | `01-graph-seeds.json` | Empty seed set to C2 only as explicit fallback evidence |
| C2 | Valid C1 | `02-graph-relations.json` | Relocalize once, then baseline fallback |
| C7 | Valid C2 and fresh workspace | `07-relational-snapshot.json` | Incomplete witness blocks derivation |
| C3 | Frozen C7 | `03-structural-ir.json` | Missing/lossy IR to S as named uncertainty |
| C5 | Frozen C7 | `05-edge-coherence.json` | Contradiction/missing relation to S |
| C6 | Frozen C7 | `06-api-contract.json` | Missing API boundary to C4 and S |
| C4 | C3, C5, C6, C7 | `04-risk-compliance.json` | Critical risk blocks S implement verdict |
| S | C3–C7 | `decision-packet.json` | Relocalize, fallback, or no patch |
| I | Fresh C7 and admitted S | Workspace source delta | Stale hash blocks edit |
| C8 | S, I, current diff | `08-verification.json` | Exact failure to F; no false pass |
| F | C8 and live status | One `submit_patch` call | Honest `no_patch` or terminal failure |

The evidence schemas cover C7, generic compartment records, S, judge receipts, controller chronology, and host export custody. Lane payloads, implementation results, and verification command receipts still need dedicated schemas. The controller and host export schemas are offline contracts; they do not imply a deployable deterministic controller or a real host export hook.
