# Telemetry: local harness runs → SQLite

Status: **COMPONENT-TESTED** (39 tests in `tests/`) and **LIVE-MEASURED** on run_11 (proxy equivalence gate passed against `mlx_lm.server` 0.32.2, 2026-11-17).

Lightweight by design. During a run, the only extra work is one Python proxy that relays model calls and writes one SQLite row per call. Tokenizing, trace parsing, failure classes, reports and the Docker image all happen **after** the harness exits.

## Pieces

| File | Role | When |
|---|---|---|
| `../seatbelt/no_network.sb` | macOS seatbelt profile: loopback + Unix sockets only | model server, proxy, harness |
| `llm_proxy.py` | Harness → proxy (8125) → `mlx_lm.server` (8124). Asks upstream for a stream, timestamps the first token, returns the normal non-streaming response, logs `llm_calls` | during run |
| `check_proxy_equivalence.py` | Live gate: proxy output == server output for the same greedy request | before trusting a new server |
| `ingest.py` | `task_results.jsonl`, `traces/`, `patches/`, `test_outputs/`, `run_meta.json` → `runs`, `tasks`, `steps`, `tool_calls`; attaches `llm_calls` to tasks | post-run |
| `report.py` | Markdown report (`TELEMETRY.md`) for one run | post-run |
| `export_run.py` | One run's rows to a standalone SQLite + `steps.jsonl` | post-run |
| `bake_image.sh` | Docker image `gemma4-e4b-telemetry:<run-id>` with DB, per-step reasoning, traces, patches, logs | post-run |
| `../run_eval_seatbelt.sh` | Orchestrates all of the above | — |

Store: `results/telemetry.sqlite` (git-ignored via `results/*.sqlite*`).

## What is measured

| Need | Where | Definition |
|---|---|---|
| Token consumption | `steps`, `tasks`, `llm_calls` | prompt / completion / cached tokens per model step, per task, per call |
| Tool calls pass / fail | `tool_calls`, view `v_tool_pass_fail` | `ok` = observation `status != "error"`; shell exit codes kept separately |
| Thinking budget vs use | `steps.thinking_tokens`, view `v_thinking_budget` | thinking text re-tokenized with the model tokenizer vs `thinking_budget` (scorer enforces it; local MLX does not) |
| Reasoning traces per step | `steps.thinking_text`, `tool_name`, `tool_args`, `observation`; `steps.jsonl` in the image | verbatim from the harness trace |
| Context budget | `steps.context_frac`, `tasks.peak_context_frac`, `compactions` | prompt tokens / 32,768 |
| TTFT | `llm_calls.ttft_s`, `t_first_reasoning_s`, `t_first_action_s`, `decode_tok_per_s` | seconds from the proxy receiving the request |
| Steps within a tool call | `tool_calls.nested_steps`, `depth`, `tasks.subagent_steps` | sub-agent steps between an `agent_tool` call and the root agent's next step |
| Steps for the whole task | `tasks.steps`, `agent_steps`, `nudges` | trace steps |
| Failure class | `tasks.failure_class` | first match: resolved, test_env_broken (grader cannot import the code: missing `inline_snapshot`/`dirty_equals`, or the arm64 pydantic-core mismatch), timeout, harness_error, no_patch, destructive_write, unresolved_unclassified (gold unknown), wrong_file, right_file_wrong_function, right_function_wrong_fix, right_file_unresolved (no function match run) |
| Tool-call counts | `tasks.tool_calls` vs `harness_tool_calls` | ours counts every call including the free `submit_patch`/`get_status`; the harness count excludes them |

## Use

```bash
Tools/run_eval_seatbelt.sh AgenticSubmission/v6_1_budget results/run_X ids.txt run_X v6.1
.venv-harness/bin/python Tools/telemetry/report.py --db results/telemetry.sqlite --run-id run_X
sqlite3 results/telemetry.sqlite "select * from v_tool_pass_fail where run_id='run_X'"
docker run --rm gemma4-e4b-telemetry:run-X sqlite3 telemetry.sqlite "select failure_class, count(*) from tasks group by 1"
```

## Limits

- Local stand-in only: MLX on Apple silicon, not the scorer's L4/vLLM. TTFT and tok/s describe this Mac.
- `thinking_budget` is not enforced locally, and local `swegemma eval` does not configure the scorer's events compaction (14,336 tokens), so `compactions` is 0 locally. Both are reported, not reproduced.
- `reasoning_chunks` approximates reasoning tokens (mlx_lm streams about one chunk per token); `thinking_tokens` from the tokenizer is the reference.
- Proxy rows are joined to tasks by wall clock, which holds because local runs use concurrency 1.
- HyperDX is not wired. SQLite stays the authoritative local record; an exporter can be added once needed.
