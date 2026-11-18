---
name: semdag
description: Deterministic scripts for the v8 ensemble - fork (army), audit, review_pack, save_cex, gate, adopt - plus meta and repo_eval.
---

All calls go through `run_skill_script` with `skill_name: semdag`. Every script prints one compact JSON object and never raises. Caches live in the temp directory, so nothing enters the patch.

| file_path | args | Use |
|---|---|---|
| `scripts/fork.py` | `["<k>", "<problem statement>"]` | Implementer k: own copy at `.git/wt_<k>`, start site with exact source, `run_prefix`, `test_cmd`, `audit_args` |
| `scripts/edit.py` | `["<k>", "<file>", "<old>", "<new>"]` | Implementer k's only edit tool: always writes into `.git/wt_<k>` (rescue refs `@1`, `L120-126` as fix_edit) |
| `scripts/audit.py` | `["--wt", "<k>", "--repro", cmd]` or `["--repro", cmd]` | Sign-off for copy k, or for the main workspace. `decision`: submit / submit_best / revise |
| `scripts/review_pack.py` | `["<k>"]` | Reviewer: candidate k's diff, files and self-audit |
| `scripts/save_cex.py` | `["<k>", "<python code>"]` | Reviewer: save a counterexample (asserts the correct behaviour) |
| `scripts/gate.py` | `[]` | Coordinator: pytest + static typecheck + code review + counterexamples on all candidates, ranked |
| `scripts/adopt.py` | `["<k>"]` | Final implementer: apply candidate k to `/workspace` and audit it |
| `scripts/fix_edit.py` | `[filepath, old, new]` | Whitespace-tolerant edit rescue |

Repro files belong in `/tmp`, created with `run_command` (heredoc). `write_file` to `/tmp/...` lands inside the repository, because the harness strips the leading `/`.
