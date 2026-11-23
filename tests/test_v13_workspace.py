"""v13 component regressions; fixtures do not establish SWE task success."""
import importlib
import os
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "AgenticSubmission/v13_orchestrator/skills/semdag/scripts"

@pytest.fixture
def wm(tmp_path, monkeypatch):
    names = ["workspace_mgr", "wsroot", "impact", "cache", "snapshot", "semdag_ir_ast", "retriever", "flow", "edit_tx", "fix_edit"]
    saved = {n: sys.modules.pop(n) for n in names if n in sys.modules}
    monkeypatch.syspath_prepend(str(SCRIPTS))
    mod = importlib.import_module("workspace_mgr")
    monkeypatch.setattr(mod, "WS_PREFIX", str(tmp_path / "ws_"))
    yield mod
    for n in names:
        sys.modules.pop(n, None)
    sys.modules.update(saved)

@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "central"
    p.mkdir()
    (p / "source.py").write_bytes((SCRIPTS / "retriever.py").read_bytes())
    return p


def test_independent_edit_collect_apply_reset(wm, repo):
    before = (repo / "source.py").read_bytes()
    for slot in ["1", "2"]:
        wm._spawn_copy(slot, "source.py", "1-20", repo=str(repo))
    first = Path(wm._ws_dir("1")) / "source.py"
    second = Path(wm._ws_dir("2")) / "source.py"
    first.write_bytes(before + b"\n# changed in slot one\n")
    assert (repo / "source.py").read_bytes() == before
    assert second.read_bytes() == before
    patch = wm.collect("1", repo=str(repo))
    assert not patch["empty"] and patch["files"] == ["source.py"]
    assert not wm.apply_ws("1", repo=str(repo))["ok"]
    assert (repo / "source.py").read_bytes() == before
    assert second.read_bytes() == before
    wm.reset("1")
    assert not first.parent.exists() and second.exists()

@pytest.mark.parametrize("slot", ["", "../2", "/tmp/x", "1/../../x", ".", "a" * 65])
def test_bad_slots_refused(wm, slot):
    with pytest.raises(ValueError):
        wm._ws_dir(slot)

@pytest.mark.parametrize("rel", ["../outside.py", "/etc/passwd"])
def test_bad_targets_refused(wm, repo, rel):
    with pytest.raises(ValueError):
        wm._spawn_copy("1", rel, "1-2", repo=str(repo))


def test_symlink_copy_and_apply_refused(wm, repo, tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("untouched")
    (repo / "link.py").symlink_to(outside)
    with pytest.raises(ValueError):
        wm._spawn_copy("1", "source.py", "1-2", repo=str(repo))
    (repo / "link.py").unlink()
    wm._spawn_copy("1", "source.py", "1-2", repo=str(repo))
    (Path(wm._ws_dir("1")) / "link.py").symlink_to(outside)
    assert not wm.apply_ws("1", repo=str(repo))["ok"]
    assert outside.read_text() == "untouched"


def test_protected_and_binary_files_not_collected(wm, repo):
    wm._spawn_copy("1", "source.py", "1-2", repo=str(repo))
    slot = Path(wm._ws_dir("1"))
    (slot / "tests").mkdir()
    (slot / "tests/test_fix.py").write_text("assert False")
    (slot / "conftest.py").write_text("raise RuntimeError")
    (slot / "blob.bin").write_bytes(b"\xff\x00")
    assert wm.collect("1", repo=str(repo))["empty"]


def test_literal_slot_resolves_to_sandbox_tmp(wm, repo, monkeypatch, tmp_path):
    sandbox_tmp = tmp_path / "task_tmp"
    (sandbox_tmp / "ws_1").mkdir(parents=True)
    monkeypatch.setattr(wm.wsroot.tempfile, "gettempdir", lambda: str(sandbox_tmp))
    assert wm.wsroot.workspace_root("/tmp/ws_1") == str(sandbox_tmp / "ws_1")
    with pytest.raises(ValueError):
        wm.wsroot.workspace_root(str(tmp_path / "missing"))


def test_packed_workspace_arguments(wm, repo):
    import shlex
    packed = "--spawn 1 --file source.py --lines 1-20 --issue 'keep spaces' --repo " + shlex.quote(str(repo))
    packed += " --check 'python -c pass'"
    result = wm.main([packed])
    assert result["ok"]
    assert "keep spaces" in (Path(wm._ws_dir("1")) / "Agents.md").read_text()
    assert wm.main(["--collect", "1", "--repo", str(repo)])["empty"]
    with pytest.raises(SystemExit):
        wm.main(["--spawn 'unterminated"])


def test_bad_literal_slot_alias_refused(wm):
    with pytest.raises(ValueError):
        wm.wsroot.workspace_root("/tmp/ws_1/../ws_2")
