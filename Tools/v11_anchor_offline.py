"""Offline measurement of v11 locate on task snapshots: which join anchored each task, whether the
edit span lies in a gold file or gold function, how often a loop locus fires, and the stdout size.

Measurement only: gold (from per_task.jsonl, derived from each task's patch) is never read by the
submission, and nothing in AgenticSubmission/ is changed from these numbers.

Usage: v11_anchor_offline.py --tasks tasks.jsonl --snapshots DIR --gold per_task.jsonl --out OUT.json
"""
import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "AgenticSubmission", "v11_task_ir", "skills", "semdag", "scripts", "repo_eval.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--snapshots", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    gold = {}
    for line in open(a.gold):
        r = json.loads(line)
        gold[r["instance_id"]] = {"files": set(r.get("gold_files") or []),
                                  "fns": {(g[0], g[1]) if isinstance(g, list) else (g.get("file"), g.get("qual"))
                                          for g in (r.get("gold") or [])}}
    rows = []
    for line in open(a.tasks):
        t = json.loads(line)
        iid = t["instance_id"]
        tgz = os.path.join(a.snapshots, iid + ".tgz")
        if not os.path.exists(tgz):
            continue
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, "repo")
            os.makedirs(repo)
            with tarfile.open(tgz) as tf:
                tf.extractall(repo, filter="data")
            cache = os.path.join(d, "cache")
            t0 = time.time()
            p = subprocess.run([sys.executable, "-I", "-B", SCRIPT, t["problem_statement"]], capture_output=True, text=True,
                               env={"PATH": os.environ["PATH"], "SEMDAG_REPO": repo, "SEMDAG_CACHE": cache}, timeout=300)
            secs = time.time() - t0
            text = p.stdout.strip()
            try:
                state = json.load(open(os.path.join(cache, "task", "task_ir.json")))
            except (OSError, ValueError):
                state = {}
            try:
                top = json.load(open(os.path.join(cache, "task", "eval.json")))["retrieval"]["top"]
                bm1 = (top[0]["file"], top[0]["qualname"]) if top else (None, None)
            except (OSError, ValueError, KeyError):
                bm1 = (None, None)
        anc = state.get("anchor") or {}
        g = gold.get(iid, {"files": set(), "fns": set()})
        rows.append({"id": iid, "how": anc.get("how"), "file": anc.get("file"), "qualname": anc.get("qualname"),
                     "in_gold_file": anc.get("file") in g["files"],
                     "gold_fn": (anc.get("file"), anc.get("qualname")) in g["fns"] if g["fns"] else None,
                     "bm25_top1_gold_fn": bm1 in g["fns"] if g["fns"] else None,
                     "locus": bool(state.get("locus")), "chars": len(text), "secs": round(secs, 2),
                     "error": None if p.returncode == 0 and text.startswith(("edit", "no anchor")) else text[:200]})
    by = {}
    for r in rows:
        b = by.setdefault(r["how"] or "none", {"n": 0, "gold_file": 0, "gold_fn": 0, "gold_fn_known": 0, "locus": 0,
                                               "v6_bm25_top1_gold_fn": 0})
        b["n"] += 1
        b["gold_file"] += r["in_gold_file"]
        if r["gold_fn"] is not None:
            b["gold_fn_known"] += 1
            b["gold_fn"] += r["gold_fn"]
            b["v6_bm25_top1_gold_fn"] += bool(r["bm25_top1_gold_fn"])
        b["locus"] += r["locus"]
    summary = {"tasks": len(rows), "by_anchor": by,
               "max_chars": max((r["chars"] for r in rows), default=0),
               "max_secs": max((r["secs"] for r in rows), default=0),
               "errors": [r for r in rows if r["error"]]}
    json.dump({"summary": summary, "rows": rows}, open(a.out, "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
