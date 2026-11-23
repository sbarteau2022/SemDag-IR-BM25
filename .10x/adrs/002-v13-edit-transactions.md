# ADR-002: Native edit transactions and fused lifecycle operations

Status: Accepted (owner approved Stage 1).

Context: measured off-span edits, stale-coordinate edits and stale apply; live tool-format failures. Existing official skill envelopes remain mandatory.

Decision: task/slot manifests and hash-bound single-use edit handles; scoped atomic edits; fused prepare and finalize with independent verification and conditional rollback. Protect legacy managed-slot edit/apply paths through the same transaction checks. No hidden model-output repair or official harness modification. Preserve current v13 through Git and a local snapshot before edits. Work on v13-edit-transactions.

Alternative: instructions alone do not enforce file/version checks. Persistent host adapters would change scorer behavior and are rejected.

Consequences: extra native checks/copies can cost time; the approved no-more-than-10-percent native timing regression and three-call reduction gates may fail. Record failures without relaxing thresholds. No task-quality promotion from component proof. Root/subagent role counts and dispatch policy stay fixed for Stage 1.
