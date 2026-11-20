# Pretrained LoRA adapters for gemma-4-e4b-it-qat-w4a16-ct (survey, 2026-11-20)

Sources:
- Hugging Face Hub search over the tags `base_model:adapter:{google/gemma-4-E4B-it, google/gemma-4-E4B, unsloth/gemma-4-E4B-it, google/…-qat-q4_0-unquantized}` and about 25 keyword queries (code, coder, swe, agent, tool, function, terminal, trajectory, distill, …).
- Each shortlisted repo's `adapter_config.json` and README.
- The tensor-name header of each `adapter_model.safetensors`, read by HTTP range request. No weights were downloaded.
- Local code: the checkpoint index, and vLLM 0.33 `gemma4.py` / `lora/utils.py`. The scorer runs patched vLLM 0.19.1, so that code is a proxy.

## What an adapter must match

From the local checkpoint (`Models/gemma-4-e4b-it-qat-w4a16-ct/config.json` and its safetensors index):

- `Gemma4ForConditionalGeneration` with a text decoder: 42 layers, hidden 2560, MLP 10240, 8 heads / 2 KV heads, head_dim 256. The layer types are sliding (window 512) with every sixth layer full attention.
- **KV sharing: `num_kv_shared_layers = 18`.** Layers 24 to 41 have only `q_proj`. `k_proj`, `v_proj` and `k_norm` exist on 24 layers only. vLLM's weight mapper drops k/v for layers 24 to 41, so adapter k/v weights there do nothing.
- Per-layer embeddings: `per_layer_input_gate` and `per_layer_projection` on every layer, plus `per_layer_model_projection`.
- Module paths: `model.language_model.layers.N.{self_attn.{q,k,v,o}_proj, mlp.{gate,up,down}_proj}`. The vision and audio towers wrap their linears as `….q_proj.linear`.
- The base is **QAT int4 (compressed-tensors W4A16)**. Every adapter found was trained on the bf16 `google/gemma-4-E4B-it`, on unsloth's bnb-4bit copy of it, or on the `E4B` base. None was trained on the QAT weights (`google/gemma-4-E4B-it-qat-q4_0-unquantized`). The deltas will be applied to slightly different weights, and that effect is unmeasured.
- Scorer: `enable_lora`, `max_loras = #adapters`, `max_lora_rank = max detected rank`. vLLM applies LoRA to any `LinearBase` by name suffix, and expects PEFT `.safetensors` with rank ≤ 128 and a 3 GiB total. The forum reports LoRA makes tasks about 29% slower and shrinks the KV cache. Rank and adapter count cost KV memory.

## Inventory

- About 200 or more E4B LoRA adapters exist on the Hub. The `google/gemma-4-E4B-it` adapter tag alone returned 100, the search cap.
- Almost all are domain adapters: languages, medicine, legal, ASR, OCR, and so on.
- **No SWE-bench-style (repository patch) LoRA exists for E4B.**
  - The one SWE agent LoRA found, `nexaaii/gemma-4-tfd-swe-agent`, is for the 31B QAT base and is incompatible.
  - `bbkdevops/gemma-4-developer-agent` is another entrant's prompt-only submission with no adapter. It also ships repo-specific skills (fastapi, rich, requests, httpx), which we would not copy.

### Shortlist: code, agent and tool-use adapters, verified from tensor headers

| Repo | r | Tensors cover | Size (F32) | Data | License | Fit |
|---|---|---|---|---|---|---|
| [carlesoctav/grafting-e4b_base_termgrade-1.0](https://hf.co/carlesoctav/grafting-e4b_base_termgrade-1.0) | 16 | language q/k/v/o + MLP only, k/v on the 24 non-shared layers | 140 MB | TermGrade terminal-agent episodes (multi-turn bash, pytest-verified); "grafting" ([arXiv 2610.05872](https://arxiv.org/abs/2610.05872)): learned on the E4B base, applied to -it | no license tag on the model; dataset `ai-and/termgrade-*` is apache-2.0 | **Best behavioural match** (multi-turn shell agent). Clean layout, loads as-is. License must be confirmed. |
| [roshangrewal/gemma4-e4b-toolcall-v02-lora](https://hf.co/roshangrewal/gemma4-e4b-toolcall-v02-lora) | 64 | language q/k/v/o + MLP on all 42 layers, **plus vision and audio towers** | 679 MB | nvidia/Nemotron-SFT-Agentic-v2 (cc-by-4.0/apache/mit) + glaive-function-calling-v2; Gemma-native `<\|tool_call>` format; BFCL non-live 86.5% (author's numbers, unverified) | apache-2.0 | **Targets our run_26 failure** (malformed tool-call arguments). The tower tensors must be stripped. |
| [S4MPL3BI4S/gemma4-e4b-openclaw-agent-lora](https://hf.co/S4MPL3BI4S/gemma4-e4b-openclaw-agent-lora) | 32 | language only (k/v on all 42) | 294 MB | driaforall/pythonic-function-calling, 1,000 steps | none on the model | Pythonic tool calls for a coding agent. License unknown. |
| [jonlimanza/gemma-4-e4b-hermes-agent-reasoning-lora](https://hf.co/jonlimanza/gemma-4-e4b-hermes-agent-reasoning-lora) | 64 (rsLoRA) | language only | 587 MB | not stated | apache-2.0 | Undocumented data, so it can't be checked for contamination. Low priority. |
| [josephmayo/gemma-4-E4B-it-coding-lora](https://hf.co/josephmayo/gemma-4-E4B-it-coding-lora) | 16 | language incl. per_layer_*, **plus vision and audio** | 202 MB | 1,024 "benign coding" rows, 200 steps; HumanEval-50 34 → 42 (author's numbers) | apache-2.0 | Small, single-function codegen. Weak match for multi-turn repair. |
| [armand0e/Gemma-4-E4B-it-Fable-Distill-LoRA](https://hf.co/armand0e/Gemma-4-E4B-it-Fable-Distill-LoRA) | 32 | language only | 294 MB | distilled from a closed model | apache-2.0 tag | Distilled from a closed model; check that model's terms first. Reasoning style, not tool use. |
| [Elysianmind/CodeSight-Gemma4-E4B-LoRA](https://hf.co/Elysianmind/CodeSight-Gemma4-E4B-LoRA) | 16 | **vision and audio towers only** (`*.linear`) | 11 MB | — | — | **No effect on text.** Its config lists `q_proj.linear`, which matches only the towers. |

Rejected: `laion/Alexandria…-r128` (scientific knowledge units, cc-by-4.0, 1.1 GB), `BrejBala/gemma-toolcall-guard` (a safety classifier), `StrandsAgents/strands-decider-E4B` (a classification head), and every language, medical and other domain adapter.

### Full fine-tunes that could become LoRAs by SVD extraction (delta = FT − base, truncated to rank ≤ 128)

| Repo | What | License |
|---|---|---|
| [hmkz-1981/gemma-4-e4b-agentic-rl-think-effort](https://hf.co/hmkz-1981/gemma-4-e4b-agentic-rl-think-effort) | agentic RL, tool use, reasoning-effort control | apache-2.0 |
| [LLM-OS-Models/gemma-4-E4B-it-Terminal-SFT-Native-Liquid-2Epoch](https://hf.co/LLM-OS-Models/gemma-4-E4B-it-Terminal-SFT-Native-Liquid-2Epoch) | terminal next-command SFT (JSON actions), 5.1k downloads | none tagged |
| [RockToken/gemma4_31b_to_e4b_onpolicy_code_5k](https://hf.co/RockToken/gemma4_31b_to_e4b_onpolicy_code_5k) | on-policy distillation from Gemma 4 31B on OpenThoughts3 code | gemma |

Extraction keeps only the top singular directions, and the result again sits on the non-QAT base. How much of each fine-tune survives at rank 16 to 64 has to be measured.

## Conversion each candidate needs before it can be submitted

1. Keep only `language_model.layers.N.{self_attn.{q,k,v,o}_proj, mlp.{gate,up,down}_proj}` tensors. Drop the vision and audio towers, `per_layer_*` (scorer support unverified), and `k_proj`/`v_proj` on layers 24 to 41.
2. Cast F32 to BF16, which halves the size.
3. Optionally SVD-truncate the rank (64 → 16 or 32) to cut KV-cache cost and the LoRA slowdown.
4. Rewrite `adapter_config.json` with an explicit `target_modules` list and an anchored regex, and set `base_model_name_or_path` to the competition model.
5. Place it in `adapters/<name>/` and validate with `validate_directory`.
6. Prove it loads and changes outputs. Locally that means vllm-metal with `--enable-lora`. On Kaggle it means the patched vLLM 0.19.1, where staff fixed a LoRA-wipe bug in wheelhouse v23.

## What this survey does not establish

- That any adapter helps on our task. None was trained on repository-repair trajectories, so each needs a paired23 run against v6 (7/23).
- That adapters trained on the bf16 base transfer to the QAT int4 base.
- Whether vLLM 0.19.1 accepts `per_layer_*` LoRA targets, and whether it errors or skips on k/v for KV-shared layers. Both were read from 0.33 source only.
- Licenses: two shortlisted models carry no license tag. The competition requires winners to release under a license that does not limit commercial use.
- Contamination: TermGrade is Linux terminal tasks and Nemotron-Agentic is synthetic tool use. Neither names fastapi, rich, requests or httpx, but neither was scanned.
