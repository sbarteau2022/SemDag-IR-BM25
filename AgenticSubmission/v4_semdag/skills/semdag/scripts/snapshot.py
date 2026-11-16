"""Stage 2 — exec snapshot: capture a rollback-preserving snapshot of the repo
into the SharedContainerCache. Deterministic: file inventory + per-file sha256
+ a single tree hash. Stores content for small text files so a rollback can
restore them without re-reading the working tree. Writes snapshot.json.

Usage: python snapshot.py <container_id> <target_dir>
"""
import os, sys, json, hashlib
import cache

SKIP_DIRS = {".git", "target", "node_modules", ".venv", "venv", "__pycache__",
             ".cache", "dist", "build", ".claude", ".idea", ".vscode",
             ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox"}
MAX_STORE_BYTES = 256 * 1024  # store contents only for small text files

def is_texty(fp: str) -> bool:
    try:
        with open(fp, "rb") as f:
            chunk = f.read(4096)
        return b"\x00" not in chunk
    except Exception:
        return False

def snapshot(container_id: str, target: str) -> dict:
    target = os.path.abspath(target)
    files = {}
    for root, dirs, names in os.walk(target):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(names):
            fp = os.path.join(root, name)
            if not os.path.isfile(fp):  # isfile follows symlinks; os.walk won't loop on dir links
                continue
            rel = os.path.relpath(fp, target)
            try:
                size = os.path.getsize(fp)
                digest = cache.sha256_file(fp)
            except OSError:
                continue
            entry = {"size": size, "sha256": digest}
            if size <= MAX_STORE_BYTES and is_texty(fp):
                with open(fp, "r", errors="replace") as f:
                    entry["content"] = f.read()
            files[rel] = entry
    # Hash the completed inventory in one canonical order.  os.walk ordering is
    # deterministic per directory, but it is not the same as a global path
    # sort when a directory and a sibling file share a prefix.  parity_check()
    # deliberately recomputes from sorted paths, so snapshot creation must use
    # that identical definition.
    tree = hashlib.sha256()
    for rel in sorted(files):
        tree.update(rel.encode()); tree.update(files[rel]["sha256"].encode())
    snap = {"target": target, "file_count": len(files),
            "tree_sha256": tree.hexdigest(), "files": files}
    cache.write(container_id, "snapshot.json", snap)
    cache.mark_stage(container_id, "snapshot",
                     {"files": len(files), "tree_sha256": snap["tree_sha256"]})
    return snap

def restore(container_id: str) -> int:
    """Rollback: rewrite stored file contents back to the target tree."""
    snap = cache.read(container_id, "snapshot.json")
    target = snap["target"]; n = 0
    for rel, e in snap["files"].items():
        if "content" in e:
            fp = os.path.join(target, rel)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w") as f:
                f.write(e["content"])
            n += 1
    return n

if __name__ == "__main__":
    cid, target = sys.argv[1], sys.argv[2]
    s = snapshot(cid, target)
    # compact line to stdout only (agent-facing); full data stays in cache
    print(json.dumps({"stage": "snapshot", "files": s["file_count"],
                      "tree_sha256": s["tree_sha256"]}))
