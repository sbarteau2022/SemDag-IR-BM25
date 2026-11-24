# SemDAG: graph-guided code localization for a small coding agent

This repository is a solo entry in Kaggle's *Gemma 4 Developer Agent* competition. A 4B-parameter model, `gemma-4-e4b-it-qat-w4a16-ct`, has to resolve real GitHub issues inside a sandbox with a 4-minute budget per task. The work has two parts:

1. **SemDAG**, a typed graph IR of a Python repository plus a BM25-seeded walk. It ranks the functions an issue most likely touches. It is evaluated in a paper with a controlled retrieval study.
2. **An agent line** (v0 to v13), packaged as offline ADK submissions. Each version is a separate, zippable folder, measured end to end on held-out tasks.

The paper is **[SemDAG: A Controlled Evaluation of Lexical and Graph Retrieval for Code Agents](PaperTrack/Paper_SemDAG.pdf)** ([LaTeX](PaperTrack/Paper_SemDAG.tex)).

## Results so far

**Localization (paper, 129 public tasks).** Every primary arm uses the same non-test candidate filter.

| Retriever | Function Hit@5 / 116 | Function Hit@10 / 116 | File Hit@10 / 128 |
|---|---:|---:|---:|
| BM25 over live function source | 58 | 68 | 108 |
| SemDAG, damping 0.15 | 56 | 69 | 111 |

The paired function Hit@5 difference is −1.7 pp (95% bootstrap interval −7.8 to +4.3), so no function-level advantage is established. That negative result is what motivated v9's graph rewrite.

**End to end (local stand-in for the scorer, paired task set).**

| Version | Idea | Result |
|---|---|---|
| `v0_baseline` | stock reference agent | 4/23 |
| `v2_bm25` | BM25 localizer | 7/23 |
| `v6_impact` | SemDAG plus impact analysis (callers, test reach) | 7/23, 25% faster than v2. **Best measured, frozen reference.** |
| `v7_brigade_lite` | parallel lanes | tied v6 (2/11 vs 2/11) |
| `v8_ensemble` | plan, 4 implementers, adversary, finalizer | 0/5. Stage 1 alone uses the whole 4-minute budget. |
| `v9_recurrent` | recurrent typed graph (below) | 0/2 smoke run. Localization correct, editing failed. |
| `v10_edit_rescue` | v9 with the edit path repaired ([audit](docs/audit_2026-11-19.md)) and loop flow in the localizer output | 1/3 smoke run ([run_25](docs/runs/run_25_RESULTS.md)); 5 of 6 edits applied, against 3 of 9 for v9. Not yet measured against v6. |
| `v11_task_ir` | The issue is typed (traceback frames, literals, qualnames) and anchored in the code graph before BM25; the localizer prints one ~400-character action; edits go only through line ranges; verify blocks a patch that misses the located loop or rewrites a file ([README](AgenticSubmission/v11_task_ir/README.md)) | Smoke run 1/3, and that one resolve is an empty patch; 5 of 5 edits applied ([run_26 to run_28](docs/runs/run_26_28_RESULTS.md)). Not yet measured against v6. |

Every run has a preregistration and a results note in [`docs/runs/`](docs/runs/).

## v9: one hybrid recurrent graph

The first SemDAG graph was forward-only: containment, calls and imports. It could not represent a loop or a recursion, which is often exactly where the bug is. v9 ([`semdag_ir_ast.py`](AgenticSubmission/v9_recurrent/skills/semdag/scripts/semdag_ir_ast.py)) keeps one typed graph and adds recurrence to it:

- **Loop nodes** for `for`, `while`, async loops and comprehensions. Each has a `loop_back` self-edge, its loop-carried variables (upward-exposed uses that are also written in the body), its exits, and `loop_calls` edges to what the body calls.
- **Recursion.** `recurses` edges, plus one recursion node per call-graph SCC (Tarjan) with `member_of` edges. Every function gets a `topo_rank` from the condensed call DAG, so ordering stays acyclic even though the graph is not.
- **Inverse edges** for every relation (`called_by`, `contained_in`, ...), so impact analysis walks callers directly.
- **Better resolution:** src-layout packages, re-exports, `self`/`cls` through the MRO, `super()`, instantiation and inheritance edges, `@overload` stubs, and local shadowing of imports.

On four outside repositories (attrs, click, jinja, marshmallow), resolved call edges went from 444/435/731/147 to 751/2137/1245/915. The graph has 888 loop nodes and 13 recursion SCCs (one of them is jinja's 22-function parser cycle). Builds take under 0.5 s. [`flow.py`](AgenticSubmission/v9_recurrent/skills/semdag/scripts/flow.py) gives the agent a compact view of any function's loops, recursion, callers and callees, and 13 tests cover the graph ([`tests/test_semdag_recurrent.py`](tests/test_semdag_recurrent.py)).

**What the smoke run showed.** On one task, v9 ranked the right function #2 and attached the note "loop carrying `cell_pos`, `pos`: check first/last iteration". That is the actual bug. The model ignored the note and 6 of its 10 edits failed to apply. The bottleneck is now the editing step, not localization, and that is the next piece of work.

## Layout

| Path | What |
|---|---|
| [`AgenticSubmission/`](AgenticSubmission/) | Agent versions v0 to v9, each a self-contained submission folder |
| [`PaperTrack/`](PaperTrack/) | Paper source, PDF and measurement scripts with JSON receipts |
| [`docs/runs/`](docs/runs/) | Preregistrations and results for every evaluation run |
| [`results/`](results/) | Raw run outputs, traces and telemetry |
| [`Tools/`](Tools/) | Local runner (vLLM on Apple silicon), telemetry proxy |
| [`Designs/`](Designs/) | Audits, roadmap, dataset and LoRA designs |
| [`docs/SESSION_README.md`](docs/SESSION_README.md) | Working notes and session protocol |

## Run the localizer

For Qwen decode, `Tools/local/serve_vllm_metal_qwen.sh` exposes performance
mode, sequence count, and device-memory utilization as environment overrides.
The measured default remains `interactivity`, two sequences, and 80%: warm
512-token requests reached 66.4--68.3 tok/s, while the matched throughput-mode,
one-sequence profile reached 65.2 tok/s and was not promoted.
Native MTP remains opt-in with `VLLM_MTP_SPEC_TOKENS`; vLLM Metal 0.33 rejects
MTP for this hybrid GDN target, so the safe default is `0` until that backend
combination is implemented.

The skill uses only Python's standard library:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 \
  AgenticSubmission/v9_recurrent/skills/semdag/scripts/repo_eval.py \
  local-task /absolute/path/to/python/repository \
  --problem 'Describe the issue with exact identifiers and error text'
```

Add `--flow Class.method` to see the recurrent structure of one function. To reproduce the paper, see [`PaperTrack/`](PaperTrack/) and `requirements-research.txt`.

## Limits

Dynamic dispatch and runtime imports stay unresolved. End-to-end numbers come from a local Apple-silicon stand-in, not the scorer's 4×L4 vLLM. Local grading covers rich, requests and httpx only, because fastapi tasks fail on the arm64 image. No Kaggle submission has been made yet.

Licensed under Apache 2.0; see [LICENSE](LICENSE).


## v13 qualification and optimization

`AgenticSubmission/v13_orchestrator` is experimental, Gemma E4B only. Runs use macOS Seatbelt and the official subprocess backend, without Docker. Fixed budgets remain four minutes/task, 40 tool calls, 60 turns, 16,384 output and 4,096 thinking tokens. Local vllm-metal does not enforce thinking budget; local timing does not predict the scorer.

Native role-bound transactions provide independent slot copies, scoped/versioned edit handles, actual Python compilation, fresh outside and central verification, and conditional rollback. Root prepares/verifies; statically bound editors edit their own slot. Root registers `run.py` and `finalize.py`; editors register `run.py` and the exact-fragment `replace.py`. State replies identify the owning editor, distinguish private edits from central application, and publish explicit next-operation data. The model must choose valid tool calls; no SDK/model-output repair or automatic dispatch is used.

Verification shares one operation-local immutable Git baseline and original-file reads. Working-tree diffs and subsequent verification calls remain fresh. Profiling confirms eight to five Git calls. The original seven-pair benchmark passes: 0.155151 to 0.149583 seconds, **3.59% faster**, identical output, nine to four modeled control operations. This is component execution timing, not a model-call or task-resolution gain. An earlier correctness-repair benchmark failed at +15.44%; that negative result remains documented.

**317 host tests pass**, including actual compiled SDK/subprocess lifecycle and denial fixtures; official directory validation, role-asset equality and undefined-name lint also pass. E4B development runs have accepted private edits, but have not achieved a verified central apply or resolved task. No candidate promotion or Kaggle submission is established. The repeated external Dask issue is development evidence, not a held-out quality estimate. Its grading control passed: empty patch 2 failures/43 passes, reference 45 passes.

Evidence: [qualification](docs/runs/v13_QUALIFICATION_2026-11-22.md), [Stage 1](docs/runs/v13_STAGE1_2026-11-23.md), [role policy](docs/runs/v13_ROLE_POLICY_2026-11-23.md), and [current protocol/execution report](docs/runs/v13_PROTOCOL_2026-11-23.md). Raw request/task captures stay local. The host-only Edge research library is never included in the submission.

The v13 editor now replaces one small exact fragment while native code preserves the surrounding function header/docstring. All **337 tests pass** and official validation succeeds. In two live E4B component gates on actual retriever source, the editor executed the exact-fragment endpoint and passed outside/central verification: None-input handling (26.88s) and Windows path separators (29.01s), with surrounding source unchanged. The driver prepared/finalized these assignments; they establish editing capability, not autonomous benchmark performance. Those component changes remain in disposable workspaces.

The unchanged full external task is running separately. [Exact-edit evidence and limits](docs/runs/v13_EXACT_EDITS_2026-11-24.md).
