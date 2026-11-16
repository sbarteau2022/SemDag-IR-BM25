# Frontier loop: Gemma 4 E4B SWE agent (DRAFT, not yet set)

Status: draft for the owner's go-ahead. The gate is not set. Status is derived from LOG.md.

## Examine (evidence from run_10, v6_impact, paired23, 5 min budget, local MLX)

- Resolved 7/23. Every one of the 23 tasks produced a non-empty patch, and none timed out.
- Localization is mostly solved. The agent edited the gold file in 20/23 tasks and the gold function in 15/23 (`Tools/trace_report.py`).
- **Fix correctness is the bottleneck.** In 9 tasks the agent edited the gold function and still failed (requests_7502, 7433, 7328, 7205, 6589, httpx_3672, rich_3180, 3052, 3061).
- **Budget left unused.** Tasks averaged 122 s of the 300 s budget. Typical sequence: locate, read, one edit, verify, submit. There was no reproduction before the edit, and 4/23 tasks ran no test at all.
- **Edit robustness.** 7 of 42 edit_file calls failed, spread over 3 tasks. fix_edit.py was called 0 times. 2 tasks fell back to a destructive write_file, and one of them submitted despite verify reporting `"clean": false`.

Candidates, ordered by expected gain:
1. A reproduce-first, test-driven fix loop that spends the unused budget: write a failing repro to /tmp, run it, edit, re-run it, and only then submit. This addresses the 9 right-place-wrong-fix tasks.
2. Edit-rescue routing plus write_file and submit guards, enforced through skill script output and prompt structure (the harness tools cannot be changed). This addresses the 3 edit-failure tasks.
3. Candidate sampling with a self-check: two patches, keep the one whose repro passes.

**Chosen target:** 1 and 2 together, as one agent version (`AgenticSubmission/v7_*`, a new directory; v6 stays frozen). Expected gain: the 9 + 3 failing tasks above.

## Preregistered bar (written before any v7 run)

- Dev set: `results/paired23_ids.txt` (23 tasks). Iteration is allowed against it.
- Held-out set: a fixed, seeded sample of N tasks from the 106 public tasks never run (fastapi 67, rich 39). It is drawn once, written to `results/heldout_ids.txt`, and run only at baseline and at a candidate stop. No tuning against it.
- Conditions for every scored run: `Tools/run_agent_eval_5m.sh` (5 min per task, 40 tool calls, Docker sandbox, concurrency 1), the same MLX checkpoint and sampling, no adapters.
- **Step gate:** a v7 candidate validates (`validate_directory`), has 0 harness errors, 0 timeouts and 0 destructive whole-file rewrites on dev, and resolves at least 9/23 on dev.
- **Drastic bar (stops the loop):** dev resolved at least 12/23 (v6: 7/23) with no more than 1 v6-resolved task lost, AND held-out resolved at least v6's held-out score × 1.5 and at least +4 tasks, both measured on the same held-out ids.
- Only the owner changes these numbers.

## Isolation (deviation from the skill, needs owner approval)

The skill says to implement and measure inside a Lima VM. Here the measurement needs MLX on Metal and Docker Desktop, and neither runs inside a Lima VM on this Mac. Proposed isolation:
- All changes go in new directories: `AgenticSubmission/v7_*`, `results/run_1x_*`, `docs/frontier-loop/`.
- v0 through v6, the original Tools scripts, the dataset, and the Qwen3.6Cyber tree are never modified.
- Every measured run uses the port 8124 server, which is already running. No process outside the loop is killed, and the ClickHouse container is left alone.

## Gate state (needs owner approval)

`~/.claude/frontier-loop/state.json` is one global file. It currently holds the Qwen3.6Cyber tppe-economics goal (status `blocked`). Running `frontier_goal.py set` here would overwrite it, and AGENTS.md says not to touch that goal. Options: (a) back that file up and restore it afterwards, or (b) give this loop its own `FRONTIER_STATE_DIR`, which means editing the Stop hook command in `~/.claude/settings.json`.

## Rules

No moving gates. Receipts (command and output) go in LOG.md. Nothing is submitted to Kaggle. Nothing is committed or pushed without asking. Max 20 rounds. One dev run takes about 50 min.
