#!/bin/zsh
# Run the official swegemma harness in the Docker sandbox against the local E4B server.
# Usage: Tools/run_agent_eval.sh <submission_dir> <results_dir> <ids_file>
# Needs: Docker Desktop running, image swebench-sandbox:latest, Tools/serve_e4b_mlx.sh on 127.0.0.1:8123.
set -e
cd "$(dirname "$0")/.."
SUB="$1"; OUT="$2"; IDS="$3"
OPENAI_BASE_URL=http://127.0.0.1:8123/v1 OPENAI_API_KEY=EMPTY .venv-harness/bin/swegemma eval \
  --tasks DataSets/public/data/tasks.jsonl --snapshots-dir DataSets/public/data/snapshots \
  --submission-dir "$SUB" --results-dir "$OUT" --sandbox docker --concurrency 1 \
  --task-ids $(cat "$IDS") --models-yaml Tools/local/models_local.yaml \
  --max-tool-calls 40 --max-time-minutes 8 --max-turns 60 --timeout-seconds 120 --display quiet
