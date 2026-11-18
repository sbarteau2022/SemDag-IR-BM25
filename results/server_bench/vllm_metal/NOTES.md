# vllm-metal 0.33.0: scorer-parity gates and throughput (2026-11-17)

Status: **LIVE-MEASURED** on this Mac (M-series, 51.5 GB Metal memory). Install: `brew tap vllm-project/vllm-metal https://github.com/vllm-project/vllm-metal && brew install vllm-project/vllm-metal/vllm-metal`. That installs 2.3 GB (vllm 0.33.0, vllm-metal 0.33.0, mlx 0.32.4, mlx-lm 0.32.3.dev, Python 3.12).

Launch: `Tools/local/serve_vllm_metal_kaggle.sh` (scorer flags, mapping in the header). The server log confirms the non-default args, and that `generation_config.json` defaults apply: `{'temperature': 1.0, 'top_k': 64, 'top_p': 0.95}`.

## Model

It loads `~/models/gemma-4-e4b-it-qat-w4a16-mlx` directly, the lossless repack of the competition checkpoint. No GGUF is needed. vllm-metal can read GGUF, but a GGUF would be a re-quantization, so it is not used.

## Gates (`gates.json`, `gates.py`; proxy equivalence via `Tools/telemetry/check_proxy_equivalence.py`)

| Gate | Result |
|---|---|
| G1 proxy equivalence (greedy) | **2/2 MATCH**, twice, with a warm prefix cache. The first attempt had 1 mismatch on a cold vs warm prefix-cache pair; repeated direct calls are deterministic (identical md5 ×6, stream and non-stream). Fixing the proxy also needed a change in `llm_proxy.py`: vLLM streams tool-call arguments in fragments, so the proxy now merges them by index (3 new tests) |
| G2 thinking budget | **FAIL: HTTP 400** `vllm-metal does not support sampling controls backed by vLLM logits processors (thinking_token_budget)` |
| G3 penalties | Applied. A forced "banana ×300" loop at temp 0: frequency_penalty 0 gave 700 tokens; 0.5 stopped at 33 tokens. The sampler passes full `output_token_ids` to vLLM's `SamplingMetadata` (`vllm_metal/v1/sampling_batch.py:716-737`), which is vLLM's whole-output semantics. This test cannot by itself tell a whole-output penalty from a short window |
| G4 tool call + reasoning | PASS: `read_file {"filepath": "src/app.py"}`, finish `tool_calls`, reasoning extracted (132 chars) |

## Throughput (512 tokens, thinking off, `ignore_eos`)

| Streams | Aggregate tok/s | Per request tok/s |
|---|---|---|
| 1 | 57.6 | 57.6 |
| 4 | **203.0** (3.5×) | 50.8 |

For comparison, oMLX 0.7.0 does 57.5 single-stream and 136 with 4 streams (2.3×; `../NOTES.md`).

## Verdict

- vllm-metal is closer to the scorer on every axis except the thinking budget. It has the same vLLM front end, parsers, flags, generation-config defaults and penalty semantics, and it batches better.
- It cannot take harness traffic yet: every role with a positive `thinking_budget` gets HTTP 400.
- Options:
  (a) the proxy removes `thinking_token_budget` and enforces it itself: stream, count reasoning tokens, stop at the budget, then resume with `<channel|>` forced (the same behaviour as vLLM's processor);
  (b) keep oMLX as the default, where the budget works today.
- oMLX stays the runner default until (a) is built and passes a budget gate.
