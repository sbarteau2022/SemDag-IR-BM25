# v13 role-bound capability experiment — 2026-11-23

Status: compiled/native permission and lifecycle gates pass; live preparation/edit/apply and task-resolution gates FAIL. Candidate remains experimental; no performance promotion, Kaggle upload, model training or dispatch-timing tuning.

## Implemented boundary

Root and both editors no longer declare run_command or raw edit/write/read tools. Root retains its official get_status, submit_patch and two agent_tools plus its skill tools. Editors retain get_status plus their own skill tools.

All agents use the canonical skill name semdag and entry scripts/run.py, with separate resources:
- Root: skills/semdag; fixed root actions prepare/finalize/status.
- Editor 1: skills/editor_1/semdag; fixed editor actions view/edit/status, bound to slot 1.
- Editor 2: skills/editor_2/semdag; same editor actions, bound to slot 2.

Only run.py is registered as executable. Shared implementation dependencies reside in readable assets/engine and are byte-identical across all three bundles. Static entry constants bind role and slot; no user role or host repo flag is accepted. SDK script lookup rejects helper/asset/traversal paths before execution. This is packaged native authorization/computation, not a host prompt/output adapter.

The installed SDK requires skill name to equal its directory basename; nested role folders satisfy that while keeping one skill name per agent. Actual compiled-toolset tests verify that identical names do not merge role resources. A symlinked sandbox path exposed a native status identity mismatch; normalizing to real paths fixed it, with the failing probe retained.

## Component verification

**272 full host tests pass**, zero errors/failures/skips (host_tests_round2.xml). Official package validation and E4B/default-budget checks pass. Role engine byte identity is checked by Tools/local/sync_v13_role_assets.py --check.

Actual Google ADK compilation, run_skill_script lookup, official AdkSandboxCodeExecutor and swegemma SubprocessManager are exercised. These are component fixtures with no model inference:
- Root edit/view and editor prepare/finalize are denied before mutation.
- Editors cannot use another slot/handle, including omitted-slot attempts.
- Role override flags, model-supplied host repo paths, malformed arguments and traversal are refused.
- Only run.py executes; edit_tx.py, fix_edit.py, workspace_mgr.py and assets paths return SCRIPT_NOT_FOUND.
- Missing outer SDK keys and quoted/unknown skill names remain SDK errors.
- Legitimate root prepare -> editor 1 status/edit -> root outside verification/apply succeeds; a separate distinct BM25 alternative completes through editor 2.
- A complete JSON array serialized as one argv value is decoded only inside native code, with all string types/actions/roles revalidated. Wrong-role serialized arrays remain denied. No skill name/file path is invented or stripped outside the SDK.

## Frozen live comparison

Same external development issue as Stage 1: SWE-Gym/Lite dask__dask-8801, pinned source commit 9634da11a5a6e5eb64cf941d2088aabffe504adb. This is a diagnostic development case, not held-out generalization. Its official empty/reference grading gate was previously verified (2 fail/43 pass vs 45 pass). No public competition tasks were used for tuning.

Runtime: Gemma E4B only (competition-weight local MLX repack, vLLM Metal), macOS Seatbelt plus official subprocess backend, no Docker. Four-minute task budget, 40 calls, 60 turns, 300-second command ceiling; 16384 output and 4096 thinking tokens for thinking roles. Same two editors, ambiguity condition and retry instructions. Proxy adaptation is not the scorer's CUDA logits-processor implementation.

| Run | Resolved | Patch | Total time | Finding |
|---|---:|---:|---:|---|
| Stage 1 reference | 0/1 | empty | 104.39 s | Six generic shell calls bypassed the intended flow. |
| Role policy, first version | 0/1 | empty | 241.58 s | Timeout; quoted outer tool values, encoded argv and repeated unprepared dispatch. |
| Role policy, format/codec repair | 0/1 | empty | 84.82 s | Wrong skill then missing outer file_path; no registered native script request. |

First policy trace contains get_status 3, unknown semdag tool 1, load_skill 2, run_skill_script 14, editor_1 5, list_skills 6, unknown run.py tool 1. Nine requests targeted the registered entry, but none produced a prepared slot, managed edit or verified apply. Native status returned unprepared and denied progress; no generic shell/helper execution occurred.

The first failure was retained, then exact JSON examples/terminal unprepared feedback and bounded explicit-JSON argv decoding were repaired. The same component and full gates were rerun before sealing the second source version. Neither missing SDK outer fields nor quoted outer names were corrected by a host wrapper. Second trace: get_status 1, load_skill 1, run_skill_script 3, submit_patch 1; zero registered-entry requests. The agent's prose claim of a fix is contradicted by the empty patch and failed grading.

No live root preparation, managed edit or outside-verified apply occurred in either run. The live adoption gate is NOT met. Runtime/call-count differences among failed runs are not a task-quality improvement. Source versions and failures are retained; no successful editor timing exists for choosing dispatch thresholds.

## Reproduction and raw receipts

- PYTHONDONTWRITEBYTECODE=1 LITELLM_LOCAL_MODEL_COST_MAP=True sandbox-exec -f Tools/seatbelt/no_network.sb .venv-harness/bin/python -m pytest tests/test_v13_role_capabilities.py.
- Full suite: PYTHONDONTWRITEBYTECODE=1 LITELLM_LOCAL_MODEL_COST_MAP=True .venv-harness/bin/python -m pytest.
- Bundle identity: python3 Tools/local/sync_v13_role_assets.py --check. Without --check it syncs canonical root engine assets to editor bundles.
- Live evaluation uses Tools/local/eval_parity.py with explicit external tasks/snapshots and v13 submission, --sandbox subprocess --concurrency 1 and owner limits above. Endpoint variables are pinned to the local E4B proxy; no hosted fallback.
- Local reports/v13_policy_2026-11-23/: baseline/, source_manifest*.json, compiled_policy_tests.txt, compiled_alias_baseline.txt, host_tests*.xml, iteration_plan.json, live_summary.json, model_run*/, telemetry.sqlite and service_cleanup.json. Task bodies/transcripts remain local.

## Limits and remaining gate

This proves the registered action surface and native helper invariants. It does not provide full host confinement or make arbitrary patched library code safe to execute. Root agent_tool and submit_patch remain callable, so unprepared dispatch and empty submission are not fully prevented. Native error feedback cannot force a model to stop thinking or call valid tools. Required outer tool fields must actually be generated correctly before native code can act. No SDK patches, argument-guessing adapter, budget changes, other-model inference or LoRA training were added.

Further policy-quality work must first demonstrate correct live tool protocol and a successful E4B editor lifecycle. Do not derive timing thresholds from these failed dispatches or promote based on component tests alone. Frozen v6 remains unchanged. Owned E4B/proxy services were stopped after the experiment.
