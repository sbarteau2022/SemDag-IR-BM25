# SemDAG: lexical retrieval on a typed code graph

SemDAG localizes likely edit sites for a small code agent. It snapshots live Python source, scores each eligible function against an issue with BM25, and uses those scores to restart a light walk over a typed graph of containment, resolved calls, and imports. The output is a ranked list for inspection, not a patch correctness verdict.

The current paper is **[SemDAG: A Controlled Evaluation of Lexical and Graph Retrieval for Code Agents](PaperTrack/Paper_SemDAG.pdf)** ([LaTeX source](PaperTrack/Paper_SemDAG.tex)). Subtitle: *Auditing a graph-first localizer and measuring BM25-seeded typed walks on 129 public edit-site tasks.* The PDF includes the architecture, damping, and uncertainty figures.

## Measured result

The evaluation covers 129 public competition tasks. Gold function sites exist for 116 tasks; gold file sites exist for 128. Every primary arm uses the same non-test candidate filter.

| Retriever | Function Hit@5 / 116 | Function Hit@10 / 116 | File Hit@10 / 128 |
|---|---:|---:|---:|
| BM25 over live function source | 58 | 68 | 108 |
| SemDAG, damping 0.15 | 56 | 69 | 111 |

The paired SemDAG-minus-BM25 function Hit@5 difference is −1.7 percentage points (95% task-bootstrap interval −7.8 to +4.3); no function-level advantage is established. The file-level count rises by three tasks; no paired interval for that contrast is claimed. Snapshot parity and candidate production pass on all 129 full snapshots. These are localization results. The production SemDAG agent has not had a paired end-to-end resolution run.

The figures and counts come from [`v2_summary.json`](PaperTrack/phase4_semdag/out/v2_summary.json) and [`verify_summary.json`](PaperTrack/phase4_semdag/out/verify_summary.json).

## Design

1. `snapshot.py` inventories Python files and computes a deterministic tree hash. `repo_eval.py` checks parity before ranking.
2. `semdag_ir_ast.py` records file, class, function, and method nodes, including `async def` and exact source spans. It adds lexical `contains`, conservative `calls`, and repository-resolved `imports` edges. Ambiguous calls stay unresolved.
3. `retriever.py` indexes live function bodies with BM25 (`k1=1.2`, `b=0.75`), repeating path and qualified-name terms three times. Positive scores define the restart distribution for a 30-iteration typed walk at damping 0.15.
4. Only positive-BM25 functions can be returned. Tests, generated wrappers, and bundled tool code are excluded from both candidates and the graph. Full-precision scores and file/line tie-breaks make the output deterministic.

At damping zero the ranking equals BM25 exactly; the measurement asserts this task by task. The graph reorders lexical matches but cannot add a function the query did not touch.

## Layout

| Path | Purpose |
|---|---|
| [`AgenticSubmission/v4_semdag/`](AgenticSubmission/v4_semdag/) | Offline ADK agent package and production SemDAG skill |
| [`PaperTrack/Paper_SemDAG.tex`](PaperTrack/Paper_SemDAG.tex) | Single current paper source; compiled PDF alongside it |
| [`PaperTrack/phase4_semdag/measure_v2.py`](PaperTrack/phase4_semdag/measure_v2.py) | Retrieval evaluation using the production retriever |
| [`PaperTrack/phase4_semdag/adversarial_check.py`](PaperTrack/phase4_semdag/adversarial_check.py) | Parity, resolution, exclusion, and determinism checks |
| [`PaperTrack/phase4_semdag/verify_gate.py`](PaperTrack/phase4_semdag/verify_gate.py) | Full-snapshot integrity measurement |
| [`PaperTrack/phase4_semdag/out/`](PaperTrack/phase4_semdag/out/) | Aggregate JSON receipts |

`measure.py`, `phase1/measure.py`, and `legacy_semdag/` support historical control arms in the measurement scripts. They are not the production retriever. Raw datasets, model weights, credentials, task-level patches, and local run logs are not included.

## Run the localizer

The production skill uses Python's standard library. From this repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 \
  AgenticSubmission/v4_semdag/skills/semdag/scripts/repo_eval.py \
  local-task /absolute/path/to/python/repository \
  --problem 'Describe the issue with exact identifiers and error text'
```

The JSON output includes `parity_ok`, graph and relation counts, and `top_edit_sites` with source locations and lexical/structural scores. Its cache defaults to `/tmp`. The agent package invokes the same code as an ADK skill.

## Reproduce the paper

Use Python 3.13 or a compatible Python 3 version. The research measurement needs NumPy for a graph control; the production skill does not. Obtain the public competition dataset separately and point `P4_DATA` at the extracted `data/` directory containing `tasks.jsonl`, `snapshots/`, and `graphs/`.

```bash
python3 -m pip install -r requirements-research.txt
PYTHONDONTWRITEBYTECODE=1 python3 PaperTrack/phase4_semdag/adversarial_check.py
P4_DATA=/absolute/path/to/data P4_SCRATCH=/tmp P4_PROCS=6 \
  python3 PaperTrack/phase4_semdag/measure_v2.py
P4_DATA=/absolute/path/to/data P4_SCRATCH=/tmp P4_PROCS=4 \
  python3 PaperTrack/phase4_semdag/verify_gate.py
tectonic PaperTrack/Paper_SemDAG.tex --outdir PaperTrack
```

The scripts write task-level results locally and refresh aggregate receipts. `verify_gate.py` also reads an earlier completion directory when available; its parity and candidate counts do not depend on those optional diffs. Gold patches are used for scoring only; `hints_text` and `test_patch` do not enter retrieval. The fixed split is 74 selection tasks and 42 disjoint held-out function tasks.

## Limits and license

Dynamic dispatch and runtime imports remain unresolved. Function-level scoring omits module-level and newly added code. The file-level gain is small, and the current agent has no paired resolution evaluation. The agent package targets `gemma-4-e4b-it-qat-w4a16-ct`, with no adapter or second model; this release is not a Kaggle submission.

Licensed under Apache 2.0; see [LICENSE](LICENSE).
