#!/usr/bin/env bash
# vllm-metal 0.33.0 (vLLM 0.33.0 on MLX) started with the scorer's vLLM flags.
#
# Source of the flags: adk_submission/server.py VllmServer.build_cmd (installed 0.2.13) and
# HARNESS_README.md §3.1. Mapping (scorer -> here):
#   --model <ct checkpoint>                 -> lossless MLX repack of the same checkpoint
#   --max-model-len 32768                   -> same
#   --dtype auto                            -> same
#   --gpu-memory-utilization 0.90           -> not passed: Metal sizes the KV pool itself
#                                              (VLLM_METAL_MEMORY_FRACTION); see serve_excerpt.log
#   --tensor-parallel-size 4                -> not applicable (one Apple GPU)
#   --enable-auto-tool-choice               -> same
#   --tool-call-parser gemma4               -> same
#   --reasoning-parser gemma4               -> same
#   --reasoning-config {<|channel>,<channel|>} -> same
#   --no-scheduler-reserve-full-isl         -> same
#   --enable-lora/--max-loras/--max-lora-rank/--lora-modules -> only when adapters exist (none yet)
#   --generation-config auto (vLLM default) -> same: temperature 1.0, top_k 64, top_p 0.95 fill
#                                              any field a request leaves unset
#
# Known gap: vllm-metal rejects `thinking_token_budget` with HTTP 400 (vllm_metal/platform.py,
# "does not support sampling controls backed by vLLM logits processors"). The harness sends it
# for every role with a positive thinking budget, so this server cannot take harness traffic
# until the proxy emulates the budget. See results/server_bench/vllm_metal/NOTES.md.
#
# Usage: Tools/local/serve_vllm_metal_kaggle.sh [port]   (default 8124)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${1:-8124}"
MODEL="${MODEL:-$HOME/models/gemma-4-e4b-it-qat-w4a16-mlx}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1
# no_network_ipc.sb = no_network.sb + local Unix sockets (vLLM's ZMQ engine channel).
exec sandbox-exec -f "$ROOT/Tools/seatbelt/no_network_ipc.sb" /opt/homebrew/bin/vllm serve "$MODEL" \
  --served-model-name "$(basename "$MODEL")" --host 127.0.0.1 --port "$PORT" \
  --max-model-len 32768 --dtype auto \
  --enable-auto-tool-choice --tool-call-parser gemma4 \
  --reasoning-parser gemma4 \
  --reasoning-config '{"reasoning_start_str": "<|channel>", "reasoning_end_str": "<channel|>"}' \
  --no-scheduler-reserve-full-isl
