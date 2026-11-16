# I — Implementation

Purpose: apply the smallest source change only after adversarial outline admission.

- Inputs: C7 exact source and admitted decision packet.
- Tools: targeted reads, source edit/write, targeted commands, budget status.
- Before edit: recompute file hashes and reject stale evidence.
- Required adversary: try to disprove target ownership, control flow, and API safety using C7.
- Output: source delta and implementation result; no approval.
- Forbidden: tests/config edits, unrelated refactors, ledger edits, `submit_patch`.
- Gate: changed paths are a subset of `allowed_files`; diff is nonempty and contract-scoped.

## Procedure and receipt

1. Recompute full-file hashes for every C7 file needed to justify the edit. If any differs, stop with `stale` before writing; request the single permitted relocalization if budget permits.
2. Attempt to falsify target ownership and the proposed fix against caller, sibling, API, and invariant evidence. Record a counterexample or a bounded failure to find one; neither is hidden-test proof.
3. Apply one source-scoped edit inside the allowed paths. Re-read changed files and inspect the exact diff. If the diff reaches tests, runner config, unrelated files, or ledger files, revert and record Q4 failure.
4. Record preimage/postimage hashes and a unified diff digest. Return the implementation result to C8 without calling `submit_patch` or asserting approval.
