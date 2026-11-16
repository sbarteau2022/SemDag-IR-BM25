# F — Finalization

Purpose: submit exactly the admitted source patch.

- Inputs: passed C8 receipt and live status.
- Tools: `get_status`, then `submit_patch`.
- Actions: confirm scratch files are outside `/workspace`, confirm protected paths absent, inspect patch size/files, call `submit_patch` once and last.
- Forbidden: investigation, edits, tests, second submission, or post-submit tool work.
- Gate: nonempty patch receipt or explicit `no_patch` outcome allowed by the controller.

## Procedure and receipt

1. Read the Q5 disposition and live `get_status`. Confirm the diff still has the recorded digest and all changed paths are admitted source paths. Confirm no scratch files are inside `/workspace`.
2. If Q5 passed, call `submit_patch` once. If the controller chose `no_patch`, record that outcome and submit only according to the harness contract. A failed Q5 is never relabeled as verified.
3. Stop. No post-submit tool invocation, second submission, or source mutation is permitted in this lane. The host trace, if available, must capture the pre-submit receipts separately from the scored patch.
