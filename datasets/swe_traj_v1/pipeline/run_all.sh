#!/bin/bash
# Build trajectories for every configured repo, 5 repos in parallel.
cd "$(dirname "$0")"
OUT=${1:-/tmp/claude-0/work/out_v1}
N=${2:-30}
/tmp/claude-0/work/venv/bin/python -c "from config import REPOS; print('\n'.join(REPOS))" | \
  xargs -P 5 -I{} /tmp/claude-0/work/venv/bin/python build.py {} $N $OUT 0
