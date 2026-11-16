---
title: "Four-Role Gemma 4 Brigade Candidate"
document_type: "implementation"
version: "0.1.0"
date: "2026-11-11T00:00:00Z"
implementation_date: null
author: "Codex"
reviewers: []
status: "draft"
related_files:
  - path: "AgenticSubmission/v1_brigade/agent.yaml"
    lines: "1-25"
    role: "config"
  - path: "AgenticSubmission/v1_brigade/sub_agents/localizer.yaml"
    lines: "1-8"
    role: "config"
  - path: "AgenticSubmission/v1_brigade/sub_agents/analyst.yaml"
    lines: "1-8"
    role: "config"
  - path: "AgenticSubmission/v1_brigade/sub_agents/verifier.yaml"
    lines: "1-8"
    role: "config"
related_issues: []
related_documents: ["../../Designs/Brigade/roles-and-skills.md", "../../Designs/Brigade/Governing_law.md"]
tags: ["gemma-4", "brigade", "candidate", "agent-tools", "skills"]
---

# Executive Summary

This candidate packages one Gemma 4 E4B lead, three bounded helpers, and three deterministic check skills. It is isolated from `v0_baseline` and contains no LoRA adapters. Its first purpose is to prove the four-role layout compiles and then measure whether the added structure helps within a matched task budget.

# Problem Statement

The eleven-lane design has no executable submission variant. A runtime candidate is needed to test whether fewer model agents can preserve localization, snapshot challenge, and verification without exhausting the competition budget.

# Solution Overview

The lead owns edits and the single `submit_patch` call. Localizer, analyst, and verifier are read-only `agent_tool` helpers. Snapshot, packet, and pre-submit skills expose deterministic scripts, but their successful execution depends on the lead invoking them; this package does not yet enforce a controller DAG.

# Implementation Details

| File group | Change |
|---|---|
| `agent.yaml`, `sub_agents/*.yaml` | One base model, one root editor/submitter, three helper views. |
| `prompts/*.md` | Bounded role instructions and source-anchored challenge. |
| `skills/*/SKILL.md`, `skills/*/scripts/check.py` | Exact source hash, packet structure, and changed-path checks. |
| `eval_config.yaml`, `configs/sampling.yaml` | Named five-minute/100-call experimental profile and competition sampling. |

YAML declares the harness graph; Python skills perform only local read-only checks. The skills are supplemental. They cannot prove the cited source semantics, command outcomes, or hidden-test correctness.

# Grounding in Verifiable Literature

This implementation uses the local `DataSets/public/HARNESS_README.md` agent and skill schema and the installed `adk_submission` / ADK skill loader. It is an engineering candidate rather than a literature-derived performance claim.

# Configuration Changes

Only this separate candidate directory was added. Its `eval_config.yaml` is an experimental profile; matched baseline evaluation must use the same cap. No active service or baseline configuration changed.

# Testing Evidence

`validate_directory` passed on this directory and all three skills loaded through ADK's loader. The packet-check parser rejected duplicate keys and non-finite values in direct hostile cases. Skill scripts still require full negative cases, compiler inspection, and a sandbox smoke. No task resolution or throughput result is claimed.

The snapshot and pre-submit path helpers also passed direct traversal and malformed-path checks. Actual ADK skill execution, symlink/rename behavior in an isolated workspace, and patch extraction parity remain unverified.

Offline `compile_submission` with placeholder implementations of the nine allowed tools produced the root lead, three named `AgentTool` helpers, and a root `SkillToolset`. This checks tree shape only; the runner's real registries and task sandbox still need validation.

Reproduce the structural check:

```bash
.venv-harness/bin/python -c "from pathlib import Path; from adk_submission import validate_directory; from swegemma.config import build_submission_limits; validate_directory(Path('AgenticSubmission/v1_brigade'), limits=build_submission_limits()[0])"
```

The change is necessary to test the proposed four-role architecture; its performance necessity is not established.

# Deployment / Rollout

Not deployed. Compile, inspect skill registration, run one sandbox task, then compare matched-budget variants before considering admission. Restore by selecting unchanged `v0_baseline`; never carry a per-task ledger into another task.

# Next Stage of Implementation

Complete skill adversarial checks, compile the agent tree, and confirm `run_skill_script` execution in a sandbox. Add controller enforcement and missing lane receipt schemas before claiming that the whole brigade law is executable.

# What We Learned

Directory validation establishes packaging shape only. The root must actually invoke the skill tools and obey the order before the evidence workflow exists in runtime.

# Changelog

| Version | Date | Author | Change |
|---|---|---|
| 0.1.0 | 2026-11-11 | Codex | Added isolated four-role candidate package and deterministic read-only skill checks. |
