# Telemetry: run_28_v11_smoke

- Arm: `v11_task_ir`; submission `AgenticSubmission/v11_task_ir` (sha256 `72a64272928a`); git `5ac089c154`
- Sandbox: subprocess; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 300, "max_tool_calls": 40, "max_time_minutes": 4, "max_turns": 60}`; sampling: `{"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 16384, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}`

**Resolved 1/3** (33.3%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 86.71 | 142.15 | 142.15 |
| steps | 11 | 14 | 14 |
| agent_steps | 9 | 12 | 12 |
| tool_calls | 7 | 10 | 10 |
| tool_errors | 0 | 0 | 0 |
| prompt_tokens | 48382 | 96039 | 96039 |
| completion_tokens | 4046 | 6678 | 6678 |
| peak_prompt_tokens | 8096 | 12307 | 12307 |
| peak_context_frac | 0.25 | 0.38 | 0.38 |
| thinking_tokens | 3649 | 5808 | 5808 |
| compactions | 0 | 0 | 0 |
| first_edit_s | - | - | - |

## Model calls (proxy)

- Calls: 25; errors: 0; attached to tasks: 25
- TTFT s: p50 0.16, p90 0.82, max 3.19
- Decode tok/s: p50 50.2, p10 47.1
- Finish reasons: {'tool_calls': 22, 'stop': 3}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 116, p90 2266, max 2385; steps over budget: 0/25

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| run_skill_script | scripts/fix_edit.py | 9 | 9 | 0 | 63.16 |
| run_skill_script | scripts/repo_eval.py | 6 | 6 | 0 | 55.91 |
| run_command |  | 3 | 3 | 0 | 89.31 |
| submit_patch |  | 3 | 3 | 0 | 92.20 |
| run_skill_script |  | 1 | 1 | 0 | 57.62 |

## Failure classes

{'right_function_wrong_fix': 2, 'resolved': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| requests_7315 | resolved | 87 | 11 | 7 | 0 | 0.25 | 3649 | 1 | 0 |
| httpx_3672 | right_function_wrong_fix | 142 | 14 | 10 | 0 | 0.38 | 5808 | 1 | 0 |
| rich_3506 | right_function_wrong_fix | 64 | 9 | 5 | 0 | 0.23 | 2569 | 1 | 0 |
