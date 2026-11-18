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


def test_v8_ensemble_caps():
    """v8 (owner design 2026-11-17): 4k hard caps for implementers/adversaries, 6k for the
    coordinator and final implementer. Thinking comes from a literal <|think|> (owner 2026-11-18):
    thinking_budget 0, so no thinking_token_budget is sent and the output cap is the only bound."""
    sub = ROOT / "AgenticSubmission" / "v8_ensemble"
    if not sub.exists():
        pytest.skip("not built")
    caps = {"sampling_implement.yaml": 4096, "sampling_adversary.yaml": 4096,
            "sampling_lead.yaml": 6144, "sampling_final.yaml": 6144}
    for name, cap in caps.items():
        d = yaml.safe_load((sub / "configs" / name).read_text())
        assert d["max_output_tokens"] == cap, name
        assert d["thinking_config"]["thinking_budget"] == 0, name   # thinking via <|think|>
    ev = yaml.safe_load((sub / "eval_config.yaml").read_text())["evaluation"]
    assert (ev["max_time_minutes"], ev["timeout_seconds"], ev["max_tool_calls"], ev["max_turns"]) \
        == (4, 300, 100, 500)

    for prompt in ("implementer_1.md", "adversary_1.md", "lead.md", "finalizer.md"):
        assert (sub / "prompts" / prompt).read_text().startswith("<|think|>"), prompt
