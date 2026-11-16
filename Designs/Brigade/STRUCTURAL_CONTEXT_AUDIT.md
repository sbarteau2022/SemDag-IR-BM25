---
title: "Structural Context Reachability Audit"
document_type: "research"
version: "0.1.0"
date: "2026-11-11T00:00:00Z"
implementation_date: null
author: "Codex"
reviewers: []
status: "draft"
related_files:
  - path: "Tools/repo_structural_ir/src/main.rs"
    lines: "794-1194"
    role: "primary"
  - path: "Tools/repo_structural_ir/tests/test_context.py"
    lines: "1-75"
    role: "test"
  - path: "Tools/repo_structural_ir/README.md"
    lines: "1-44"
    role: "supporting"
related_issues: []
related_documents: ["design.md", "Governing_law.md", "runbooks/C2-graph-relations.md", "runbooks/C4-risk-compliance.md"]
tags: ["gemma-4", "structural-ir", "reachability", "audit", "heuristics"]
---

# Question investigated

Can `repo_ir context` provide bounded, source-anchorable graph hints for the brigade without presenting a static-call heuristic as a calibrated vulnerability probability or a proven mitigation chain?

# Methodology

I read the Rust implementation, built the release binary, ran an adversarial three-function fixture and a same-name cross-module fixture, then ran `context` over five public repository snapshots. Outputs were copied to [`evidence/structural-context-2026-11-11`](evidence/structural-context-2026-11-11). The final release binary SHA-256 was `685bfc0df760a99eb5d7e49b2a5a304cd0e9a7f6a04b3cd8329cb94b8bdf5823`. The five saved JSON files were regenerated after the final same-module resolver build.

The command form was `repo_ir context <extracted-snapshot> --out-dir <extracted-snapshot>/.ir`. Wall times were local single-run observations with warm filesystem/cache and are not comparable to the earlier five-repo table or a 12-hour campaign estimate.

# Findings with evidence

| Snapshot | Function nodes | Heuristic sources | Vulnerability rows | Reachable flags | Closure review candidates | Output SHA-256 |
|---|---:|---:|---:|---:|---:|---|
| fastapi_11194 | 3553 | 34 | 576 | 0 | 0 | `6f529c5d194ccd90c579c4a22b30f43f6fc8bf69491d432efe3e0128b3873385` |
| fastapi_11355 | 4094 | 71 | 641 | 24 | 24 | `6b0ed6a19d2d1439a3c8d8c164c6796a4e48a3004b2c9eeff69123a64c63e85e` |
| httpx_3672 | 762 | 8 | 14 | 4 | 4 | `ee33daea715b0f66d92a5e3e7a7c70434b9d0c5c7c9236e72eef29eb9dcc2151` |
| requests_6589 | 644 | 5 | 16 | 0 | 0 | `b9f768c49d567f25ac43bd844aa79e2dbc908990ddbf2f5ad836c969da4b9541` |
| rich_2725 | 1752 | 1 | 105 | 0 | 0 | `8d0cd05e5836bde9011eec68c086f99f62bb94ef87b5fa39270c2275ea26a517` |

The five outputs were regenerated using the final release binary. Their function-node counts differ from the earlier `decompose` node counts because `context` counts functions only, while `decompose` includes macro and micro node types. This table measures output structure and heuristic reachability, not detection precision or task usefulness.

The fixture exposed two false claims in the original implementation: `type_issue` rows appeared in `vulnerable_flags`, and isolated zero-in-degree functions were called reachable sources. Those were corrected. A later fixture demonstrated that global simple-name matching could connect unrelated modules; the resolver now accepts only same-module bare calls and `self.`/`cls.` calls within the current class. Imported and dynamic calls remain unresolved.

For HTTPX `ASSERT-11` at `src/ahttpx/_parsers.py:445`, the scanner's raw `confidence` was **0.5**, not 0.688. The earlier 0.688 was the computed boosted score when the overly broad source rule marked it reachable. Under the conservative final graph it has no found source path and retains score 0.5. No data-flow, guard dominance, exploit, or actual validation gate has been demonstrated for this flag.

`contextual_score` is uncalibrated. `contextual_probability` remains a legacy alias and must not be described as an empirical probability. `needed_closures` is empty because path-node names cannot prove a missing gate; `closure_review_candidates` are prompts for source review. This limits the output to a C2 ranking hint and C4 test seed, with C7 exact source as the authority.

# Recommendation

Use the artifacts to prioritize which source relationships C7 should inspect. Do not submit a vulnerability or mitigation claim from this JSON alone. Before promoting `context`, add import-aware call resolution with ambiguity receipts, explicit source-root provenance, and a held-out precision/recall study against reviewed call paths. Keep the score outside any paper probability claim until calibrated on labeled outcomes.

# Literature review

This audit is grounded in local source and five public snapshots, not a published vulnerability-calibration result. No external paper is used to justify the score formula. The brigade's research register holds broader graph and evidence sources.

# Time invested and reproduction

This was a local design-time audit on 2026-11-11. Reproduce integration checks after `cargo build --release` with:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-harness/bin/python -m unittest Tools/repo_structural_ir/tests/test_context.py -v
```

The two integration tests passed. `cargo test` passed with zero Rust unit tests; the Python integration tests are the meaningful behavioral checks. The five snapshots were rerun after the final resolver build. A reviewed call-path precision/recall study remains open.

# Changelog

| Version | Date | Author | Change |
|---|---|---|
| 0.1.0 | 2026-11-11 | Codex | Recorded code corrections, fixture evidence, five intermediate snapshot outputs, and claim limits. |
