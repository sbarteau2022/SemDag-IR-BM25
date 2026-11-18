"""v8 ensemble skill scripts on a throwaway repo: fork -> implement in worktrees -> audit --wt ->
review_pack / save_cex -> gate -> adopt. Scripts run as subprocesses, like run_skill_script."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "AgenticSubmission" / "v8_ensemble" / "skills" / "semdag" / "scripts"
ISSUE = "add returns the wrong result: add(2, 3) should be 5 but calc.add subtracts"
BUGGY = 'def add(a, b):\n    """Return the sum."""\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n'
TESTS = ("from pkg.calc import add, mul\n\n\ndef test_add():\n    assert add(2, 3) == 5\n\n\n"
         "def test_mul():\n    assert mul(2, 3) == 6\n")

pytestmark = pytest.mark.skipif(not SCRIPTS.exists(), reason="run Tools/v8_ensemble/build_v8.py")


def git(repo, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=repo,
                   check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "pkg").mkdir(parents=True)
    (r / "tests").mkdir()
    (r / "pkg" / "__init__.py").write_text("")
    (r / "pkg" / "calc.py").write_text(BUGGY)
    (r / "tests" / "test_calc.py").write_text(TESTS)
    git(r, "init", "-q")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "base")
    git(r, "branch", "_swegemma_baseline")
    (tmp_path / "cache").mkdir()
    (tmp_path / "tmp").mkdir()
    return r


def run(script, repo, *args):
    env = dict(os.environ, SEMDAG_REPO=str(repo), TMPDIR=str(repo.parent / "cache"))
    env.pop("PYTHONPATH", None)
    env.pop("SEMDAG_CACHE", None)          # another test module may have set it in-process
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=repo.parent, env=env,
                       capture_output=True, text=True, timeout=240)
    lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    assert lines, p.stderr[-2000:]
    return json.loads(lines[-1])


def implement(repo, k, new):
    f = repo / ".git" / f"wt_{k}" / "pkg" / "calc.py"
    f.write_text(BUGGY.replace("return a - b", new))


def repro_cmd(repo, k):
    return f"cd {repo}/.git/wt_{k} && python -c 'from pkg.calc import add; assert add(2, 3) == 5'"


def test_fork_creates_isolated_worktrees_and_distinct_sites(repo):
    a = run("fork.py", repo, "1", ISSUE)
    b = run("fork.py", repo, "4", ISSUE)
    assert "error" not in a and "error" not in b, (a, b)
    assert (repo / ".git" / "wt_1" / "pkg" / "calc.py").exists()
    assert a["start_site"]["file"] == ".git/wt_1/pkg/calc.py"
    assert "start_sites" in b and "note" in b               # k=4 is the localization check
    assert a["audit_args"][:2] == ["--wt", "1"]
    out = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)
    assert out.stdout.strip() == ""                         # worktrees never show in the main repo


def test_audit_wt_judges_the_copy_not_the_main_workspace(repo):
    run("fork.py", repo, "1", ISSUE)
    implement(repo, 1, "return a + b")
    out = run("audit.py", repo, "--wt", "1", "--repro", repro_cmd(repo, 1))
    assert out["wt"] == 1 and out["decision"] == "submit", out
    assert out["patch_files"] == ["pkg/calc.py"]
    assert (repo / "pkg" / "calc.py").read_text() == BUGGY  # main workspace untouched


def test_review_pack_and_save_cex(repo):
    run("fork.py", repo, "2", ISSUE)
    assert run("review_pack.py", repo, "2").get("empty") is True
    implement(repo, 2, "return a + b if a != 0 else -b")
    pack = run("review_pack.py", repo, "2")
    assert "pkg/calc.py" in pack["files"] and "-b" in pack["diff"]
    assert "error" in run("save_cex.py", repo, "2", "print('no assert')")
    assert "error" in run("save_cex.py", repo, "2", "assert (")
    ok = run("save_cex.py", repo, "2", "from pkg.calc import add\nassert add(0, 3) == 3")
    assert ok["saved"] is True


def test_gate_ranks_correct_candidate_first_and_adopt_applies_it(repo):
    for k in (1, 2, 3):
        run("fork.py", repo, str(k), ISSUE)
    implement(repo, 1, "return a + b if a != 0 else -b")   # passes repro, fails the counterexample
    implement(repo, 2, "return a + b")                      # correct
    implement(repo, 3, "return a +")                        # syntax error
    for k in (1, 2, 3):
        run("audit.py", repo, "--wt", str(k), "--repro", repro_cmd(repo, k))
    run("save_cex.py", repo, "1", "from pkg.calc import add\nassert add(0, 3) == 3")
    g = run("gate.py", repo)
    assert g["winner"] == 2, g
    by_k = {c["k"]: c for c in g["candidates"]}
    assert by_k[3]["static"], by_k[3]                       # typecheck stand-in caught it
    assert by_k[1]["cex_failed"] == ["k1_1.py"]
    assert by_k[4].get("empty") is True
    a = run("adopt.py", repo, "2")
    assert a["adopted"] == 2 and a["decision"] == "submit", a
    assert "return a + b" in (repo / "pkg" / "calc.py").read_text()
    a2 = run("adopt.py", repo, "1")                         # re-adopt replaces, never stacks
    assert "a != 0" in (repo / "pkg" / "calc.py").read_text()
    diff = subprocess.run(["git", "diff", "_swegemma_baseline", "--stat"], cwd=repo,
                          capture_output=True, text=True).stdout
    assert ".git/wt_" not in diff and "pkg/calc.py" in diff


def test_every_v8_yaml_parses_like_the_harness_loader():
    """The validator does not parse sub-agent YAML; a bad scalar only fails at run time."""
    import yaml

    class L(yaml.SafeLoader):
        pass
    L.add_constructor("!include", lambda loader, node: loader.construct_scalar(node))
    sub = SCRIPTS.parents[2]
    for f in sorted(sub.rglob("*.yaml")):
        data = yaml.load(f.read_text(), Loader=L)
        assert isinstance(data, dict), f
