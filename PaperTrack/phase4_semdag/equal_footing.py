"""Paired bootstrap contrasts on equal footing: both arms with the test-file filter (X vs Af),
and both without it (X with tests kept vs A as shipped). Reads the outputs of measure.py,
measure_v2.py, and a P4_KEEP_TESTS=1 run of measure_v2.py written to <out>_keep_tests.
"""
import json
import os
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("P4_OUT", HERE / "out"))
KEEP = Path(os.environ.get("P4_OUT_KEEP", str(OUT) + "_keep_tests"))


def load(p):
    return {json.loads(l)["instance_id"]: json.loads(l) for l in open(p)}


v1 = {i: r for i, r in load(OUT / "per_task.jsonl").items() if "arms" in r}
v2 = load(OUT / "v2_per_task.jsonl")
kt = load(KEEP / "v2_per_task.jsonl")
ev = [i for i, r in v2.items() if r["gold_n"]]
held = [i for i in ev if v2[i]["repo"].endswith("rich")]
hit = lambda v, k: (v or 10 ** 6) <= k
get = {"X": lambda i: v2[i]["arms"]["X"]["first_fn"], "D15": lambda i: v2[i]["arms"]["D15"]["first_fn"],
       "Af": lambda i: v1[i]["arms"]["Af"]["first_fn"], "A": lambda i: v1[i]["arms"]["A"]["first_fn"],
       "Xall": lambda i: kt[i]["arms"]["X"]["first_fn"]}
rng = random.Random(0)


def boot(ids, x, y, k):
    pt = sum(hit(get[x](i), k) - hit(get[y](i), k) for i in ids) / len(ids)
    ds = []
    for _ in range(4000):
        smp = [ids[rng.randrange(len(ids))] for _ in ids]
        ds.append(sum(hit(get[x](i), k) - hit(get[y](i), k) for i in smp) / len(smp))
    ds.sort()
    return {"diff": round(pt, 4), "ci95": [round(ds[100], 4), round(ds[3899], 4)]}


count = lambda arm, ids: [sum(hit(get[arm](i), k) for i in ids) for k in (1, 5, 10)]
dg = [r["ppr_diag"]["A"] for r in v1.values() if r.get("gold") and "A" in r["ppr_diag"]]
out = {"X-Af fn@5 all (both filtered)": boot(ev, "X", "Af", 5), "X-Af fn@5 heldout": boot(held, "X", "Af", 5),
       "X-Af fn@10 all": boot(ev, "X", "Af", 10),
       "Xall-A fn@5 all (both unfiltered)": boot(ev, "Xall", "A", 5), "Xall-A fn@5 heldout": boot(held, "Xall", "A", 5),
       "D15-Af fn@5 all": boot(ev, "D15", "Af", 5),
       "counts": {"Af_all": count("Af", ev), "Af_heldout": count("Af", held),
                  "Af_selection": count("Af", [i for i in ev if i not in held]),
                  "Xall_all": count("Xall", ev), "Xall_heldout": count("Xall", held), "A_heldout": count("A", held)},
       "ppr_A": {"mean_mass_on_test_functions": round(statistics.mean(d["mass_on_test_functions"] for d in dg), 3),
                 "mean_test_fns_in_top10": round(statistics.mean(d["test_fns_in_top10"] for d in dg), 2)}}
json.dump(out, open(OUT / "equal_footing.json", "w"), indent=1)
print(json.dumps(out, indent=1))
