# Failure-Driven Dataset for the Gemma-4-E4B Agent LoRA

Status: **PROPOSED** (design, 2026-11-17). Replaces the demoted `LoRAData/final/` set (see the banner in `LORA_TRAINING_DESIGN.md`). Owner sign-off is needed on §6 before any repository is downloaded or any trajectory is generated.

## 1. What the adapter has to do

- The scorer runs about 120 hidden tasks **from private repositories**, one at a time, 5 minutes each, through the nine harness tools plus skills. A task counts only if the hidden tests pass after test and config edits are stripped from the patch.
- The model is `gemma-4-e4b-it-qat-w4a16-ct`, served on 4×L4 vLLM with `thinking_budget` 4096 enforced, 32,768-token context, events compaction at 14,336 tokens.
- So the adapter must improve **process on unseen repos**: reproduce, localize inside the file, edit safely, verify, submit only on green. It must not memorize the four public repos.

## 2. Measured failure modes (the targets)

Classes come from `Tools/telemetry/ingest.py` (definitions in `Tools/telemetry/README.md`). **LIVE-MEASURED**, local MLX stand-in.

### run_10: v6 on paired23 (requests 13, rich 9, httpx 1)

| Class | Tasks | Ids |
|---|---|---|
| resolved | 7 | requests_7427, 7315, 7309; rich_3468, 2943, 2725, 3006 |
| right_function_wrong_fix | 8 | requests_7502, 7328, 7205, 6589; httpx_3672; rich_3180, 3052, 3061 |
| right_file_wrong_function | 4 | requests_7505, 6629, 6592; rich_3296 |
| destructive_write | 2 | requests_7433, rich_3043 |
| wrong_file | 2 | requests_6757, 6644 |

Behaviour signals from the same run:
- `edit_file` failed 7 of 42 times; `fix_edit.py` was never called; 2 tasks fell back to `write_file` over a source file.
- No task wrote a reproduction to `/tmp` before editing.
- Median task used 92 s of 300 s.
- 0 sub-agent calls and 0 graph-tool calls.

Thinking and context:
- Thinking per model step: p50 137 tokens, p90 1,305, max 3,461. **None over 4,096**, so thinking length is not the problem.
- Peak context: p50 35%, max 67% of 32k. Many tasks cross the scorer's 14,336-token compaction point, which local runs do not reproduce.

### run_11: v6.1 on 25 unseen tasks (fastapi 16, rich 9)

Details are in `docs/runs/run_11_RESULTS.md`.

- **15 of 16 fastapi tasks are ungradable locally** (arm64 pydantic-core mismatch; scorer unaffected). They give process signal only.
- On the 9 rich tasks: 1 resolved, 3 right_file_wrong_function, 1 right_function_wrong_fix, 1 wrong_file, 1 no_patch, 2 timeouts.
- **`edit_file` failed 30 of 65.** 25 were "old_string not found", meaning the model quoted text that is not in the file. That is the single largest process defect across both runs. The sub-agent editor (12/31 failed) is no better than the root agent (18/34).
- **Reproduce-first never happens:** 0 of 25 tasks wrote a repro to `/tmp` before editing (0 of 23 in run_10 as well).
- Context pressure is real: median peak 44%, p90 77%, max 99% of 32k. The scorer compacts at 14,336 tokens, which more than half of these tasks crossed.
- Thinking stays mostly inside budget: 1 of 412 steps over 4,096.

## 3. Failure → behaviour → data family

| # | Failure (measured) | Target behaviour | Family | Acceptance gate (all also need harness `resolved=True`) |
|---|---|---|---|---|
| F1 | right_function_wrong_fix; 0/48 tasks reproduce first | Write a failing repro to `/tmp`, run it red, edit, re-run green, run the targeted tests, then submit | **repro-fix** | Trace shows repro red before the first edit and green after the last |
| F2 | right_file_wrong_function | Inside the right file, follow the failing path (callers/callees, traceback lines) before choosing the edit site | **in-file localize** | Edited functions ∩ gold-diff functions ≠ ∅ |
| F3 | edit_file "old_string not found" (30/65 failed in run_11, 7/42 in run_10), destructive_write | After an edit error: re-read the exact lines, retry a small edit or call `fix_edit.py`. Never `write_file` over existing source | **edit recovery** | ≥1 edit error followed by a successful small edit; 0 destructive writes |
| F4 | wrong_file | Localize with `repo_eval`/`locate` output plus a targeted read before editing | **file localize** | Edited files ∩ gold files ≠ ∅ |
| F5 | submit despite red verify | Continue while budget remains; at budget end submit the smallest green-or-best diff | **submit gate** | No `submit_patch` after a red verify when ≥ 60 s remain |
| F6 | peak context 44% median, 99% max; scorer compacts at 14,336 | Targeted reads (line ranges), stop exploring once localized, keep a short `/tmp/notes.md` of facts and tried edits | **context economy** | Resolved with peak context < 14,336 tokens, or the task carries a notes file it re-reads after compaction |

Starting weights follow measured share across run_10 and run_11's gradable tasks:
- **F3 edit-recovery and F1 repro-fix lead.** F3 shows up in most failing tasks even when they also fail for another reason.
- F2 is next (7 tasks), then F4 (3) and F5.
- A sixth family, **F6 context economy**, covers short reads, closing exploration and summarising into a `/tmp` note before ~14k tokens. It is added because peak context crossed the scorer's compaction point in most tasks.

Re-weight after each pilot.

## 4. Where the rows come from (never the public 129)

1. **Repositories:** permissive-licence Python projects with pytest suites. Not fastapi, rich, requests, httpx or their forks. One licence and commit is recorded per repo. Splits are by repository.
2. **Tasks:**
   - (a) Real bug-fix commits: issue or commit text, the source change, and tests that fail before and pass after. This is the SWE-bench recipe, reproduced locally.
   - (b) Seeded single-function defects under existing tests, for volume.
   - Each task is packaged in the harness format: a `tasks.jsonl` row plus a `snapshots/<id>.tgz` git tree with history after the base commit removed.
3. **Trajectories:** generated by **E4B itself** through the real harness and the same telemetry (`Tools/run_eval_seatbelt.sh`): K samples per task, and only resolved runs are kept (rejection-sampling fine-tuning). A frontier teacher is optional and only after the provider-terms check (open-questions Q5).
4. **Selection:** a resolved trajectory joins a family only if it passes that family's gate in §3. The telemetry store supplies the per-step fields: thinking text, tool name and args, observation, ok/error, tokens.
5. **Rendering:** reuse `LoRAData/gen/render.py`. It already applies the Gemma-4 template, `enable_thinking`, assistant-only masks and the schema/dup/cap audits. Thinking and tool-call tokens are targets; tool outputs are masked.

## 5. Integrity gates (all mandatory)

- **Decontamination:** no file from the four public repos; issue-text near-duplicate check against all 129 public problem statements; no public task id, base commit or gold patch in any row.
- **Execution receipt** per row: the harness's own Phase-2 verdict, `run_id`, telemetry row ids, trajectory hash.
- **Length:** ≤ 32,768 tokens per rendered row. Rows that cross 14,336 tokens are also rendered in the compacted form the scorer would show (events compaction, retention 5), so the adapter trains on what it will see.
- **Balance:** per-repo and per-family caps. Failed and partial episodes are logged in the failure ledger, never silently dropped.
- **Evaluation stays on public tasks only:** dev = paired23; probe = run_11's 25; held-out = the 81 never-run tasks, drawn once and run only at baseline and final.

## 6. Decisions needed from the owner

1. **Repository list and download.** Downloading 10–20 repos (mostly small) needs network access, which AGENTS.md says to ask about. A shortlist will be proposed for approval.
2. **Where to generate.** Local MLX runs one task at a time at 51 tok/s decode, a median 217 s per task (run_11). A Kaggle L4×4 vLLM notebook can run concurrent tasks. Generation at the needed scale (hundreds of tasks × K samples) belongs on Kaggle; the Mac stays free for development.
3. **Teacher trajectories** (yes/no), pending the licence check.
4. **Local fastapi grading fix.** Either an amd64 sandbox image (emulated, slower) or an arm64 `pydantic_core 2.46.4` wheel overlay (one small download). Until then, local evaluation is effectively rich + requests + httpx (62 tasks).

## 7. Known limits

- Graph and embedding files for `get_code_neighbors`, `get_code_subgraph` and `search_similar_code` come from Google's internal pipeline (`swegemma/graph/embedding_utils.py` points at internal storage). No public generator ships. New tasks will not support those three tools unless compatible graphs are built (schema in `DATASET_DESCRIPTION.md`; the embedding model is unknown). v6 made zero graph-tool calls, so trajectories without them match current behaviour.
- Local runs install test dependencies the scorer's subprocess sandbox lacks, so local resolve rates are upper bounds.
- Pilot yield is unknown until measured. No dataset size is promised before a pilot run reports one.
