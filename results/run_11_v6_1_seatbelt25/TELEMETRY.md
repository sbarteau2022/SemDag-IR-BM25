# Telemetry: run_11_v6_1

- Arm: `v6.1`; submission `AgenticSubmission/v6_1_budget` (sha256 `0449d4e1170d`); git `4e51c9835e`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx (mlx_lm.server)`
- Budget: `{"timeout_seconds": 120, "max_tool_calls": 40, "max_time_minutes": 5, "max_turns": 60}`; sampling: `{"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 8192, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}`

**Resolved 1/25** (4.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 217.15 | 330.78 | 332.77 |
| steps | 20 | 41 | 44 |
| agent_steps | 16 | 32 | 38 |
| tool_calls | 12 | 24 | 32 |
| tool_errors | 1 | 5 | 7 |
| prompt_tokens | 128769 | 290426 | 554795 |
| completion_tokens | 7651 | 14700 | 14813 |
| peak_prompt_tokens | 14429 | 25291 | 32401 |
| peak_context_frac | 0.44 | 0.77 | 0.99 |
| thinking_tokens | 6740 | 12167 | 12910 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 100.93 | 264.21 | 289.45 |

## Model calls (proxy)

- Calls: 419; errors: 0; attached to tasks: 419
- TTFT s: p50 0.36, p90 0.78, max 4.67
- Decode tok/s: p50 51.2, p10 47.0
- Finish reasons: {'tool_calls': 374, 'stop': 44, 'length': 1}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 210, p90 1067, max 4610; steps over budget: 1/412

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| read_file |  | 157 | 155 | 2 | 92.48 |
| edit_file |  | 65 | 35 | 30 | 166.98 |
| run_skill_script | scripts/repo_eval.py | 45 | 45 | 0 | 75.38 |
| run_command |  | 35 | 18 | 17 | 140.88 |
| code_editor_agent |  | 24 | 24 | 0 | 126.32 |
| submit_patch |  | 18 | 18 | 0 | 152.94 |
| search_similar_code |  | 10 | 10 | 0 | 93.60 |
| run_skill_script | scripts/test_readiness.py | 5 | 5 | 0 | 149.41 |
| code_analyzer_agent |  | 3 | 3 | 0 | 60.56 |
| get_code_neighbors |  | 1 | 1 | 0 | 109.57 |
| get_status |  | 1 | 1 | 0 | 292.87 |

## Failure classes

{'test_env_broken': 15, 'timeout': 3, 'right_file_wrong_function': 3, 'no_patch': 1, 'wrong_file': 1, 'resolved': 1, 'right_function_wrong_fix': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| fastapi_15023 | test_env_broken | 119 | 14 | 10 | 0 | 0.47 | 2919 | 1 | 0 |
| rich_4079 | no_patch | 163 | 20 | 12 | 2 | 0.46 | 5648 | 1 | 0 |
| fastapi_14349 | test_env_broken | 224 | 26 | 14 | 1 | 0.38 | 7711 | 1 | 0 |
| fastapi_14306 | test_env_broken | 243 | 28 | 20 | 1 | 0.61 | 7148 | 1 | 0 |
| fastapi_14458 | test_env_broken | 309 | 23 | 17 | 3 | 0.71 | 9167 | 0 | 0 |
| fastapi_9753 | test_env_broken | 304 | 33 | 21 | 5 | 0.53 | 12167 | 1 | 0 |
| fastapi_5077 | test_env_broken | 87 | 12 | 8 | 0 | 0.50 | 2989 | 1 | 0 |
| fastapi_9555 | test_env_broken | 308 | 16 | 10 | 0 | 0.44 | 9181 | 0 | 0 |
| fastapi_14361 | test_env_broken | 146 | 16 | 8 | 1 | 0.30 | 3979 | 1 | 0 |
| fastapi_13207 | test_env_broken | 327 | 44 | 32 | 1 | 0.99 | 10807 | 1 | 0 |
| fastapi_14360 | test_env_broken | 302 | 41 | 27 | 3 | 0.61 | 10235 | 1 | 0 |
| fastapi_14419 | test_env_broken | 192 | 18 | 10 | 1 | 0.38 | 4858 | 1 | 0 |
| fastapi_14262 | test_env_broken | 332 | 17 | 9 | 0 | 0.37 | 3215 | 0 | 0 |
| fastapi_9425 | test_env_broken | 88 | 15 | 7 | 0 | 0.25 | 2044 | 1 | 0 |
| rich_3718 | timeout | 330 | 42 | 24 | 4 | 0.33 | 12910 | 1 | 0 |
| rich_3953 | wrong_file | 132 | 17 | 9 | 2 | 0.29 | 3669 | 1 | 0 |
| rich_3942 | right_file_wrong_function | 142 | 24 | 17 | 4 | 0.68 | 3849 | 1 | 0 |
| rich_3905 | resolved | 107 | 17 | 9 | 1 | 0.30 | 2806 | 1 | 0 |
| fastapi_15745 | test_env_broken | 333 | 21 | 15 | 6 | 0.44 | 11032 | 0 | 0 |
| fastapi_14953 | test_env_broken | 37 | 10 | 6 | 0 | 0.28 | 906 | 1 | 0 |
| fastapi_11194 | timeout | 312 | 30 | 24 | 7 | 0.81 | 11531 | 0 | 0 |
| rich_3777 | right_file_wrong_function | 199 | 20 | 14 | 1 | 0.77 | 6740 | 1 | 0 |
| rich_3480 | right_function_wrong_fix | 217 | 16 | 8 | 0 | 0.53 | 6830 | 1 | 0 |
| rich_3470 | right_file_wrong_function | 133 | 18 | 10 | 1 | 0.29 | 4352 | 1 | 0 |
| rich_3469 | timeout | 331 | 33 | 23 | 5 | 0.36 | 12588 | 0 | 0 |
