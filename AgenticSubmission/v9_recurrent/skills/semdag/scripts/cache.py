"""SharedContainerCache: one namespace per container ("one probe per container").
All pipeline stages read/write here; the orchestrating agent reads only the
compact results, never the repo text — context is preserved by construction.

Layout:  <root>/<container_id>/{snapshot.json, semdag_ir.json, vulcan_ranking.json, meta.json}
Default root: $SEMDAG_CACHE or ~/.cache/semdag
"""
import os, json, time, hashlib

def cache_root() -> str:
    return os.environ.get("SEMDAG_CACHE", os.path.expanduser("~/.cache/semdag"))

def container_dir(container_id: str) -> str:
    d = os.path.join(cache_root(), container_id)
    os.makedirs(d, exist_ok=True)
    return d

def init_container(container_id: str, target: str) -> dict:
    d = container_dir(container_id)
    meta = {"container_id": container_id, "target": os.path.abspath(target),
            "created": time.time(), "stages": {}}
    write(container_id, "meta.json", meta)
    return meta

def path(container_id: str, name: str) -> str:
    return os.path.join(container_dir(container_id), name)

def write(container_id: str, name: str, obj) -> str:
    p = path(container_id, name)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, sort_keys=True, separators=(",", ":"))
    os.replace(tmp, p)  # atomic
    return p

def read(container_id: str, name: str):
    with open(path(container_id, name)) as f:
        return json.load(f)

def mark_stage(container_id: str, stage: str, info: dict):
    meta = read(container_id, "meta.json")
    meta.setdefault("stages", {})[stage] = {"at": time.time(), **info}
    write(container_id, "meta.json", meta)

def sha256_file(fp: str) -> str:
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
