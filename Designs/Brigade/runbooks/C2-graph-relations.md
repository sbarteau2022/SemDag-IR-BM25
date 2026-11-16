# C2 — Graph Relations

Purpose: test C1 candidates against callers, callees, and connecting subgraphs.

- Inputs: admitted C1 records.
- Tools: graph neighbors/subgraph/similarity and targeted reads.
- Output: compartment 2 with ranked target hypotheses and graph provenance.
- Required adversary: record disconfirming edges and disconnected candidates.
- Stop: one primary and one competing hypothesis are bounded, or budget/fallback fires.
- Forbidden: treating embedding similarity as semantic proof.
- Optional input: `repo_ir` `decompose.json` and `context_prob.json` may rank candidates only after their artifact hashes are recorded. `contextual_score` is uncalibrated; a static path is a graph hypothesis, not C7 source proof.
- Gate: each ranked target has an exact graph identifier and reason.

## Procedure and receipt

1. Verify C1 task ID, digest, gate, and candidate IDs. For each candidate, request bounded neighbors or a subgraph; record tool query and graph artifact identity.
2. Rank primary and competing hypotheses by issue fit and observed connectivity. Record disconfirming edges, disconnected candidates, and missing graph coverage explicitly.
3. Use a targeted source read only to resolve an identifier ambiguity. Do not promote an embedding match to a source relationship without C7 verification.
4. Emit `hypotheses` with target identifier, rank, supporting and contradicting graph refs, and unresolved questions. If no target survives, return `empty` and invoke the single relocalization or baseline fallback.
5. Hash and publish `02-graph-relations.json`; Q1 checks unique ranks/IDs and a stated competing hypothesis or its absence reason.
