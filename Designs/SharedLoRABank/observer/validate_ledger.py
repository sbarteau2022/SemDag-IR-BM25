"""Validate an observer ledger against its catalog and artifact bytes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ledger import load_jsonl, sha256_bytes, validate


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: validate_ledger.py ledger.jsonl catalog.json artifacts_dir")
        return 2
    events = load_jsonl(Path(sys.argv[1]))
    catalog = json.loads(Path(sys.argv[2]).read_text())
    artifacts = {}
    for item in Path(sys.argv[3]).iterdir():
        if item.is_file():
            blob = item.read_bytes()
            artifacts[sha256_bytes(blob)] = blob
    errors = validate(events, catalog, artifacts)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"ok events={len(events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
