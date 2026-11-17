"""Tools/paired_report.py: joins two arms on shared task ids."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import paired_report as pr

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    out = subprocess.run([sys.executable, str(ROOT / "Tools" / "paired_report.py"), *args],
                         capture_output=True, text=True, check=True)
    return out.stdout


def test_load_merges_dirs_last_wins(make_run):
    a = make_run("a", [{"instance_id": "t1", "resolved": False, "patch": "x"}])
    b = make_run("b", [{"instance_id": "t1", "resolved": True, "patch": "x"},
                       {"instance_id": "t2", "resolved": False}])
    got = pr.load([a, b])
    assert set(got) == {"t1", "t2"}
    assert got["t1"]["resolved"] is True


def test_load_missing_dir_is_empty(tmp_path):
    assert pr.load([tmp_path / "nope"]) == {}


def test_paired_counts_and_empty_patch(make_run, tmp_path):
    base = make_run("base", [
        {"instance_id": "t1", "resolved": True, "patch": "p"},
        {"instance_id": "t2", "resolved": True, "patch": ""},       # empty-patch pass
        {"instance_id": "t3", "resolved": False, "patch": "p"},
        {"instance_id": "only_base", "resolved": True, "patch": "p"},
    ])
    test = make_run("test", [
        {"instance_id": "t1", "resolved": False, "patch": "p"},
        {"instance_id": "t2", "resolved": True, "patch": "p"},
        {"instance_id": "t3", "resolved": True, "patch": "p"},
        {"instance_id": "only_test", "resolved": True, "patch": "p"},
    ])
    out_json = tmp_path / "rep.json"
    run(["--base", str(base), "--test", str(test), "--json", str(out_json)])
    rep = json.loads(out_json.read_text())
    assert rep["paired_tasks"] == 3                       # only shared ids
    assert rep["base"]["resolved"] == 2 and rep["test"]["resolved"] == 2
    assert rep["base"]["resolved_nonempty_patch"] == 1
    assert rep["base"]["empty_patch"] == 1
    assert rep["both"] == 1
    assert rep["base_only"] == ["t1"] and rep["test_only"] == ["t3"]
    assert rep["resolved_by_empty_patch_in_either"] == ["t2"]


def test_ids_file_restricts_and_drops_unknown(make_run, tmp_path):
    base = make_run("b", [{"instance_id": "t1", "resolved": True, "patch": "p"},
                          {"instance_id": "t2", "resolved": False, "patch": "p"}])
    test = make_run("t", [{"instance_id": "t1", "resolved": True, "patch": "p"},
                          {"instance_id": "t2", "resolved": True, "patch": "p"}])
    ids = tmp_path / "ids.txt"
    ids.write_text("t2\nghost\n")
    out_json = tmp_path / "rep.json"
    run(["--base", str(base), "--test", str(test), "--ids", str(ids), "--json", str(out_json)])
    rep = json.loads(out_json.read_text())
    assert rep["paired_tasks"] == 1 and rep["test_only"] == ["t2"]


def test_no_overlap_reports_zero_without_crash(make_run, tmp_path):
    base = make_run("b", [{"instance_id": "x", "resolved": True, "patch": "p"}])
    test = make_run("t", [{"instance_id": "y", "resolved": True, "patch": "p"}])
    out_json = tmp_path / "rep.json"
    run(["--base", str(base), "--test", str(test), "--json", str(out_json)])
    rep = json.loads(out_json.read_text())
    assert rep["paired_tasks"] == 0 and rep["base"]["mean_seconds"] == 0
