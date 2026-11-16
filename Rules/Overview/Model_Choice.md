# Model choice: gemma-4-e4b-it-qat-w4a16-ct

## Decision

Use **`gemma-4-e4b-it-qat-w4a16-ct`** as the single base model for the agent, every sub-agent, and any LoRA adapters.

## Why this model

- **On the allowed list.** It is one of the four Gemma 4 variants the rules permit.
- **Qualifies for the Small Model bonus.** The bonus ($10k) requires Gemma E2B or E4B as the base. E4B is the bigger of the two, so it should give better results than E2B for the same prize rules.
- **Fits local development.** The `qat-w4a16` build is 4-bit weights, so it runs on consumer hardware. It is the realistic choice for iterating on a laptop before final runs.
- **Quantization-aware.** QAT means the model was trained to hold up under 4-bit quantization. That matters for tool-call reliability, which is the failure point for small agents.

## Alternatives considered

| Model | Pro | Con |
|---|---|---|
| `gemma-4-e2b-it-qat-w4a16-ct` | Smallest, fastest, also bonus-eligible | Likely weakest on multi-file bug fixes |
| `gemma-4-12b-it-qat-w4a16-ct` | Stronger reasoning | Not bonus-eligible; heavier to iterate on locally |
| `gemma-4-31b-it-qat-w4a16-ct` | Strongest of the set | Largest; slowest to iterate; not bonus-eligible |

Pick 12B or 31B only if E4B clears the baseline comfortably and the goal shifts to the general leaderboard instead of the bonus.

## Rules that bind this choice

- One base model across all agents and sub-agents. No mixing.
- LoRA adapters are optional. If used, they go in `adapters/<adapter_name>/` with `adapter_config.json` and `adapter_model.safetensors`. Reference them with `adapter: <name>` in the agent YAML.
- No runtime internet, so all weights and adapters must be inside the submission.

## Open items

- Confirm the exact model page (`kaggle.com/models/google/gemma-4/other`) and license before downloading.
- Confirm the bonus deadline. The page lists Nov 12 in one place and "same as main track" in another.
- Benchmark E4B against E2B on the 129 public tasks before committing fully.
