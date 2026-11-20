# Telemetry: run_26_v11_smoke

- Arm: `v11_task_ir`; submission `AgenticSubmission/v11_task_ir` (sha256 `1593cc3da7ca`); git `5ac089c154`
- Sandbox: subprocess; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 300, "max_tool_calls": 40, "max_time_minutes": 4, "max_turns": 60}`; sampling: `{"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 16384, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}`

**Resolved 1/3** (33.3%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 130.02 | 167.90 | 167.90 |
| steps | 15 | 17 | 17 |
| agent_steps | 13 | 15 | 15 |
| tool_calls | 11 | 13 | 13 |
| tool_errors | 1 | 2 | 2 |
| prompt_tokens | 86628 | 125178 | 125178 |
| completion_tokens | 6151 | 8122 | 8122 |
| peak_prompt_tokens | 11170 | 12685 | 12685 |
| peak_context_frac | 0.34 | 0.39 | 0.39 |
| thinking_tokens | 5496 | 6930 | 6930 |
| compactions | 0 | 0 | 0 |
| first_edit_s | - | - | - |

## Model calls (proxy)

- Calls: 36; errors: 0; attached to tasks: 36
- TTFT s: p50 0.13, p90 0.20, max 1.47
- Decode tok/s: p50 49.4, p10 46.4
- Finish reasons: {'tool_calls': 33, 'stop': 3}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 195, p90 1908, max 3469; steps over budget: 0/36

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| run_skill_script | scripts/fix_edit.py | 12 | 12 | 0 | 97.16 |
| run_skill_script | scripts/repo_eval.py | 8 | 8 | 0 | 79.44 |
| read_file |  | 4 | 4 | 0 | 18.98 |
| run_command |  | 4 | 0 | 4 | 120.84 |
| submit_patch |  | 3 | 3 | 0 | 134.39 |
| run_skill_script |  | 2 | 2 | 0 | 95.46 |

## Failure classes

{'no_patch': 2, 'resolved': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| requests_7315 | resolved | 124 | 15 | 11 | 1 | 0.31 | 5285 | 0 | 1 |
| httpx_3672 | no_patch | 168 | 17 | 13 | 1 | 0.39 | 6930 | 0 | 0 |
| rich_3506 | no_patch | 130 | 13 | 9 | 2 | 0.34 | 5496 | 0 | 0 |
