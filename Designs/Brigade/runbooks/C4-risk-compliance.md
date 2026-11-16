# C4 — Risk and Compliance

Purpose: assault the combined hypothesis before synthesis.

- Inputs: C3, C5, C6, C7, live budget status, competition constraints.
- Output: compartment 4 with per-risk severity, evidence, mitigation, and disposition.
- Required attacks: hidden boundary values, ordering/mutation, API compatibility, protected files, missing dependencies, timeout, malformed output, and budget exhaustion.
- Stop: every applicable risk is fixed, accepted with explicit residual risk, or blocks implementation.
- Forbidden: bulk waivers and unlabeled assumptions.
- Optional input: `closure_review_candidates` may seed hostile checks. An empty or populated `needed_closures` field alone cannot establish that a validation or authorization gate exists or is missing; C7 source and a concrete path check are required.
- Gate: zero undispositioned critical risks.

## Procedure and receipt

1. Verify C3, C5, C6, and C7 identities; call `get_status` once for the live task budget. Never infer the remaining campaign budget from it.
2. Enumerate each applicable attack: boundary input, ordering/mutation, public signature/exception, protected edit path, missing dependency, stale snapshot, output truncation, and deadline exhaustion.
3. For each risk, record severity, C7 or derived-lane refs, concrete hostile input, expected failure mode, mitigation, and residual uncertainty. A hidden-test threat is a proposal, not a verified hidden outcome.
4. Mark each item `mitigated`, `blocking`, or `accepted_with_residual`. Critical risk without an explicit, defensible disposition blocks an `implement` verdict; no bulk waiver.
5. Emit `risks`, hash, and publish `04-risk-compliance.json`. Q3 checks all enumerated IDs have dispositions and no critical blocker is hidden from S.
