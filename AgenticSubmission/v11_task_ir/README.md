# v11_task_ir: the graph types the problem and gates the patch

Started 2026-11-19 from a copy of `v10_edit_rescue`. v6_impact stays frozen as the reference (7/23 on
paired23). Design brief: the owner's 2026-11-19 review ("Make the graph a typed task IR the model
executes"). Tests: `tests/test_v11_task_ir.py`. Offline locate measurement: `results/v11_offline/`.
Smoke runs 26 to 28 (3 tasks): `docs/runs/run_26_28_RESULTS.md`. run_28 resolved 1/3, but that one resolve is an empty patch. 5 of 5 edits applied.

## What changed against v10

| Spec item | Where | What it does now |
|---|---|---|
| 1. Problem IR, no model | `scripts/task_ir.py` `problem_ir`, `anchor` | The issue becomes `idents`, `dotted`, `frames` (traceback `File "...", line N, in q`), `literals` (quoted strings, exception messages), `paths`. Joined to the code IR in a fixed order: traceback line inside a library function (site-packages paths matched by suffix), a literal found in exactly one function, a qualname mention (dotted first, then a distinctive bare name), then BM25 rank 1 marked as a guess. Ties use (BM25 score, file, line). |
| 2. Locus IR on the anchor only | `task_ir.locus` | The issue's identifiers intersected with the anchor's loops' carried names and targets. A hit gives the span, the loop condition, and the guarded exits; no hit means no flow is printed at all. |
| 3. locate prints one action | `repo_eval.locate` | Plain text, at most 457 characters on all 129 public snapshots: `edit`, `loop` (only with a locus), `read`, `check` (one pytest node when a test names the anchor), `forbid`, and `alt` for a BM25 guess. Hubs, walk paths, risk, fan-in and topo ranks go to `eval.json` only. |
| 4. The model does not retype anchors | `agent.yaml`, `fix_edit.py` | `edit_file` and `write_file` are no longer agent tools. The edit is `fix_edit [file, "LX-Y", new_text]`. |
| 5. Verify blocks | `repo_eval.gate` | With a loop locus and no diff hunk intersecting it, `next` is `blocked: patch does not touch while A-B carrying ...` and `clean` is false. `patch.empty` is left as it is, so a later good edit can still submit. `recurrence_notes` is gone. |
| 6. Five calls | `prompts/system.md`, `agent.yaml` | locate, numbered read, fix_edit, verify, one check, then submit. No sub-agent, no graph tools (`get_code_neighbors`, `search_similar_code`, `get_code_subgraph` removed), no second localizer. |

Hardening of the code IR (`semdag_ir_ast.py`, front end `stdlib-ast/recurrent-v2`):

- Carried locations include attribute chains (`self.pos`) and subscripted bases (`buf[]`).
- The single source-order pass is replaced by a must-defined dataflow (`_Flow`). Branches meet by intersection, a branch that returns, raises, breaks or continues does not constrain the meet, and a nested loop may run zero times. A name stored on one branch and read later is now carried.
- Every loop records its own condition (`test`) and each exit with the condition that guards it (`exit_conds`: `{"kind": "return", "line": 24, "cond": "width > cut"}`). The counts stay.
- `x: T = make()` types a local (annotation first, then the call).
- Function-level imports go into that function's table and shadow module-level bindings there. They no longer resolve calls elsewhere in the file. A call sees the file's table overlaid by each enclosing function's.
- Method lookup follows the C3 linearization, with a depth-first fallback for an inconsistent hierarchy. v10 used breadth-first search to depth 8.
- The retriever's relation weights and damping are unchanged. Per the brief, the recurrence edges are not stuffed into the walk. `vulnwalk`'s risk prior and fan-in boost no longer reach the agent; they are computed only for `eval.json`.

## Deviations from the brief, and why

1. **The read is `fix_edit [file, "LA-B"]`, not `read_file`.** The harness's `read_file` returns content without line numbers (`swegemma/tools/workspace.py`), and the edit is by line range, so the model needs numbered lines. fix_edit's numbered view now shows up to 90 lines and 4,600 characters, in whole lines only.
2. **The locus span starts at the last pre-loop assignment of the intersected names.** A carried value is its initial value plus its update, so a fix to the initialisation is inside the locus. Without this, the gate would block a correct fix to the loop's entry state.
3. **`read_file` is removed too** (after run_27). The model counted lines from `read_file` output, which has no numbers, and replaced the wrong lines. locate's `read` line now prints the exact call: `read fix_edit.py ["FILE LA-B"]`.
4. **fix_edit accepts the argument shapes E4B actually sends** (run_26, run_27): the call packed into one string (`"FILE L87-89\n<new lines>"`, the documented form), comma-separated with a quoted text, a range without the `L`, escaped `\n`, and shell-style trailing backslashes. A refused range edit returns `lines_you_replaced`, the numbered lines the range really holds.
5. **Verify also blocks a whole-file rewrite**: a change that deletes at least 40 lines and at least half the file. The brief says enforcement belongs in the script return value; run_10 had two such destructive rewrites (requests_7433, rich_3043).

## Facts from checking the brief against the data

- **rich_3506.** The issue text is "fix split cells / Fixed `Segment._split_cells` issue discovered in textual#4996". `cell_pos` is not in it. So v11 anchors `Segment._split_cells` by qualname and prints no locus there; the loop gate does not fire on that task.
- **Offline locate, all 129 public snapshots** (`results/v11_offline/anchor_129.json`, measurement only, nothing tuned):

  | anchor | tasks | edit span in a gold file | in the gold function | v6 BM25 rank 1 in the gold function |
  |---|---|---|---|---|
  | qualname | 26 | 23 | 19 / 26 | 10 / 26 |
  | traceback | 1 | 1 | 1 / 1 | 0 / 1 |
  | literal | 1 | 0 | 0 / 1 | 0 / 1 |
  | bm25 guess | 101 | 27 | 13 / 88 | 13 / 88 |

  A loop locus fires on 10 tasks. Locate takes at most 1.4 s.
- **The main risk.** 101 of 129 tasks fall back to a single BM25 guess plus two `alt` lines, and that guess is the gold function in 15% of the tasks where gold is known. v6 showed ten ranked sites. Whether one action beats ten candidates on those tasks has to be measured on paired23.
