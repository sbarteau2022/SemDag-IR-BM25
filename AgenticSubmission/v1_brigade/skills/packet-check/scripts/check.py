import hashlib
import json
from pathlib import Path
import sys


def fail(reason: str) -> int:
    print(json.dumps({"ok": False, "error": reason}))
    return 2


def safe_path(value: str) -> bool:
    parts = value.split("/")
    return bool(value) and not value.startswith("/") and "\\" not in value and all(part not in ("", ".", "..") for part in parts)


def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def main() -> int:
    if len(sys.argv) != 2:
        return fail("usage: PACKET_PATH")
    root = Path("/tmp/gemma-brigade").resolve()
    path = Path(sys.argv[1])
    if not path.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        return fail("unsafe or missing packet path")
    try:
        packet = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    except (OSError, UnicodeError, ValueError):
        return fail("packet is unreadable JSON")
    if not isinstance(packet, dict) or packet.get("schema_version") != "0.1.0":
        return fail("invalid packet version")
    digest = packet.get("packet_sha256")
    body = {key: value for key, value in packet.items() if key != "packet_sha256"}
    try:
        expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError):
        return fail("packet contains non-canonical values")
    if digest != expected:
        return fail("packet digest mismatch")
    contract = packet.get("edit_contract", {})
    paths = contract.get("allowed_files", [])
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) or not safe_path(p) for p in paths):
        return fail("unsafe or missing allowed paths")
    if any(p.split("/")[-1] in {"pytest.ini", "conftest.py"} or p.split("/")[-1].startswith("test_") or "tests" in p.split("/") for p in paths):
        return fail("protected file allowed")
    claims = packet.get("outline_claims", [])
    if packet.get("verdict") == "implement" and (not claims or not any(c.get("critical", True) for c in claims) or any(c.get("critical", True) and c.get("verdict") != "supported" for c in claims)):
        return fail("critical outline claim unsupported")
    print(json.dumps({"ok": True, "packet_sha256": digest, "verdict": packet.get("verdict"), "allowed_files": paths}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
