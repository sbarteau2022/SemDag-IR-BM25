# run_10: v6_impact on paired23 (local MLX E4B, 5 minute budget)

- Submission: `AgenticSubmission/v6_impact`, unchanged. `validate_directory` passed.
- Model: `~/models/gemma-4-e4b-it-qat-w4a16-mlx` via `mlx_lm.server` on 127.0.0.1:8124, using `Tools/serve_e4b_mlx_8124.sh` (8123 is held by the `hypermind-clickstack` ClickHouse container).
- Harness: `Tools/run_agent_eval_5m.sh` (Docker sandbox, concurrency 1, `--max-time-minutes 5 --max-tool-calls 40 --max-turns 60`), pointed at port 8124 via `Tools/local/models_local_8124.yaml`.
- Run date: 2026-11-14, about 22:00 to 22:52 CST (about 50 minutes of wall-clock time).

## Result

**7 / 23 resolved (30.4%).** 0 harness errors, 0 empty patches, 0 timeouts (the longest task took 264 s against the 300 s budget).

| repo | resolved |
|---|---|
| psf/requests | 3 / 13 |
| Textualize/rich | 4 / 9 |
| encode/httpx | 0 / 1 |

Paired comparison on the same 23 ids. The earlier arms ran with an 8 minute budget; this one had 5 minutes.

| arm | resolved | mean s/task |
|---|---|---|
| baseline (run_02 + run_05) | 4 / 23 | 197 |
| bm25 (run_04 + run_06) | 7 / 23 | 162 |
| **v6_impact (this run)** | **7 / 23** | **122** |

- v6 against baseline: v6 resolved 3 tasks that baseline did not (rich_2725, rich_2943, rich_3468), and baseline resolved none that v6 missed. Baseline's requests_7427 "pass" came from an empty patch.
- v6 against bm25: both arms resolved exactly the same 7 tasks, so this run shows no gain in resolves. v6 used about 25% less time per task and fewer tool calls (7.4 vs 9.3 mean on the 20 bm25 ids).

## Per task

| task | resolved | patch bytes | tool calls | secs | notes |
|---|---|---|---|---|---|
| requests_7505 | no | 752 | 7 | 160 | |
| requests_7502 | no | 582 | 4 | 84 | |
| requests_7433 | no | 42231 | 13 | 202 | 3 failed edit_file calls, then write_file truncated models.py (576 lines down to 3); submitted with a syntax error that verify had flagged |
| requests_7427 | YES | 716 | 5 | 72 | |
| requests_7315 | YES | 729 | 10 | 166 | |
| requests_7328 | no | 543 | 5 | 170 | |
| requests_7309 | YES | 529 | 5 | 82 | |
| requests_7205 | no | 514 | 5 | 66 | |
| httpx_3672 | no | 2305 | 14 | 264 | 1 failed edit_file |
| requests_6757 | no | 323 | 8 | 199 | |
| requests_6629 | no | 516 | 6 | 88 | |
| requests_6644 | no | 609 | 6 | 83 | |
| requests_6589 | no | 470 | 5 | 61 | |
| requests_6592 | no | 579 | 4 | 51 | |
| rich_3180 | no | 774 | 4 | 92 | |
| rich_3468 | YES | 1265 | 13 | 233 | |
| rich_3296 | no | 418 | 12 | 151 | |
| rich_3052 | no | 979 | 14 | 139 | |
| rich_2943 | YES | 400 | 5 | 43 | |
| rich_2725 | YES | 1099 | 9 | 127 | |
| rich_3043 | no | 2723 | 11 | 156 | 3 failed edit_file calls, then write_file rewrote _export_format.py (broke the `{{ }}` escapes) |
| rich_3006 | YES | 558 | 6 | 54 | |
| rich_3061 | no | 503 | 5 | 53 | |

Every task produced a non-empty patch, and none timed out.

## Skill usage (from traces)

| signal | count |
|---|---|
| tasks that called `repo_eval.py` locate | 23 / 23 (always the first call) |
| tasks that called `repo_eval.py --verify` | 23 / 23 (6 called it twice) |
| tasks that called `fix_edit.py` | **0 / 23** |
| edit_file calls | 42 total, **7 failed** (all `FileEditError: old_string not found`), spread over 3 tasks (httpx_3672, requests_7433, rich_3043) |
| fix_edit call followed by a successful edit | n/a (fix_edit was never called) |

## Notes

- The edit problem is still there and the rescue path was not used. `prompts/system.md` says "If `edit_file` fails, do not send it again. Call ... fix_edit.py". In all 3 tasks with failures, the model instead retried `edit_file` with a re-read `old_string`. In requests_7433 and rich_3043 it then fell back to `write_file` on the whole file. Both rewrites were destructive, and both tasks failed.
- `--verify` caught the requests_7433 breakage (it reported a syntax error both times), but the model submitted anyway. In rich_3043, verify reported the module-level rewrite as "clean", because there were no syntax or name errors and the broken `{{ }}` escapes are semantic.
- Two guards suggested by these failures: block or warn on `write_file` over an existing non-test source file, and route on `"clean": false` before allowing `submit_patch`. This run changed nothing in the submission.
- The smoke run (`results/run_10_v6_smoke`, requests_7427) resolved and followed the same call order.
- Counts come from `count_v6.py`, a scratch script that walks `traces/trace_*.json`. The paired numbers come from `Tools/paired_report.py`.
