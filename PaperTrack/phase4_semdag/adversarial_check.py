"""Adversarial contract checks for the production SemDAG retriever.

This is intentionally a standalone verification script rather than a harness
test file: scored task patches must never contain test-file modifications.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SEMDAG = Path(os.environ.get("P4_SEMDAG", ROOT / "AgenticSubmission/v4_semdag/skills/semdag/scripts"))
sys.path.insert(0, str(SEMDAG))

import cache  # noqa: E402
import repo_eval  # noqa: E402
import retriever  # noqa: E402
import semdag_ir_ast  # noqa: E402
import snapshot  # noqa: E402


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def main():
    with tempfile.TemporaryDirectory(prefix="semdag_adversarial_") as td:
        root = Path(td) / "repo"
        write(root / "pkg/__init__.py", "from .util import helper\n\ndef entry(value):\n    return helper(value)\n")
        write(root / "pkg/util.py", "def helper(value):\n    return value + 1\n")
        write(root / "other.py", "def helper(value):\n    return value - 1\n")
        write(root / "test_pkg.py", "from pkg import entry\n\ndef test_entry():\n    assert entry(1) == 2\n")
        write(root / ".adk_exec_probe.py", "def wrapper():\n    return helper('value')\n")
        write(root / "semdag/internal.py", "def helper(value):\n    return 'tool-only'\n")
        write(root / "z_file.py", "def unrelated():\n    return 'noise'\n")

        os.environ["SEMDAG_CACHE"] = str(Path(td) / "cache")
        cache.init_container("fixture", str(root))
        snap = snapshot.snapshot("fixture", str(root))
        ir = semdag_ir_ast.build("fixture")
        parity = repo_eval.parity_check("fixture", snap, ir)
        assert parity["ok"], parity

        edges = {(e["src"], e["dst"], e["rel"], e.get("resolution")) for e in ir["edges"]}
        entry = next(n["id"] for n in ir["nodes"] if n.get("qualname") == "entry")
        pkg_helper = next(n["id"] for n in ir["nodes"] if n.get("qualname") == "helper" and n["file"] == "pkg/util.py")
        other_helper = next(n["id"] for n in ir["nodes"] if n.get("qualname") == "helper" and n["file"] == "other.py")
        assert (entry, pkg_helper, "calls", "from_import") in edges
        assert not any(s == entry and d == other_helper and rel == "calls" for s, d, rel, _ in edges)
        assert {"contains", "calls", "imports"} <= {e["rel"] for e in ir["edges"]}

        issue = "pkg.util helper called by entry should add one to value"
        first = retriever.rank(ir, snap, issue, top_n=5)
        second = retriever.rank(ir, snap, issue, top_n=5)
        assert first == second
        assert first["top"][0]["id"] == pkg_helper, first["top"]
        assert all(not retriever.is_test_path(site["file"]) for site in first["top"])
        assert all(not retriever.is_tool_path(site["file"]) for site in first["top"])
        assert {"contains", "calls", "imports"} <= set(first["relations_used"])

        lexical = retriever.rank(ir, snap, issue, top_n=5, damping=0.0)
        assert all(site["lexical_rank"] == i + 1 for i, site in enumerate(lexical["top"]))

        print(json.dumps({"ok": True, "parity": parity["ok"], "counts": ir["counts"],
                          "relations_used": first["relations_used"],
                          "top": [f"{s['file']}::{s['qualname']}" for s in first["top"]]}, indent=2))


if __name__ == "__main__":
    main()
