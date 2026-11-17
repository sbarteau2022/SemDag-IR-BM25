"""Print a markdown telemetry report for one run from the SQLite store.

Usage: report.py --db results/telemetry.sqlite --run-id ID [--out FILE.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db as tdb  # noqa: E402


def pct(values, q):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    k = min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))
    return v[k]


def fmt(x, nd=2):
    if x is None:
        return "-"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def build(con, run_id: str) -> str:
    run = con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    tasks = [dict(r) for r in con.execute(
        "SELECT * FROM tasks WHERE run_id=? ORDER BY t_start, instance_id", (run_id,))]
    calls = [dict(r) for r in con.execute("SELECT * FROM llm_calls WHERE run_id=?", (run_id,))]
    tools = [dict(r) for r in con.execute(
        "SELECT * FROM v_tool_pass_fail WHERE run_id=? ORDER BY calls DESC", (run_id,))]
    think = [r["thinking_tokens"] for r in con.execute(
        "SELECT thinking_tokens FROM steps WHERE run_id=? AND event_type='thinking'", (run_id,))]
    sampling = json.loads(run["sampling_json"] or "{}") if run else {}
    budget = (sampling.get("thinking_config") or {}).get("thinking_budget")
    if budget is None:  # per-role sampling files
        budget = max(((c.get("thinking_config") or {}).get("thinking_budget") or 0
                      for c in sampling.values() if isinstance(c, dict)), default=None) or None

    n = len(tasks)
    res = sum(t["resolved"] for t in tasks)
    L = [f"# Telemetry: {run_id}", ""]
    if run:
        L += [f"- Arm: `{run['arm']}`; submission `{run['submission_dir']}` "
              f"(sha256 `{(run['submission_sha256'] or '')[:12]}`); git `{(run['git_head'] or '')[:10]}`",
              f"- Sandbox: {run['sandbox']}; seatbelt (no network): {bool(run['seatbelt'])}; "
              f"model: `{run['model']}`",
              f"- Budget: `{run['budget_json']}`; sampling: `{run['sampling_json']}`", ""]
    L += [f"**Resolved {res}/{n}**" + (f" ({100 * res / n:.1f}%)" if n else ""), ""]

    def col(k):
        return [t[k] for t in tasks]

    L += ["## Per-task distribution (median / p90 / max)", "",
          "| metric | median | p90 | max |", "|---|---|---|---|"]
    for k in ["duration_s", "steps", "agent_steps", "tool_calls", "tool_errors",
              "prompt_tokens", "completion_tokens", "peak_prompt_tokens", "peak_context_frac",
              "thinking_tokens", "compactions", "first_edit_s"]:
        v = col(k)
        L.append(f"| {k} | {fmt(pct(v, .5))} | {fmt(pct(v, .9))} | "
                 f"{fmt(max([x for x in v if x is not None], default=None))} |")
    L.append("")

    if calls:
        ttft = [c["ttft_s"] for c in calls]
        dec = [c["decode_tok_per_s"] for c in calls]
        L += ["## Model calls (proxy)", "",
              f"- Calls: {len(calls)}; errors: {sum(1 for c in calls if c['error'])}; "
              f"attached to tasks: {sum(1 for c in calls if c['instance_id'])}",
              f"- TTFT s: p50 {fmt(pct(ttft, .5))}, p90 {fmt(pct(ttft, .9))}, max {fmt(pct(ttft, 1))}",
              f"- Decode tok/s: p50 {fmt(pct(dec, .5), 1)}, p10 {fmt(pct(dec, .1), 1)}",
              f"- Finish reasons: {_count(c['finish_reason'] for c in calls)}", ""]

    if think:
        over = sum(1 for t in think if budget and t and t > budget)
        L += ["## Thinking budget (per model step)", "",
              f"- Budget (scorer-enforced, not enforced by local MLX): {budget}",
              f"- Thinking tokens per step: p50 {fmt(pct(think, .5))}, p90 {fmt(pct(think, .9))}, "
              f"max {fmt(pct(think, 1))}; steps over budget: {over}/{len(think)}", ""]

    L += ["## Tools (pass / fail)", "", "| tool | script | calls | ok | failed | mean s |",
          "|---|---|---|---|---|---|"]
    for t in tools:
        L.append(f"| {t['name']} | {t['skill_script'] or ''} | {t['calls']} | {t['ok']} | "
                 f"{t['failed']} | {fmt(t['mean_s'])} |")
    L.append("")

    L += ["## Failure classes", "", f"{_count(t['failure_class'] for t in tasks)}", "",
          "## Per task", "",
          "| task | class | s | steps | calls | tool err | peak ctx | think tok | tests | repro |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for t in tasks:
        L.append(f"| {t['instance_id']} | {t['failure_class']} | {fmt(t['duration_s'], 0)} | "
                 f"{t['steps']} | {t['tool_calls']} | {t['tool_errors']} | "
                 f"{fmt(t['peak_context_frac'])} | {fmt(t['thinking_tokens'])} | "
                 f"{t['ran_tests']} | {t['repro_before_edit']} |")
    return "\n".join(L) + "\n"


def _count(it):
    out = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    text = build(tdb.connect(a.db), a.run_id)
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
