# Telemetry: run_15_v7_requests

- Arm: `v7`; submission `AgenticSubmission/v7_brigade_lite` (sha256 `30ec5bf4dea5`); git `06cbe51378`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 120, "max_tool_calls": 40, "max_time_minutes": 5, "max_turns": 60}`; sampling: `{"audit": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 1024, "thinking_config": {"thinking_budget": 0, "include_thoughts": false}}, "execute": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 1024, "include_thoughts": true}}, "think": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0.3, "frequency_penalty": 0.2, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}}`

**Resolved 1/5** (20.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 303.77 | 331.11 | 331.11 |
| steps | 20 | 36 | 36 |
| agent_steps | 19 | 35 | 35 |
| tool_calls | 17 | 21 | 21 |
| tool_errors | 4 | 6 | 6 |
| prompt_tokens | 85663 | 101131 | 101131 |
| completion_tokens | 15780 | 16347 | 16347 |
| peak_prompt_tokens | 7876 | 9135 | 9135 |
| peak_context_frac | 0.24 | 0.28 | 0.28 |
| thinking_tokens | 13793 | 14954 | 14954 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 149.65 | 173.42 | 173.42 |

## Model calls (proxy)

- Calls: 95; errors: 0; attached to tasks: 95
- TTFT s: p50 0.27, p90 0.68, max 1.58
- Decode tok/s: p50 58.0, p10 55.7
- Finish reasons: {'tool_calls': 81, 'stop': 14}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 509, p90 1709, max 3311; steps over budget: 0/80

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| read_file |  | 28 | 28 | 0 | 131.02 |
| run_command |  | 18 | 8 | 10 | 139.38 |
| edit_file |  | 13 | 5 | 8 | 186.57 |
| run_skill_script | scripts/meta.py | 6 | 6 | 0 | 39.91 |
| submit_patch |  | 5 | 5 | 0 | 171.76 |
| run_skill_script | scripts/audit.py | 4 | 4 | 0 | 149.72 |
| run_skill_script | scripts/fix_edit.py | 4 | 4 | 0 | 234.84 |

## Failure classes

{'timeout': 2, 'right_file_wrong_function': 1, 'right_function_wrong_fix': 1, 'resolved': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| requests_7505 | right_file_wrong_function | 156 | 14 | 7 | 0 | 0.15 | 6134 | 0 | 1 |
| requests_7502 | timeout | 304 | 20 | 17 | 6 | 0.21 | 14281 | 0 | 0 |
| requests_7433 | right_function_wrong_fix | 259 | 36 | 21 | 5 | 0.24 | 9251 | 1 | 0 |
| requests_7427 | resolved | 331 | 21 | 18 | 3 | 0.24 | 13793 | 1 | 0 |
| requests_6644 | timeout | 307 | 18 | 15 | 4 | 0.28 | 14954 | 1 | 0 |
