"""Scorer-parity shims (docs/SCORER_PARITY.md GAP 1 and GAP 2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tools" / "telemetry"))
sys.path.insert(0, str(ROOT / "Tools" / "local"))

import llm_proxy  # noqa: E402


# ---------------------------------------------------------------- GAP 2: thinking budget

@pytest.mark.parametrize("body, expect", [
    ({"thinking_token_budget": 512}, 512),                         # top level (LiteLLM merges)
    ({"extra_body": {"thinking_token_budget": 1024}}, 1024),       # nested
    ({"thinking_token_budget": 0}, None),                           # thinking off: nothing copied
    ({}, None),                                                     # no budget at all
    ({"thinking_token_budget": 64, "thinking_budget": 8}, 8),       # client value wins
])
def test_enforce_thinking_budget(body, expect):
    out = llm_proxy.enforce_thinking_budget(body, "thinking_budget")
    assert out.get("thinking_budget") == expect
    assert "thinking_budget" not in body or body["thinking_budget"] == 8   # input not mutated


def test_enforce_thinking_budget_disabled_without_field():
    body = {"thinking_token_budget": 512}
    assert llm_proxy.enforce_thinking_budget(body, None) is body


# ---------------------------------------------------------------- GAP 1: compaction

def _config(tmp_path):
    from swegemma.config import EvalConfig
    from adk_submission.registry import ModelRegistry
    return EvalConfig(tasks_path=tmp_path / "t.jsonl", snapshots_dir=tmp_path,
                      results_dir=tmp_path / "r", submission_dir=tmp_path,
                      models=ModelRegistry())


def test_eval_parity_sets_scorer_compaction_and_cache(tmp_path):
    import eval_parity
    eval_parity.install()
    eval_parity.install()                    # idempotent
    cfg = _config(tmp_path)
    ec, cc = cfg.events_compaction_config, cfg.context_cache_config
    assert (ec.compaction_interval, ec.overlap_size, ec.token_threshold,
            ec.event_retention_size) == (15, 2, 14336, 5)
    assert ec.summarizer is None             # ADK builds it from the root agent's own model
    assert (cc.min_tokens, cc.ttl_seconds, cc.cache_intervals) == (2048, 1800, 10)


def test_eval_parity_keeps_explicit_config(tmp_path):
    import eval_parity
    from google.adk.apps._configs import EventsCompactionConfig
    from swegemma.config import EvalConfig
    from adk_submission.registry import ModelRegistry
    eval_parity.install()
    mine = EventsCompactionConfig(compaction_interval=3, overlap_size=1)
    cfg = EvalConfig(tasks_path=tmp_path / "t.jsonl", snapshots_dir=tmp_path,
                     results_dir=tmp_path / "r", submission_dir=tmp_path,
                     models=ModelRegistry(), events_compaction_config=mine)
    assert cfg.events_compaction_config is mine


# ---------------------------------------------------------------- streamed tool calls

def _feed(acc, delta):
    acc.feed({"choices": [{"delta": delta}]}, 0.0)


def test_accumulator_merges_vllm_fragmented_tool_calls():
    acc = llm_proxy.Accumulator(0.0)
    _feed(acc, {"tool_calls": [{"id": "c1", "type": "function", "index": 0,
                                "function": {"name": "read_file"}}]})
    for frag in ('{"filepath": "', "src/", 'app.py"}'):
        _feed(acc, {"tool_calls": [{"index": 0, "function": {"arguments": frag}}]})
    _feed(acc, {"tool_calls": [{"id": "c2", "index": 1,
                                "function": {"name": "get_status", "arguments": "{}"}}]})
    calls = acc.response()["choices"][0]["message"]["tool_calls"]
    assert [(c["id"], c["function"]["name"], c["function"]["arguments"]) for c in calls] == [
        ("c1", "read_file", '{"filepath": "src/app.py"}'), ("c2", "get_status", "{}")]


def test_accumulator_keeps_whole_tool_calls_without_index():
    acc = llm_proxy.Accumulator(0.0)
    for name in ("a", "b"):
        _feed(acc, {"tool_calls": [{"id": name, "type": "function",
                                    "function": {"name": name, "arguments": "{}"}}]})
    assert [c["function"]["name"] for c in acc.response()["choices"][0]["message"]["tool_calls"]] \
        == ["a", "b"]


def test_accumulator_same_index_new_id_is_a_new_call():
    acc = llm_proxy.Accumulator(0.0)
    for cid in ("x", "y"):
        _feed(acc, {"tool_calls": [{"id": cid, "index": 0,
                                    "function": {"name": cid, "arguments": "{}"}}]})
    assert [c["id"] for c in acc.response()["choices"][0]["message"]["tool_calls"]] == ["x", "y"]


def test_fill_generation_defaults_top_k():
    assert llm_proxy.fill_generation_defaults({}, 64)["top_k"] == 64
    assert llm_proxy.fill_generation_defaults({"top_k": 5}, 64)["top_k"] == 5
    assert "top_k" not in llm_proxy.fill_generation_defaults({}, None)
