---
title: "Shared LoRA Bank Design Index"
document_type: "architecture"
version: "0.3.0"
date: "2026-11-11T00:00:00Z"
implementation_date: null
author: "Codex"
reviewers: []
status: "draft"
related_files:
  - path: "Designs/SharedLoRABank/design.md"
    lines: "1-754"
    role: "primary"
  - path: "Designs/SharedLoRABank/README.md"
    lines: "1-117"
    role: "supporting"
related_issues: []
related_documents: ["design.md", "obsidian-4d-observer.md"]
tags: ["gemma-4", "lora", "architecture", "research-handoff"]
---

# Executive Summary

This folder contains the draft architecture for a shared, sparse LoRA basis bank whose role-specific gates are compiled into ordinary competition adapters. It also defines a time-indexed relational observer for reviewing frozen-model activation evidence. Both are research designs; no E4B pathway or adapter improvement has been measured here.

# Problem Statement

Independent specialist adapters may duplicate or interfere with capabilities; this is a hypothesis, not an observed E4B result. The competition runtime does not expose arbitrary rank-level gating, so the design must preserve one legal base model and produce standard loadable adapters.

# Solution Overview

Read [`design.md`](design.md) for the mathematics, evidence boundaries, training and compilation plan, controls, and admission gates. Read [`obsidian-4d-observer.md`](obsidian-4d-observer.md) for the proposed event ledger, causal graph, time slices, and Obsidian projection. The earlier carved Glimmer swarm motivates matched scoped-view controls; it is not an E4B latent-pathway result.

# Implementation Details

## Files Modified

| File | Lines | Change type | Description |
|---|---:|---|---|
| `design.md` | 1-754 | modified | Research architecture and experimental contract |
| `README.md` | 1-117 | modified | Folder index and handoff status |
| `obsidian-4d-observer.md` | 1-151 | new | Temporal graph and evidence contract |

## Languages Chosen and Why

| Language | Component | Rationale |
|---|---|---|
| Markdown | Architecture handoff | Human-reviewable, diffable, and permitted by the competition package rules |
| JSONL | Planned observer ledger | Append-only experiment events with hashes and explicit status |

Push further: after review and an exact-E4B capture probe, express bank, gate, compiler receipt, experiment manifest, observer events, and admission gates as JSON Schemas and validated YAML.

## Grounding in Verifiable Literature

The design is grounded in the primary papers and local harness sources registered in `design.md`. The capture ledger is a measurement. No basin or adapter result is claimed.

## Configuration Changes

None. This folder does not modify the baseline submission or runtime.

# Testing Evidence

## Test Files and Locations

`observer/test_observer.py`. Successful capture ledger: `observer/out/e4b-mlx-capture-20261111T074425Z/`.

## What the Tests Showed

Twelve observer tests passed. The MLX research-copy prefill `e4b-mlx-capture-20261111T074425Z` validated with zero errors, parity 1.0, and `critical=0`, `unnecessary=0`. Logit KL was recorded and cannot admit either label. No adapter was trained. No basin, pathway, or LoRA effect was measured. This is not a CUDA QAT competition-base result.

## Test Command to Reproduce

From `Designs/SharedLoRABank/observer`, with the repo `.venv-mlx` interpreter: `python -m unittest test_observer.py`, then `python capture_probe.py`. Do not retune the frozen margin, prompts, ablation rule, or selector after seeing a run.

## Was It Proven Necessary?

No. Independent LoRAs have not been trained or shown inadequate.

# Deployment / Rollout

| Aspect | Detail |
|---|---|
| Deployment date | Not deployed |
| Rollout strategy | Review → feasibility probe → controls → held-out evaluation |
| Rollback plan | Remove this candidate directory; baseline remains unchanged |
| Monitoring | Not applicable until implementation |
| Post-deploy validation | Official submission validation and held-out task verification |

# Next Stage of Implementation

| Next step | Description | Depends on this? | Target date |
|---|---|---|---|
| External review | Red-team mathematics, novelty, runtime, and leakage | Yes | Before implementation |
| Feasibility probe | Train/export/load one rank-4 E4B adapter | Yes | After review |
| Machine contracts | Define bank/gate/receipt schemas | Yes | With prototype |
| Observer projection | Measurement ledger validated and vault exported; zero labels admitted | Done for the MLX copy | 2026-11-11 |

This design sets up the feasibility decision because it makes the hypothesis, controls, and failure conditions explicit. It does not establish deployment readiness.

# What We Learned

| Category | Learning |
|---|---|
| Technical | Static compiled views fit the current runtime; dynamic rank routing does not. |
| Process | Another agent set should challenge the proposal before scarce GPU time is used. |
| Tooling | The local harness exposes adapter aliases as served model identities. |
| Estimation | CUDA compatibility is the first implementation unknown. |
| Collaboration | Review questions are embedded in `design.md` for clean handoff. |
| Evidence | Obsidian is a navigable projection; the hashed event ledger must remain authoritative. |

# Changelog

| Version | Date | Author | Change |
|---|---|---|---|
| 0.3.0 | 2026-11-11 | Codex | Added prior carved-swarm boundary and the time-indexed Obsidian observer design. |
| 0.2.0 | 2026-11-11 | Codex | Added final-pass compiler, identifiability, fairness, isolation, provenance, and paper-evidence requirements. |
| 0.1.0 | 2026-11-11 | Codex | Initial folder index for design handoff. |
