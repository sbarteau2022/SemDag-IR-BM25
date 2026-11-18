# Telemetry: run_24

- Arm: `v9_recurrent`; submission `AgenticSubmission/v9_recurrent` (sha256 `6c567f6289c0`); git `9e18b90ee5`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 300, "max_tool_calls": 40, "max_time_minutes": 4, "max_turns": 60}`; sampling: `{"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 16384, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}`

**Resolved 0/2** (0.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 244.23 | 245.13 | 245.13 |
| steps | 17 | 27 | 27 |
| agent_steps | 15 | 23 | 23 |
| tool_calls | 15 | 21 | 21 |
| tool_errors | 3 | 4 | 4 |
| prompt_tokens | 134981 | 193786 | 193786 |
| completion_tokens | 8500 | 8888 | 8888 |
| peak_prompt_tokens | 14394 | 15595 | 15595 |
| peak_context_frac | 0.44 | 0.48 | 0.48 |
| thinking_tokens | 7370 | 7732 | 7732 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 78.12 | 115.56 | 115.56 |

## Model calls (proxy)

- Calls: 47; errors: 0; attached to tasks: 40
- TTFT s: p50 0.41, p90 0.91, max 2.84
- Decode tok/s: p50 46.2, p10 42.5
- Finish reasons: {'tool_calls': 44, 'stop': 3}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 247, p90 650, max 2450; steps over budget: 0/37

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| read_file |  | 18 | 18 | 0 | 105.31 |
| edit_file |  | 9 | 3 | 6 | 161.96 |
| run_command |  | 4 | 3 | 1 | 124.76 |
| run_skill_script | scripts/repo_eval.py | 3 | 3 | 0 | 31.37 |
| code_editor_agent |  | 2 | 2 | 0 | 171.66 |

## Failure classes

{'timeout': 2}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| rich_3486 | timeout | 245 | 27 | 21 | 3 | 0.48 | 7370 | 0 | 0 |
| rich_3506 | timeout | 244 | 17 | 15 | 4 | 0.44 | 7732 | 1 | 0 |
