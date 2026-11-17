# Telemetry: run_14_v7_requests

- Arm: `v7`; submission `AgenticSubmission/v7_brigade_lite` (sha256 `30ec5bf4dea5`); git `a3fbfd112c`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx (mlx_lm.server)`
- Budget: `{"timeout_seconds": 120, "max_tool_calls": 40, "max_time_minutes": 5, "max_turns": 60}`; sampling: `{"audit": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 1024, "thinking_config": {"thinking_budget": 0, "include_thoughts": false}}, "execute": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 1024, "include_thoughts": true}}, "think": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0.3, "frequency_penalty": 0.2, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}}`

**Resolved 0/5** (0.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 11.55 | 233.83 | 233.83 |
| steps | 0 | 30 | 30 |
| agent_steps | 0 | 29 | 29 |
| tool_calls | 0 | 17 | 17 |
| tool_errors | 0 | 4 | 4 |
| prompt_tokens | 0 | 71027 | 71027 |
| completion_tokens | 0 | 11247 | 11247 |
| peak_prompt_tokens | 0 | 5535 | 5535 |
| peak_context_frac | 0.00 | 0.17 | 0.17 |
| thinking_tokens | 0 | 7567 | 7567 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 66.94 | 112.55 | 112.55 |

## Model calls (proxy)

- Calls: 45; errors: 0; attached to tasks: 45
- TTFT s: p50 0.26, p90 0.70, max 1.23
- Decode tok/s: p50 55.0, p10 51.8
- Finish reasons: {'tool_calls': 33, 'stop': 12}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 244, p90 595, max 3122; steps over budget: 0/33

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| read_file |  | 9 | 9 | 0 | 99.45 |
| run_command |  | 7 | 2 | 5 | 117.71 |
| edit_file |  | 4 | 2 | 2 | 127.30 |
| run_skill_script | scripts/audit.py | 4 | 4 | 0 | 128.22 |
| run_skill_script | scripts/meta.py | 3 | 3 | 0 | 37.28 |
| submit_patch |  | 3 | 3 | 0 | 173.29 |
| load_skill |  | 1 | 1 | 0 | 75.69 |
| run_skill_script | scripts/fix_edit.py | 1 | 1 | 0 | 195.29 |

## Failure classes

{'harness_error': 3, 'right_function_wrong_fix': 2}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| requests_6644 | harness_error | 4 | 0 | 0 | 0 | 0.00 | 0 | 0 | 0 |
| requests_7427 | harness_error | 11 | 0 | 0 | 0 | 0.00 | 0 | 0 | 0 |
| requests_7433 | harness_error | 12 | 0 | 0 | 0 | 0.00 | 0 | 0 | 0 |
| requests_7505 | right_function_wrong_fix | 234 | 27 | 15 | 3 | 0.17 | 7567 | 1 | 0 |
| requests_7502 | right_function_wrong_fix | 170 | 30 | 17 | 4 | 0.16 | 5413 | 1 | 1 |
