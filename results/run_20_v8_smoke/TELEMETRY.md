# Telemetry: run_20_v8_smoke

- Arm: `v8`; submission `AgenticSubmission/v8_ensemble` (sha256 `513496c128f6`); git `644110ac77`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 300, "max_tool_calls": 100, "max_time_minutes": 4, "max_turns": 500}`; sampling: `{"adversary": {"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 3072, "include_thoughts": true}}, "coordinator": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}, "final": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}, "implement": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0.3, "frequency_penalty": 0.2, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 3072, "include_thoughts": true}}}`

**Resolved 0/5** (0.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 243.51 | 243.86 | 243.86 |
| steps | 43 | 48 | 48 |
| agent_steps | 41 | 47 | 47 |
| tool_calls | 37 | 47 | 47 |
| tool_errors | 9 | 22 | 22 |
| prompt_tokens | 201466 | 305045 | 305045 |
| completion_tokens | 28926 | 33179 | 33179 |
| peak_prompt_tokens | 9962 | 15718 | 15718 |
| peak_context_frac | 0.30 | 0.48 | 0.48 |
| thinking_tokens | 23494 | 28202 | 28202 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 85.48 | 137.79 | 137.79 |

## Model calls (proxy)

- Calls: 200; errors: 0; attached to tasks: 200
- TTFT s: p50 0.51, p90 4.76, max 13.76
- Decode tok/s: p50 38.0, p10 32.9
- Finish reasons: {'tool_calls': 196, 'stop': 4}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 369, p90 1891, max 3071; steps over budget: 0/187

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| read_file |  | 52 | 50 | 2 | 89.90 |
| edit_file |  | 49 | 16 | 33 | 157.18 |
| run_command |  | 38 | 20 | 18 | 91.82 |
| run_skill_script | scripts/fork.py | 22 | 22 | 0 | 22.52 |
| run_skill_script |  | 8 | 8 | 0 | 180.68 |
| run_skill_script | scripts/audit.py | 7 | 7 | 0 | 152.47 |
| run_skill_script | scripts/semdag.py | 5 | 5 | 0 | 13.02 |
| list_skills |  | 2 | 2 | 0 | 23.55 |
| run_skill_script | 'scripts/semdag' | 1 | 1 | 0 | 6.76 |

## Failure classes

{'timeout': 4, 'harness_error': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| rich_3180 | timeout | 243 | 43 | 33 | 12 | 0.30 | 28202 | 0 | 1 |
| rich_3468 | timeout | 244 | 47 | 38 | 6 | 0.30 | 22830 | 1 | 1 |
| rich_3296 | harness_error | 227 | 36 | 29 | 9 | 0.48 | 23050 | 1 | 1 |
| rich_3052 | timeout | 244 | 48 | 47 | 22 | 0.31 | 23494 | 0 | 1 |
| rich_3043 | timeout | 244 | 42 | 37 | 4 | 0.30 | 27433 | 0 | 1 |
