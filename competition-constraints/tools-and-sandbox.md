# Tools, Budgets, Sandbox and Grading

Tags: see [README.md](README.md). [HR §n] quotes are verbatim from HARNESS_README.md.

## 1. Allowed tools

- [OV] "only the harness tools and custom subagents defined with `agent_tool`."
- [HR §5.3] Hallucinated or undeclared tool calls come back as `{"status": "error", ...}` and do not crash the task.

| # | Tool | Counts toward `max_tool_calls`? | Key behavior |
|---|---|---|---|
| 1 | `run_command(command)` | Yes | `/bin/bash -c` in `/workspace`. Timeout `min(300s, remaining time)`. A timeout does not end the session. stdout/stderr truncated to 5,000 chars. |
| 2 | `submit_patch()` | **No** | `git add -N .` then `git diff --binary _swegemma_baseline \|\| git diff --binary HEAD`. **Ends the agent loop once the turn finishes.** |
| 3 | `get_status()` | **No** | Reports tool calls used/remaining, time remaining, patch status. |
| 4 | `read_file(filepath, start_line?, end_line?)` | Yes | Max **150 lines** and **10,000 chars** per call. |
| 5 | `edit_file(filepath, old_string, new_string, allow_multiple=False)` | Yes | 3-tier match (exact → whitespace-flexible → regex). Errors if the match is not unique, the file is missing or empty, or `old_string` is empty. |
| 6 | `write_file(filepath, content)` | Yes | Creates parent dirs. |
| 7 | `get_code_neighbors(node, edge_type?, max_neighbors=50)` | Yes | Output capped at 5,000 chars. |
| 8 | `search_similar_code(query, k=10)` | Yes | **Offline: pass a symbol name** (e.g. `Class.method`), not free text. Free text falls back to lexical overlap. |
| 9 | `get_code_subgraph(nodes)` | Yes | Output capped at 5,000 chars. |

Skill tools: `load_skill`, `load_skill_resource`, `run_skill_script`. [HR §5.3; OV]

Paths: a leading `/` or `/workspace/` is stripped, and `..` raises `ValidationError`. [HR §6.2]
Budget warning: once ≤ 10 calls remain (when the budget is ≥ 20), every response carries a `budget_warning`. [HR §6]

## 2. Time limits

- **Whole run:** [OV, Issue Scoring] "You have 12 hours to submit patches for all tasks, including sandbox setup time but excluding validation. You may set per-task time limits in `eval_config.yaml`."
- **Hidden test set:** "About 120 tasks". [DD] That averages about 6 minutes per task, all-in.
- **Per-task agent clock:** [HR §7.1] "Your `time_minutes` budget measures strictly the time spent inside the agent loop". Container setup is excluded from the per-task clock, but it still counts toward the 12 hours.

## 3. `eval_config.yaml` budgets [HR §7.1]

```yaml
evaluation:
  timeout_seconds:   # per-command timeout (default 300)
  max_tool_calls:    # default 100 in inference.py; 10 in sample
  max_time_minutes:  # default 60; 1 in sample
  max_turns:         # default 500; 50 in sample
```

| Budget | Scorer default if omitted | Sample submission value |
|---|---|---|
| Wall clock per task | 60 min | **1 min** |
| Tool calls per task | 100 | **10** |
| Turns | 500 | 50 |
| Command timeout | 300 s | 60 s (dataset copy) |
| Phase 2 pytest timeout | 300 s, fixed | n/a |

**Official (forum, Ryan Holbrook):**
- The scorer runs tasks **sequentially**.
- The scorer reads only these four fields, and "The default is no limit."
- Going over 12 hours **errors the whole submission**.

With about 120 tasks, keep **`max_time_minutes` ≤ 5** and set all four fields explicitly. See the budget arithmetic in open-questions.md. Background processes inside a task (`cmd &`) aren't ruled on. They share 2 vCPUs and 4 GiB of RAM.

Note: the base folder has two copies. `DataSets/public/eval_config.yaml` is 60/10/1/50. `DataSets/public/data/sample_submission/eval_config.yaml` is 300/60/30/500 (likely edited locally).

## 4. Sandbox [HR §3.1, §4.1, §5.2]

- Docker image `swebench-sandbox:latest`, **`network_mode="none"`**. No pip installs, no downloads.
- **4 GiB RAM** (exit 137 if exceeded) and **2 vCPUs** per container.
- Python 3.13. Wheels at `/wheels`. [DD]
- Inference: vLLM on 4× L4 (96 GB), `tensor_parallel_size=4`, `max_model_len=32768`, `tool_call_parser=gemma4`, `reasoning_parser=gemma4`.
- Context compaction kicks in at 14,336 tokens (`compaction_interval=15`, `event_retention_size=5`). [HR §7.2]
- Git history after `base_commit` does not exist in `.git`. [HR §4.2]
- Nudges: up to 3 consecutive turns without a tool call get a "continue" nudge. After that the loop ends. [HR §5.3]

## 5. Patch extraction [HR §8.1]

- `git add -N .` means **new untracked files in `/workspace` are included**. Only these are ignored: `__pycache__/ *.pyc .pytest_cache/ *.egg-info/ build/ dist/ .coverage`.
- **Stripped from the patch, always:** "protected test files (`test_*.py`, `*_test.py`, or `.py` files under `tests/`, `test/`, `testing/`) or runner configuration files (`conftest.py`, `pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg`, `.pytest.ini`, `sitecustomize.py`, `usercustomize.py`, `_swegemma_stubs.py`, `*.pth`)".
- **If `submit_patch()` is never called**, the harness extracts the diff automatically on finish, timeout or budget exhaustion, and still grades it.
- Do not modify the harness-written `/workspace/pytest.ini` or `/workspace/conftest.py`. [HR §4.2]

## 6. Grading [HR §8.2]

- Fresh Container B. The patch is applied with 4 fallback passes. If all fail, `resolved = False`.
- Test and config files are reset, `test_patch` is applied, then hermetic `pytest` runs.
- `resolved = True` only if pytest exits 0 **and** JUnit XML shows `passed_tests > 0`, `failures == 0`, `errors == 0`, and every required test passed without being skipped.
- Score = resolved tasks / total tasks. Public/private split is 50/50. [DD]

## 7. Gotchas [HR §10]

1. Keep `edit_file`/`write_file` payloads small, or the `<|tool_call>` gets cut off at `max_output_tokens`.
2. Put repro scripts in `/tmp`, not `/workspace`.
3. Wrap exploration in an `agent_tool` sub-agent with `skip_summarization: true` to save root context.
4. Call `submit_patch()` last. It is free but ends the loop.
