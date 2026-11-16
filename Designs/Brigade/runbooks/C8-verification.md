# C8 — Verification

Purpose: test the patch and close the provenance chain.

- Inputs: admitted packet, C7 preimages, current source delta.
- Tools: targeted reads/commands and budget status.
- Record: pre/post file hashes, patch hash, exact commands, exit codes, output hashes, adverse checks, and unresolved risks.
- Required adversary: verify neighboring behavior and inspect the exact diff for forbidden paths.
- Stop: checks pass, budget reserve requires finalization, or exact failure is recorded.
- Forbidden: source/test edits, claiming hidden-test proof, suppressing failures.
- Gate: every planned check has a receipt and every failure is dispositioned.

## Procedure and receipt

1. Verify the S packet digest, I diff, changed-file list, and preimage hashes. Recompute patch hash from exact bytes. A mismatch blocks a passing Q5 receipt.
2. Run each planned targeted command once within remaining budget; record command, exit code, stdout/stderr bytes or retrievable artifact location, and their hashes. Missing dependencies are an unresolved failure, not a pass.
3. Inspect neighboring behavior, boundary values, and protected paths. Record every failed or skipped adverse check individually with its reason and residual risk.
4. Emit compartment 8 with patch digest, judge receipt references, unresolved list, and a Q5 disposition. C8 never edits the patch to make a test pass; send a failure to the controller for a distinct implementation retry or honest finalization.
