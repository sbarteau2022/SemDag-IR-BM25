# Telemetry: run_17_v7_httpx

- Arm: `v7`; submission `AgenticSubmission/v7_brigade_lite` (sha256 `30ec5bf4dea5`); git `d46e6fb730`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 120, "max_tool_calls": 40, "max_time_minutes": 5, "max_turns": 60}`; sampling: `{"audit": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 1024, "thinking_config": {"thinking_budget": 0, "include_thoughts": false}}, "execute": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 1024, "include_thoughts": true}}, "think": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0.3, "frequency_penalty": 0.2, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}}`

**Resolved 0/1** (0.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 329.01 | 329.01 | 329.01 |
| steps | 27 | 27 | 27 |
| agent_steps | 26 | 26 | 26 |
| tool_calls | 24 | 24 | 24 |
| tool_errors | 20 | 20 | 20 |
| prompt_tokens | 174449 | 174449 | 174449 |
| completion_tokens | 16679 | 16679 | 16679 |
| peak_prompt_tokens | 11106 | 11106 | 11106 |
| peak_context_frac | 0.34 | 0.34 | 0.34 |
| thinking_tokens | 13425 | 13425 | 13425 |
| compactions | 0 | 0 | 0 |
| first_edit_s | 73.72 | 73.72 | 73.72 |

## Model calls (proxy)

- Calls: 26; errors: 0; attached to tasks: 26
- TTFT s: p50 0.29, p90 0.49, max 0.80
- Decode tok/s: p50 57.9, p10 56.1
- Finish reasons: {'tool_calls': 25, 'stop': 1}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): 4096
- Thinking tokens per step: p50 600, p90 753, max 893; steps over budget: 0/25

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| run_command |  | 21 | 1 | 20 | 179.39 |
| edit_file |  | 1 | 1 | 0 | 73.72 |
| read_file |  | 1 | 1 | 0 | 59.56 |
| run_skill_script | scripts/meta.py | 1 | 1 | 0 | 14.05 |

## Failure classes

{'timeout': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| httpx_3672 | timeout | 329 | 27 | 24 | 20 | 0.34 | 13425 | 1 | 0 |
