import json
from pathlib import Path
import subprocess
import sys


def fail(reason: str) -> int:
    print(json.dumps({"ok": False, "error": reason}))
    return 2


def safe_path(value: str) -> bool:
    parts = value.split("/")
    return bool(value) and not value.startswith("/") and "\\" not in value and "\x00" not in value and all(part not in ("", ".", "..") for part in parts)


def main() -> int:
    allowed = set(sys.argv[1:])
    if not allowed or any(not safe_path(path) for path in allowed):
        return fail("missing or unsafe allowlist")
    result = subprocess.run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd="/workspace", capture_output=True, check=False)
    if result.returncode:
        return fail("git status failed")
    entries = result.stdout.split(b"\0")
    changed = []
    for entry in entries:
        if not entry:
            continue
        if len(entry) < 4:
            return fail("malformed status entry")
        status = entry[:2]
        if b"R" in status or b"C" in status or b"U" in status:
            return fail("rename, copy, or unresolved merge requires manual disposition")
        path = entry[3:].decode("utf-8", errors="surrogateescape")
        if not safe_path(path):
            return fail("unsafe changed path")
        if (Path("/workspace") / path).is_symlink():
            return fail("changed symlink forbidden")
        changed.append(path)
    if not changed:
        return fail("empty diff")
    if any(path not in allowed for path in changed):
        return fail("changed path outside allowlist")
    if any(path.split("/")[-1] in {"pytest.ini", "conftest.py"} or path.split("/")[-1].startswith("test_") or "tests" in path.split("/") for path in changed):
        return fail("protected changed path")
    print(json.dumps({"ok": True, "changed_paths": sorted(changed)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
