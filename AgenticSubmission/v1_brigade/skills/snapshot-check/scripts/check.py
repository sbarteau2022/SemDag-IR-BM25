import hashlib
import json
from pathlib import Path
import sys


def safe_path(value: str) -> bool:
    parts = value.split("/")
    return bool(value) and not value.startswith("/") and "\\" not in value and "\x00" not in value and all(part not in ("", ".", "..") for part in parts)


def main() -> int:
    if len(sys.argv) != 4:
        print(json.dumps({"ok": False, "error": "usage: PATH START_LINE END_LINE"}))
        return 2
    raw_path = sys.argv[1]
    relative = Path(raw_path)
    try:
        start, end = int(sys.argv[2]), int(sys.argv[3])
    except ValueError:
        print(json.dumps({"ok": False, "error": "line numbers must be integers"}))
        return 2
    if not safe_path(raw_path) or start < 1 or end < start:
        print(json.dumps({"ok": False, "error": "unsafe path or range"}))
        return 2
    root = Path("/workspace").resolve()
    path = root / relative
    if any((root.joinpath(*relative.parts[:index])).is_symlink() for index in range(1, len(relative.parts) + 1)) or not path.is_file() or not path.resolve().is_relative_to(root):
        print(json.dumps({"ok": False, "error": "missing, linked, or escaping file"}))
        return 2
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    if end > len(lines):
        print(json.dumps({"ok": False, "error": "range beyond file"}))
        return 2
    excerpt = b"".join(lines[start - 1:end])
    print(json.dumps({
        "ok": True, "path": relative.as_posix(), "start_line": start, "end_line": end,
        "file_sha256": hashlib.sha256(data).hexdigest(),
        "source_sha256": hashlib.sha256(excerpt).hexdigest(),
        "file_size_bytes": len(data), "excerpt_size_bytes": len(excerpt),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
