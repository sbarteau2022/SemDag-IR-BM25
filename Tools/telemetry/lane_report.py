"""Per-role breakdown of a brigade run: where each task broke (planner, executor, auditor).

Usage: lane_report.py --db results/telemetry.sqlite --run-id ID [--ref-run ID] [--out FILE.md]

Reads only the telemetry store (`steps`, `tool_calls`, `tasks`). Per task:
  - rounds        planner turns that ended with a PLAN block
  - plan_ok       every planner round produced a PLAN block
  - meta_ok       meta.py returned a report without "error"
  - repro_runs    executor run_command calls touching /tmp (reproduction attempts)
  - edit_fail     executor edit_file failures / attempts
  - decisions     audit.py decisions in order (submit / submit_best / revise)
  - submitted     submit_patch was called
  - role seconds  wall time attributed to each role: time from the previous step to this step
  - role tokens   completion tokens per role
  - broke_at      first role that failed its job, in pipeline order:
                    planner  no PLAN, or meta.py error
                    executor no successful edit, or every repro attempt still failing
                    auditor  never ran audit.py, or ran it and the task still was not submitted
                    verify   submitted but not resolved (the change was wrong; audit could not tell)
                    none     resolved
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db as tdb  # noqa: E402

ROLES = ("planner", "executor", "auditor")


def _obs_json(text):
    try:
        outer = json.loads(text or "")
    except ValueError:
        return {}
    if isinstance(outer, dict) and isinstance(outer.get("stdout"), str):
        try:
            return json.loads(outer["stdout"].strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {}
    return outer if isinstance(outer, dict) else {}


def task_rows(con, run_id):
    tasks = {r["instance_id"]: dict(r) for r in con.execute(
        "SELECT * FROM tasks WHERE run_id=?", (run_id,))}
    out = []
    for iid, t in sorted(tasks.items()):
        steps = [dict(r) for r in con.execute(
            "SELECT * FROM steps WHERE run_id=? AND instance_id=? ORDER BY CAST(step_id AS INTEGER)",
            (run_id, iid))]
        secs = {r: 0.0 for r in ROLES}
        toks = {r: 0 for r in ROLES}
        rounds = plans = meta_err = repro = 0
        edit_try = edit_fail = 0
        decisions, submitted, prev_ts = [], False, None
        for s in steps:
            role = s["author"] if s["author"] in ROLES else None
            if prev_ts is not None and s["ts"] is not None and role:
                secs[role] += max(0.0, s["ts"] - prev_ts)
            if s["ts"] is not None:
                prev_ts = s["ts"]
            if role:
                toks[role] += s["completion_tokens"] or 0
            name, args = s["tool_name"], s["tool_args"] or ""
            if role == "planner" and s["event_type"] == "final":
                rounds += 1
                plans += "PLAN" in (s.get("message_text") or "")
            if name == "run_skill_script" and "meta.py" in args:
                meta_err += "error" in _obs_json(s["observation"])
            if role == "executor" and name == "run_command" and "/tmp" in args:
                repro += 1
            if role == "executor" and name == "edit_file":
                edit_try += 1
                edit_fail += '"status": "error"' in (s["observation"] or "")
            if name == "run_skill_script" and "audit.py" in args:
                d = _obs_json(s["observation"]).get("decision")
                if d:
                    decisions.append(d)
            if name == "submit_patch":
                submitted = True
        out.append({"task": iid, "resolved": bool(t["resolved"]), "class": t["failure_class"],
                    "rounds": rounds, "plan_ok": rounds > 0 and plans == rounds,
                    "meta_ok": meta_err == 0, "repro_runs": repro,
                    "edits": f"{edit_try - edit_fail}/{edit_try}", "edit_fail": edit_fail,
                    "decisions": decisions, "submitted": submitted, "secs": secs, "toks": toks,
                    "duration": t["duration_s"], "peak_ctx": t["peak_context_frac"],
                    "patch_bytes": t["patch_bytes"],
                    "broke_at": _broke_at(t, rounds, plans, meta_err, edit_try, edit_fail,
                                          decisions, submitted)})
    return out


def _broke_at(t, rounds, plans, meta_err, edit_try, edit_fail, decisions, submitted):
    if t["resolved"]:
        return "none"
    if rounds == 0 or plans == 0 or meta_err:
        return "planner"
    if edit_try == 0 or edit_try == edit_fail or not t["patch_bytes"]:
        return "executor"
    if not decisions or not submitted:
        return "auditor"
    return "verify"


def build(con, run_id, ref_run=None):
    rows = task_rows(con, run_id)
    ref = {}
    if ref_run:
        ref = {r["instance_id"]: r for r in con.execute(
            "SELECT instance_id, resolved, failure_class FROM tasks WHERE run_id=?", (ref_run,))}
    n, res = len(rows), sum(r["resolved"] for r in rows)
    L = [f"# Lane report: {run_id}", "", f"**Resolved {res}/{n}**"
         + (f" (reference {ref_run}: {sum(ref[r['task']]['resolved'] for r in rows if r['task'] in ref)}"
            f"/{sum(1 for r in rows if r['task'] in ref)} on the same tasks)" if ref else ""), ""]
    broke = {}
    for r in rows:
        broke[r["broke_at"]] = broke.get(r["broke_at"], 0) + 1
    L += [f"Broke at: {broke}", "",
          "| task | resolved | ref | broke at | rounds | plan ok | repro runs | edits ok/tried | audit decisions | submitted | s plan/exec/audit | tok plan/exec/audit | peak ctx |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        rr = ref.get(r["task"])
        L.append(
            f"| {r['task']} | {'YES' if r['resolved'] else 'no'} | "
            f"{('YES' if rr['resolved'] else rr['failure_class']) if rr else '-'} | {r['broke_at']} | "
            f"{r['rounds']} | {int(r['plan_ok'])} | {r['repro_runs']} | {r['edits']} | "
            f"{','.join(r['decisions']) or '-'} | {int(r['submitted'])} | "
            f"{r['secs']['planner']:.0f}/{r['secs']['executor']:.0f}/{r['secs']['auditor']:.0f} | "
            f"{r['toks']['planner']}/{r['toks']['executor']}/{r['toks']['auditor']} | "
            f"{(r['peak_ctx'] or 0):.2f} |")
    tot = {k: sum(r["secs"][k] for r in rows) for k in ROLES}
    all_s = sum(tot.values()) or 1
    L += ["", "Time share by role: " + ", ".join(f"{k} {100 * v / all_s:.0f}%" for k, v in tot.items())]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--ref-run")
    ap.add_argument("--out")
    a = ap.parse_args()
    text = build(tdb.connect(a.db), a.run_id, a.ref_run)
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
