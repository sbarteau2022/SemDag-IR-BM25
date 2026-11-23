#!/usr/bin/env python3
"""Report whether the sandbox can run repository tests, and suggest a fallback."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil


def main() -> None:
    modules = {}
    for name in ("pytest", "inline_snapshot", "dirty_equals"):
        spec = importlib.util.find_spec(name)
        modules[name] = spec is not None

    pytest_exe = shutil.which("pytest") or shutil.which("python")
    can_pytest = modules["pytest"] and bool(pytest_exe)

    if can_pytest:
        message = "pytest is available; run test_cmd from --verify."
    else:
        message = (
            "pytest is unavailable. Do not run test_cmd. Fall back to compile/import "
            "checks: python -m compileall on changed files and a minimal repro script."
        )

    print(
        json.dumps(
            {"pytest_available": can_pytest, "modules": modules, "next": message},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
