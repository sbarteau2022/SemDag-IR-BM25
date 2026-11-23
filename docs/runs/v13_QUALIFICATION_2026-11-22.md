# v13 E4B sandbox qualification — 2026-11-22

## Status

The candidate under test is v13_orchestrator. No Docker evaluation and no other model is used. This run repairs measured component correctness failures; no held-out task-resolution gain or Kaggle score is established.

## Inputs and method

- Official Kaggle requirements were refreshed through its live page API; the local source receipt is reports/competition_requirements_2026-11-22/REQUIREMENTS.md.
- Runtime: Gemma E4B competition-weight MLX repack via vLLM Metal, model endpoint 8124; telemetry proxies 8125/8126; official swegemma subprocess backend under macOS Seatbelt. The proxy adapts the unsupported thinking-budget field using streaming/resume, which is not scorer logits-processor equivalence.
- Budget: 4 minutes/task, 40 tool calls, 60 turns, 300 seconds/command, 16384 output and 4096 thinking tokens in each thinking role.
- External development issue: SWE-Gym/SWE-Gym-Lite, dask__dask-8801, pinned Dask commit 9634da11a5a6e5eb64cf941d2088aabffe504adb. Selected as a config-only environment-qualification issue to avoid optional dataframe/array dependencies. This is one development task, not a representative or sealed evaluation sample. Public competition tasks and mutation-generated trajectories are not used for optimization evidence.
- Dataset: https://huggingface.co/datasets/SWE-Gym/SWE-Gym-Lite . Source: https://github.com/dask/dask/tree/9634da11a5a6e5eb64cf941d2088aabffe504adb . BSD-3-Clause verified in source LICENSE.txt. Snapshot/task hashes, normalized source archive and environment versions are retained locally.

## Measured defects and repairs

1. Original workspace_mgr hardlinks slot files to central files. An in-place write to slot 1 changed central and slot 2 before apply, and collect returned empty. Independent copies now preserve both until explicit apply; a real-source component reproduction records a nonempty collection and successful apply.
2. Literal /tmp paths in skill arguments are not rewritten inside Python scripts by the subprocess backend. Workspaces now use that sandbox's temporary directory, and explicit slot aliases resolve there. Missing explicit paths fail instead of falling back to central code.
3. Editor sampling was 8192 output / 2048 thinking. Restored owner defaults 16384 / 4096; model unchanged.
4. First E4B run repeatedly sent one packed workspace command, rejected by argparse, then called a nonexistent shell script path. Added native shlex parsing for that observed input form and documented workspace_mgr in the skill manifest. Missing required run_skill_script keys are still rejected; no model-output rewriting or invented tool calls are added.

## Qualification evidence

- Official v13 directory validation passes. Initial inspection imports generated .pyc files; they were preserved outside the submission before validation. This was an inspection artifact, not an original-package defect.
- External empty patch: 2 failed / 43 passed; reference patch: 45 passed. The official verifier passes the empty-fails/reference-passes gate.
- Host suite after repairs: 217 passed, zero failures/errors/skips, from host_tests_round2.xml. Includes 14 focused workspace regressions.
- Seatbelt network probe: external HTTPS blocked (curl exit 7); loopback model listing succeeds and lists only gemma-4-e4b-it-qat-w4a16-mlx.
- First live E4B run: no patch, 0/1 resolved; finished agent at 187.1 seconds. Repeated workspace invocation failures prevented a valid edit workflow. This run already includes independent-copy and budget repairs, so it is not an untouched-original performance baseline.
- A subsequent attempt failed authentication before any E4B completion reached its proxy. It is an infrastructure failure, not a valid model-quality comparison. Preserved separately as model_run_round2.
- The diagnostic rerun pins all endpoint environment settings to the verified local E4B proxy and retains the same external development task and task budgets. Outcome is appended after completion.

## Reproduce

Host regressions: PYTHONDONTWRITEBYTECODE=1 .venv-harness/bin/python -m pytest.

Grading qualifier (dependencies already staged in .venv-v13-eval): set PYTHONPATH to the absolute .venv-harness/lib/python3.13/site-packages path, then run sandbox-exec -f Tools/seatbelt/no_network.sb .venv-v13-eval/bin/python Tools/local/qualify_v13.py --data DataSets/v13_external_qualification --output reports/v13_qualification_2026-11-22/grading.

For live eval use Tools/local/eval_parity.py eval with explicit external tasks/snapshots, v13 submission, --sandbox subprocess --concurrency 1 --max-tool-calls 40 --max-time-minutes 4 --max-turns 60 --timeout-seconds 300. Pin OPENAI_BASE_URL, MODEL_PROXY_URL, LITELLM_API_BASE and LOCAL_INFERENCE_URL to the local E4B proxy; use local placeholder keys. The report's model YAML binds only the E4B alias. Dependencies and sources are staged before the offline run; no runtime pip/network downloads.

## Limits and next action

Independent file copies fix byte aliasing, not full host filesystem confinement. The existing Seatbelt profile restricts network; the subprocess backend is not a VM or chroot. Component path checks are tested, but this does not establish a complete adversarial security boundary. No Kaggle CUDA timing, official score or held-out improvement is claimed. Keep frozen v6 as the measured reference. Decide the next intervention from the final v13 trace, without promoting this single-task diagnostic result as generalization.

Local raw receipt directory: reports/v13_qualification_2026-11-22/ (baseline.json, post_fix.json, packed_args_baseline.json, grading/, host_tests_round2.xml, network_isolation.json, run_metadata.json, round2_metadata.json, task_provenance.json, model_run*/, and telemetry*.sqlite). Private/local runtime artifacts are not pushed.


## Final diagnostic outcome

| Run | Resolved | Patch bytes | Duration | Finding |
|---|---:|---:|---:|---|
| model_run | 0/1 | 0 | 191.34 s total (agent finished at 187.1 s) | Repeated workspace invocation failures; dispatched editors without a workspace. |
| model_run_round2 | excluded | 0 | 1.61 s | Authentication infrastructure failure; zero model tokens. |
| model_run_round2_retry | 0/1 | 0 | 241.44 s | Four-minute timeout after a run_skill_script call omitted skill_name/file_path; no successful workspace spawn. |

The prespecified live mechanism gate (successful spawn) was NOT met. The packed-input unit gate passes, but that fix was not successfully exercised by the model in the rerun. Neither valid run resolved the issue; there is no measured task-resolution improvement. Do not promote this as a better competition agent. This is a same-task development diagnostic, not a paired held-out performance estimate.

Next design must address the E4B tool protocol and budget consumption using further evidence, rather than loosening budgets or silently correcting missing model arguments in a host wrapper. Native workspace correctness fixes are retained; frozen v6 is unchanged. No LoRA training, Kaggle upload, other-model inference or Docker evaluation occurred. Local task artifacts, snapshots and transcripts remain local. Services launched for this experiment are stopped after the run.
