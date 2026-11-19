# Telemetry: run_25

- Arm: `v10_edit_rescue`; submission `AgenticSubmission/v10_edit_rescue` (sha256 `db62f4ed6131`); git `1703270381`
- Sandbox: subprocess; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 300, "max_tool_calls": 40, "max_time_minutes": 4, "max_turns": 60}`; sampling: `{"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 16384, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}`

**Resolved 1/3** (33.3%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 205.84 | 243.24 | 243.24 |
| steps | 14 | 15 | 15 |
| agent_steps | 12 | 12 | 12 |
| tool_calls | 6 | 12 | 12 |
| tool_errors | 0 | 1 | 1 |
| prompt_tokens | 79084 | 137202 | 137202 |
| completion_tokens | 8481 | 8513 | 8513 |
| peak_prompt_tokens | 15543 | 16167 | 16167 |
| peak_context_frac | 0.47 | 0.49 | 0.49 |
| thinking_tokens | 6194 | 7851 | 7851 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 91.45 | 180.64 | 180.64 |

## Model calls (proxy)

- Calls: 30; errors: 0; attached to tasks: 30
- TTFT s: p50 0.32, p90 1.25, max 3.28
- Decode tok/s: p50 47.6, p10 43.2
- Finish reasons: {'tool_calls': 24, 'stop': 6}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 168, p90 1295, max 7447; steps over budget: 1/27

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| read_file |  | 8 | 8 | 0 | 82.06 |
| edit_file |  | 6 | 5 | 1 | 141.74 |
| run_skill_script | scripts/repo_eval.py | 5 | 5 | 0 | 50.42 |
| run_command |  | 3 | 3 | 0 | 135.66 |
| submit_patch |  | 2 | 2 | 0 | 151.08 |

## Failure classes

{'resolved': 1, 'timeout': 1, 'right_function_wrong_fix': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| requests_7315 | resolved | 108 | 15 | 6 | 0 | 0.32 | 4002 | 1 | 0 |
| httpx_3672 | timeout | 243 | 14 | 12 | 1 | 0.47 | 6194 | 0 | 0 |
| rich_3506 | right_function_wrong_fix | 206 | 12 | 6 | 0 | 0.49 | 7851 | 1 | 0 |
