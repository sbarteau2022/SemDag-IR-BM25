# CHECKPOINT: 2026-11-17, v6 baseline + telemetry

Resume point for the next session. Rules and layout: [AGENTS.md](AGENTS.md) / [CLAUDE.md](CLAUDE.md). Audit of the space: `Designs/AUDIT_2026-11-17.md`.

## Dates

- Entry and rules acceptance: **Nov 25** (by hand, owner).
- Final submission and Small Model bonus: **Dec 2**, 23:59 UTC.
- No Kaggle submission has been made yet. The Paper Track deadline (Nov 12) has passed.

## Agent versions

| Version | State | Evidence |
|---|---|---|
| `v0_baseline` | Stock reference. Its `eval_config` is the 1 min / 10-call sample: **never zip it** | 4/23 on paired23 |
| `v2_bm25` | Valid | 7/23 on paired23 |
| `v4_semdag` | Valid, now 5 min/task (was 8) | offline localization only |
| `v6_impact` | **Frozen reference** | **7/23 on paired23** (run_10, same 7 as v2, 25% faster) |
| `v6_1_budget` | **Current** = v6 + `max_output_tokens` 8192 | run_11, see below |

Canonical budget (owner rule 2026-11-17, competition defaults; do not ask to change):
- `eval_config`: `timeout_seconds 300 / max_tool_calls 40 / max_time_minutes 5 / max_turns 60`.
- Sampling: max_output 16384 and thinking_budget 4096 for every thinking role; include_thoughts true.
- Tasks that hit the cap end about 30 s late, so plan the 12 h budget at 5.5 min per task.

## Measured state (LIVE-MEASURED, local MLX stand-in)

- **run_10** (v6, paired23):
  - 7 resolved, 8 right_function_wrong_fix, 4 right_file_wrong_function, 2 destructive_write, 2 wrong_file.
  - `edit_file` 7/42 failed.
- **run_11** (v6.1, 25 unseen fastapi+rich tasks, no-network seatbelt):
  - 1/25 resolved. 15 fastapi tasks were ungradable locally (environment defect below).
  - `edit_file` failed 30/65, 25 of them "old_string not found".
  - 0/25 reproduced the bug before editing.
  - Peak context max 99%.
  - Details: `docs/runs/run_11_RESULTS.md`.
- **Local environment defect:**
  - The arm64 sandbox image gets pydantic-core 2.50.4 while pydantic needs 2.46.4, whose cached wheel is x86_64-only. So all 67 fastapi tasks fail to import locally; the scorer (x86_64) is unaffected.
  - Until it is fixed, local evaluation covers rich + requests + httpx (62 tasks).

## Tooling now in place

- `Tools/telemetry/` (README there):
  - A timing proxy (TTFT, decode tok/s, per call).
  - A SQLite store: tokens, tool pass/fail, thinking vs budget, context, nested sub-agent steps, failure classes.
  - Per-run report, export, and a baked Docker image per run.
  - Proxy equivalence gate passed against `mlx_lm.server`.
- `Tools/run_eval_seatbelt.sh` + `Tools/seatbelt/no_network.sb`:
  - Scored-style local runs with no network.
  - Always uses Docker Desktop, never Colima.
  - Reads the budget from the submission's `eval_config.yaml`.
  - Heavy work runs only after the harness exits.
- Tests: `.venv-harness/bin/python -m pytest` → **63 passed** (reporting tools, telemetry, structural IR, observer).

## Decisions taken today

- The 6,874-row `LoRAData/final` set is **demoted** (72% derived from public eval tasks, 88% graph puzzles). Replacement design: `Designs/FAILURE_DRIVEN_DATASET.md`.
- `!include ../x` is allowed when it resolves inside the submission root. Verified in `adk_submission` code and by a live load; docs corrected.

## Next (ordered)

1. **Fix local fastapi grading.** Owner picks: amd64 sandbox image, or an arm64 `pydantic_core 2.46.4` wheel overlay.
2. **v7 agent** aimed at the two largest measured defects:
   - (a) Edit reliability: re-read the exact lines before `edit_file`, small unique anchors, route failures to `fix_edit.py`.
   - (b) Reproduce-first: write a `/tmp` repro, run it red, then green.
   - Measure on paired23 against v6's 7/23.
3. **Kaggle L4 timing run** (notebook still never executed): seconds per task, vLLM start-up, projected 120-task wall time ≤ 10 h.
4. **Seal a floor zip** of the best prompt-only version; first daily submission with owner approval.
5. **Failure-driven dataset pilot** after owner sign-off on `FAILURE_DRIVEN_DATASET.md` §6: repo list + download, generation on Kaggle, teacher yes/no.

## Open questions for the owner

- The fastapi fix choice (item 1).
- Approve the frontier-loop gates in `docs/frontier-loop/GOAL.md`.
- Dataset §6 decisions.
- No GitHub remote exists. Add a private one?
