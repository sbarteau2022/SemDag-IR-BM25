#!/bin/zsh
# Bake one run's telemetry into a Docker image (Docker Desktop, post-run only).
# Contents under /telemetry/<run_id>/: telemetry.sqlite (this run's rows only),
# steps.jsonl (per-step reasoning text, tool call, args, observation, tokens),
# TELEMETRY.md, run_meta.json, task_results.jsonl, summary.json, traces/, patches/,
# test_outputs/, logs/, run.log. Base: swebench-sandbox:latest (python3 + sqlite3 to query;
# its layers are shared, so the image adds only the run data on disk).
# Usage: Tools/telemetry/bake_image.sh <run_id> <results_dir>
set -euo pipefail
cd "$(dirname "$0")/../.."
RUN_ID="$1"; OUT="$2"
export DOCKER_HOST="${DOCKER_HOST:-unix://$HOME/.docker/run/docker.sock}"
TAG="gemma4-e4b-telemetry:${RUN_ID//_/-}"
CTX=$(mktemp -d /tmp/telemetry-bake.XXXXXX)
D="$CTX/telemetry/$RUN_ID"
mkdir -p "$D"
.venv-harness/bin/python Tools/telemetry/export_run.py --db results/telemetry.sqlite \
  --run-id "$RUN_ID" --out-db "$D/telemetry.sqlite" --steps-jsonl "$D/steps.jsonl"
for f in TELEMETRY.md run_meta.json task_results.jsonl summary.json run.log; do
  [[ -f "$OUT/$f" ]] && cp "$OUT/$f" "$D/"
done
for d in traces patches test_outputs logs; do [[ -d "$OUT/$d" ]] && cp -R "$OUT/$d" "$D/"; done
cat >"$CTX/Dockerfile" <<DOCKER
FROM swebench-sandbox:latest
LABEL org.opencontainers.image.title="gemma4-e4b telemetry ${RUN_ID}" \
      run_id="${RUN_ID}" git_head="$(git rev-parse HEAD)" created_utc="$(date -u +%FT%TZ)"
COPY telemetry /telemetry
WORKDIR /telemetry/${RUN_ID}
DOCKER
docker build -q -t "$TAG" "$CTX" >/dev/null
rm -rf "$CTX"
echo "baked $TAG ($(docker image inspect "$TAG" --format '{{.Id}}' | cut -c1-19))"
