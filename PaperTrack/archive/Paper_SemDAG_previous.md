# Stored but Not Scored: Auditing Graph-Based Edit Localization for Code Agents

*An audit and repair of a code-graph ranker on 129 Gemma 4 tasks: BM25 over function source, then a light walk on a typed repository graph.*

**Stewart Barteau** · Independent · Gemma 4 Developer Agent Competition, Paper Track

## Abstract

A small code agent must find the edit site with almost no context to spare. We built a graph-based localizer, SemDAG, and then audited it on all 129 public tasks. The audit found three independent failures. An integrity gate with inconsistent hash ordering suppressed all output on 129 of 129 task snapshots. The ranker read only reversed `calls` edges and exact bare-name seeds, never the `contains` edges, `imports` edges or function source the graph was built to hold. And 40% of its rank mass fell on test functions. Under a common test-file filter it places a gold edit function in the top five on 28 of 116 tasks; BM25 over function source reaches 58, and 20 of 42 in a held-out task pool. We repaired the system by making BM25 the restart distribution of a random walk over typed containment, call and import edges. A light walk is statistically level with BM25 at function level and best at file level (gold file in the top ten on 111 of 128 tasks against 108). The same query over the organizers' shipped graph text reaches 54, so most of the gain is the query type, which the shipped tools do not offer. Separate paired agent runs tested a lexical BM25 skill, not the repaired graph walk: on 23 tasks it resolved 7 against the baseline's 4 (not significant). Its traces measure candidate coverage, not production SemDAG's effect on agent resolution.

## 1 Introduction

A 4B model in a 32k-token window cannot read an entire codebase to find where an issue should be fixed. The competition supplies a precomputed code graph per task and three tools over it.

The agent has a second option. Skill scripts run Python inside the sandbox, so an agent can index the repository as it exists at task time. We built a graph-first localizer on that idea and only then measured it. It did not work, for reasons that had little to do with graphs. This paper reports the audit, the repair, and what remained true afterwards, around four questions.

- **RQ1.** What does a graph ranker actually consume, and was our comparison with lexical retrieval fair?
- **RQ2.** Once the query reads source text, does repository structure add anything?
- **RQ3.** Is the gain due to rebuilding the index, or to the type of query?
- **RQ4.** What do paired lexical-skill runs and candidate traces establish about agent behavior?

**Contributions.** An audit that separates what a graph ranker stores from what it scores; a repaired retriever (lexical restart on a typed graph) measured by importing the file the agent runs; a control separating query type from index; paired agent runs with trace analysis; and function-level edit-site labels for the 129 public tasks. The work addresses the track's Code Comprehension and Graph Reasoning topics.

## 2 Related work

LocAgent (Chen et al., 2025) builds a heterogeneous code graph with containment, import, invocation and inheritance edges for an agent to traverse. ARISE (2026) adds data-flow edges and observes that BM25 suffices for file-level localization in most cases. Sepidband et al. (2026) find map-style repository views help most when localization is the bottleneck. BM25 is due to Robertson and Zaragoza (2009); walks with restart follow Personalized PageRank (Haveliwala, 2002); the setting follows SWE-bench (Jimenez et al., 2024). We claim no new method; the contribution is a controlled audit and repair of existing ones.

## 3 Systems

### 3.1 Legacy SemDAG

The system as first shipped is standard-library Python. A snapshot stage hashes the tree. An IR stage parses every `.py` file with `ast` into file, class, function and method nodes (including `async def`) joined by `contains`, `calls` and `imports` edges. A taint stage, inherited from a security use case, marks functions matching patterns such as `request`, `params`, `exec` and `loads`. A parity check must pass before any ranking is returned.

**What the ranker consumes.** IR nodes carry only name, file, line and class: no body, signature or data flow. The ranker is Personalized PageRank (damping 0.85, 80 iterations) over reversed `calls` edges alone. Its seed is every function, tests included, whose bare name equals an issue token exactly, plus the taint seed at weight 0.25. Across the IRs built here, 1.02 million `calls` edges are used and 0.68 million `contains` and `imports` edges are ignored. Scores are rounded to six decimals before sorting, so ties fall to node-id order. This is arm **A**.

### 3.2 Lexical retrieval

Arm **X** is BM25 (k1 = 1.2, b = 0.75) between the issue text and the source of each function outside test files. Tokens are identifiers plus their snake-case and camel-case parts; qualified-name and path tokens are repeated three times.

### 3.3 Production SemDAG: lexical restart on a typed graph

The repaired front end records qualified names, exact spans and import aliases. Calls resolve through same-module functions, `self` and `cls`, class-qualified targets and imported symbols; an ambiguous bare name stays unresolved. Snapshot and parity hash in one order, and scores keep full precision.

Ranking is a random walk with restart over file, class and function nodes outside test files:

```
r(0) = p        r(t+1) = (1 − d) · p + d · Wᵀ r(t)        30 iterations
```

Here `p` is the BM25 score normalized over functions with a positive score, `W` is the row-normalized adjacency over undirected `contains`, resolved `calls` and repository-resolved `imports` edges, and `d` is the damping. Mass at a node without edges returns to `p`. Only functions with a positive lexical score are ranked, so the walk reorders lexical matches and cannot introduce a function the query did not touch. Arms **D15, D30, D50** set `d` to 0.15, 0.30 and 0.50. At `d = 0` the ranking is exactly X; the measurement asserts this on every task.

The production retriever ships as an ADK skill; a script directory beside `agent.yaml` is not present in the sandbox, which our first package assumed.

## 4 Experimental setup

**Data.** The 129 public competition tasks span four codebases. `hints_text` and `test_patch` are never read; `patch` is used only for scoring.

**Gold edit sites.** For each `.py` hunk in a pre-existing file, a gold function is the innermost function, in the pre-patch source, containing a deleted line, or for a pure insertion, containing both old-side neighbours of the insertion. Of 695 hunks, 434 align, giving 438 gold functions over 116 tasks and 128 tasks with a gold file. None lies in a test file.

**Metric.** Hit@k = 1 if a gold function (or file) is among the first k entries, else 0, summed over tasks. Contrasts are paired task-level bootstraps (4,000 resamples, seed 0, 95% intervals).

**Selection.** Eleven arms were compared. The reported arm has the highest function Hit@5 on a 74-task selection pool, ties to the simpler arm. A disjoint 42-task pool is held out: reported, never used to choose. The measurement script fixes the exact split.

**Agent runs.** The official `swegemma` harness with the Docker sandbox; `gemma-4-e4b-it-qat-w4a16-ct` as a lossless MLX 4-bit repack; temperature 0.2, top-p 0.95; 40 tool calls and 8 minutes per task. **B0** is the unmodified baseline agent. **B1** adds the X retriever as a skill, called first.

## 5 Results

### 5.1 Coverage

**Table 1.** Gold edit functions present in each index.

| | Shipped graph | Rebuilt from source |
|---|---:|---:|
| Gold functions present (of 438) | 376 (85.8%) | 438 |
| Async gold functions present (of 56) | 0 | 56 |
| Tasks with no gold function present (of 116) | 8 | 0 |

The rebuild's 100% is by construction. The informative number is the shipped graph's 14.2% miss, which includes every async function.

### 5.2 Audit of the legacy ranker (RQ1)

**Table 2.** Legacy arms, function level, 116 tasks. Af removes test functions from A; B removes the taint seed. Median repository: 3,530 functions, 1,029 outside tests. A random list would hit 0.82 tasks at k = 5.

| Arm | Hit@1 | Hit@5 | Hit@10 | File Hit@10 (of 128) |
|---|---:|---:|---:|---:|
| A: as designed | 13 | 25 | 34 | 64 |
| Af: test functions removed | 13 | 28 | 36 | 75 |
| B: no taint seed | 7 | 18 | 22 | 35 |

Three properties explain the ceiling. A mean of 40% of A's rank mass sits on test functions, and 106 of its 580 top-five slots are tests. On 53 of 116 tasks its fifth and sixth entries tie after rounding, so the Hit@5 boundary is decided by node id. And 43 tasks have no issue-derived seed, leaving the security prior, which supplies 7 of A's 25 hits.

**The gate.** Run as the agent was instructed to run it, the system returned `parity_ok: false` and no edit sites on 129 of 129 full snapshots (128 of 129 when only `.py` files are extracted). The snapshot hashed files in directory-walk order and the check rehashed them in sorted-path order. Ranking was computed only when parity held, so the output was empty everywhere, with no error. Table 2 was computed with the gate bypassed. With one hash order the gate passes on all 129.

### 5.3 Lexical retrieval and the repaired walk (RQ1, RQ2)

**Table 3.** Function Hit@1 / Hit@5 / Hit@10 by pool, and file Hit@10 on all tasks. NX is reciprocal rank fusion of X with name seeds; DC85 is the legacy walk (reversed `calls`, d = 0.85) restarted from BM25.

| Arm | Selection (74) | Held-out (42) | All (116) | File Hit@10 (128) |
|---|---|---|---|---:|
| Af: legacy, tests removed | 11 / 20 / 26 | 2 / 8 / 10 | 13 / 28 / 36 | 75 |
| **X: BM25** | 18 / **38** / 44 | 3 / 20 / 24 | 21 / **58** / 68 | 108 |
| X, test functions kept | 14 / 26 / 33 | 4 / 11 / 14 | 18 / 37 / 47 | 82 |
| NX | 15 / 30 / 34 | **10** / 16 / 24 | **25** / 46 / 58 | 103 |
| D15: production | 15 / 36 / 43 | 4 / 20 / 26 | 19 / 56 / 69 | **111** |
| D50 | 10 / 22 / 40 | 6 / **23** / **28** | 16 / 45 / 68 | 110 |
| DC85: legacy walk, BM25 restart | 8 / 24 / 41 | 3 / 13 / 21 | 11 / 37 / 62 | 109 |

**Like for like.** With the same test-file filter, X − Af at Hit@5 is +0.259 [0.155, 0.362] on all tasks and +0.286 [0.119, 0.452] on the held-out pool. With tests kept on both sides, X − A is +0.103 [0.009, 0.198] on all tasks and +0.095 [−0.024, 0.214] on the held-out pool, which touches zero. The filter is worth more to BM25 (37 to 58) than to the graph ranker (25 to 28); comparing filtered BM25 with unfiltered A overstates the gap.

**Does structure add anything?** A lexical restart recovers part of the legacy walk's deficit: DC85 reaches 37 where A reached 25. Walking all three edge types lightly is statistically level with BM25 at function level (D15 − X at Hit@5: −0.017 [−0.078, 0.043]) and best at file level, 111 of 128. On all tasks, more diffusion lowers Hit@5, from 56 to 52 (D30) and 45. The held-out pool does not follow that trend: D50 leads there with 23 at top five and 28 at top ten against X's 20 and 24, with intervals that touch zero. The useful amount of diffusion varies across these task pools; we did not tune it on the held-out pool.

The selection rule picks X. The production skill uses D15, for its file-level gain at no distinguishable function-level cost.

### 5.4 Index or query? (RQ3)

**Table 4.** The same BM25, tokenizer and filter over two indexes; the shipped index uses each node's stored text.

| BM25 over | Hit@1 | Hit@5 | Hit@10 | Async-gold tasks (20), Hit@5 / Hit@10 |
|---|---:|---:|---:|---:|
| Shipped graph node text | 21 | 54 | 61 | 7 / 9 |
| Functions rebuilt from source | 21 | 58 | 68 | 12 / 15 |

Most of the gain is the query. BM25 over text the organizers already ship reaches 54 at k = 5, nearly double the filtered graph ranker. The shipped tools cannot run it: `search_similar_code` takes a node name, not text. Rebuilding the index adds 4 tasks at k = 5 and 7 at k = 10, mostly where the gold function is async or absent from the shipped graph.

### 5.5 The verifier gate

In verify mode without a test command, the gate judged all 129 gold patches clean. It also judged clean all 11 one-turn `gemma-4-e4b` diffs that applied (of 64, from an earlier experiment on the held-out task pool), including 5 that created a new file instead of editing one. It rejects nothing; discriminating power must come from the task's tests, which we did not measure.

### 5.6 Agent runs (RQ4)

**Table 5.** Paired runs on 23 public tasks (13 Requests, 1 httpx, 9 Rich), one sample each.

| | B0 baseline | B1 with retriever skill |
|---|---:|---:|
| Resolved | 4 | 7 |
| Resolved with a non-empty patch | 3 | 7 |
| Mean tool calls | 11.4 | 9.4 |
| `edit_file` calls rejected | 25 of 55 | 18 of 48 |

B1 wins three tasks B0 loses and loses none. Three discordant pairs is not significant (exact McNemar p = 0.25), so we report a direction only. One B0 pass is an empty patch on a task whose tests pass unchanged. On the nine Rich tasks, run separately, the production SemDAG skill resolved 3, against 4 for B1 and 1 for B0; it was not run on the other fourteen.

**Traces.** B1 called the skill on 15 of 23 tasks. Its candidates held a gold file 12 times and a gold function 10 times. Every call also ranked a generated `.adk_exec_*` wrapper script, an admission defect the production retriever excludes. Localization is not the bottleneck: most failures edited a gold file and wrote the wrong fix (13 of 19 in B0, 11 of 16 in B1; `results/reports/failure_classes.json`). Forty-five percent of B0's `edit_file` calls were rejected for an inexact `old_string`, and every empty submission followed repeated rejections.

## 6 Discussion

**A graph is only as good as what its ranker reads.** The legacy system stored containment and imports and scored neither, so its failure said nothing about graphs. Once the walk starts from the text, structure contributes a small file-level gain and no function-level gain we can detect.

**The audit transfers.** Five checks apply to any retrieval tool given to an agent: list what the scorer reads against what the index stores; give every arm the same candidate admission; count ties at the cutoff; assert that the combined system reduces exactly to its baseline when the new component is switched off; and give every gate a positive and a negative control. Each one caught a defect here.

**For competitors.** Query function source with the issue text, drop tests and tool scaffolding, and ship the retriever as a skill. Measure candidate coverage and end-to-end resolution separately.

## 7 Limitations

- **Localization is not resolution.** The agent runs cover 23 tasks, one sample each, on an MLX repack with arms partly sharing one model server; the difference is not significant.
- **Coverage.** Function-level results cover 116 of 129 tasks across four public codebases; one contributes 62 of the 116. Unseen tasks may share less vocabulary between issues and code.
- **Selection.** X's margin over D15 is two tasks. Four arms in the released output (EX, D85, NXG, XF) are not tabulated; NXG and XF do not use the SemDAG IR.
- **Damping and file size.** 0.15 was the best DAG setting on the selection pool; the held-out pool scored higher at 0.50. The production snapshot skips source files over 256 KB; none occurs outside tests here.

## 8 Reproducibility

Everything except the agent runs is CPU-only, about a minute per script, from the competition dataset. Scripts are in `PaperTrack/phase4_semdag/` and write to `out/`; `adversarial_check.py` tests the resolver and admission rules.

| Claim | Script | Output |
|---|---|---|
| Tables 1 and 2; rank mass; ties | `measure.py` on `legacy_semdag/` | `summary.json` |
| Tables 3 and 4; selection; DAG contrasts | `measure_v2.py` | `v2_summary.json` |
| Like-for-like contrasts | `equal_footing.py` | `equal_footing.json` |
| Gate and verifier | `verify_gate.py` | `verify_summary.json` |
| Table 5; traces | `Tools/paired_report.py`, `Tools/trace_report.py` | `results/reports/` |

`legacy_semdag/` is a frozen copy of the system as first shipped. The production retriever is `AgenticSubmission/v4_semdag/skills/semdag/`; the B1 skill is `AgenticSubmission/v2_bm25/`.

Public notebook: **[URL to be inserted before submission]**.

## References

- ARISE (2026). A repository-level graph representation and toolset for agentic fault localization and program repair. arXiv:2605.03117.
- Chen, Z., et al. (2025). LocAgent: Graph-guided LLM agents for code localization. ACL.
- Haveliwala, T. (2002). Topic-sensitive PageRank. WWW.
- Jimenez, C., et al. (2024). SWE-bench: Can language models resolve real-world GitHub issues? ICLR.
- Robertson, S., and Zaragoza, H. (2009). The probabilistic relevance framework: BM25 and beyond.
- Sepidband, M., et al. (2026). How should agents see code? arXiv:2611.07286.
