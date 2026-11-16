import sys, time, collections
from common import *
import g_graph, g_synth, g_py, g_agent
fam = sys.argv[1]
ts = load_tasks(); sm = split_map(ts)
ts = sorted(ts, key=lambda t: (SPLITS.index(sm[t["instance_id"]]), t["instance_id"]))   # train-split snapshots claim shared code first
t0 = time.time()
if fam == "graph": rows = g_graph.make_rows(ts, sm, per_type=3)
elif fam == "synth": rows = g_synth.dag_rows({"train": 1600, "dev": 160, "test": 160})
elif fam == "ir": rows = g_synth.ir_rows(ts, sm, per_task=12)
elif fam == "py": rows = g_py.make_rows(ts, max_fn=1500)
elif fam == "agent": rows = g_agent.make_rows(ts, per_task=6)
for r in rows:
    t = r["source"].get("task")
    r["source"]["task_split"] = sm.get(t, "synthetic")
OUT.mkdir(exist_ok=True)
write_jsonl(OUT / f"raw_{fam}.jsonl", rows)
print(fam, len(rows), round(time.time() - t0, 1), "s", dict(collections.Counter(r["split"] for r in rows)), flush=True)
