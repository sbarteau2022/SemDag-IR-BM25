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


## Update (same day): Kaggle, ModelScope, GitHub, arXiv

Sources:
- Kaggle CLI: `kaggle models list --search …`, `kaggle kernels list --competition gemma-4-developer-agent -s …`, `kaggle datasets list -s …`, and model and dataset metadata.
- `gh search repos` and `gh search code`.
- Web search scoped to modelscope.cn and arXiv.

Only metadata and cards were read. Nothing was downloaded.

### The one competition-grade E4B adapter: Kaggle, not Hugging Face

[`omallo/gemma4-e4b-swe-agent-lora-from-31b`](https://www.kaggle.com/models/omallo/gemma4-e4b-swe-agent-lora-from-31b) (Kaggle Models, v1, 69.8 MB, Apache 2.0). From its card:

- Built for `gemma-4-e4b-it-qat-w4a16-ct` itself: trained on the scorer's int4 checkpoint unpacked to bf16, with prompts re-rendered through the scorer's chat template and checked token by token against vLLM.
- Rank 16 on q, k, v, o, gate, up and down. Trained at alpha 32 (scale 2.0) and served at alpha 16 (scale 1.0); the card says scale 2.0 scored lower on every set. Two epochs, learning rate 1e-4.
- Data: 485 resolved Gemma 4 31B trajectories under the competition harness, 425 from a validated SWE-rebench pool and **60 from the competition's public tasks**.
- Results under the harness (28 tool calls, 8 minutes per task, three runs):

  | Set | Plain E4B | With the adapter | 31B |
  |---|---|---|---|
  | held-out 47 | 9.7 | **19.7** (sign test p < 0.001) | 36.3 |
  | large 49 | 8.3 | 12.7 (p = 0.12) | — |
  | SWE-bench Verified 50 | 11.3 | 10.3 | — |

- Companion dataset [`omallo/gemma4-swe-agent-lora-distillation`](https://www.kaggle.com/datasets/omallo/gemma4-swe-agent-lora-distillation) (CC BY 4.0): validated task sets `heldout48` and `large49`, 3,286 graded traces, and **767 resolved 31B trajectories plus 950 DeepSeek V4.1 Flash trajectories in the organisers' trace format**. The 425 non-public training trajectories are flagged.
- Caveats:
  - The 60 public-task trajectories mean the adapter's score on our paired23 overstates it. Adopting it as-is also conflicts with our rule never to train on public tasks.
  - It was measured at 8 minutes per task; we run 4 minutes, and LoRA adds latency.
  - It was measured with the author's prompt and tools, not ours.

### Others found on Kaggle (none drop-in)

- Adapters for the 31B base only: `scottweeden/gemma-4-31b-swe-tool-use-lora` (with an Apache-2.0 recipe kit), `robinamirbahar/gemma-4-31b-loop-breaker-lora`, `robinamirbahar/gemma-4-ccr-loop-breaker`. Also on Hugging Face: `karthik-a/sparkflashxgemma4` (31B).
- `karthikvattem/gemma-4-e4b-pallas-lora` writes JAX Pallas TPU kernels, a different domain.
- Notebooks with E4B training code: `nooktablet/gemma-4-e4b-oracle-sft-scripts`, `boristown/gemma-4-e2b-lora-fine-tuning-swe-agent-baseline`, `fjnulinweisong/gemma-agent-trajectory-sft`, `kevindiazcordova/gemma-4-validated-oracle-trajectories`, `dmitriigluzdov/gemma-4-serving-and-lora-verification-kit` (a dataset, 766 MB).

### Training-data candidates (if we train our own)

| Source | What | License |
|---|---|---|
| `omallo/gemma4-swe-agent-lora-distillation` | 425 clean + 342 more resolved Gemma 4 31B trajectories and 950 DeepSeek V4.1 Flash trajectories, in harness trace format | CC BY 4.0 |
| `adesolanke/gemma4-swe-agent-trajectories` | nebius SWE-rebench OpenHands trajectories (Qwen3-Coder-480B) converted to the harness tools, with a curated top-40% subset; conversion code in `damsolanke/gemma4-swe-kit` | CC BY 4.0 |
| `jayp2005/berth-swe-tasks` | 653 harness-compatible offline tasks from 24 permissive libraries: `extended` (350) for training, `core` (301) for evaluation | Apache 2.0 |
| `nvidia/SWE-Zero2Hero` (HF, [arXiv 2604.01496](https://arxiv.org/abs/2604.01496)) | execution-free then execution-based SWE SFT data distilled from open frontier models | CC BY 4.0 (paper) |
| our `DataSets/swe_traj_v1` | 791 synthetic verified trajectories, excluding the four test repos | ours |

Each needs filtering against fastapi, rich, requests and httpx before use.

### ModelScope, GitHub, arXiv

- **ModelScope:** mirrors of `google/gemma-4-E4B(-it)` and LoRA tutorial posts (emotion classification). No coding or agent adapters.
- **GitHub:** no repo ships an E4B SWE adapter.
  - `berkayaybar14/gemma4-e4b-swe-harness` (GPL-3.0) is a harness study: 3-5/25 on SWE-bench Verified.
  - `damsolanke/gemma4-swe-kit` is a local scorer replica and trajectory converter.
  - Many competition starter repos exist.
- **arXiv:** no paper releases an E4B SWE adapter.
  - Relevant: [2610.33958](https://arxiv.org/abs/2610.33958) (small agents and code-graph tools; E4B localization rises from 18.0 with grep alone to 32.4 with all tools).
  - [2604.01496](https://arxiv.org/abs/2604.01496) is NVIDIA's SWE-Zero to SWE-Hero SFT recipe and data.
  - [2611.23205](https://arxiv.org/abs/2611.23205) is E4B QLoRA on MATLAB code; it reports a 17-19% adapter speed cost.
- **Also missed on the first Hugging Face pass:** `RedTeamLab/Gemma-4-E4B-Sol-Traces-v3` (Hermes-agent tool traces, r16, language modules only, 35 MB adapter folder, Gemma license). It is tagged as GGUF, not as an adapter.
