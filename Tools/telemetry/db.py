"""SQLite store for harness telemetry. Stdlib only.

One database holds every run. Rows are keyed by `run_id`; re-ingesting a run replaces
its rows. The proxy writes `llm_calls` live; `ingest.py` writes everything else from
the harness's own output (task_results.jsonl, traces/, patches/, test_outputs/).

Units: seconds for time, tokens for token counts, characters for `*_chars`.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  arm TEXT,
  submission_dir TEXT,
  submission_sha256 TEXT,
  git_head TEXT,
  sandbox TEXT,
  seatbelt INTEGER,
  model TEXT,
  budget_json TEXT,
  sampling_json TEXT,
  started_utc TEXT,
  ingested_utc TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
  run_id TEXT, instance_id TEXT, repo TEXT,
  resolved INTEGER, error TEXT, test_exit_code INTEGER,
  duration_s REAL, patch_bytes INTEGER,
  harness_tool_calls INTEGER, harness_llm_calls INTEGER,
  steps INTEGER, agent_steps INTEGER, nudges INTEGER, compactions INTEGER,
  prompt_tokens INTEGER, completion_tokens INTEGER, cached_tokens INTEGER,
  peak_prompt_tokens INTEGER, peak_context_frac REAL,
  thinking_chars INTEGER, thinking_tokens INTEGER,
  thinking_calls_over_budget INTEGER,
  tool_calls INTEGER, tool_errors INTEGER, edit_errors INTEGER, write_file_calls INTEGER,
  skill_calls INTEGER, subagent_calls INTEGER, subagent_steps INTEGER,
  first_edit_s REAL, ran_tests INTEGER, repro_before_edit INTEGER,
  edited_files TEXT, gold_files TEXT, touched_gold_file INTEGER,
  edited_functions TEXT, gold_functions TEXT, touched_gold_function INTEGER,
  test_env_missing_dep INTEGER, destructive_write INTEGER,
  failure_class TEXT,
  t_start REAL, t_end REAL,
  PRIMARY KEY (run_id, instance_id)
);

CREATE TABLE IF NOT EXISTS steps (
  run_id TEXT, instance_id TEXT, step_id INTEGER,
  source TEXT, author TEXT, depth INTEGER, event_type TEXT,
  ts REAL, elapsed_s REAL,
  prompt_tokens INTEGER, completion_tokens INTEGER, cached_tokens INTEGER,
  context_frac REAL,
  thinking_chars INTEGER, thinking_tokens INTEGER, over_thinking_budget INTEGER,
  n_tool_calls INTEGER, llm_call_count INTEGER,
  thinking_text TEXT, tool_name TEXT, tool_args TEXT, observation TEXT,
  PRIMARY KEY (run_id, instance_id, step_id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
  run_id TEXT, instance_id TEXT, step_id INTEGER, seq INTEGER,
  name TEXT, skill_name TEXT, skill_script TEXT,
  author TEXT, depth INTEGER,
  ok INTEGER, status TEXT, error_type TEXT, error_message TEXT,
  exit_code INTEGER,
  elapsed_s REAL, args_chars INTEGER, obs_chars INTEGER,
  nested_steps INTEGER,
  PRIMARY KEY (run_id, instance_id, seq)
);

CREATE TABLE IF NOT EXISTS llm_calls (
  run_id TEXT, call_id TEXT PRIMARY KEY, instance_id TEXT,
  wall_start REAL, ttft_s REAL, t_first_reasoning_s REAL, t_first_action_s REAL,
  reasoning_s REAL, total_s REAL,
  prompt_tokens INTEGER, completion_tokens INTEGER, cached_tokens INTEGER,
  stream_chunks INTEGER, reasoning_chunks INTEGER,
  reasoning_chars INTEGER, content_chars INTEGER,
  n_tool_calls INTEGER, tool_names TEXT, finish_reason TEXT,
  req_messages INTEGER, req_tools INTEGER, req_bytes INTEGER,
  req_max_tokens INTEGER, req_thinking_budget INTEGER, req_temperature REAL,
  client_stream INTEGER, upstream_status INTEGER, error TEXT,
  decode_tok_per_s REAL
);

CREATE VIEW IF NOT EXISTS v_tool_pass_fail AS
  SELECT run_id, name, COALESCE(skill_script, '') AS skill_script,
         COUNT(*) AS calls, SUM(ok) AS ok, COUNT(*) - SUM(ok) AS failed,
         ROUND(AVG(elapsed_s), 2) AS mean_s
  FROM tool_calls GROUP BY run_id, name, skill_script;

CREATE VIEW IF NOT EXISTS v_thinking_budget AS
  SELECT s.run_id, s.instance_id, s.step_id, s.thinking_tokens,
         CAST(json_extract(r.sampling_json, '$.thinking_config.thinking_budget') AS INTEGER)
           AS thinking_budget,
         s.over_thinking_budget
  FROM steps s JOIN runs r USING (run_id)
  WHERE s.event_type = 'thinking';
"""

# Columns added after a table first shipped: (table, column, type). connect() adds any that
# an existing database lacks, so older stores keep working without a rebuild.
MIGRATIONS = [("tasks", "destructive_write", "INTEGER")]

_LOCK = threading.Lock()


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    for table, column, ctype in MIGRATIONS:
        have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if column not in have:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ctype}")
    con.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    con.commit()
    return con


def insert(con: sqlite3.Connection, table: str, row: dict, replace: bool = True) -> None:
    cols = ",".join(row)
    marks = ",".join("?" for _ in row)
    verb = "INSERT OR REPLACE" if replace else "INSERT"
    with _LOCK:
        con.execute(f"{verb} INTO {table} ({cols}) VALUES ({marks})", tuple(row.values()))
        con.commit()
