#!/usr/bin/env bash
# Serve the converted competition model with the competition sampling defaults
# (configs/sampling.yaml: temperature 0.2, top_p 0.95, max_output_tokens set to 4096 to match Zed (caps thinking + answer),
#  thinking on). Clients that send their own values override these defaults.
# Note: mlx-lm has no equivalent of vLLM's thinking_token_budget (4096 in the competition).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/.venv-mlx/bin/python" -m mlx_lm.server \
  --model "$HOME/models/gemma-4-e4b-it-qat-w4a16-mlx" \
  --host 127.0.0.1 --port 8123 \
  --temp 0.2 --top-p 0.95 --max-tokens 4096 \
  --chat-template-args '{"enable_thinking": true}'
