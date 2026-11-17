# Telemetry: run_12_v5_loop

- Arm: `v5-loop-e4b`; submission `AgenticSubmission/v5_loop_e4b` (sha256 `ed91425e43cd`); git `1c41e51577`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx (mlx_lm.server)`
- Budget: `{"timeout_seconds": 300, "max_tool_calls": 60, "max_time_minutes": 30, "max_turns": 500}`; sampling: `{"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 16384, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}`

**Resolved 3/10** (30.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 154.10 | 779.11 | 1081.35 |
| steps | 15 | 172 | 222 |
| agent_steps | 14 | 162 | 209 |
| tool_calls | 10 | 47 | 50 |
| tool_errors | 2 | 12 | 13 |
| prompt_tokens | 88975 | 2228338 | 5558237 |
| completion_tokens | 5926 | 31806 | 43754 |
| peak_prompt_tokens | 12540 | 49791 | 51448 |
| peak_context_frac | 0.38 | 1.52 | 1.57 |
| thinking_tokens | 5477 | 23114 | 27839 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 59.29 | 99.04 | 117.33 |

## Model calls (proxy)

- Calls: 506; errors: 0; attached to tasks: 503
- TTFT s: p50 0.28, p90 1.01, max 6.35
- Decode tok/s: p50 45.7, p10 39.2
- Finish reasons: {'stop': 281, 'tool_calls': 225}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 188, p90 534, max 4788; steps over budget: 1/391

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| run_command |  | 64 | 44 | 20 | 325.80 |
| run_skill_script | scripts/repo_eval.py | 57 | 57 | 0 | 305.33 |
| edit_file |  | 47 | 36 | 11 | 300.61 |
| read_file |  | 37 | 36 | 1 | 138.48 |
| submit_patch |  | 16 | 7 | 9 | 256.01 |

## Failure classes

{'right_function_wrong_fix': 4, 'resolved': 3, 'wrong_file': 2, 'right_file_wrong_function': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| requests_7502 | right_function_wrong_fix | 79 | 11 | 6 | 1 | 0.31 | 2202 | 1 | 0 |
| requests_7427 | resolved | 109 | 11 | 6 | 0 | 0.28 | 3365 | 1 | 0 |
| requests_7328 | right_file_wrong_function | 779 | 146 | 29 | 6 | 0.79 | 23114 | 1 | 0 |
| requests_7309 | resolved | 1081 | 222 | 47 | 12 | 1.52 | 27839 | 1 | 0 |
| requests_7205 | right_function_wrong_fix | 646 | 82 | 50 | 13 | 1.57 | 16521 | 1 | 0 |
| httpx_3672 | right_function_wrong_fix | 370 | 48 | 27 | 0 | 0.80 | 11382 | 1 | 0 |
| requests_6757 | wrong_file | 98 | 15 | 10 | 2 | 0.34 | 2656 | 0 | 0 |
| requests_6644 | wrong_file | 711 | 172 | 31 | 4 | 0.88 | 19670 | 1 | 0 |
| rich_3180 | right_function_wrong_fix | 154 | 12 | 7 | 2 | 0.38 | 5477 | 1 | 0 |
| rich_3468 | resolved | 131 | 13 | 8 | 1 | 0.34 | 4165 | 1 | 0 |
