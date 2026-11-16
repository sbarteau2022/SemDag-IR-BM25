# C7 — Relational Snapshot

Purpose: freeze the exact witness set against which the outline is judged.

- Inputs: C2 hypotheses and current repository baseline.
- Tools: targeted `read_file`; deterministic hashing through `run_command` or admitted skill script.
- Capture: target, callers, callees, relevant siblings, types/imports, usages/tests, base commit, graph identity, exact line ranges, and hashes.
- Output: immutable compartment 7.
- Required adversary: verify that captured source actually supports every proposed relation.
- Stop: minimal causal chain captured or snapshot declared insufficient.
- Forbidden: paraphrasing source as `exact_source`, silently refreshing after freeze.
- Gate: schema valid, unique references, hashes current, target source nonempty.

## Procedure and receipt

1. Read the exact C2 hypothesis identifiers. Resolve each target path and symbol against the current task workspace; record a missing target rather than substituting a similar file.
2. For every captured file, obtain full file bytes and compute `file_sha256`. Extract inclusive 1-based lines without newline normalization and compute `source_sha256` over those excerpt bytes. Record base commit and capture time.
3. Capture a target plus the smallest witness set that can refute its ownership: a caller or entry point, relevant callee, sibling, import/type contract, and test or usage when present. Each relation names two captured file refs and at least one evidence ref.
4. Check that exact excerpts support each observed relation. Mark inferred relations as inferred. Missing endpoints or insufficient context prevent Q2 admission; the controller may spend its single relocalization retry.
5. Serialize canonical JSON, compute the envelope digest, validate schema and live full-file digests, then atomically publish `07-relational-snapshot.json`. Freeze its digest for C3/C5/C6. Any later source change invalidates the snapshot; never refresh it silently.
