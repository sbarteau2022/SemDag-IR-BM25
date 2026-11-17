---
name: semdag
description: Deterministic preflight (meta.py), sign-off (audit.py), localization (repo_eval.py) and edit rescue (fix_edit.py) for the repository under /workspace.
---

All calls go through `run_skill_script` with `skill_name: semdag`. Every script prints one compact JSON object and never raises. Caches live in the temp directory, so nothing enters the patch.

| file_path | args | Returns |
|---|---|---|
| `scripts/meta.py` | `[problem statement]` | `ready` (pytest and test deps importable), `checkpoint_ref`, `sites` (top 3 edit sites with the exact current source), `tests_near_sites`, `baseline_tests` (collected / passed / failed and `red_reason`: assertion, collection_error, no_tests_collected, timeout), `test_cmd`, `next`. A second call returns the cached report. |
| `scripts/audit.py` | `["--repro", cmd]` or `[]` | `decision` (`submit`, `submit_best` or `revise`), `reasons`, `gaps`, `tests`, `repro`, `strike`. A green exit code with 0 collected tests is never green. A diff already judged red is flagged as an identical retry. After the second red, a non-empty unbroken diff gets `submit_best`. |
| `scripts/repo_eval.py` | `[issue]` / `["--verify"]` | Ranked edit sites; the patch contents and breakages of the current change. |
| `scripts/fix_edit.py` | `[filepath, old, new]`, then `[filepath, "@1", new]` | Whitespace-tolerant edit, or the closest real block to target. Refuses test/config files and edits that break parsing. |

Repro files belong in `/tmp`, created with `run_command` (heredoc). `write_file` to `/tmp/...` lands inside the repository, because the harness strips the leading `/`.
