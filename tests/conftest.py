"""Shared helpers for host-side tests. Builds tiny swegemma-style results dirs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Never write bytecode while testing: a __pycache__ inside an AgenticSubmission folder makes
# the harness reject the submission (.pyc is a disallowed extension). run_14 lost 3 tasks this way.
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "Tools", ROOT / "Tools" / "telemetry"):
    sys.path.insert(0, str(p))


def step(step_id, source="agent", author="root", event_type="thinking", message="",
         tool=None, args=None, obs=None, ts=1000.0, elapsed=1.0, pt=100, ct=10, cached=0):
    s = {"step_id": step_id, "source": source, "message": message,
         "extra": {"author": author, "event_type": event_type, "timestamp": ts,
                   "elapsed_s": elapsed}}
    if source == "agent":
        s["metrics"] = {"prompt_tokens": pt, "completion_tokens": ct, "cached_tokens": cached}
        s["llm_call_count"] = 1
    if tool:
        s["tool_calls"] = [{"tool_call_id": f"c{step_id}", "function_name": tool,
                            "arguments": args or {},
                            "extra": {"author": author, "elapsed_s": elapsed, "timestamp": ts}}]
        s["observation"] = {"content": obs if isinstance(obs, str) else json.dumps(obs or {"status": "ok"}),
                            "extra": {"tool_name": tool}}
    return s


def write_run(root: Path, tasks: list[dict]) -> Path:
    """tasks: dicts with instance_id, resolved, steps, patch, test_log, extra result fields."""
    (root / "traces").mkdir(parents=True, exist_ok=True)
    (root / "patches").mkdir(exist_ok=True)
    (root / "test_outputs").mkdir(exist_ok=True)
    lines = []
    for t in tasks:
        iid = t["instance_id"]
        patch = t.get("patch", "")
        res = {"instance_id": iid, "repo": t.get("repo", "o/r"), "resolved": t.get("resolved", False),
               "agent_patch_size": len(patch.encode()), "duration_seconds": t.get("duration", 10.0),
               "tool_calls": t.get("tool_calls", 1), "total_llm_calls": t.get("llm_calls", 1),
               "error": t.get("error"), "test_exit_code": t.get("test_exit_code", 1), "task_index": 0}
        lines.append(json.dumps(res))
        if t.get("steps") is not None:
            (root / "traces" / f"trace_{iid}.json").write_text(json.dumps(
                {"schema_version": "ATIF-v1.7", "agent": {}, "steps": t["steps"],
                 "final_metrics": {}}))
        (root / "patches" / f"{iid}.patch").write_text(patch)
        if t.get("test_log") is not None:
            (root / "test_outputs" / f"{iid}.log").write_text(t["test_log"])
    (root / "task_results.jsonl").write_text("\n".join(lines) + "\n")
    return root


def diff(path, body="-a\n+b\n"):
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n{body}"


@pytest.fixture
def make_run(tmp_path):
    def _make(name, tasks):
        return write_run(tmp_path / name, tasks)
    return _make
