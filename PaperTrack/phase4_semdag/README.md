---
title: "Repair SemDAG Source Retrieval and Typed Structural Walk"
document_type: "implementation"
version: "1.0.0"
date: "2026-11-12T22:50:48Z"
implementation_date: "2026-11-12T22:50:48Z"
author: "Stewart Barteau / Local Codex"
reviewers: []
status: "draft"
related_files:
  - path: "AgenticSubmission/v4_semdag/skills/semdag/scripts/snapshot.py"
    lines: "1-77"
    role: "supporting"
  - path: "AgenticSubmission/v4_semdag/skills/semdag/scripts/semdag_ir_ast.py"
    lines: "1-175"
    role: "primary"
  - path: "AgenticSubmission/v4_semdag/skills/semdag/scripts/retriever.py"
    lines: "1-134"
    role: "primary"
  - path: "AgenticSubmission/v4_semdag/skills/semdag/scripts/repo_eval.py"
    lines: "1-231"
    role: "supporting"
  - path: "PaperTrack/phase4_semdag/measure_v2.py"
    lines: "1-462"
    role: "test"
  - path: "PaperTrack/phase4_semdag/adversarial_check.py"
    lines: "1-74"
    role: "test"
  - path: "AgenticSubmission/v4_semdag"
    lines: "1-1"
    role: "config"
related_issues: []
related_documents: ["PaperTrack/Paper_SemDAG.tex", "PaperTrack/Paper_SemDAG.pdf"]
tags: ["gemma-4", "retrieval", "code-graph", "bm25", "pagerank"]
---

# Executive Summary

We repaired SemDAG so it queries live function source before using repository structure. The agent now receives source-grounded candidates, while a light typed graph walk adds file context without overwhelming the lexical signal.

# Problem Statement

The original ranker used exact bare-name seeds and reversed call edges only. It ignored function source, containment, imports, and test-file admission; its snapshot hash also disagreed with its own parity check. Offline Hit@5 was 25 of 116 tasks, and the runtime gate returned no candidates on every full snapshot.

# Solution Overview

The repaired pipeline builds qualified file, class, function, and method nodes; resolves conservative calls and repository imports; scores non-test function source with BM25; and uses those scores as the restart distribution for a damping-0.15 typed walk. The measurement imports the production retriever, preventing a paper-only implementation from drifting away from shipped code.

# Implementation Details

## Files Modified

| File | Lines | Change Type | Description |
|---|---:|---|---|
| `semdag/snapshot.py` | 20-58 | modified | Canonical globally sorted tree hash |
| `semdag/semdag_ir_ast.py` | 1-175 | rewritten | Qualified spans, imports, and conservative call resolution |
| `semdag/retriever.py` | 1-134 | new | BM25 restart and typed graph walk |
| `semdag/repo_eval.py` | 32-231 | modified | Production retriever integration and compact evidence |
| `measure_v2.py` | 266-462 | modified | Calls production retriever for all DAG arms |
| `adversarial_check.py` | 1-74 | new | Hostile structural and admission checks |
| `AgenticSubmission/v4_semdag/` | all | new | Validated competition package |

## Languages Chosen and Why

| Language | Component | Rationale |
|---|---|---|
| Python | IR, retrieval, verification | Required offline runtime; `ast` and standard library need no vendored dependency |
| Markdown | paper and operations | Human review and Kaggle paper compatibility |

Next, the typed walk could add edge-specific learned weights, but only after a repository-disjoint training protocol prevents public-task tuning.

## Grounding in Verifiable Literature

| Paper | Venue/Year | What Was Used | Link/DOI |
|---|---|---|---|
| Robertson and Zaragoza, “The Probabilistic Relevance Framework: BM25 and Beyond” | FnTIR, 2009 | BM25 retrieval | <https://doi.org/10.1561/1500000019> |
| Haveliwala, “Topic-Sensitive PageRank” | WWW, 2002 | Personalized restart walk | <https://doi.org/10.1145/511446.511513> |

## Configuration Changes

`DEFAULT_DAMPING=0.15`; relation weights default to 1.0 for `contains`, `calls`, and `imports`. Tests and tool paths (`.adk_exec_*`, `semdag/`) are excluded before retrieval and traversal.

## Paper Track Artwork

`PaperTrack/assets/semdag-card-v5-560x280.png` is the selected 560 × 280 Kaggle write-up card and thumbnail. It places “SemDAG” over a realistic code workstation and centers the compact two-line subtitle “Query the Source. Walk the Structure.” beneath the title, within the thumbnail safe area. Earlier card versions are retained as alternates. This is presentation artwork, not measured evidence; the paper's reported results remain in the tables and run receipts.

Write-up metadata and current LaTeX title page (character counts include spaces and punctuation):

- Title (78/80): `SemDAG: A Controlled Evaluation of Lexical and Graph Retrieval for Code Agents`
- Subtitle (101/140): `Auditing a graph-first localizer and measuring BM25-seeded typed walks on 129 public edit-site tasks.`

# Testing Evidence

## Test Files and Locations

| Test File | Lines | Test Type | Coverage |
|---|---:|---|---|
| `adversarial_check.py` | 1-74 | adversarial contract | parity, import/call resolution, duplicate names, determinism, admission |
| `measure_v2.py` | 1-462 | corpus evaluation | all 129 public tasks, held-out repository, paired bootstrap |
| `verify_gate.py` | 1-125 | integration | all full snapshots and candidate patches |

## What the Tests Showed

The adversarial fixture passes and uses all three relation types without linking the wrong duplicate function. Full-corpus D15 reaches 56/116 Hit@5 and 69/116 Hit@10, statistically level with BM25, while file Hit@10 improves from 108 to 111 of 128. Repaired parity and localization pass 129 of 129 full snapshots. The syntax-only verifier still rejects none of 129 gold and 11 applicable model patches; tests remain required for correctness.

## Test Commands

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-harness/bin/python PaperTrack/phase4_semdag/adversarial_check.py
P4_SCRATCH=/tmp P4_PROCS=6 .venv-harness/bin/python PaperTrack/phase4_semdag/measure_v2.py
.venv-harness/bin/python -c "from pathlib import Path; from adk_submission import validate_directory; from swegemma.config import build_submission_limits; validate_directory(Path('AgenticSubmission/v4_semdag'), limits=build_submission_limits()[0])"
```

## Was It Proven Necessary?

Yes. The legacy ranker reached 28/116 Hit@5 after equal filtering, versus 56/116 for repaired D15, and its parity gate produced zero candidates on full snapshots.

# Deployment / Rollout

| Aspect | Detail |
|---|---|
| Deployment date | Not deployed or submitted |
| Rollout strategy | New `v4_semdag` candidate; preserve `v2_bm25` for paired comparison |
| Rollback plan | Select the unchanged `v2_bm25` submission |
| Monitoring | Axe 4 trace reader plus harness resolution and tool-call reports |
| Post-deploy validation | Required: paired real-harness run on the same task IDs |

# Next Stage of Implementation

| Next Step | Description | Depends On This? | Target Date |
|---|---|---|---|
| Paired v4 run | Compare D15 agent against v2 on identical tasks | Yes | Before final submission |
| Edit reliability | Reduce rejected exact-string edits | No | Before final submission |
| Test-aware verifier | Require targeted behavioral evidence | Yes | Before final submission |

This implementation set us up for the competition goal because the shipped package and the measured algorithm are now the same code, but it does not prove an agent-level gain until the paired v4 run finishes.

# What We Learned

| Category | Learning |
|---|---|
| Technical | Graph traversal needs a strong query distribution; structure alone cannot infer issue relevance |
| Process | Equal candidate admission must be checked before comparing retrieval systems |
| Tooling | Axe 4 exposed wrapper candidates invisible to offline repository snapshots |
| Estimation | Repairing the graph required fixing indexing, query, admission, parity, and measurement together |
| Collaboration | Preserve historical arms rather than rewriting evidence in place |

## Changelog

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.2 | 2026-11-12 | Stewart Barteau / Local Codex | Established one current LaTeX paper and compiled PDF with measured vector figures; archived the superseded Markdown draft |
| 1.0.1 | 2026-11-12 | Stewart Barteau / Local Codex | Revised Paper Track narrative to anonymize benchmark codebase names and remove claims about patch content while preserving measured retrieval and agent results |
| 1.0.0 | 2026-11-12 | Stewart Barteau / Local Codex | Initial repaired SemDAG implementation record |

# Layout after cleanup (2026-11-12, 23:10 UTC)

- **One production copy.** `AgenticSubmission/v4_semdag/skills/semdag/scripts/` holds `repo_eval.py`, `retriever.py`, `semdag_ir_ast.py`, `snapshot.py` and `cache.py`. It ships as an ADK skill because a script directory beside `agent.yaml` is not present in the sandbox. `measure_v2.py`, `verify_gate.py` and `adversarial_check.py` import these files directly.
- **One frozen legacy copy.** `legacy_semdag/` is the system as first shipped (parity fails, reversed-calls ranker). `measure.py` runs against it; `P4_SEMDAG=legacy_semdag verify_gate.py` reproduces the as-shipped gate.
- **Removed.** The working copy under `DataSets/public/data/sample_submission/semdag/` was moved to the Trash; rows above that say `semdag/...` refer to the production copy.
- **Tests-kept control.** `P4_KEEP_TESTS=1 measure_v2.py` passes `include_tests=True` to the production retriever and skips the zero-damping identity assertion, because the production snapshot omits files over 256 KB.
