# S — Synthesis and Outline Gate

Purpose: compile admitted evidence and attempt to falsify the repair outline.

- Inputs: schema-valid C3–C7 records only.
- Tools: deterministic validator/compiler first; model reasoning second.
- Output: one bounded decision packet.
- Rules: introduce no new evidence; cite C7 for every critical claim; verdict each claim supported/contradicted/missing/stale.
- Stop: `implement`, `relocalize`, `fallback`, or `no_patch` verdict emitted.
- Forbidden: source reads/edits, tests, uncited facts, hiding disagreement through summarization.
- Gate: no critical non-supported claim may accompany `implement`.

## Procedure and receipt

1. Verify all input task IDs, hashes, schema versions, and the shared C7 digest. Preserve disagreement instead of majority voting across same-model agents.
2. Build a bounded claim table: claim ID, source lane, exact C7 refs, competing explanation, support, counterevidence, and `supported|contradicted|missing|stale` verdict. Deduplicate only claims with the same meaning and evidence; retain provenance of all originals.
3. Try to defeat the primary outline using C5 contradictions, C6 public contracts, C3 conversion losses, and C4 critical risks. A critical missing or contradicted claim cannot be converted to `supported` by fluent explanation.
4. Emit exactly one decision packet. `implement` requires a fresh snapshot, supported critical claims, safe allowed paths, and an explicit preservation contract. Otherwise choose one permitted relocalization, predeclared baseline fallback, or `no_patch`, with reason.
5. Hash and atomically publish the packet. The implementer must independently recheck source bytes and may reject it as stale; S does not self-approve.
