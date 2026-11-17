# Telemetry: run_16_v7_rich

- Arm: `v7`; submission `AgenticSubmission/v7_brigade_lite` (sha256 `30ec5bf4dea5`); git `ec74673bdb`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 120, "max_tool_calls": 40, "max_time_minutes": 5, "max_turns": 60}`; sampling: `{"audit": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 1024, "thinking_config": {"thinking_budget": 0, "include_thoughts": false}}, "execute": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 1024, "include_thoughts": true}}, "think": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0.3, "frequency_penalty": 0.2, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}}`

**Resolved 1/5** (20.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 330.65 | 330.93 | 330.93 |
| steps | 27 | 39 | 39 |
| agent_steps | 26 | 38 | 38 |
| tool_calls | 18 | 36 | 36 |
| tool_errors | 5 | 33 | 33 |
| prompt_tokens | 83902 | 458339 | 458339 |
| completion_tokens | 14417 | 16309 | 16309 |
| peak_prompt_tokens | 9509 | 20137 | 20137 |
| peak_context_frac | 0.29 | 0.61 | 0.61 |
| thinking_tokens | 11706 | 14436 | 14436 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 102.98 | 106.49 | 106.49 |

## Model calls (proxy)

- Calls: 114; errors: 0; attached to tasks: 114
- TTFT s: p50 0.39, p90 0.77, max 19.66
- Decode tok/s: p50 57.3, p10 52.5
- Finish reasons: {'tool_calls': 95, 'stop': 16, 'length': 3}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 312, p90 933, max 4093; steps over budget: 0/101

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| run_command |  | 53 | 4 | 49 | 161.57 |
| read_file |  | 20 | 18 | 2 | 141.11 |
| edit_file |  | 8 | 8 | 0 | 147.12 |
| run_skill_script | scripts/meta.py | 6 | 6 | 0 | 48.33 |
| run_skill_script | scripts/audit.py | 3 | 3 | 0 | 174.55 |
| get_status |  | 1 | 1 | 0 | 199.46 |
| submit_patch |  | 1 | 1 | 0 | 212.33 |

## Failure classes

{'timeout': 3, 'resolved': 1, 'right_file_wrong_function': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| rich_3180 | timeout | 331 | 27 | 20 | 13 | 0.19 | 14436 | 0 | 0 |
| rich_3468 | resolved | 331 | 39 | 36 | 33 | 0.61 | 12706 | 1 | 0 |
| rich_3296 | right_file_wrong_function | 290 | 28 | 16 | 0 | 0.15 | 10865 | 0 | 0 |
| rich_3052 | timeout | 331 | 26 | 18 | 5 | 0.33 | 11706 | 0 | 0 |
| rich_3043 | timeout | 312 | 7 | 2 | 0 | 0.29 | 4880 | 0 | 0 |
