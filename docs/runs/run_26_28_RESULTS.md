# run_26 to run_28: v11_task_ir smoke (3 tasks, vllm-metal, subprocess sandbox)

Date: 2026-11-19/20. Arm: `AgenticSubmission/v11_task_ir` (design and changes: its `README.md`).
The tasks and setup are the same as run_25 (v10): `rich_3506`, `requests_7315`, `httpx_3672`,
`SANDBOX=subprocess`, `SERVER=vllm_metal`, seatbelt no-network, budget 300 s / 40 calls / 4 min / 60 turns,
max_output 16384, thinking 4096 (not enforced locally). Raw outputs: `results/run_2{6,7,8}_v11_smoke/`.

Public tasks were used to evaluate only. The fixes made between runs are argument-transport and tool-surface
fixes read off the traces. They are tested on synthetic repositories, they contain no task content, and
the prompt's examples are synthetic (`test_prompt_example_is_synthetic`).

## Results

| run | change before it | resolved | patches non-empty | fix_edit edits applied | notes |
|---|---|---|---|---|---|
| run_26 | v11 as first built | 1/3 | 0/3 | 0 of 14 attempts | E4B could not form the three-element fix_edit call: it packed it into one string, dropped the `L`, used `positional_args` |
| run_27 | fix_edit accepts packed and comma forms; one-string edit form in the prompt | 1/3 | 1/3 | 1 (requests_7315) | httpx: target file passed as `file_path` (SCRIPT_NOT_FOUND x3). rich: escaped `\n` and line counts taken from `read_file`, so 5 refusals on parse |
| run_28 | escaped newlines decoded; `read_file` removed; locate prints the exact read call; a refused range edit shows what it holds | 1/3 | 2/3 | 5 of 5 | edit path works. No real fix yet (below) |

Per task, run_28 (grader output, `results/run_28_v11_smoke/test_outputs/`):

| task | anchor | resolved | patch bytes | calls | wall s | why |
|---|---|---|---|---|---|---|
| requests_7315 | qualname `RequestEncodingMixin.path_url` | yes | **0** | 5 | 87 | Resolved with an empty patch: the hidden test passes at baseline under this sandbox. Not a real fix. |
| httpx_3672 | qualname `HTTPParser.complete` | no | 2,109 | 9 | 142 | Three edits applied. The model added `from builtins import KeyboardException` and `from ._streams import Stream`, so test collection fails. |
| rich_3506 | qualname `Segment._split_cells` | no | 472 | 4 | 64 | Edited the `cell_pos > cut` return inside the loop. 49 local tests passed; hidden `test_split_cells_mixed` fails. No locus fired (no carried name in the issue), so the gate did not apply. |

Against run_25 (v10, same tasks): v10 had 1/3 with a real patch on requests_7315, and httpx timed out.
In run_28 v11 also has 1/3, but its one resolve is an empty patch. No task timed out, and the slowest took 142 s.
Edits: v10 applied 5 of 6 `edit_file` calls; v11 run_28 applied 5 of 5 `fix_edit` calls.

## Offline locate (no model), all 129 public snapshots

`results/v11_offline/anchor_129.json`, produced by `Tools/v11_anchor_offline.py`. This is a measurement; gold is read only by
the tool, never by the submission.

| anchor | tasks | span in gold function | v6 BM25 rank 1 in gold function, same tasks |
|---|---|---|---|
| qualname | 26 | 19/26 | 10/26 |
| traceback | 1 | 1/1 | 0/1 |
| literal | 1 | 0/1 | 0/1 |
| bm25 guess | 101 | 13/88 | 13/88 |

A loop locus fires on 10 of 129 tasks. stdout is at most 457 characters and locate takes at most 1.4 s.

## What this shows and what it does not

- Shows: the task-IR locate is short, fast and deterministic. Where the issue names the function it anchors
  correctly far more often than BM25 rank 1. After two transport fixes, the line-range edit path lands every
  edit E4B sends.
- Does not show: a pass-rate gain. Three tasks are a smoke, and none of the three had a locus, so the
  blocking gate was never exercised live. The decisive measurement is paired23 against v6's 7/23.
- Risk: 78% of public tasks fall back to a single BM25 guess plus two alternatives (v6 showed ten sites).
