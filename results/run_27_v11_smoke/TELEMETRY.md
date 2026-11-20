# Telemetry: run_27_v11_smoke

- Arm: `v11_task_ir`; submission `AgenticSubmission/v11_task_ir` (sha256 `4aa59d60e07c`); git `5ac089c154`
- Sandbox: subprocess; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 300, "max_tool_calls": 40, "max_time_minutes": 4, "max_turns": 60}`; sampling: `{"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 16384, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}`

**Resolved 1/3** (33.3%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 150.80 | 191.13 | 191.13 |
| steps | 14 | 15 | 15 |
| agent_steps | 12 | 13 | 13 |
| tool_calls | 10 | 11 | 11 |
| tool_errors | 0 | 0 | 0 |
| prompt_tokens | 92121 | 100426 | 100426 |
| completion_tokens | 6788 | 8786 | 8786 |
| peak_prompt_tokens | 11920 | 13521 | 13521 |
| peak_context_frac | 0.36 | 0.41 | 0.41 |
| thinking_tokens | 5990 | 7664 | 7664 |
| compactions | 0 | 0 | 0 |
| first_edit_s | - | - | - |

## Model calls (proxy)

- Calls: 32; errors: 0; attached to tasks: 32
- TTFT s: p50 0.15, p90 0.61, max 2.30
- Decode tok/s: p50 49.0, p10 43.5
- Finish reasons: {'tool_calls': 29, 'stop': 3}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 207, p90 1898, max 3666; steps over budget: 0/32

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| run_skill_script | scripts/repo_eval.py | 10 | 10 | 0 | 48.44 |
| read_file |  | 6 | 6 | 0 | 55.00 |
| run_skill_script | scripts/fix_edit.py | 6 | 6 | 0 | 102.69 |
| run_skill_script | src/httpx/_parsers.py | 3 | 3 | 0 | 138.98 |
| submit_patch |  | 3 | 3 | 0 | 139.78 |
| run_command |  | 1 | 1 | 0 | 88.86 |

## Failure classes

{'no_patch': 2, 'resolved': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| requests_7315 | resolved | 99 | 12 | 8 | 0 | 0.29 | 4155 | 1 | 0 |
| httpx_3672 | no_patch | 191 | 14 | 10 | 0 | 0.41 | 7664 | 0 | 0 |
| rich_3506 | no_patch | 151 | 15 | 11 | 0 | 0.36 | 5990 | 0 | 0 |
