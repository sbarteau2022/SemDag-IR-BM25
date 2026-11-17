"""Build a local arm64 wheel overlay for Apple-silicon Docker runs (local evaluation only).

Why: the harness unpacks every cp313 wheel from the folder beside tasks.jsonl straight into
the container's site-packages, without checking the CPU architecture. The public wheel cache
holds x86_64-only builds of some compiled packages (pydantic_core 2.46.4), so on an arm64
sandbox the arm64 copy baked into the image stays loaded and pydantic refuses to import
(run_11: every fastapi task ungradable). The scorer runs x86_64 and is not affected.

What it builds (DataSets is git-ignored; the official folder is never modified):
  DataSets/local_overlay/data/tasks.jsonl -> symlink to the public tasks.jsonl
  DataSets/local_overlay/data/wheels/     -> symlinks to every public wheel, except that each
                                            x86_64 wheel with an arm64 twin in
                                            DataSets/local_overlay/wheels/ is replaced by it
It also lists the remaining x86_64-only compiled cp313 wheels (candidates for the same bug).

Usage: build_wheel_overlay.py [--root .]
Then run with TASKS=DataSets/local_overlay/data/tasks.jsonl (see Tools/run_eval_seatbelt.sh).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def key(name: str):
    """(distribution, version, python tag) of a wheel filename, or None."""
    parts = name[:-4].split("-")
    return (parts[0].lower(), parts[1], parts[2]) if name.endswith(".whl") and len(parts) >= 5 else None


def build(root: Path) -> dict:
    pub = root / "DataSets/public/data"
    arm_src = root / "DataSets/local_overlay/wheels"
    out = root / "DataSets/local_overlay/data"
    wheels = out / "wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    for old in wheels.iterdir():
        if old.is_symlink():
            old.unlink()
    arm = {key(p.name): p for p in sorted(arm_src.glob("*aarch64*.whl"))}
    replaced, linked, x86_only = [], 0, []
    for w in sorted((pub / "wheels").glob("*.whl")):
        k = key(w.name)
        if "x86_64" in w.name and k in arm:
            target = arm[k]
            replaced.append({"x86_64": w.name, "aarch64": target.name})
        else:
            target = w
            if "x86_64" in w.name and k and k[2] == "cp313":
                x86_only.append(w.name)
        (wheels / target.name).symlink_to(target.resolve())
        linked += 1
    tasks = out / "tasks.jsonl"
    if tasks.is_symlink() or tasks.exists():
        tasks.unlink()
    tasks.symlink_to((pub / "tasks.jsonl").resolve())
    receipt = {"wheels_linked": linked, "replaced": replaced, "x86_64_only_cp313": x86_only}
    (out / "overlay_receipt.json").write_text(json.dumps(receipt, indent=1))
    return receipt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    r = build(Path(ap.parse_args().root).resolve())
    print(json.dumps({"wheels_linked": r["wheels_linked"], "replaced": r["replaced"],
                      "x86_64_only_cp313": len(r["x86_64_only_cp313"])}, indent=1))


if __name__ == "__main__":
    main()
