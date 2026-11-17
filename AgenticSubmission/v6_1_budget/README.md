# v6_impact: localize, check the change before submit, rescue failed edits

- Base model: `gemma-4-e4b-it-qat-w4a16-ct`; no adapter and no second model.
- Runtime: standard-library Python, offline, shipped as the ADK skill `skills/semdag`, reachable in the
  sandbox through `run_skill_script`.
- `eval_config.yaml`: 120 s per command, 40 tool calls, 5 min, 60 turns.

## What changed from v4_semdag and v5_vulnwalk

1. **Repository path.** v1 to v5 read the literal path `/workspace` inside their scripts. The subprocess
   sandbox (the backend of the official Kaggle notebook) keeps the repository elsewhere and rewrites
   `/workspace` only in command strings, so those scripts scan a directory that does not exist and return
   an empty result with status success. `scripts/wsroot.py` finds the repository from the location of the
   harness wrapper file, which is correct in both backends. The cache moved to the temp directory.
2. **Edit sites use v4's ranking.** BM25 over live function source plus the damped walk. On 15 held-out
   tasks v5's own ranking was not better than v4's, so v6 keeps v4's order and uses v5's vulnerability
   walk only as context (`hubs`, `walk_paths`, `risk`, `fan_in`).
3. **Verify reads git, as the harness does** (`scripts/impact.py`). `args: ["--verify"]` reports
   - the patch preview: files the patch will carry, files the harness strips, new files, empty or not;
   - syntax errors, names that became undefined, definitions removed while still imported or called,
     signature changes that break existing callers;
   - library callers of the changed functions;
   - the existing tests closest to the change, with a ready `pytest` command;
   - one `next` line with the most important step.
4. **Edit rescue** (`scripts/fix_edit.py`). After a failed `edit_file`, it applies the edit if the text
   differs only in whitespace, otherwise it prints the closest real block with line numbers and a
   reference (`@1`) and writes nothing. A second call replaces exactly that block. It refuses test and
   config files and any edit that stops a Python file from parsing.
5. **Arguments.** Every shape a model can send through `run_skill_script` (list, dict, flags only, no
   arguments, several strings) returns JSON. No traceback reaches the model.
6. **Harness temp file.** `.adk_exec_<hex>.py` no longer enters the snapshot or the verify result.
7. **Output size.** Locate prints at most 3,600 characters, verify at most 2,600.

## Constants

All constants are fixed by design. None was fitted to benchmark tasks. Test ranking weights: 3.0 per
changed function a test calls, 2.0 per changed name a test mentions (at most 3), 1.0 for importing the
changed file, 3.0 for `test_<stem>.py`, 1.5 per shared path token. Edit rescue offers a block only at
similarity 0.5 or more.

## Evidence

See `results/v6_impact_audit/report.md` in the project files: 30 fresh tasks drawn with seed 20261115,
with the protocol written before any v6 output on them was seen. No agent run with the model has been
done for v6 yet.
