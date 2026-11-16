---
title: "Four-Role Runtime and Eleven-Lane Evidence Contract"
document_type: "architecture"
version: "0.1.0"
date: "2026-11-11T00:00:00Z"
implementation_date: null
author: "Codex"
reviewers: []
status: "draft"
related_files:
  - path: "Designs/Brigade/roles-and-skills.md"
    lines: "1-91"
    role: "primary"
  - path: "Designs/Brigade/README.md"
    lines: "1-52"
    role: "supporting"
related_issues: []
related_documents: ["design.md", "brigade-workflow.md", "Governing_law.md", "runbooks/README.md"]
tags: ["gemma-4", "brigade", "agent-roles", "skills", "architecture"]
---

# Executive Summary

The proposed runtime has one root implementer and three bounded read-only helpers. Eleven evidence lanes remain as logical stages, receipts, and quality gates; they do not require eleven model agents. Deterministic scripts handle hashing and schema checks, while the root remains the sole source editor and submitter.

# Context

The current design has eleven agent declarations, one per lane. That roster adds generation and coordination cost to a shared 12-hour inference campaign. The harness supports `agent_tool` delegation and skill directories, but a skill is exposed through ADK's `SkillToolset`; its script execution and budget behavior must be tested on the actual runner before it becomes a trusted gate.

# Decision

Use four **runtime roles** and retain all eleven **logical lanes**. This is a candidate architecture, not a scored submission change.

| Runtime role | Logical lanes | Write authority | Tools and output |
|---|---|---|---|
| Lead / implementer | Controller, I, F; invokes S compiler and C7 snapshot script | Sole source editor and submitter | File/command/status/submit tools; receives bounded decision packet and receipts. |
| Localizer | C1, C2 | Read-only | Graph and targeted file tools; returns ranked targets and misses. |
| Analyst | C3, C4, C5, C6 | Read-only | Consumes frozen C7; ideally no repository reads; returns source-anchored IR, edges, API, and risks. |
| Verifier | C8 | Read-only source; commands may create ignored test artifacts | Targeted `run_command`, `read_file`, `get_status`; returns exact test receipts and unresolved risks. |

The snapshot is not a conversational summary. C7 must capture exact bytes, full-file and excerpt hashes, and relational witnesses. S is a deterministic packet compiler plus a bounded adversarial judgment step. The lead must recheck fresh source and challenge the packet before editing. If the analyst fails to improve held-out resolution or useful risk detection under matched budgets, remove that agent while preserving C3–C6 checks as deterministic/local lead procedures where possible.

# Consequences

- Fewer model handoffs may save time, but the analyst combines four kinds of reasoning and could miss contradictions. Measure this rather than assuming improvement.
- A four-view LoRA bank can map one adapter to each runtime role. The base remains E4B for all; adapters are optional and separately admitted. Do not couple the brigade design gate to an untrained bank.
- Logical lane IDs and evidence schemas remain stable for audit, rollback, and comparisons. Consolidation changes **who produces** a lane record, not the meaning of that record.
- Only the lead edits source and calls `submit_patch`. The verifier's `run_command` cannot become an indirect source edit; pre/post hashes and path inspection must detect that.
- Skill scripts may compute hashes, validate schemas, compile bounded packets, and inspect a patch. They may not invent evidence, fetch the internet, or bypass the nine permitted harness tools. Confirm actual skill-script execution through `validate_directory`, compilation, and a sandbox smoke before reliance.

# Alternatives considered

| Alternative | Benefit | Cost / reason not selected now |
|---|---|---|
| Eleven runtime agents | Clear ownership per lane | High handoff and context cost; no measured quality gain. |
| Root only | Simplest orchestration | Loses independent read-only localization and verification views. |
| Four roles, discard lanes | Short prompts | Loses stable receipts and the relational snapshot's falsification trail. |

# Implementation contract

1. Keep this file as the consolidated architecture decision. `design.md` owns the evidence model, `brigade-workflow.md` owns order/budgets, and `Governing_law.md` owns precedence and gates. The bank design owns adapter research, not brigade runtime procedure.
2. Replace `contracts/agents.yaml` with a versioned four-role candidate **only when** a `v1_brigade` package is drafted. Preserve the eleven-lane `contracts/lanes.yaml` and add a role-to-lane map. Do not silently reinterpret existing validator passes as four-role validation.
3. Draft `AgenticSubmission/v1_brigade/` as an isolated candidate, leaving `v0_baseline` unchanged. It should contain root and three helper YAMLs, prompts, named skill directories, sampling/eval configs, and a README. No adapter is required for the first compiler smoke.
4. Validate directory, compile the agent tree, inspect actual tool registration, and run a one-task sandbox smoke with a fixed cap. Capture wall time, tool calls, model tokens, patch validity, and whether skill scripts executed. Do not promote on compilation alone.
5. Compare matched-budget variants: baseline; lead+localizer; lead+localizer+verifier; four roles. Keep the same task split and model service. Admit the analyst only if it improves the pre-registered primary outcome or a material, explicitly named safety/quality endpoint without breaking time budget.

# Grounding in Verifiable Literature

This decision uses the local `DataSets/public/HARNESS_README.md` sections 2.1–2.4 and the installed `adk_submission` schema/resolver as its runtime sources. It is an engineering architecture proposal, not a claim established by published literature. The parent design's local source register and research record cover the snapshot and adversarial-outline rationale.

# Testing Evidence

The current design-contract validator passes the eleven-agent fixture. It does not validate this four-role candidate. No four-role `validate_directory`, compiler smoke, task run, or matched ablation has occurred.

# Rollout and restore

Keep the baseline package and Phase 2 outputs unchanged. Build v1 in a separate directory; the first release gate is local compilation, the second is a one-task behavior smoke, and the third is matched held-out evaluation. Restore by selecting the unchanged baseline package; never reuse a task ledger across runs. Port 8123 remains shared and is not restarted for this draft.

# Next Stage of Implementation

Create the role-to-lane YAML map and four-role package, then extend the validator to check producer permissions and lane coverage. Add dedicated controller, implementation, command, and host-export schemas before claiming a deterministic workflow proof. This document sets up a reviewable implementation path, but it does not establish that the architecture beats the baseline.

# What We Learned

The number of evidence stages and the number of model agents are independent design choices. Preserving C7 and the receipts is essential to test whether a concise outline remains relationally coherent.

# Changelog

| Version | Date | Author | Change |
|---|---|---|
| 0.1.0 | 2026-11-11 | Codex | Chose four candidate runtime roles while preserving eleven logical evidence lanes and explicit admission gates. |
