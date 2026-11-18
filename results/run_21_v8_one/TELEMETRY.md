# Telemetry: run_21_v8_one

- Arm: `v8`; submission `AgenticSubmission/v8_ensemble` (sha256 `64a5da0b54fe`); git `4a4b02f9cc`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 300, "max_tool_calls": 100, "max_time_minutes": 4, "max_turns": 500}`; sampling: `{"adversary": {"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 0, "include_thoughts": true}}, "coordinator": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 0, "include_thoughts": true}}, "final": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 0, "include_thoughts": true}}, "implement": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0.3, "frequency_penalty": 0.2, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 0, "include_thoughts": true}}}`

**Resolved 0/1** (0.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 241.80 | 241.80 | 241.80 |
| steps | 26 | 26 | 26 |
| agent_steps | 24 | 24 | 24 |
| tool_calls | 22 | 22 | 22 |
| tool_errors | 0 | 0 | 0 |
| prompt_tokens | 113366 | 113366 | 113366 |
| completion_tokens | 11537 | 11537 | 11537 |
| peak_prompt_tokens | 10498 | 10498 | 10498 |
| peak_context_frac | 0.32 | 0.32 | 0.32 |
| thinking_tokens | 10672 | 10672 | 10672 |
| compactions | 0 | 0 | 0 |
| first_edit_s | - | - | - |

## Model calls (proxy)

- Calls: 23; errors: 0; attached to tasks: 23
- TTFT s: p50 0.41, p90 3.22, max 3.35
- Decode tok/s: p50 20.8, p10 17.8
- Finish reasons: {'tool_calls': 22, 'stop': 1}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): None
- Thinking tokens per step: p50 172, p90 1272, max 1981; steps over budget: 0/23

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| run_skill_script | scripts/fork.py | 8 | 8 | 0 | 21.64 |
| read_file |  | 6 | 6 | 0 | 110.13 |
| run_command |  | 5 | 5 | 0 | 142.17 |
| run_skill_script | "scripts/fork.py" | 2 | 2 | 0 | 21.67 |
| list_skills |  | 1 | 1 | 0 | 21.75 |

## Failure classes

{'timeout': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| rich_3468 | timeout | 242 | 26 | 22 | 0 | 0.32 | 10672 | 0 | 0 |
