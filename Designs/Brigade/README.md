# Gemma 4 Brigade Design Bundle

Status: **PROPOSED / NOT YET ADMITTED TO THE SUBMISSION**  
Packet: `BRIGADE-DESIGN-001`  
Date: 2026-11-10

This directory specifies an ephemeral, per-task evidence brigade for the Gemma 4 E4B competition agent. It does not claim that the design improves resolution rate. Admission requires the gates in `Governing_law.md` and measured comparison against the validated baseline.

## Documents

- `design.md`: architecture, boundaries, and evidence model.
- `brigade-workflow.md`: executable order, lane budgets, and task lifecycle.
- `Governing_law.md`: binding protocol, quality gates, release, restore, and reset.
- `roles-and-skills.md`: four-role candidate mapping that preserves the eleven logical lanes.
- `HANDOFF_CHECKPOINT.md`: current package, validation, risks, and exact resume actions.
- `STRUCTURAL_CONTEXT_AUDIT.md` and `evidence/structural-context-2026-11-11/`: measured Rust context output and its claim limits.
- `RESEARCH.md`: question, pre-registered criteria, provenance, and labeled synthesis.
- `PRESSURE_TEST.md`: hostile-edge inventory and dispositions.
- `AUDIT.md`: deviations, unsupported claims, open risks, and admission status.
- `contracts/*.yaml`: deterministic lane and agent contracts.
- `contracts/roles.yaml`: candidate four-role mapping; the existing eleven-agent contract remains a design comparator.
- `schemas/*.json`: machine-readable evidence, snapshot, decision, and judge formats.
- `schemas/controller-ledger.schema.json` and `schemas/host-export.schema.json`: task chronology and out-of-patch audit custody.
- `schemas/implementation-result.schema.json` and `schemas/command-receipt.schema.json`: source-delta and targeted-command receipts.
- `examples/*.json`: non-production fixtures for validation.
- `runbooks/*.md`: per-lane operating procedures.
- `tools/validate_contracts.py`: offline structural validator.

The validator checks example digests, schema shape, lane/agent coverage, controller sequence/counters, export path custody, and selected hostile mutations. It rejects derived sections without the exact C7 input digest, duplicate claims, relation/file reference confusion, and protected edit targets. It does **not** validate a live task workspace, full-file preimages, runtime budget enforcement, or host trace retention; those gates remain open.

The lane index now names each input and committed output and defines the common atomic handoff rule. Every lane has a stepwise draft procedure. Dedicated lane payload schemas remain open work; implementation and command receipt schemas now pass offline fixture and hostile checks.

The [four-role decision](roles-and-skills.md) retains eleven logical evidence lanes while assigning runtime work to a lead, localizer, analyst, and verifier. The validator checks role/lane coverage, unique source-write and submit authority, tool allowlisting, and deterministic skill ownership. This candidate has not been compiled into a submission package or run on tasks.

## Status vocabulary

- `VERIFIED`: directly read or measured.
- `REPORTED`: stated by a source but not independently measured here.
- `INFERRED`: reasoned from evidence; the evidence boundary is named.
- `PROPOSED`: design or policy awaiting admission.

## Non-claims

- The eight stores are application-level evidence compartments, not partitions of vLLM's GPU KV cache.
- Hashes prove identity and integrity, not semantic truth.
- Phase-1 targeted tests are not hidden-test proof.
- `/tmp` evidence disappears with the task container unless the host trace captures it.
- The model server stays shared and persistent; task containers and ledgers are ephemeral.

## Validation

```bash
.venv-harness/bin/python Designs/Brigade/tools/validate_contracts.py Designs/Brigade
```

The active Phase 2 generation process and port `8123` are outside this packet's blast radius.
