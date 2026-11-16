"""Join harness results from two agent arms on the same tasks and print a paired report.

Usage: paired_report.py --base DIR [DIR ...] --test DIR [DIR ...] [--ids FILE ...] [--json OUT]
Each DIR is a swegemma results dir (task_results.jsonl, patches/). Only tasks present in
both arms are reported. A task "resolved" with an empty agent patch is counted separately:
its tests pass with no change, so it cannot tell agents apart.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(dirs):
    out = {}
    for d in dirs:
        p = Path(d) / "task_results.jsonl"
        if p.exists():
            for line in p.read_text().splitlines():
                r = json.loads(line)
                out[r["instance_id"]] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", nargs="+", required=True)
    ap.add_argument("--test", nargs="+", required=True)
    ap.add_argument("--ids", nargs="*", default=[])
    ap.add_argument("--json")
    a = ap.parse_args()
    b, t = load(a.base), load(a.test)
    ids = [i for f in a.ids for i in Path(f).read_text().split()] or sorted(set(b) & set(t))
    ids = [i for i in ids if i in b and i in t]

    def stats(rs):
        n = len(rs)
        return {"tasks": n,
                "resolved": sum(r["resolved"] for r in rs),
                "resolved_nonempty_patch": sum(1 for r in rs if r["resolved"] and r["agent_patch_size"] > 0),
                "empty_patch": sum(1 for r in rs if r["agent_patch_size"] == 0),
                "errors": sum(1 for r in rs if r.get("error")),
                "mean_tool_calls": round(sum(r["tool_calls"] for r in rs) / max(1, n), 2),
                "mean_llm_calls": round(sum(r["total_llm_calls"] for r in rs) / max(1, n), 2),
                "mean_seconds": round(sum(r["duration_seconds"] for r in rs) / max(1, n), 1)}
    B, T = [b[i] for i in ids], [t[i] for i in ids]
    rep = {"paired_tasks": len(ids), "base": stats(B), "test": stats(T),
           "both": sum(1 for x, y in zip(B, T) if x["resolved"] and y["resolved"]),
           "base_only": [x["instance_id"] for x, y in zip(B, T) if x["resolved"] and not y["resolved"]],
           "test_only": [x["instance_id"] for x, y in zip(B, T) if y["resolved"] and not x["resolved"]],
           "resolved_by_empty_patch_in_either": [x["instance_id"] for x, y in zip(B, T)
                                                 if (x["resolved"] and x["agent_patch_size"] == 0)
                                                 or (y["resolved"] and y["agent_patch_size"] == 0)]}
    print(f"{'task':16} {'base':>22} {'test':>22}")
    for x, y in zip(B, T):
        f = lambda r: f"{'PASS' if r['resolved'] else 'fail'} patch={r['agent_patch_size']:<5} calls={r['tool_calls']:<3}"
        print(f"{x['instance_id']:16} {f(x):>22} {f(y):>22}")
    print(json.dumps(rep, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
