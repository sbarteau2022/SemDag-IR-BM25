"""Tools/telemetry/lane_report.py: per-role attribution of where a brigade task broke."""

from __future__ import annotations

import json

import db as tdb
import ingest
import lane_report
from conftest import diff, step


def audit_obs(decision):
    return {"status": "ok", "stdout": json.dumps({"mode": "audit", "decision": decision})}


def plan_final(i, ts, text="PLAN\nexpected: x"):
    return step(i, author="planner", event_type="final", message=text, ts=ts)


def brigade_steps(resolved_like=True):
    return [
        step(1, source="user", author="user", event_type="task_prompt", ts=100.0),
        step(2, author="planner", tool="run_skill_script",
             args={"skill_name": "semdag", "file_path": "scripts/meta.py", "args": ["x"]},
             obs={"status": "ok", "stdout": json.dumps({"mode": "preflight"})}, ts=110.0, ct=50),
        plan_final(3, 130.0),
        step(4, author="executor", tool="run_command", args={"command": "python /tmp/repro.py"},
             ts=140.0, ct=20),
        step(5, author="executor", tool="edit_file", args={"filepath": "a.py"},
             obs={"status": "error"}, ts=150.0, ct=30),
        step(6, author="executor", tool="edit_file", args={"filepath": "a.py"}, ts=160.0, ct=30),
        step(7, author="executor", event_type="final", message="DONE", ts=165.0),
        step(8, author="auditor", tool="run_skill_script",
             args={"skill_name": "semdag", "file_path": "scripts/audit.py", "args": []},
             obs=audit_obs("submit" if resolved_like else "revise"), ts=180.0, ct=10),
    ] + ([step(9, author="auditor", tool="submit_patch", ts=181.0)] if resolved_like else [])


def test_lane_report_attribution(make_run, tmp_path):
    rd = make_run("r", [
        {"instance_id": "ok", "resolved": True, "steps": brigade_steps(True), "patch": diff("a.py")},
        {"instance_id": "noplan", "resolved": False, "patch": "",
         "steps": [step(1, source="user", author="user", event_type="task_prompt", ts=1.0),
                   plan_final(2, 5.0, text="I am not sure.")]},
        {"instance_id": "nosubmit", "resolved": False, "steps": brigade_steps(False),
         "patch": diff("a.py")},
        {"instance_id": "wrongfix", "resolved": False, "steps": brigade_steps(True),
         "patch": diff("a.py")},
    ])
    dbp = tmp_path / "t.sqlite"
    ingest.ingest_run(dbp, rd, "R")
    rows = {r["task"]: r for r in lane_report.task_rows(tdb.connect(dbp), "R")}
    assert rows["ok"]["broke_at"] == "none" and rows["ok"]["plan_ok"]
    assert rows["ok"]["edits"] == "1/2" and rows["ok"]["repro_runs"] == 1
    assert rows["ok"]["decisions"] == ["submit"] and rows["ok"]["submitted"]
    assert rows["ok"]["secs"]["planner"] == 30.0 and rows["ok"]["secs"]["executor"] == 35.0
    assert rows["noplan"]["broke_at"] == "planner"
    assert rows["nosubmit"]["broke_at"] == "auditor"
    assert rows["wrongfix"]["broke_at"] == "verify"
    md = lane_report.build(tdb.connect(dbp), "R")
    assert "Resolved 1/4" in md and "Time share by role" in md
