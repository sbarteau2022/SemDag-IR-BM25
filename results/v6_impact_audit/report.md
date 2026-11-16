# Audit of v4_semdag and v5_vulnwalk, and the improved version v6_impact

Date: 2026-11-13. Model for all versions: `gemma-4-e4b-it-qat-w4a16-ct`.

## Summary

- **The most serious finding: under Kaggle's sandbox, the localizer in v4 and v5 returns nothing.** Both
  read the literal path `/workspace` inside their skill script. The official notebook runs the harness
  with `sandbox='subprocess'`, where the repository is in a temp folder and `/workspace` does not
  exist. Run in the harness's real subprocess sandbox, v4 and v5 report `files: 0` and no edit sites,
  with status success, and v5's verify reports `clean: true` for a modified repository. v1 to v3 have
  the same hard-coded path.
- v6_impact fixes that and seven smaller defects, keeps v4's ranking for edit sites (the held-out check
  showed v5's ranking was not better), and adds three new tools: a patch preview, a change checker, and
  an edit rescue.
- Each new part was checked on 30 fresh tasks drawn with a new seed, with the rules written before any
  output was seen. Results are below.
- **Not proven:** no run with the model has been done for v6. Everything here measures the tools, not
  the solve rate. The Kaggle notebook now includes v6 and is ready to push.
- v4 and v5 are unchanged in their folders.

## 1. Audit findings

All findings were reproduced by running the scripts the way the harness runs them: the wrapper built by
ADK's own `_SkillScriptCodeExecutor._build_wrapper_code`, written to `.adk_exec_<hex>.py` in the
repository root and started with `python3`.

| # | Finding | Affects | Evidence |
|---|---|---|---|
| 1 | Literal `/workspace` inside the script. Under the subprocess sandbox the localizer scans a missing folder and returns an empty result with status success. | v1 to v5 | `harness_tools/subproc_run.py` with the real `SubprocessManager`: v4 `files 0, sites 0`; v5 `files 0, sites 0`, verify `clean: true, changed: []` on a modified file; v6 `files 37, sites 10`, correct top site |
| 2 | The harness's own temp file `.adk_exec_<hex>.py` enters the snapshot. Every verify lists it as added and removed, and the v5 prompt tells the model to delete listed added files. | v4, v5 | stress run, verify output |
| 3 | 7 of 14 plausible argument shapes fail with an argparse error: dict arguments, no arguments, an empty list, `["--verify"]`, `{"verify": ...}`. | v4, v5 | `harness_tools/stress_v4_v5.py` |
| 4 | Two strings are read as container id and repository path, giving an empty result with status success. | v4, v5 | `harness_tools/stress_v4_v5.py` |
| 5 | Verify without an earlier localize call ends in a `FileNotFoundError` traceback. | v5 | `harness_tools/stress_v4_v5.py` |
| 6 | Verify compares against a private snapshot, not against git. It cannot say what the patch will contain, and it does not know that test and config files are stripped. | v5 | harness source, `strip_protected_files_from_patch` |
| 7 | Output is 4,900 to 4,945 characters, over v5's own 4,800 budget, because the envelope is not counted. | v5 | stress run |
| 8 | `eval_config.yaml` allows 8 minutes per task. About 120 tasks in 12 hours means 5 minutes at most. | v4 | `v4_semdag/eval_config.yaml` |
| 9 | The prompt suggests free text for `search_similar_code`. The harness tool takes a symbol name. | v4 | harness source, `swegemma/tools/graph.py` |
| 10 | The harness's `edit_file` can report success and write wrong code. Its regex fallback matched a slightly wrong `old_string` and re-indented the replacement. In 274 mechanical cases it made 14 wrong writes, 10 of which no longer parse. | harness | `checks/run_e.py` |

Speed is not a problem: on full FastAPI (about 3,200 Python files) localize takes 2.6 s and verify 0.2 s
on two cores.

What the earlier agent runs say (23 tasks, MLX stand-in): the failure classes were right file but wrong
fix 11, wrong file 3, no patch 2. No task was solved when an edit failed (0 of 4), against 7 of 19 when
none failed, and 10 failed edits were retried without reading the file. So the weak points are edit
reliability and checking the fix, more than finding the file. That is where v6 puts its new parts.

## 2. What v6_impact changes

| Area | v6 |
|---|---|
| Repository path | `wsroot.py` finds the repository from the location of the harness wrapper file. Correct in the docker backend and in the subprocess backend. Cache in the temp directory, so it is per task and outside the patch. |
| Edit sites | v4's ranking (BM25 over function source plus the damped walk), unchanged. v5's hubs and walk paths stay as context, limited to three hubs. |
| Patch preview (new) | Verify reads the change from git against `_swegemma_baseline`, as the harness does: files the patch carries, files the harness strips, new files, and whether the patch is empty after stripping. |
| Change checker (new) | Syntax errors; names that became undefined; definitions removed or renamed while still imported or called; signature changes that break existing callers; library callers of changed functions; one `next` line with the most important step. |
| Tests to run (new) | Existing test files ranked by resolved test-to-source calls, name mentions, imports and path, with a ready `pytest` command. |
| Edit rescue (new) | `fix_edit.py`. Applies the edit if the text differs only in whitespace. Otherwise prints the closest real block with line numbers and a reference `@1`, and writes nothing. A second call replaces exactly that block. Refuses test and config files and any edit that stops the file from parsing. |
| Arguments | All 20 tested shapes return JSON. No traceback reaches the model. |
| Prompt | Uses the new tools, tells the model not to resend a failed edit, asks for the whole issue text, and adds two Python rules (new parameters get defaults, every name is imported). |
| Budgets | 120 s per command, 40 tool calls, 5 minutes, 60 turns. Output at most 3,600 characters for localize and 2,600 for verify. |

Novel parts, in one line each: the verdict comes from the same git diff and strip rule the scorer uses;
breaking changes are found by comparing the syntax tree before and after against the call graph; a
failed edit is answered with a reference to the real text, so the model does not have to reproduce it.

## 3. Checks on fresh tasks (sample C)

30 merged pull requests, 10 each from FastAPI, Rich and Requests, drawn with seed 20261115 from the same
pool as the held-out sample, excluding the 15 locked and 15 held-out tasks. The selection rule and all
five checks are written in `checks/select_c.py`, fixed before any v6 output on these tasks. No v6
constant was changed after the draw.

| Check | Result |
|---|---|
| Edit sites equal v4's ranking | 30 of 30 |
| Patch preview equals the harness's own stripped patch (file set) | 30 of 30; empty flag agrees 30 of 30 |
| False findings on correct merged changes (syntax, undefined name, removed but used, signature break) | 0 on 30 tasks |
| Fault found: import dropped | 26 of 26 |
| Fault found: required parameter added | 24 of 24 |
| Fault found: file cut inside a function | 18 of 18 |
| Fault found: function renamed at its definition only | 15 of 17. The 2 misses have no real reference: the test's own rule matched a string and a comment |
| Test to run, first suggestion is a test the pull request changed | v6 7 of 10, name matching 6 of 10 |
| Tests listed at localize time, before any edit (top 3) | 5 of 10 |

Edit rescue, 274 mechanical corruptions of the true text of real hunks (indent dropped, trailing
spaces, a line dropped, one identifier wrong, quotes swapped, blank lines and spacing changed):

| | Count |
|---|---|
| Harness applies correctly | 99, plus 16 that differ only in blank lines |
| Harness writes wrong code and reports success | 14 (10 no longer parse) |
| Harness rejects | 145 |
| Of the 145: rescue names exactly the true block, and replacing it gives the correct file | 77 (53%) |
| Of the 145: rescue names a block covering at least half of the true block | 46 (32%) |
| Of the 145: rescue touches the true block | 10 (7%) |
| Of the 145: rescue points elsewhere / offers nothing | 9 (6%) / 3 (2%) |
| Wrong writes by the rescue tool | 0 of 274 |

Two scoring rules of the edit check were corrected after its first run, before any change to v6:
corrupted text that is still an exact unique match is a valid edit and is skipped (13 cases), and a
write that differs only in blank lines counts as cosmetic, not wrong. The first run had counted both as
errors for the harness and for the rescue tool alike.

Also run: the real validator (v4, v5, v6 valid, one model each), six unit tests of the rules
(`checks/test_units.py`), 20 argument shapes and 18 edit cases through the harness wrapper
(`checks/stress6.out`, `checks/stress_edit.out`).

## 4. What is not proven

- **No agent run.** Whether the model calls the new tools, and whether they raise the solve rate, is
  unknown. The paired notebook answers that: `notebooks/gemma4_e4b_paired_v4_v5_v6.ipynb`.
- The test suggestion beat name matching by one task of ten. That is not a reliable difference.
- The tests listed before any edit were right for 5 of 10 tasks. The prompt treats them as a hint.
- Sample C uses pull request titles as the issue text, shorter than the official statements.
- The corruptions in the edit check are mechanical. A model's real mistakes may differ.
- The fault checks inject four fault types. The checker is scope-insensitive on purpose, so it misses
  names that are defined in another scope of the same file.
- Whether the hidden-test scoring run uses the subprocess sandbox is inferred from the official
  notebook and the harness comment `'subprocess' (Kaggle/notebooks)`. v6 works in both backends.

## 5. Recommendations

1. Treat v6_impact as the candidate. Do not submit v4 or v5 as they are: on Kaggle their localizer is
   dead, and v4 also has the 8-minute limit.
2. Push the three-way notebook and run it on L4 x4. It fixes the path in its own copies of v4 and v5
   (switch `PATCH_WORKSPACE_PATH`), so the comparison measures the methods.
3. Read the traces of that run for how often `fix_edit.py` and `--verify` are called, before changing
   the prompt again.

## Files

- `AgenticSubmission/v6_impact/`: the submission folder.
- `results/v6_impact_audit/checks/`: selection, check scripts, raw results, unit tests, stress outputs.
- `results/v6_impact_audit/harness_tools/`: runners that call the scripts through the harness's own
  wrapper and its subprocess sandbox, and the path fix used by the notebook.
- `notebooks/gemma4_e4b_paired_v4_v5_v6.ipynb`, `notebooks/PUSH.md`, `notebooks/kernel-metadata.json`.
