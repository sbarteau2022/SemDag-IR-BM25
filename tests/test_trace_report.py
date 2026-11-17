"""Tools/trace_report.py: pure parsing and summary logic (no snapshots needed)."""

from __future__ import annotations

import json

import pytest

import trace_report as tr
from conftest import step


def test_parse_candidates_ignores_noise():
    out = "header\nsrc/a.py:10-20 mod.Cls.fn\nnot a match\n.adk_exec_1.py:1-2 x\nb/c.py:3-4 f extra"
    assert tr.parse_candidates(out) == [("src/a.py", 10, 20, "mod.Cls.fn"),
                                        (".adk_exec_1.py", 1, 2, "x")]


def test_load_gold_skips_rows_without_gold(tmp_path):
    p = tmp_path / "per_task.jsonl"
    p.write_text("\n".join([
        json.dumps({"instance_id": "t1", "repo": "o/r", "gold": [{"file": "a.py", "qual": "f"}],
                    "gold_files": ["a.py"]}),
        json.dumps({"instance_id": "t2", "repo": "o/r"}),
    ]))
    g = tr.load_gold(p)
    assert set(g) == {"t1"}
    assert g["t1"]["fns"] == {("a.py", "f")} and g["t1"]["files"] == {"a.py"}


def _locate_obs(stdout):
    return {"status": "ok", "stdout": stdout}


def test_scan_trace_locate_and_first_edit(tmp_path):
    steps = [
        step(1, source="system", event_type="system_instruction"),
        step(2, tool="run_skill_script",
             args={"skill_name": "locate", "file_path": "scripts/locate.py", "args": ["q1", "q2"]},
             obs=_locate_obs("src/a.py:1-9 a.f\nsrc/b.py:3-5 b.g")),
        step(3, tool="edit_file", args={"filepath": "src/a.py"},
             obs={"status": "error"}, elapsed=50.0),
        step(4, tool="edit_file", args={"filepath": "src/a.py"}, elapsed=60.0),
        step(5, tool="run_skill_script", args={"skill_name": "other"}),
    ]
    p = tmp_path / "trace.json"
    p.write_text(json.dumps({"steps": steps}))
    calls, locate, first_edit = tr.scan_trace(p)
    assert calls == ["run_skill_script", "edit_file", "edit_file", "run_skill_script"]
    # first edit_file call time, whatever its status (documented behaviour)
    assert first_edit == 50.0
    assert len(locate) == 1
    rec = locate[0]
    assert rec["via"] == "run_skill_script" and rec["call_index"] == 1
    assert rec["candidates"][0] == ("src/a.py", 1, 9, "a.f")
    assert rec["query_chars"] == len("q1 q2")


def test_scan_trace_bad_json_observation(tmp_path):
    s = step(1, tool="run_skill_script", args={"skill_name": "locate"}, obs="not json")
    p = tmp_path / "trace.json"
    p.write_text(json.dumps({"steps": [s]}))
    _calls, locate, _ = tr.scan_trace(p)
    assert locate[0]["candidates"] == []


@pytest.mark.parametrize("wanted,expected", [({("b.py", "g")}, 2), ({("z.py", "q")}, None)])
def test_best_rank(wanted, expected):
    cands = [("a.py", 1, 2, "f"), ("b.py", 1, 2, "g")]
    assert tr.best_rank(cands, wanted) == expected


def test_best_file_rank():
    cands = [("a.py", 1, 2, "f"), ("b.py", 1, 2, "g")]
    assert tr.best_file_rank(cands, {"b.py"}) == 2
    assert tr.best_file_rank(cands, set()) is None


def _row(iid, resolved, locate_rank=None, edited_gold=False, first_edit=None):
    loc = [] if locate_rank is None else [{
        "via": "run_skill_script", "call_index": 1, "query_chars": 10, "n_candidates": 8,
        "wrapper_candidates": 1, "gold_fn_rank": locate_rank, "edited_fn_rank": locate_rank}]
    return {"instance_id": iid, "resolved": resolved, "patch_size": 5, "first_edit_s": first_edit,
            "calls": {"read_file": 2}, "first_call": "read_file", "n_calls_trace": 2,
            "locate": loc, "locate_called": bool(loc),
            "first_locate_is_first_call": bool(loc),
            "locate_top5_had_gold_fn": bool(loc) and locate_rank <= 5,
            "locate_top5_had_edited_fn": bool(loc) and locate_rank <= 5,
            "locate_candidates_had_gold_file": bool(loc),
            "gold_fn_in_top5_not_edited": bool(loc) and not edited_gold,
            "edited_gold_fn": edited_gold, "edited_gold_file": edited_gold}


def test_summarise_counts_and_skips():
    rows = [_row("a", True, 1, True, 10.0), _row("b", False, 7, False, 30.0),
            _row("c", False), {"instance_id": "d", "resolved": False, "skipped": "x"}]
    s = tr.summarise(rows, "arm")
    assert s["tasks"] == 3 and s["skipped"] == 1 and s["resolved"] == 1
    assert s["locate_called"] == 2 and s["locate_top5_had_gold_fn"] == 1
    assert s["locate_gold_fn_rank1"] == 1 and s["wrapper_candidate_seen"] == 2
    assert s["median_first_edit_s"] == 30.0 and s["tool_mix"] == {"read_file": 6}


def test_summarise_empty():
    s = tr.summarise([], "x")
    assert s["tasks"] == 0 and s["mean_first_edit_s"] is None


def test_paired_table_intersection_only():
    rows = {"A": [_row("t1", True, 1), _row("t2", False)], "B": [_row("t1", False, 3)]}
    out = tr.paired_table(rows)
    assert [l["instance_id"] for l in out] == ["t1"]
    assert out[0]["arms"]["A"]["resolved"] is True and out[0]["arms"]["B"]["gold_fn_rank"] == 3
    assert tr.paired_table({"A": rows["A"]}) == []


def test_run_dir_marks_missing_gold(make_run):
    d = make_run("r", [{"instance_id": "t1", "resolved": False, "steps": []}])
    rows = tr.run_dir(d, gold={})
    assert rows[0]["skipped"] == "gold_or_trace_missing"
    assert tr.run_dir(d.parent / "missing", gold={}) == []
