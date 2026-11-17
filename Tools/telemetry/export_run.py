"""Export one run from the shared telemetry store: a standalone SQLite file holding only
that run's rows, plus a per-step JSONL with reasoning text, tool call, args and observation.

Usage: export_run.py --db results/telemetry.sqlite --run-id ID --out-db X.sqlite
                     [--steps-jsonl steps.jsonl]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db as tdb  # noqa: E402

TABLES = ("runs", "tasks", "steps", "tool_calls", "llm_calls")


def export(db_path: str, run_id: str, out_db: str, steps_jsonl: str | None = None) -> dict:
    src = tdb.connect(db_path)
    Path(out_db).unlink(missing_ok=True)
    dst = tdb.connect(out_db)
    counts = {}
    for t in TABLES:
        rows = [dict(r) for r in src.execute(f"SELECT * FROM {t} WHERE run_id=?", (run_id,))]
        for r in rows:
            cols = ",".join(r)
            dst.execute(f"INSERT INTO {t} ({cols}) VALUES ({','.join('?' * len(r))})",
                        tuple(r.values()))
        counts[t] = len(rows)
    dst.commit()
    dst.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    dst.close()
    for suffix in ("-wal", "-shm"):
        Path(out_db + suffix).unlink(missing_ok=True)
    if steps_jsonl:
        with open(steps_jsonl, "w") as fh:
            for r in src.execute(
                    "SELECT * FROM steps WHERE run_id=? ORDER BY instance_id, step_id", (run_id,)):
                fh.write(json.dumps(dict(r)) + "\n")
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-db", required=True)
    ap.add_argument("--steps-jsonl")
    a = ap.parse_args()
    print(json.dumps(export(a.db, a.run_id, a.out_db, a.steps_jsonl)))


if __name__ == "__main__":
    main()
