# Telemetry: run_13_v7_requests

- Arm: `v7`; submission `AgenticSubmission/v7_brigade_lite` (sha256 `804dbb065493`); git `d92b3209e9`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx (mlx_lm.server)`
- Budget: `{"timeout_seconds": 120, "max_tool_calls": 40, "max_time_minutes": 5, "max_turns": 60}`; sampling: `{"audit": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 1024, "thinking_config": {"thinking_budget": 0, "include_thoughts": false}}, "execute": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 1024, "include_thoughts": true}}, "think": {"temperature": 1.0, "top_k": 64, "top_p": 0.95, "presence_penalty": 0.3, "frequency_penalty": 0.2, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 4096, "include_thoughts": true}}}`

**Resolved 0/5** (0.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 4.14 | 11.75 | 11.75 |
| steps | 1 | 1 | 1 |
| agent_steps | 0 | 0 | 0 |
| tool_calls | 0 | 0 | 0 |
| tool_errors | 0 | 0 | 0 |
| prompt_tokens | 0 | 0 | 0 |
| completion_tokens | 0 | 0 | 0 |
| peak_prompt_tokens | 0 | 0 | 0 |
| peak_context_frac | 0.00 | 0.00 | 0.00 |
| thinking_tokens | 0 | 0 | 0 |
| compactions | 0 | 0 | 0 |
| first_edit_s | - | - | - |

## Model calls (proxy)

- Calls: 30; errors: 30; attached to tasks: 30
- TTFT s: p50 -, p90 -, max -
- Decode tok/s: p50 -, p10 -
- Finish reasons: {None: 30}

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|

## Failure classes

{'harness_error': 5}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| requests_7505 | harness_error | 4 | 1 | 0 | 0 | 0.00 | 0 | 0 | 0 |
| requests_7502 | harness_error | 4 | 1 | 0 | 0 | 0.00 | 0 | 0 | 0 |
| requests_7433 | harness_error | 12 | 1 | 0 | 0 | 0.00 | 0 | 0 | 0 |
| requests_7427 | harness_error | 12 | 1 | 0 | 0 | 0.00 | 0 | 0 | 0 |
| requests_6644 | harness_error | 4 | 1 | 0 | 0 | 0.00 | 0 | 0 | 0 |
