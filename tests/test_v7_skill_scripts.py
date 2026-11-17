"""v7 brigade skill scripts (meta.py preflight, audit.py sign-off) against a throwaway repo.

Each test builds a tiny git repository with a planted bug, points the scripts at it through
SEMDAG_REPO, and isolates their cache through TMPDIR. The scripts are run as subprocesses,
exactly as run_skill_script would, and their single JSON line is parsed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "AgenticSubmission" / "v7_brigade_lite" / "skills" / "semdag" / "scripts"
ISSUE = "add returns the wrong result: add(2, 3) should be 5 but calc.add subtracts"
BUGGY = 'def add(a, b):\n    """Return the sum."""\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n'
TESTS = ("from pkg.calc import add, mul\n\n\ndef test_add():\n    assert add(2, 3) == 5\n\n\n"
         "def test_mul():\n    assert mul(2, 3) == 6\n")
REPRO = "python -c 'from pkg.calc import add; assert add(2, 3) == 5'"


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "pkg").mkdir(parents=True)
    (r / "tests").mkdir()
    (r / "pkg" / "__init__.py").write_text("")
    (r / "pkg" / "calc.py").write_text(BUGGY)
    (r / "tests" / "test_calc.py").write_text(TESTS)
    git(r, "init", "-q")
    git(r, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(r, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    git(r, "branch", "_swegemma_baseline")
    (tmp_path / "cache").mkdir()
    return r


def run(script, repo, *args):
    env = dict(os.environ, SEMDAG_REPO=str(repo), TMPDIR=str(repo.parent / "cache"))
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=repo.parent,
                       env=env, capture_output=True, text=True, timeout=180)
    lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    assert lines, p.stderr[-2000:]
    return json.loads(lines[-1])


def edit(repo, new):
    (repo / "pkg" / "calc.py").write_text(BUGGY.replace("return a - b", new))


def test_meta_preflight_report(repo):
    out = run("meta.py", repo, ISSUE)
    assert "error" not in out, out
    assert out["ready"]["pytest"] is True
    assert out["checkpoint_ref"] == "_swegemma_baseline"
    top = out["sites"][0]
    assert top["file"] == "pkg/calc.py" and top["qualname"].endswith("add")
    assert "return a - b" in top["source"]          # exact current text for the first edit
    bt = out["baseline_tests"]
    assert bt["red_reason"] == "assertion" and bt["failed"] >= 1 and bt["collected"] >= 1
    assert out["test_cmd"].startswith("python -m pytest tests/test_calc.py")
    assert len(json.dumps(out)) <= 6000
    again = run("meta.py", repo, ISSUE)
    assert again.get("cached") is True and again["sites"] == out["sites"]


def test_meta_without_issue_text(repo):
    out = run("meta.py", repo)
    assert "error" in out and "hint" in out


def test_audit_green_fix_submits(repo):
    run("meta.py", repo, ISSUE)
    edit(repo, "return a + b")
    out = run("audit.py", repo, "--repro", REPRO)
    assert out["decision"] == "submit" and out["green"] is True, out
    assert out["tests"]["collected"] >= 1 and out["tests"]["red_reason"] is None
    assert out["repro"]["green"] is True
    assert out["patch_files"] == ["pkg/calc.py"]


def test_audit_empty_patch_revises(repo):
    run("meta.py", repo, ISSUE)
    out = run("audit.py", repo)
    assert out["decision"] == "revise"
    assert any("patch is empty" in r for r in out["reasons"])


def test_two_strike_identical_retry_then_submit_best(repo):
    run("meta.py", repo, ISSUE)
    edit(repo, "return a - b + 0")                 # unbroken but still wrong
    first = run("audit.py", repo, "--repro", REPRO)
    assert first["decision"] == "revise" and first["strike"] == 1
    second = run("audit.py", repo, "--repro", REPRO)  # same diff again
    assert second["reasons"][0].startswith("identical retry")
    assert second["strike"] == 2 and second["decision"] == "submit_best"


def test_broken_diff_never_submitted_even_at_strike_limit(repo):
    run("meta.py", repo, ISSUE)
    edit(repo, "return a +")                        # syntax error
    for _ in range(3):
        out = run("audit.py", repo, "--repro", REPRO)
    assert out["decision"] == "revise" and out["strike"] == 3
    assert any(r.startswith("syntax_errors") for r in out["reasons"])


def test_scratch_file_in_repo_blocks_submit(repo):
    run("meta.py", repo, ISSUE)
    edit(repo, "return a + b")
    (repo / "tmp").mkdir()
    (repo / "tmp" / "repro.py").write_text("print(1)\n")
    out = run("audit.py", repo, "--repro", REPRO)
    assert out["decision"] == "revise"
    assert any("scratch files" in r for r in out["reasons"])


def test_preexisting_red_tests_do_not_block_green_repro(repo):
    # mul's test is broken at baseline for a reason unrelated to the issue
    (repo / "pkg" / "calc.py").write_text(BUGGY.replace("return a * b", "return a * b + 1"))
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "mul broken")
    git(repo, "branch", "-f", "_swegemma_baseline")
    (repo / "tests" / "test_calc.py").write_text(TESTS.replace("def test_add", "def test_zadd"))
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "order")
    git(repo, "branch", "-f", "_swegemma_baseline")
    run("meta.py", repo, ISSUE)
    text = (repo / "pkg" / "calc.py").read_text().replace("return a - b", "return a + b")
    (repo / "pkg" / "calc.py").write_text(text)
    out = run("audit.py", repo, "--repro", REPRO)
    assert out["decision"] == "submit", out
    assert any("already red before the edit" in g for g in out["gaps"])


# ---------------------------------------------------------------- in-process helpers

@pytest.fixture
def mods(monkeypatch, tmp_path):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import importlib
    import audit
    import meta
    return importlib.reload(meta), importlib.reload(audit)


def test_run_pytest_counts_not_exit_code(mods, tmp_path):
    meta, _ = mods
    r = tmp_path / "r"
    (r / "tests").mkdir(parents=True)
    (r / "tests" / "test_empty.py").write_text("x = 1\n")
    (r / "tests" / "test_missing.py").write_text("import not_a_real_module_xyz\n")
    empty = meta.run_pytest(str(r), ["tests/test_empty.py"])
    assert empty["red_reason"] == "no_tests_collected" and empty["collected"] == 0
    missing = meta.run_pytest(str(r), ["tests/test_missing.py"])
    assert missing["red_reason"] == "collection_error" and missing["errors"] >= 1
    assert meta.run_pytest(str(r), [])["red_reason"] == "no_test_files"


def test_env_broken_detection(mods):
    meta, _ = mods
    log = "SystemError: The installed pydantic-core version (2.50.4) is incompatible with x"
    assert meta.ENV_BROKEN.search(log)
    assert meta.ENV_BROKEN.search("ModuleNotFoundError: No module named 'inline_snapshot'")


def test_audit_arg_shapes(mods):
    _, audit = mods
    assert audit.parse(["--repro", "python /tmp/r.py"])["repro"] == "python /tmp/r.py"
    assert audit.parse(["python /tmp/r.py"])["repro"] == "python /tmp/r.py"
    assert audit.parse(["['--repro', 'python /tmp/r.py']"])["repro"] == "python /tmp/r.py"
    assert audit.parse([])["repro"] is None


def test_rewrite_paths_for_subprocess_backend(mods, tmp_path):
    _, audit = mods
    sandbox = tmp_path / "swegemma_sandbox_1"
    (sandbox / "workspace").mkdir(parents=True)
    (sandbox / "tmp").mkdir()
    repo = str(sandbox / "workspace")
    cmd = audit.rewrite_paths("cd /workspace && python /tmp/repro.py --out /tmp/x", repo)
    assert cmd == f"cd {repo} && python {sandbox}/tmp/repro.py --out /tmp/x" or \
        cmd == f"cd {repo} && python {sandbox}/tmp/repro.py --out {sandbox}/tmp/x"
    assert "/workspace" not in cmd.replace(repo, "")
