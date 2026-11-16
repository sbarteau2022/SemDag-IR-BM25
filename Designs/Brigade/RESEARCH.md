# Research Record

Date: 2026-11-10  
Status: **PROPOSED SYNTHESIS**

## Question

Can a per-task, snapshot-backed evidence brigade improve Gemma 4 E4B patch quality without violating competition limits or losing relational source coherence? This unblocks whether to implement a candidate agent hierarchy after the baseline run.

## Pre-registered acceptance criteria

Recorded before the machine contracts were authored:

1. The design must fit the declarative agent schema and allowed tool/skill surface.
2. It must distinguish task containers, application evidence, model KV cache, and verification containers.
3. It must preserve an immutable exact-source snapshot between localization and implementation.
4. It must have deterministic gates, bounded lane budgets, failure/reset rules, and no self-graded completion.
5. It must not claim improved resolution until a held-out run demonstrates it.

## Provenance

| ID | URL/path | Version/date | License | Claim supported |
|---|---|---|---|---|
| P1 | `file://AGENTS.md` | 2026-11-10 workspace | Project-local; not stated | Competition/project constraints and prohibited actions. |
| P2 | `file://DataSets/public/HARNESS_README.md` | installed dataset, read 2026-11-10 | Apache 2.0 dataset documentation | Declarative schema, nine tools, sandbox lifecycle, budgets, patch extraction. |
| P3 | `file://.venv-harness/lib/python3.13/site-packages/adk_submission/schema.py` | adk-submission 0.2.13 | Installed package; package license not independently rechecked | Llm/Sequential/Parallel/Loop agents, output keys, include contents, limits. |
| P4 | `file://.venv-harness/lib/python3.13/site-packages/swegemma/harness/agent_runner.py` | swegemma 0.2.11 | Installed package; package license not independently rechecked | Shared task context, compiler invocation, session state, optional compaction. |
| P5 | `file://PaperTrack/phase2/generate.py` | frozen Phase 2 script, 2026-11-10 | Project-local; not stated | Active experiment invariants and exact-line generation measurement. |
| P6 | requested `atoma-harness` delivery/research/pressure skills | plugin 1.0.0, 2026-10-30 | Plugin-local; not stated | Contract-first packets, judges, honest labels, hostile-edge disposition. |

## Labeled synthesis

**VERIFIED [P2,P4]:** Task specialists share one task sandbox and harness context, while verification uses a fresh sandbox receiving the patch. Therefore an ephemeral per-task ledger is compatible with the lifecycle if it remains outside the patch.

**VERIFIED [P2,P3]:** Declarative parallel and sequential agents, `output_key`, AgentTool isolation, and skill scripts exist. Custom callbacks are not available in the scored compile path observed locally because no callback registry is supplied.

**VERIFIED [P5]:** The current Rich study contains many empty localization spans and measures exact gold-line emission, demonstrating that additional reasoning structure cannot recover source evidence that localization never captured.

**INFERRED [P2,P4]:** Application-level evidence compartments can reduce repeated context only if the deterministic compiler emits a smaller packet than the raw evidence. Evidence ends before any measured resolution benefit.

**PROPOSED:** C7 should be the immutable authority boundary, and one S lane should adversarially disposition the outline before implementation.

## Criteria disposition

Criteria 1–4 are addressed by the design and contracts but remain subject to validator and pressure-test receipts. Criterion 5 remains unmet until an evaluation run exists; no performance claim is admitted.
