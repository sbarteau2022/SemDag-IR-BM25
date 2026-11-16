# Snapshot-Backed Evidence Brigade

Status: **PROPOSED**  
Packet: `BRIGADE-DESIGN-001`

## Design question

Can one Gemma 4 E4B agent solve more repository tasks within the competition budget when read-only specialists produce compartmentalized evidence, an immutable relational snapshot grounds every claim, and a final implementer adversarially validates the outline before editing?

The design unblocks one decision: whether to build and evaluate a brigade submission variant after the single-agent baseline completes.

## Boundary model

The Kaggle inference service is one vLLM server tensor-parallel over four 24 GB L4 GPUs. It is not four task containers. Each task receives an isolated sandbox with 4 GiB RAM and 2 CPUs. All agents for a task share that sandbox, the harness tool budget, session state, and model service.

The brigade proposes an application-level ledger in `/tmp/gemma-brigade/`. It does not control or persist the model's internal attention KV. vLLM owns and reclaims GPU KV for active sequences. The current `contracts/*.yaml` are design specifications, not ADK configuration files; no runtime controller or skill script has been admitted yet.

## Stable evidence compartments

The numeric identifiers remain stable even though execution follows dependencies rather than numeric order.

1. **Graph seeds:** issue-derived symbols, resolution attempts, and failure reasons.
2. **Graph relations:** neighbors, candidate subgraphs, rankings, and provenance.
3. **Structural IR:** control flow, reads/writes, state transitions, and edit candidates derived from snapshot evidence.
4. **Risk and compliance:** hidden-test threats, protected-file rules, budget risk, and waivers.
5. **Edges and invariants:** caller/callee, data-flow, ordering, and relational coherence claims.
6. **API contracts:** exact signatures, types, exceptions, public behavior, and compatibility requirements.
7. **Relational snapshot:** immutable exact source excerpts, hashes, base commit, graph/embedding identities, imports, callers, callees, siblings, and relevant tests/usages.
8. **Verification:** pre/post hashes, diff identity, targeted commands, exit codes, and unresolved uncertainty.

## Execution DAG

```text
Controller
  └─ C1 Graph seeds
       └─ C2 Graph relations
            └─ C7 Relational snapshot [authority boundary]
                 ├─ C3 Structural IR
                 ├─ C5 Edges and invariants
                 └─ C6 API contracts
                        └─ C4 Risk and compliance
                             └─ S Synthesis and adversarial outline gate
                                  └─ I Single implementer
                                       └─ C8 Verification
                                            └─ F Submit/finalize
```

C3, C5, and C6 may execute in parallel because they are read-only and consume the same frozen C7 snapshot. All other transitions are ordered.

## Snapshot authority

The outline is a falsifiable hypothesis. The snapshot is the witness set. Every non-proposal claim must cite a snapshot reference containing an exact file hash and line range. The implementer must try to disprove the outline by checking actual source, relationships, sibling behavior, API constraints, and stale hashes.

The snapshot is relational, not a whole-repository copy. It contains the smallest exact set needed to test the proposed causal chain: target, callers, callees, relevant siblings, imports/types, and nearby tests or usages. Missing evidence produces `missing`, never an invented claim.

## S lane decision

There should be exactly one `S` lane. It is not a free-form summarizer and cannot introduce evidence. A deterministic controller validates schemas, enforces the packet budget, and compiles the admitted records before S sees them. S deduplicates claims, resolves contradictions, and emits supported/contradicted/missing/stale verdicts from those records and exact snapshot excerpts.

## Truth and proof

The ledger is an evidence record, not proof that a patch is correct. SHA-256 proves byte identity only. A workflow claim is admitted only when its source, status, boundary, and deterministic judge are present. Hidden-test correctness is established only by the competition verifier.

## Isolation and persistence

One task owns one ledger. Parallel agents write unique files or state keys. No task reads another task's ledger. Container destruction is the default reset. The source patch is the only artifact transferred into the fresh verification container. Local traces may retain ledger outputs for research; scored patches must not include the ledger.

## Admission hypothesis

The brigade is admitted only if it improves held-out resolution rate or produces a pre-registered, practically material efficiency/quality advantage without increasing invalid patches. Better ledger completeness, graph coverage, or exact-line overlap alone is insufficient.
