# Telemetry: run_18_fastapi_envcheck

- Arm: `v7`; submission `AgenticSubmission/v7_brigade_lite` (sha256 `30ec5bf4dea5`); git `9827973ec6`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 120, "max_tool_calls": 40, "max_time_minutes": 5, "max_turns": 60}`; sampling: `{"audit": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 1024, "thinking_config": {"thinking_budget": 0, "include_thoughts": false}}, "execute": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 1024, "include_thoughts": true}}, "think": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0.3, "frequency_penalty": 0.2, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}}`

**Resolved 0/1** (0.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 323.34 | 323.34 | 323.34 |
| steps | 34 | 34 | 34 |
| agent_steps | 33 | 33 | 33 |
| tool_calls | 24 | 24 | 24 |
| tool_errors | 12 | 12 | 12 |
| prompt_tokens | 169273 | 169273 | 169273 |
| completion_tokens | 15912 | 15912 | 15912 |
| peak_prompt_tokens | 18895 | 18895 | 18895 |
| peak_context_frac | 0.58 | 0.58 | 0.58 |
| thinking_tokens | 12073 | 12073 | 12073 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 141.86 | 141.86 | 141.86 |

## Model calls (proxy)

- Calls: 28; errors: 0; attached to tasks: 28
- TTFT s: p50 0.49, p90 0.77, max 3.61
- Decode tok/s: p50 59.5, p10 54.9
- Finish reasons: {'tool_calls': 24, 'stop': 4}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 409, p90 823, max 2220; steps over budget: 0/21

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| run_command |  | 12 | 0 | 12 | 148.15 |
| read_file |  | 4 | 4 | 0 | 157.29 |
| run_skill_script | scripts/audit.py | 2 | 2 | 0 | 241.43 |
| run_skill_script | scripts/install_dependencies.sh | 2 | 2 | 0 | 234.43 |
| submit_patch |  | 2 | 2 | 0 | 247.07 |
| edit_file |  | 1 | 1 | 0 | 141.86 |
| run_skill_script | scripts/meta.py | 1 | 1 | 0 | 15.12 |

## Failure classes

{'right_function_wrong_fix': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| fastapi_11194 | right_function_wrong_fix | 323 | 34 | 24 | 12 | 0.58 | 12073 | 1 | 1 |
