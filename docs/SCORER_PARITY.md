# Scorer parity: what the Kaggle scoring notebook does, and how local runs differ

Written 2026-11-17. Every line cites a source. Sources:
- **[EVAL]** `Rules/Verbatim/evaluation.md` (official page, fetched 2026-11-13)
- **[RULES]** `Rules/Verbatim/model-selection-budget-harness-rules.md` (official page)
- **[ACC]** `Rules/Verbatim/upgraded-accelerators.md` (official page)
- **[HR]** `DataSets/public/HARNESS_README.md` (dataset README; describes `scripts/inference.py`, which is not in the dataset)
- **[STAFF]** `Rules/Verbatim/forum-staff-posts.md` / `forum-findings.md` (staff forum quotes with links)
- **[SRC]** installed harness source in `.venv-harness` (swegemma 0.2.11, adk_submission 0.2.13, adk_eval_core 0.1.0)

Status labels: **OFFICIAL** (rules page or staff), **DOCUMENTED** (HARNESS_README only), **VERIFIED-SRC** (read in installed code).

## 1. The job

| Item | Value | Source | Status |
|---|---|---|---|
| Tasks | ~120: about 60 public + 60 private, all scored in one run | [STAFF] Holbrook 2026-09-24 | OFFICIAL |
| Task repos | **Private repos, not the training repos.** The training repos (fastapi, rich, requests, httpx, …) are not scored | [STAFF] Markowitz 2026-11-04; Holbrook 2026-09-27 ("test issues come from a different set of repos") | OFFICIAL |
| Order | Sequential, one task at a time | [STAFF] Holbrook 2026-09-24 | OFFICIAL |
| Total limit | 12 h for all patches, **including** sandbox setup and vLLM start-up, **excluding** patch validation | [EVAL]; [STAFF] Holbrook 2026-10-07 | OFFICIAL |
| Overrun | The whole submission errors. The "score unfinished tasks as 0" fix was withdrawn | [STAFF] 2026-09-28, 2026-10-15 | OFFICIAL |
| Validation | Separate phase, about 2 h when every task has a patch. No patch means no validation and a score of 0 | [STAFF] Holbrook 2026-09-26 | OFFICIAL |
| Internet | None (L4 sessions must have internet off; sandbox `network_mode="none"`) | [ACC]; [HR] §4.1 | OFFICIAL |
| Packages | The wheelhouse is the authoritative package set; ADK 1.x only, no ADK 2.x | [STAFF] Holbrook 2026-09-27 | OFFICIAL |

## 2. Inference server

| Item | Value | Source | Status |
|---|---|---|---|
| Hardware | 4 × NVIDIA L4, 24 GB each (96 GB) | [ACC]; [HR] §3.1 | OFFICIAL |
| Server | vLLM, `tensor_parallel_size=4`, `gpu_memory_utilization=0.90`, `max_model_len=32768`, `scheduler_reserve_full_isl=False` | [HR] §3.1 | DOCUMENTED |
| Parsers | `tool_call_parser=gemma4`, `reasoning_parser=gemma4`, `reasoning_config` `<\|channel>` … `<channel\|>`, auto tool choice | [HR] §3.1 | DOCUMENTED |
| LoRA | `enable_lora` if adapters exist, `max_loras = number of adapters`, `max_lora_rank = largest rank found` (≤128) | [HR] §3.1 | DOCUMENTED |
| Concurrency | No concurrency cap is passed (continuous batching). `ParallelAgent` concurrent LLM calls are allowed; tool calls run sequentially | [SRC] `adk_submission/server.py`; [STAFF] 2026-09-28, 2026-10-11 | OFFICIAL + VERIFIED-SRC |
| Thinking budget | Enforced: positive `thinking_budget` sends `extra_body.thinking_token_budget` to vLLM's logits processor | [HR] §2; [SRC] `adk_submission/resolvers/generation.py:435-450` | VERIFIED-SRC |
| Penalties | `presence_penalty` / `frequency_penalty` forwarded; vLLM applies them over the whole generated output | [SRC] `google/adk/models/lite_llm.py:1954-1965` | VERIFIED-SRC (forwarding) |
| Retries | `ModelRetryPlugin`: 5 retries on 429/5xx/connection errors, backoff 2 s ×2 up to 60 s | [HR] §7.2; [SRC] `agent_runner.py:671` | VERIFIED-SRC |

## 3. Agent loop and budgets

| Item | Value | Source | Status |
|---|---|---|---|
| Per-task budget | From `eval_config.yaml` (`max_time_minutes`, `max_tool_calls`, `max_turns`, `timeout_seconds`). If omitted: 60 min, 100 calls (inference.py), 500 turns, 300 s | [HR] §7.1 | DOCUMENTED (staff said "the default is no limit"; we always ship the file) |
| Time clock | Starts **after** container setup, wheel install and snapshot extract | [HR] §7.1 tip | DOCUMENTED |
| Command timeout | `min(timeout_seconds, max(5, remaining time))`; a timeout does not end the session | [HR] §6.1 | DOCUMENTED |
| Output caps | `run_command` / graph tools 5,000 chars; `read_file` 150 lines, 10,000 chars | [HR] §7.1 | DOCUMENTED |
| Compaction | `EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=14336, event_retention_size=5)` | [HR] §7.2 | DOCUMENTED |
| Context cache | `ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10)` | [HR] §7.2 | DOCUMENTED |
| Nudges | At most 3 consecutive nudges when a turn ends without a tool call or `submit_patch` | [HR] §5.3 | DOCUMENTED |
| `submit_patch` | Sets a flag; the harness exits **after the current `run_async` turn ends**. Inside a LoopAgent, the loop keeps running to its end | [HR] §5.3, §6.1 | DOCUMENTED (matches run_15 task 7433) |
| No submit | Harness falls back to `git add -N . && git diff` of the working tree; a non-empty diff is still verified | [HR] §8.1 | DOCUMENTED |

## 4. Sandboxes

| Item | Value | Source | Status |
|---|---|---|---|
| Agent and verify containers | Docker image `swebench-sandbox:latest`, `network_mode=none`, 4 GiB RAM (exit 137 above it), 2 vCPUs, fresh container per phase | [HR] §4.1 | DOCUMENTED |
| Scorer backend | A **private Docker sandbox**: "the same base image but installs a different set of dependencies" | [STAFF] Holbrook 2026-09-27 | OFFICIAL |
| Verification | Protected test/config files stripped; 4-pass patch apply; `test_patch` applied; pytest with JUnit XML; fixed 300 s timeout; resolved iff rc=0 and passed>0, failures=0, errors=0, every required test passed | [HR] §8.2; [STAFF] Holbrook 2026-09-24 | OFFICIAL + DOCUMENTED |

## 5. Local parity: where our runs match and where they do not

| Item | Scorer | Local (`Tools/run_eval_seatbelt.sh`, oMLX) | Parity |
|---|---|---|---|
| Model weights | `gemma-4-e4b-it-qat-w4a16-ct` | Lossless MLX repack of the same checkpoint | match |
| Parsers / tool format | vLLM gemma4 parsers | oMLX gemma4 parsing, proxy equivalence 2/2 | match (smoke-tested) |
| Network | none | seatbelt profile (loopback only) + Docker `network_mode=none` | match |
| Container limits | 4 GiB / 2 vCPU | same harness Docker backend | match |
| Budgets | eval_config.yaml | runner passes eval_config values as CLI flags | match |
| Verification timeout | 300 s | CLI default 300 s | match |
| Retries | ModelRetryPlugin | same `agent_runner.py` | match |
| **Compaction** | 14,336-token compaction + context cache | **Now on via `Tools/local/eval_parity.py`** (unit-tested; live check pending, Docker Desktop quit mid-run 2026-11-17). Before: off. `swegemma eval` has no flag for it and `EvalConfig` defaults are `None` ([SRC] `config.py:117-118`, `agent_runner.py:692-695`) | **GAP 1** |
| **Thinking budget** | Enforced by the vLLM logits processor | **Now enforced** by the proxy `--thinking-budget-field thinking_budget` (LIVE-MEASURED 2026-11-17: budget 64 → 61 reasoning tokens, 1024 → 1021, no budget → 1557; `results/server_bench/thinking_budget_gate/`). Before: not enforced. ADK sends `extra_body.thinking_token_budget`. oMLX 0.7.0 reads a different field, top-level `thinking_budget` (`omlx/server.py:1887-1900`, `api/openai_models.py:368`), so the budget is dropped | **GAP 2 (closable)** |
| **Penalties** | Over the whole output | mlx_lm 20-token window (`sample_utils.py:76-82`) | **GAP 3** |
| **Speed** | 4×L4 TP=4, E4B; **not measured by us** | 57.5 tok/s decode, 0.4–0.6 s TTFT (run_15, run_16) | **GAP 4, unknown size** |
| **Dependencies** | Private Docker sandbox, its own dependency set | Harness picks the newest wheel per package (`container_setup.py::_deduplicate_wheels`); fastapi breaks (run_18) | **GAP 5** (irrelevant for fastapi, which is not scored) |
| **Task repos** | Private repos | Training repos only | **GAP 6**: lane-per-repo tuning cannot transfer directly; generalization matters |
| Setup inside the 12 h | Counts | Measured locally but not budgeted | GAP 7 (budget item) |

## 5b. Additional parity facts (2026-11-17)

- **Sampling defaults:** vLLM's default `--generation-config auto` fills any field a request leaves unset from the checkpoint's `generation_config.json`: `temperature 1.0, top_k 64, top_p 0.95`. ADK sends `temperature` and `top_p` from our configs but no `top_k`, so **every scorer call samples with top_k = 64**. Confirmed by the vllm-metal 0.33.0 log line on the same checkpoint (`results/server_bench/vllm_metal/serve_excerpt.log`).
- **Thinking cut-off:** the scorer's `reasoning_end_str` is the bare `<channel|>`, so at the budget vLLM forces the end marker immediately, with no wrap-up phrase (vLLM reasoning-outputs docs).
- **vllm-metal** (vLLM 0.33.0 on MLX) runs the scorer's exact flag set on the competition weights, but rejects `thinking_token_budget` (HTTP 400). Gates and throughput: `results/server_bench/vllm_metal/NOTES.md`.
- **Compaction live check (run_19, rich_3468):** inconclusive. Peak prompt was 4,966 tokens, under the 14,336 threshold, so compaction never had cause to fire. Next: rerun with `SWEGEMMA_COMPACTION_THRESHOLD=3000`, for the check only.

## 6. Matching plan (proposed, not built)

1. **GAP 1 compaction:** a small runner in `Tools/` that builds `EvalConfig` with the documented `EventsCompactionConfig` and `ContextCacheConfig` and calls the harness evaluator, used in place of the bare CLI. Test: compaction events appear in the traces of a long task.
2. **GAP 2 thinking budget:** the proxy copies `thinking_token_budget` into oMLX's `thinking_budget`. Gate: a live call with budget 64 stops thinking near 64 tokens, and `v_thinking_budget` shows no overruns. Whether oMLX's cut-off behaves like vLLM's logits processor still needs a Kaggle check.
3. **GAP 3 penalties:** do not rely on penalties to stop loops. Cap planner `max_output_tokens`.
4. **GAP 4 speed:** one gated Kaggle L4 timing run (no submission) to measure E4B tok/s and TTFT under TP=4. Until then, local times are an upper bound on per-task wall time.
5. **GAP 5/6 repos:** stop adding per-repo lanes for fastapi. Use the fresh, unseen-repo dev set (owner decision 2026-11-17) as the generalization check.
6. **GAP 7 12 h math:** 12 h ÷ 120 tasks = 6.0 min per task **gross**, before vLLM start-up and per-task container setup. Measure both on Kaggle before fixing `max_time_minutes`. 5 min is the current value.
7. **Agent structure:** because `submit_patch` only exits after the turn, a LoopAgent must not keep iterating after submit. Restructure so that submit is the last step (run_15/7433).

## 7. Corrections to existing docs

- The claude.ai Project instructions (not the repo files) still carry the gotcha "Scored runs use the subprocess sandbox, which skips test-dependency install (about 35 tasks hit missing `inline_snapshot`…)": staff say scoring uses a **private Docker sandbox** with its own dependencies, on **private repos**. The 27 fastapi `inline_snapshot` tasks are not scored ([STAFF] Markowitz 2026-11-04, Holbrook 2026-09-27).
