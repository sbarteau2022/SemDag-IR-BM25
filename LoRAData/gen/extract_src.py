"""Stream each snapshot tgz once; keep only .py files outside .git. Content-addressed blobs shared across snapshots."""
import json, sys, tarfile
from multiprocessing import Pool
from common import *

def work(t):
    iid = t["instance_id"]
    idxp = CACHE / "index" / f"{iid}.json"
    if idxp.exists():
        return iid, "cached"
    tgz = DATA / "snapshots" / f"{iid}.tgz"
    if not tgz.exists():
        return iid, "missing"
    idx = {}
    with tarfile.open(tgz, "r|gz") as tf:
        for m in tf:
            n = m.name[2:] if m.name.startswith("./") else m.name
            if not m.isfile() or n.startswith(".git/") or not n.endswith(".py") or m.size > 400_000:
                continue
            b = tf.extractfile(m).read()
            h = sha(b, 20)
            bp = CACHE / "blobs" / h
            if not bp.exists():
                bp.write_bytes(b)
            idx[n] = h
    idxp.write_text(json.dumps(idx, sort_keys=True))
    return iid, len(idx)

if __name__ == "__main__":
    tasks = load_tasks()
    with Pool(3) as p:
        for iid, r in p.imap_unordered(work, tasks):
            print(iid, r, flush=True)
