# Telemetry: run_19_parity_gate

- Arm: `v7`; submission `AgenticSubmission/v7_brigade_lite` (sha256 `30ec5bf4dea5`); git `36c5705095`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 120, "max_tool_calls": 40, "max_time_minutes": 5, "max_turns": 60}`; sampling: `{"audit": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 1024, "thinking_config": {"thinking_budget": 0, "include_thoughts": false}}, "execute": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 1024, "include_thoughts": true}}, "think": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0.3, "frequency_penalty": 0.2, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}}`

**Resolved 1/1** (100.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 330.84 | 330.84 | 330.84 |
| steps | 35 | 35 | 35 |
| agent_steps | 34 | 34 | 34 |
| tool_calls | 22 | 22 | 22 |
| tool_errors | 8 | 8 | 8 |
| prompt_tokens | 83085 | 83085 | 83085 |
| completion_tokens | 14489 | 14489 | 14489 |
| peak_prompt_tokens | 4966 | 4966 | 4966 |
| peak_context_frac | 0.15 | 0.15 | 0.15 |
| thinking_tokens | 11908 | 11908 | 11908 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 66.95 | 66.95 | 66.95 |

## Model calls (proxy)

- Calls: 29; errors: 0; attached to tasks: 29
- TTFT s: p50 0.31, p90 0.81, max 6.61
- Decode tok/s: p50 58.8, p10 58.1
- Finish reasons: {'tool_calls': 22, 'stop': 7}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 355, p90 1023, max 1306; steps over budget: 0/22

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| edit_file |  | 6 | 2 | 4 | 156.30 |
| read_file |  | 4 | 4 | 0 | 161.16 |
| run_command |  | 4 | 0 | 4 | 121.82 |
| run_skill_script | scripts/audit.py | 2 | 2 | 0 | 164.76 |
| run_skill_script | scripts/meta.py | 2 | 2 | 0 | 58.11 |
| list_skills |  | 1 | 1 | 0 | 87.64 |
| load_skill |  | 1 | 1 | 0 | 77.26 |
| run_skill_script | scripts/run_tests.sh | 1 | 1 | 0 | 264.99 |
| submit_patch |  | 1 | 1 | 0 | 253.64 |

## Failure classes

{'resolved': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| rich_3468 | resolved | 331 | 35 | 22 | 8 | 0.15 | 11908 | 1 | 0 |
