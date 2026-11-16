# C5 — Edge Coherence

Purpose: determine whether the proposed causal chain is relationally coherent.

- Inputs: immutable C7 only.
- Output: compartment 5 with caller/callee, data-flow, ordering, mutation, and sibling invariants.
- Required adversary: search the captured witness set for a counterexample to the primary target.
- Stop: critical relations are supported/contradicted/missing.
- Forbidden: extrapolating uncaptured graph edges as fact.
- Gate: every edge has two valid endpoints and a C7 relation/source reference.

## Procedure and receipt

1. Verify the frozen C7 digest and enumerate its captured caller, callee, import, data-flow, test, and sibling relations.
2. For each critical causal edge, check both endpoints against exact excerpts and classify `supported`, `contradicted`, or `missing`. A graph edge without a confirming source excerpt remains inferred.
3. Search the captured witness set for a counterexample: alternate caller, sibling implementation, reversed ordering, mutation, or type constraint that breaks the proposed chain.
4. Emit `relations` with C7 relation refs, evidence refs, verdicts, and reasons. Retain contradictions even if the primary chain otherwise looks strong.
5. Hash and publish `05-edge-coherence.json`; Q3 checks relation-ref kind, endpoint existence, and that no critical contradiction was silently omitted.
