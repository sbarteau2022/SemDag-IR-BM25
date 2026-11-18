"""Every submission directory must fit the scorer's 12 h sequential budget, except the
named local-measurement arms, which must say so in their eval_config header."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SUBS = sorted(p for p in (ROOT / "AgenticSubmission").iterdir() if p.is_dir())
# Local-only measurement arms: may exceed the per-task cap, must never be zipped.
LOCAL_ONLY = {"v5_loop_e4b"}
MAX_MINUTES = 5          # ~120 tasks x (5 min + ~30 s overrun) + setup < 12 h
FIELDS = {"timeout_seconds", "max_tool_calls", "max_time_minutes", "max_turns"}


@pytest.mark.parametrize("sub", SUBS, ids=lambda p: p.name)
def test_eval_config_sets_all_four_fields(sub):
    cfg = yaml.safe_load((sub / "eval_config.yaml").read_text())["evaluation"]
    assert FIELDS <= set(cfg), f"{sub.name}: scorer default for a missing field is no limit"


@pytest.mark.parametrize("sub", SUBS, ids=lambda p: p.name)
def test_per_task_budget_fits_12h_unless_local_only(sub):
    text = (sub / "eval_config.yaml").read_text()
    minutes = yaml.safe_load(text)["evaluation"]["max_time_minutes"]
    if sub.name in LOCAL_ONLY:
        assert "NEVER ZIP" in text, f"{sub.name}: local-only arm must be labelled"
    else:
        assert minutes <= MAX_MINUTES, f"{sub.name}: {minutes} min/task can exceed 12 h"


@pytest.mark.parametrize("sub", SUBS, ids=lambda p: p.name)
def test_official_validator_accepts_every_submission(sub):
    """Catches stray files (e.g. __pycache__/*.pyc written by a test run) before a live run does."""
    from adk_submission import validate_directory
    from swegemma.config import build_submission_limits
    validate_directory(sub, limits=build_submission_limits()[0])


# Owner rule 2026-11-17: active submissions keep the competition budgets.
ACTIVE = ["v7_brigade_lite"]


@pytest.mark.parametrize("name", ACTIVE)
def test_active_submission_uses_competition_budgets(name):
    sub = ROOT / "AgenticSubmission" / name
    cfgs = sorted((sub / "configs").glob("*.yaml"))
    assert cfgs, name
    for c in cfgs:
        d = yaml.safe_load(c.read_text())
        assert d["max_output_tokens"] == 16384, f"{c.name}: max_output_tokens"
        assert d["thinking_config"]["thinking_budget"] in (0, 4096), f"{c.name}: thinking_budget"
    ev = yaml.safe_load((sub / "eval_config.yaml").read_text())["evaluation"]
    assert ev["max_time_minutes"] == 4 and ev["timeout_seconds"] == 300
