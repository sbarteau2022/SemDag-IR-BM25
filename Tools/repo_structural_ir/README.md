# repo_structural_ir

Rust CLI producing compact structural IR for Python repos. Invoked via `run_command`.

Build:

```bash
cd Tools/repo_structural_ir && cargo build --release
```

Commands:

```bash
# byte-for-byte snapshot into .ir/snapshot.box + index (no context dump)
Tools/repo_structural_ir/target/release/repo_ir snapshot <repo>

# systematic issue scan -> .ir/analyze.json with flag_count_key + flags
Tools/repo_structural_ir/target/release/repo_ir analyze <repo>

# skeletal decomposition -> .ir/decompose.json (context-relational DAG)
Tools/repo_structural_ir/target/release/repo_ir decompose <repo>

# reachability-conditioned heuristic ranking -> .ir/context_prob.json
Tools/repo_structural_ir/target/release/repo_ir context <repo>
```

Outputs are files on disk; commands print only compact receipts to avoid context-window bloat.
Default output dir is `<repo>/.ir` (override with `--out-dir`).

## Context output meaning

`context` emits only `vuln_flag` rows. It maps a flag to the innermost function containing its line; a flag outside every captured function has no `function_node`. A source is a function with a narrow entry-like name (`main`, `cli`, `request`, `handle_request`, `wsgi_app`, `asgi_app`, `serve_forever`, or a `handle_`, `route_`, `endpoint_` prefix). Zero-in-degree functions, file names, and broad parameter names do **not** automatically create sources. Reachability is based on the approximate static call graph, so `reachable_from_source: false` means “no path found in this graph,” not proof the code cannot be reached. At most three shortest paths are emitted per flag to bound packet size.

`contextual_score` is an **uncalibrated heuristic**, not a probability of exploitability or correctness. The legacy `contextual_probability` field carries the same number for compatibility and should not be cited as a probability. `score_kind` states this explicitly. The current score multiplies the scanner confidence by 1.25 for a found path and by another 1.1 when no emitted path node has a mitigation-like name. An absent path leaves the scanner confidence unchanged because the call graph may be incomplete. Values are capped at 0.999 and rounded to three decimals. Name matching is not evidence of actual validation or sanitization.

`closure_review_candidates` lists path nodes where a reviewer should inspect validation or authorization. `needed_closures` remains empty until a separate source-backed check proves a missing gate. `related_holes` is a scan-order-independent proximity hint, not a proven shared root cause. No source-to-sink data-flow, guard dominance, exploitability, or calibration test has been run.

The context call graph resolves bare calls to functions in the same module and `self.`/`cls.` calls to methods of the current class. It does not infer cross-module targets from a shared simple name. Imported, aliased, dynamic, and many object method calls remain unresolved; a missing path is therefore weak negative evidence.

## Minimal adversarial fixture

An eight-line fixture with `entry → helper` and an isolated `orphan` produced two `ASSERT` vulnerability rows after the 2026-11-11 correction. Only the `helper` flag had a path from the heuristic source. The isolated `orphan` flag did not. The two public-function type issues were excluded from the vulnerability output. This fixture checks output semantics, not detection accuracy on a real repository.

A second fixture gives two modules a `helper` function. Calling the first module's `helper` does not make the second module's flag reachable. Run both with `PYTHONDONTWRITEBYTECODE=1 .venv-harness/bin/python -m unittest Tools/repo_structural_ir/tests/test_context.py -v` after `cargo build --release`.
