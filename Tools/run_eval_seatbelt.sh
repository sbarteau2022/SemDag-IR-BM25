#!/bin/zsh
# Local scored-style run with no network: model server, telemetry proxy and harness all
# run inside Tools/seatbelt/no_network.sb (loopback + Unix sockets only). Task containers
# run in Docker Desktop with network_disabled=True. Colima is never used.
#
# Usage: Tools/run_eval_seatbelt.sh <submission_dir> <results_dir> <ids_file> <run_id> [arm]
# Budget flags come from <submission_dir>/eval_config.yaml (what the scorer reads), not
# from hard-coded values. Post-run (after the harness exits, so it never competes for
# throughput): ingest -> SQLite, report.md, and Tools/telemetry/bake_image.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
SUB="$1"; OUT="$2"; IDS="$3"; RUN_ID="$4"; ARM="${5:-$(basename "$SUB")}"
SB="$ROOT/Tools/seatbelt/no_network.sb"
DB="$ROOT/results/telemetry.sqlite"
MODEL="$HOME/models/gemma-4-e4b-it-qat-w4a16-mlx"
export DOCKER_HOST="unix://$HOME/.docker/run/docker.sock"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
mkdir -p "$OUT"
# TASKS selects the folder the harness reads wheels from (the folder beside tasks.jsonl).
# DataSets/local_overlay/data (Tools/local/build_wheel_overlay.py) swaps x86_64-only compiled
# wheels for arm64 twins on Apple silicon. The harness caches unpacked wheels under TMPDIR
# with a fixed name, so an overlay run gets its own TMPDIR to avoid reusing the old unpack.
TASKS="${TASKS:-DataSets/public/data/tasks.jsonl}"
HARNESS_TMP="${TMPDIR:-/tmp}"
if [[ "$TASKS" == *local_overlay* ]]; then
  HARNESS_TMP="$HOME/.cache/swegemma_overlay_tmp"; mkdir -p "$HARNESS_TMP"
fi

export TASKS SERVER="${SERVER:-mlx_lm}"
# Refuse to start on a submission the official validator rejects (e.g. a stray __pycache__).
.venv-harness/bin/python -c "import sys; from pathlib import Path; from adk_submission import validate_directory; from swegemma.config import build_submission_limits; validate_directory(Path(sys.argv[1]), limits=build_submission_limits()[0])" "$SUB" \
  || { echo "submission $SUB fails validation; not starting" >&2; exit 2; }
read -r TS CALLS MINS TURNS <<<"$(.venv-harness/bin/python - "$SUB" <<'PY'
import sys, yaml
e = yaml.safe_load(open(f"{sys.argv[1]}/eval_config.yaml"))["evaluation"]
print(e["timeout_seconds"], e["max_tool_calls"], e["max_time_minutes"], e["max_turns"])
PY
)"

.venv-harness/bin/python - "$SUB" "$OUT" "$RUN_ID" "$ARM" "$IDS" <<'PY'
import hashlib, json, subprocess, sys, time, yaml
from pathlib import Path
sub, out, run_id, arm, ids = sys.argv[1:]
h = hashlib.sha256()
for p in sorted(Path(sub).rglob("*")):
    if p.is_file():
        h.update(str(p.relative_to(sub)).encode()); h.update(p.read_bytes())
meta = {
    "run_id": run_id, "arm": arm, "submission_dir": sub, "submission_sha256": h.hexdigest(),
    "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
    "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip()),
    "sandbox": "docker", "seatbelt": 1, "docker_host": "Docker Desktop",
    "model": "gemma-4-e4b-it-qat-w4a16-mlx", "server": __import__("os").environ.get("SERVER", "mlx_lm"),
    "budget": yaml.safe_load(open(f"{sub}/eval_config.yaml"))["evaluation"],
    "sampling": (yaml.safe_load(open(f"{sub}/configs/sampling.yaml"))
                 if Path(sub, "configs", "sampling.yaml").exists() else
                 {p.stem.removeprefix("sampling_"): yaml.safe_load(p.read_text())
                  for p in sorted(Path(sub, "configs").glob("sampling*.yaml"))}),
    "task_ids_file": ids, "tasks_path": __import__("os").environ.get("TASKS", "DataSets/public/data/tasks.jsonl"), "task_ids": Path(ids).read_text().split(),
    "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "notes": "local MLX stand-in: thinking_budget not enforced, no events compaction",
}
Path(out, "run_meta.json").write_text(json.dumps(meta, indent=1))
PY

# SERVER selects the local model server behind the proxy: mlx_lm (default, verified) or
# rapid (rapid-mlx 1.0.0, NOT yet verified: see results/server_bench/NOTES.md). rapid-mlx is closer to
# the scorer's vLLM: continuous batching, prefix cache, gemma4 tool/reasoning parsers, and
# a 32,768-token context cap like max_model_len.
SERVER="${SERVER:-mlx_lm}"
STARTED_SERVER=0
if ! curl -s -m 2 http://127.0.0.1:8124/v1/models >/dev/null; then
  if [[ "$SERVER" == rapid ]]; then
    RAPID_MLX_TELEMETRY=0 sandbox-exec -f "$SB" /opt/homebrew/bin/rapid-mlx --no-telemetry \
      --disable-version-check --no-banner serve "$MODEL" --served-model-name "$MODEL" \
      --host 127.0.0.1 --port 8124 --disable-model-downloads --no-spec-decode \
      --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 \
      --context-length 32768 --max-num-seqs 4 --max-concurrent-requests 4 \
      --enable-prefix-cache --default-temperature 0.2 --default-top-p 0.95 \
      --log-level INFO >"$OUT/model_server.log" 2>&1 &
  else
    sandbox-exec -f "$SB" "$ROOT/.venv-mlx/bin/python" -m mlx_lm.server --model "$MODEL" \
      --host 127.0.0.1 --port 8124 --temp 0.2 --top-p 0.95 --max-tokens 4096 \
      --chat-template-args '{"enable_thinking": true}' >"$OUT/model_server.log" 2>&1 &
  fi
  SERVER_PID=$!; STARTED_SERVER=1
  for i in {1..240}; do curl -s -m 2 http://127.0.0.1:8124/v1/models >/dev/null && break; sleep 2; done
fi
sandbox-exec -f "$SB" "$ROOT/.venv-harness/bin/python" Tools/telemetry/llm_proxy.py \
  --listen 8125 --upstream 127.0.0.1:8124 --db "$DB" --run-id "$RUN_ID" >"$OUT/llm_proxy.log" 2>&1 &
PROXY_PID=$!
for i in {1..30}; do curl -s -m 2 http://127.0.0.1:8125/v1/models >/dev/null && break; sleep 1; done
cleanup() { kill $PROXY_PID 2>/dev/null || true; [[ $STARTED_SERVER = 1 ]] && kill $SERVER_PID 2>/dev/null || true; }
trap cleanup EXIT

echo "run $RUN_ID: budget timeout=$TS calls=$CALLS minutes=$MINS turns=$TURNS" | tee "$OUT/run.log"
set +e
OPENAI_BASE_URL=http://127.0.0.1:8125/v1 OPENAI_API_KEY=EMPTY TMPDIR="$HARNESS_TMP" sandbox-exec -f "$SB" \
  .venv-harness/bin/swegemma eval \
  --tasks "$TASKS" --snapshots-dir DataSets/public/data/snapshots \
  --submission-dir "$SUB" --results-dir "$OUT" --sandbox docker --concurrency 1 \
  --task-ids $(cat "$IDS") --models-yaml Tools/local/models_local_8125.yaml \
  --max-tool-calls "$CALLS" --max-time-minutes "$MINS" --max-turns "$TURNS" \
  --timeout-seconds "$TS" --display quiet >>"$OUT/run.log" 2>&1
RC=$?
set -e
echo "harness exit=$RC finished=$(date -u +%FT%TZ)" | tee -a "$OUT/run.log"
cleanup; trap - EXIT

# Post-run only.
.venv-harness/bin/python Tools/telemetry/ingest.py "$OUT" --db "$DB" --run-id "$RUN_ID" \
  --arm "$ARM" --tasks DataSets/public/data/tasks.jsonl --tokenizer "$MODEL/tokenizer.json" \
  --functions | tee -a "$OUT/run.log"
.venv-harness/bin/python Tools/telemetry/report.py --db "$DB" --run-id "$RUN_ID" \
  --out "$OUT/TELEMETRY.md" >/dev/null
Tools/telemetry/bake_image.sh "$RUN_ID" "$OUT" | tee -a "$OUT/run.log"
exit $RC
