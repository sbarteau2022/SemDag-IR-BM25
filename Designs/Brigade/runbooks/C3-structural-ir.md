# C3 — Structural IR

Purpose: derive a low-entropy behavioral representation from C7 without replacing exact source.

- Inputs: immutable C7 only.
- Output: compartment 3 describing branches, reads/writes, state transitions, and edit candidates.
- Required adversary: name syntax or behavior that the IR cannot preserve.
- Stop: causal control/data path is represented or evidence is insufficient.
- Forbidden: new repository reads, invented edges, pseudocode presented as source.
- Gate: every non-proposal claim cites C7 and every inference states its boundary.

## Procedure and receipt

1. Verify the frozen C7 digest. Read only its exact excerpts and relations; the lane has no repository-read tool.
2. Encode the target's entry conditions, branches, state changes, reads/writes, outputs, and exceptional exits as source-anchored blocks. Every block cites a C7 file or relation ref.
3. List conversion losses: dynamic dispatch, reflection, omitted callers, truncated functions, ambiguous types, or effects the IR cannot represent. A loss stays visible to S and I.
4. Challenge the proposed edit path with a counterexample branch or mark the branch `missing` if C7 lacks evidence. Do not convert pseudocode into a quote from source.
5. Emit `blocks` and `losses` in compartment 3, bind the C7 digest, and publish `03-structural-ir.json`. Q3 rejects unsupported exact claims and empty inference boundaries.
