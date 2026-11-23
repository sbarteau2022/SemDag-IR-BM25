# Gemma retrieval optimization — proposed

Status: DEFERRED after live competition requirements review. See reports/competition_requirements_2026-11-22/REQUIREMENTS.md. Establish trustworthy end-to-end evaluation and measured bottleneck before selecting this component optimization. No implementation authorized by this spec.

Problem: v12 retriever._documents calls content.splitlines() once per function, repeating full-file allocation and scanning. Prior validation-only frontier run established no optimization gain.

Decision proposed: create a new candidate from v12; split each referenced file once per _documents invocation. Keep the cache invocation-local, so edits cannot leave stale content across calls. Preserve tokenization, slicing, ranking, floating-point operation order, budgets and model. Keep v6 and existing dirty work untouched.

Alternatives: persistent document cache (larger potential gain but stale-file and invalidation risks); change retrieval heuristics (may alter correctness and risks tuning on public tasks). Invocation-local reuse is the smallest measurable first experiment.

Experiment: baseline and candidate on identical real source snapshots from this repository, excluding competition task data; fixed queries derived from source symbol names, no task answers. Record source hashes, corpus size, candidate counts, raw timings and exact output parity. Alternate baseline/candidate order, warm once, measure seven repetitions. Promotion requires >=20% median improvement in document construction, no more than 5% median regression in full rank, and exact document/rank parity for every query. If the bar fails, reject the candidate and record the result; do not claim optimization.

Adversarial gates: multiple functions in one file; absent content/end_line; empty and Unicode source; both include_tests modes; changed snapshot between calls; exact existing scoring and tie order. Run relevant retrieval tests, full host suite and official submission validation. Distinguish component speedup from end-to-end task resolution; no leaderboard claim.

Loop: measure baseline -> implement one change -> pressure test -> remeasure -> accept/reject with receipts. No agents, training, public-task tuning or Kaggle submission. Update README, session README and project MEMORY with measured outcome. Broader agent-quality optimization requires its own held-out evaluation design.
