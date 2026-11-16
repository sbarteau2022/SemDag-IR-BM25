#!/usr/bin/env python3
"""PR-Edit-style harness for measuring edit success (item 1 hardening).

Input: a JSON file with entries {"file", "original", "target", "edit"} where
  original = full file text before
  target   = full file text after the correct edit
  edit     = {"old": ..., "new": ...} candidate produced by a model/editor
Output: count of exact-byte matches and mean reward.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def exact_after(original: str, old: str, new: str) -> bool:
    if old not in original:
        return False
    out = original.replace(old, new, 1)
    return (
        out == original
    )  # replaced with exact candidate? caller passes comparison separately


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", type=Path)
    args = ap.parse_args()
    data = json.loads(args.cases.read_text())
    ok = 0
    total = 0
    for c in data:
        total += 1
        try:
            got = c["original"].replace(c["edit"]["old"], c["edit"]["new"], 1)
        except Exception:
            got = None
        if got == c["target"]:
            ok += 1
    print(
        json.dumps(
            {
                "total": total,
                "exact_success": ok,
                "rate": (ok / total if total else 0.0),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
EOF
