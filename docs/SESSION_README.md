# Gemma 4 Developer Agent (E4B): project README

Start here. Every session reads this file first (owner rule, 2026-11-18; moved from the root README.md on 2026-11-19), then `CHECKPOINT.md`, then `MEMORY.md`.

## Current resume point: v13 (2026-11-23)

E4B only, macOS Seatbelt plus official subprocess backend, no Docker. Native role-bound transactions and immutable Git read sharing pass **317 host tests**, official validation, asset equality and undefined-name lint. Fixed-source seven-pair lifecycle timing: 0.155150500 to 0.149583292 seconds (**3.59% faster**), identical output, modeled control operations9->4; profiling verifies Git subprocesses8->5. Earlier +15.44% failed gate is retained. Component timings do not establish model/task speed.

Repeated external Dask development trials remain unresolved with empty patches. Some edits now compile in isolated slots, but no verified central apply or successful submission has been observed. Prepared-owner trial timed out241.63s; final-source parity run also timed out241.64s with0/1 and an empty patch. Its root reached the finalizer, but outside verification rejected a missing required function definition. Do not claim a quality improvement or tune numeric editor thresholds from failed runs. No Kaggle submission or candidate promotion. v6 stays frozen as the historical reference.

Read [current report](runs/v13_PROTOCOL_2026-11-23.md), ADRs004-014 and `.10x/handoff.md`. Raw captures/task material are local-only under reports/v13_protocol_2026-11-23. Source is recorded on main after fast-forward publication of v13-protocol-diagnosis. Owned E4B/proxy services stopped; restart deliberately for the next run.

## Goal

Solo entry in Kaggle's "Google - The Gemma 4 Developer Agent Competition". Targets: Top 3 on the main leaderboard and the $10,000 Small Model Bonus. Sole base model: `gemma-4-e4b-it-qat-w4a16-ct`.

| Date (23:59 UTC) | Event |
|---|---|
| Nov 25, 2026 | Entry and rules acceptance (by hand, owner) |
| Dec 2, 2026 | Final submission and Small Model Bonus. E4B must be one of the two selected finals |

No Kaggle submission has been made yet.

## Where we are (2026-11-19)

Measured on the local MLX stand-in, not on the scorer's 4x L4 vLLM:

| Version | State | Result |
|---|---|---|
| `v0_baseline` | stock reference; its `eval_config` is 1 min, never zip it | 4/23 |
| `v2_bm25` | valid | 7/23 |
| `v6_impact` | frozen reference, best measured | 7/23, 25% faster than v2 |
| `v6_1_budget` | v6 + `max_output_tokens` 8192 | 1/25 on unseen tasks, 15 fastapi tasks ungradable locally |
| `v7_brigade_lite` | lane runs | tied v6 (2/11 vs 2/11) |
| `v8_ensemble` | lead plan, 4 implementers, 1 adversary, finalizer | 0/5 (run_20); timeout on 1 task in run_21 and run_22 |
| `v9_recurrent` | hybrid recurrent SemDAG candidate | 0/2 vllm-metal smoke (run_24); both timed out |
| `v10_edit_rescue` | v9 + repaired edit path, flow in locate, working principles | 1/3 vllm-metal smoke (run_25, subprocess sandbox); edit_file 5/6 ok vs 3/9 in run_24 |
| `v11_task_ir` | problem IR -> anchor -> loop locus; 400-char locate; fix_edit line range is the only edit path; verify blocks off-locus and whole-file patches; 5 calls, no sub-agent | 1/3 smoke (run_28), and the one resolve is an empty patch; fix_edit 5/5 applied; offline anchor beats BM25 rank 1 on qualname tasks (19/26 vs 10/26). Not yet run on paired23 |

Why v8 is stuck: stage 1 (four implementers) uses the whole 4-minute budget locally, so the adversary and finalizer never run. In run_22 the lead's ranked sites were wrong for all four assignments, and one implementer repeated a malformed `run_skill_script` call six times. See `docs/runs/run_22_RESULTS.md`.

Local model server: **vllm-metal** (owner decision 2026-11-18), on port 8124 behind the telemetry proxy on 8125. It is the only local server: oMLX was removed on 2026-11-18. `Tools/run_eval_seatbelt.sh` defaults to `SERVER=vllm_metal`; `SANDBOX=subprocess` runs tasks without Docker. vllm-metal uses the scorer's vLLM flags but rejects `thinking_token_budget`, so the proxy drops it and the thinking budget is not enforced locally. Earlier runs (run_10 to run_23) used mlx_lm or oMLX.

Known local defects: the arm64 sandbox image breaks all 67 fastapi tasks (pydantic-core mismatch), so local grading covers rich, requests and httpx only. The scorer is x86_64 and unaffected.

## Decisions on record

- Budget (owner rule): `max_time_minutes 4`, `timeout_seconds 300`, `max_tool_calls 40`, `max_turns 60`, max_output 16384, thinking 4096. Do not ask to change.
- Never tune or train on the public competition tasks. The 6,874-row `LoRAData/final` set is demoted for that reason.
- v6 stays frozen as the reference. New work goes in new version folders.

## Next steps (ordered)

00. (2026-11-20) Run v11_task_ir on paired23 against v6's 7/23 (`docs/runs/run_26_28_RESULTS.md`). Before a LoRA on the graph, v11 must beat v6 there.

0. (2026-11-19) Measure v10_edit_rescue against v6 on held-out tasks; run the Kaggle L4 timing notebook for E4B and 31B before any larger-model decision (`docs/runs/run_25_RESULTS.md`, larger-model section).

1. Seal a floor zip of v6 (best measured) and make the first Kaggle submission (needs owner approval).
2. Run the Kaggle L4 timing notebook once: seconds per task, vLLM start-up, projected 120-task time against the 12 h cap.
3. Decide whether v8 can fit 4 minutes (fewer implementers, or lead-first plus one implementer) or is dropped.
4. Fix local fastapi grading (amd64 image or arm64 pydantic-core wheel overlay).
5. Failure-driven dataset pilot, after sign-off on `Designs/FAILURE_DRIVEN_DATASET.md` section 6.

## Open questions for the owner

- Approve the floor submission and the first daily submit.
- fastapi local-grading fix choice.
- Decide whether the interview-review branch should become the repository's default branch.

## Map

| Path | What |
|---|---|
| `CHECKPOINT.md` | last resume point (written 2026-11-17, before v8) |
| `CLAUDE.md`, `AGENTS.md` | operating rules, constraints, commands |
| `MEMORY.md` | index of project memory and where to find durable facts |
| `AgenticSubmission/` | versions v0 to v8, each a zippable submission folder |
| `docs/runs/` | preregistrations and results for every run |
| `results/` | raw run outputs and `telemetry.sqlite` |
| `Tools/` | local runner, MLX server scripts, telemetry, v8 builder |
| `Designs/` | audits, roadmap, dataset and LoRA designs |
| `competition-constraints/`, `Rules/`, `DataSets/` | official rules and data (DataSets is gitignored) |
| `SemDag-IR-BM25/` | ignored local clone of the public GitHub repo |

## Session start protocol

1. Read this README.md, then CHECKPOINT.md and MEMORY.md.
2. `git log --oneline -10` and `git status`: the folder is the source of truth, GitHub is behind.
3. Check `docs/runs/` for the newest `run_*_RESULTS.md` before proposing work.
4. At the end of a session, update the "Where we are" table here and add a dated line to MEMORY.md.


## 2026-11-22: v13 qualification

Current candidate tested: v13_orchestrator, Gemma E4B only, macOS Seatbelt plus official subprocess backend, no Docker evaluation. Repaired hardlink workspace aliasing, subprocess slot-path resolution, editor budgets and packed workspace arguments/skill documentation. Host suite: 217 passed. External Dask grading: empty 2 fail/43 pass, reference 45 pass. Two valid same-task development runs both unresolved with empty patches; second times out at 241.44 s. An intervening authentication failure is excluded. No task-resolution gain established and no candidate promotion. Details: [v13 qualification](runs/v13_QUALIFICATION_2026-11-22.md). Next: design around malformed E4B tool calls and budget use, preserving the four-minute/default-token rules.

## v13 edit/tool design awaiting approval (2026-11-22)

New real-source component probes reproduced off-assignment editing, unverified stale central overwrite, and an accepted stale-coordinate edit inserting a duplicate assignment. No implementation changed. Proposed native edit transactions and fused lifecycle calls first, then a separate subagent-policy experiment after successful-edit timing exists. Design: [.10x spec](../.10x/specs/2026-11-22-v13-edit-tool-policy.md). Local receipts: reports/v13_edit_policy_design_2026-11-22/.

## 2026-11-23: v13 Stage 1 transactions

Approved native edit/tool transaction implementation completed. Scope/hash/single-use guards, atomic source writes, fused prepare/finalize, independent verification and conditional rollback are in v13. 247 full host tests and official validation pass. Final fixed-source component comparison: 9→4 modeled control ops, 0.142612→0.149561 s (+4.87%), identical output; gate passes. E4B smoke on the same external Dask development issue: 0/1 resolved, 104.39s, empty patch, no managed/edit/apply or editor dispatch; root used raw shell routes. No live adoption/promotion. See [report](runs/v13_STAGE1_2026-11-23.md). Next: review [.10x role-capability proposal](../.10x/specs/2026-11-23-v13-role-capability-policy.md); no numeric editor thresholds before successful E4B editor timings.

## 2026-11-23: role-bound v13 policy

Removed generic shell tools from root/editors; each role registers only scripts/run.py, with common native code in readable assets. Root actions prepare/finalize/status; editor actions view/edit/status with static slot binding. Canonical skill name semdag is preserved using nested role folders. Actual SDK/subprocess denial and both editor lifecycle fixtures pass; 272 full host tests and official validator pass. First E4B trial 0/1 empty patch, 241.58s timeout; exact JSON manual/native serialized-array repair retained boundaries, rerun 0/1 empty patch, 84.82s. No live preparation/edit/apply, no promotion or numeric policy tuning. See [report](runs/v13_ROLE_POLICY_2026-11-23.md). Owned services stopped; raw artifacts local. Next gate is correct live outer tool protocol and a successful editor lifecycle.
