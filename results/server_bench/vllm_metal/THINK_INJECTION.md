# Thinking switch via a literal `<|think|>` in the system prompt (smoke, 2026-11-17)

Status: **LIVE-MEASURED, smoke only**: one request per arm, temp 0, vllm-metal 0.33.0 with the scorer's flags (`Tools/local/serve_vllm_metal_kaggle.sh`), competition MLX weights. Script: `think_inject.py`.

| arm | `enable_thinking` | system prompt | reasoning chars | completion tokens | tool call |
|---|---|---|---|---|---|
| A | false | plain | 0 | 19 | read_file |
| B | true | plain | 383 | 138 | read_file |
| C | **false** | `<\|think\|>` + plain | **226** | 88 | read_file |
| D | true | plain + "Think briefly: at most 3 sentences" | 224 | 117 | read_file (plus 80 chars of narration in content) |

`/tokenize` maps the string `<|think|>` to one token (id 98): the chat template's own thinking trigger.

## What this means on the scorer

- The harness turns thinking on for a role only if its `thinking_budget` > 0, and then always sends `thinking_token_budget`, which is vLLM's hard cut.
- Arm C shows a second route: budget 0 (flag off, **no `thinking_token_budget` sent**) plus a literal `<|think|>` in that role's instruction. The model still thinks, the gemma4 reasoning parser still separates the thinking, and the tool call still parses. **No hard cap applies.** Thinking is bounded only by the role's `max_output_tokens`, and by whatever allowance the prompt states.
- The token is an on/off switch, not a depth dial: Gemma 4's template has no effort or budget variable. Depth comes from the prompt's allowance (arm D cut thinking by about 40%) and the role's structure.
- Unverified: the effect over many tasks and samples, the effect on oMLX, how `include_thoughts` and ADK compaction treat this thinking, and whether runaway loops (run_16, rich_3043) get worse without the hard cut. A preregistered A/B is needed before relying on it.
