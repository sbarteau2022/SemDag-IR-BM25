# Telemetry: run_22_v8_lead

- Arm: `v8`; submission `AgenticSubmission/v8_ensemble` (sha256 `cfb6b87d1142`); git `f1d2baf4af`
- Sandbox: docker; seatbelt (no network): True; model: `gemma-4-e4b-it-qat-w4a16-mlx`
- Budget: `{"timeout_seconds": 300, "max_tool_calls": 100, "max_time_minutes": 4, "max_turns": 500}`; sampling: `{"adversary": {"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 0, "include_thoughts": true}}, "final": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 0, "include_thoughts": true}}, "implement": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0.3, "frequency_penalty": 0.2, "max_output_tokens": 4096, "thinking_config": {"thinking_budget": 0, "include_thoughts": true}}, "lead": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 6144, "thinking_config": {"thinking_budget": 0, "include_thoughts": true}}}`

**Resolved 0/1** (0.0%)

## Per-task distribution (median / p90 / max)

| metric | median | p90 | max |
|---|---|---|---|
| duration_s | 241.72 | 241.72 | 241.72 |
| steps | 48 | 48 | 48 |
| agent_steps | 47 | 47 | 47 |
| tool_calls | 32 | 32 | 32 |
| tool_errors | 2 | 2 | 2 |
| prompt_tokens | 254238 | 254238 | 254238 |
| completion_tokens | 25789 | 25789 | 25789 |
| peak_prompt_tokens | 12711 | 12711 | 12711 |
| peak_context_frac | 0.39 | 0.39 | 0.39 |
| thinking_tokens | 20370 | 20370 | 20370 |
| compactions | 0 | 0 | 0 |
| first_edit_s | - | - | - |

## Model calls (proxy)

- Calls: 36; errors: 0; attached to tasks: 36
- TTFT s: p50 0.71, p90 5.21, max 7.66
- Decode tok/s: p50 40.9, p10 36.6
- Finish reasons: {'tool_calls': 32, 'stop': 4}

## Thinking budget (per model step)

- Budget (scorer-enforced, not enforced by local MLX): None
- Thinking tokens per step: p50 610, p90 1957, max 3699; steps over budget: 0/24

## Tools (pass / fail)

| tool | script | calls | ok | failed | mean s |
|---|---|---|---|---|---|
| run_skill_script | scripts/edit.py | 12 | 12 | 0 | 126.60 |
| read_file |  | 8 | 8 | 0 | 73.66 |
| run_skill_script |  | 6 | 6 | 0 | 158.71 |
| run_skill_script | scripts/audit.py | 3 | 3 | 0 | 187.26 |
| run_command |  | 2 | 0 | 2 | 151.10 |
| run_skill_script | scripts/plan.py | 1 | 1 | 0 | 3.86 |

## Failure classes

{'timeout': 1}

## Per task

| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |
|---|---|---|---|---|---|---|---|---|---|
| rich_3468 | timeout | 242 | 48 | 32 | 2 | 0.39 | 20370 | 1 | 0 |
