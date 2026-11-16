"""Read harness traces (ATIF-v1.7) and submitted patches for one or more agent arms, and report
where the agent looked and where it actually edited.

Usage:
  trace_report.py --gold PaperTrack/phase4_semdag/out/per_task.jsonl DIR [DIR ...]
                  [--json OUT.json] [--only-ids FILE] [--label NAME ...]

Per task the reader reports, from `traces/trace_<instance_id>.json`:
  - the tool-call sequence and mix, the first tool called, and the wall-clock time of the
    first `edit_file` call (seconds from task start, from the tool call's own `extra.elapsed_s`)
  - whether the `locate` skill was called, through which tool (`run_skill_script` or
    `load_skill`) and at which 1-based position in the tool-call sequence
  - locate's printed candidates (`path:start-end qualified.name`), parsed from the
    observation's JSON payload: the rank of the gold function and gold file, explicit top-1
    and top-5 containment, and how many candidates are harness wrapper files
    (`.adk_exec_*`), which are harness artifacts rather than repository code
  - the sites the agent actually edited, derived from the submitted patch using the same
    function that derives gold (`PaperTrack/phase4_semdag/measure.py::gold_sites`) applied to
    the task snapshot, so gold and edited sites share one definition
  - the cross signal: whether locate's top 5 held a function the agent then edited, and
    whether locate's top 5 held the gold function

Gold comes from the per-task `patch` (scoring only) via per_task.jsonl.

When more than one run directory is given, a paired section is printed for the instance ids
present in every arm: resolution per arm plus the locate and containment signals. Arms with
disjoint task sets are not compared to each other.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "PaperTrack" / "phase4_semdag"))
import measure as m1  # noqa: E402  (shared snapshot + patch-hunk to function-span logic)

CANDIDATE = re.compile(r"^(\S+\.py):(\d+)-(\d+) (\S+)$", re.M)
SNAP_CACHE = (
    Path(os.environ.get("TRACE_SNAP_CACHE") or tempfile.gettempdir())
    / "trace_report_snap"
)


def parse_candidates(stdout: str):
    """locate.py prints `path:start-end qualified.name`; return [(path, start, end, qual)]."""
    return [
        (m.group(1), int(m.group(2)), int(m.group(3)), m.group(4))
        for m in CANDIDATE.finditer(stdout)
    ]


def load_gold(path: Path):
    gold = {}
    for line in path.read_text().splitlines():
        r = json.loads(line)
        if "gold" not in r:
            continue
        gold[r["instance_id"]] = {
            "repo": r.get("repo"),
            "fns": {(g["file"], g["qual"]) for g in r["gold"]},
            "files": set(r.get("gold_files") or []),
        }
    return gold


def snapshot_repo(instance_id: str) -> Path | None:
    """Extract the task's snapshot .py files once, into a cache dir."""
    dest = SNAP_CACHE / instance_id
    if dest.exists() and any(dest.rglob("*.py")):
        return dest
    tgz = m1.DATA / "snapshots" / f"{instance_id}.tgz"
    if not tgz.exists():
        return None
    dest.mkdir(parents=True, exist_ok=True)
    m1.extract_py(tgz, str(dest))
    return dest


def edited_sites(instance_id: str, patch_text: str):
    """Functions touched by the submitted patch, as (path, qual) pairs, using gold_sites."""
    repo = snapshot_repo(instance_id)
    if repo is None:
        return None
    sites, files, n_hunks, n_aligned = m1.gold_sites(patch_text, str(repo))
    if not sites:
        return {
            "sites": set(),
            "files": set(files),
            "hunks": n_hunks,
            "aligned": n_aligned,
            "empty": True,
        }
    return {
        "sites": {(v["file"], v["qual"]) for v in sites.values()},
        "files": set(files),
        "hunks": n_hunks,
        "aligned": n_aligned,
        "empty": False,
    }


def scan_trace(trace_path: Path):
    """Return (call sequence, locate call records, first_edit_s) for one trace."""
    steps = json.loads(trace_path.read_text())["steps"]
    calls, locate, first_edit_s = [], [], None
    for s in steps:
        for tc in s.get("tool_calls") or []:
            name = tc.get("function_name")
            calls.append(name)
            elapsed = (tc.get("extra") or {}).get("elapsed_s")
            if name == "edit_file" and first_edit_s is None and elapsed is not None:
                first_edit_s = elapsed
            args = tc.get("arguments") or {}
            if name not in ("run_skill_script", "load_skill"):
                continue
            if args.get("skill_name") != "locate":
                continue
            rec = {
                "via": name,
                "call_index": len(calls),
                "candidates": None,
                "query_chars": len(" ".join(map(str, args.get("args") or []))),
            }
            obs = s.get("observation") or {}
            if name == "run_skill_script" and obs.get("content"):
                try:
                    payload = json.loads(obs["content"])
                except ValueError:
                    payload = {}
                rec["candidates"] = parse_candidates(payload.get("stdout") or "")
                rec["status"] = payload.get("status")
            locate.append(rec)
    return calls, locate, first_edit_s


def best_rank(candidates, wanted):
    """1-based rank of the first candidate whose (path, qual) is in `wanted`, else None."""
    for i, (path, _s, _e, qual) in enumerate(candidates):
        if (path, qual) in wanted:
            return i + 1
    return None


def best_file_rank(candidates, wanted_files):
    for i, (path, _s, _e, _q) in enumerate(candidates):
        if path in wanted_files:
            return i + 1
    return None


def run_dir(d: Path, gold, only=None):
    res_path = d / "task_results.jsonl"
    if not res_path.exists():
        return []
    rows = []
    for line in res_path.read_text().splitlines():
        r = json.loads(line)
        iid = r["instance_id"]
        if only is not None and iid not in only:
            continue
        g = gold.get(iid)
        trace_path = d / "traces" / f"trace_{iid}.json"
        row = {
            "instance_id": iid,
            "repo": r.get("repo"),
            "resolved": r["resolved"],
            "patch_size": r.get("agent_patch_size", 0),
            "duration_s": r.get("duration_seconds"),
            "test_exit_code": r.get("test_exit_code"),
            "n_calls": r.get("tool_calls"),
        }
        if g is None or not trace_path.exists():
            row["skipped"] = "gold_or_trace_missing"
            rows.append(row)
            continue
        calls, locate, first_edit_s = scan_trace(trace_path)
        row["n_calls_trace"] = len(calls)
        row["first_call"] = calls[0] if calls else None
        row["calls"] = dict(Counter(calls))
        row["first_edit_s"] = first_edit_s

        patch_path = d / "patches" / f"{iid}.patch"
        edited = None
        if patch_path.exists():
            edited = edited_sites(iid, patch_path.read_text(errors="replace"))
        row["edited_files"] = sorted(edited["files"]) if edited else []
        row["edited_sites"] = sorted(edited["sites"]) if edited else []
        row["edited_hunks"] = edited["hunks"] if edited else None

        recs = []
        for rec in locate:
            cands = rec.get("candidates")
            item = {
                "via": rec["via"],
                "call_index": rec["call_index"],
                "query_chars": rec["query_chars"],
                "n_candidates": len(cands) if cands is not None else None,
                "wrapper_candidates": sum(
                    1 for c in (cands or []) if c[0].startswith(".adk_exec")
                ),
            }
            if cands:
                item["gold_fn_rank"] = best_rank(cands, g["fns"])
                item["gold_file_rank"] = best_file_rank(cands, g["files"])
                item["top5"] = [f"{c[0]}::{c[3]}" for c in cands[:5]]
                if edited is not None:
                    item["edited_fn_rank"] = best_rank(cands, edited["sites"])
            recs.append(item)
        row["locate"] = recs
        row["locate_called"] = bool(recs)
        row["first_locate_is_first_call"] = bool(recs) and recs[0]["call_index"] == 1

        first = recs[0] if recs else None
        row["locate_top5_had_gold_fn"] = (
            bool(first)
            and first.get("gold_fn_rank") is not None
            and first["gold_fn_rank"] <= 5
        )
        row["locate_top5_had_edited_fn"] = (
            bool(first)
            and first.get("edited_fn_rank") is not None
            and first["edited_fn_rank"] <= 5
        )
        row["locate_candidates_had_gold_file"] = (
            bool(first) and first.get("gold_file_rank") is not None
        )
        row["gold_fn_in_top5_not_edited"] = (
            row["locate_top5_had_gold_fn"]
            and bool(edited)
            and not (edited["sites"] & g["fns"])
        )
        row["edited_gold_fn"] = bool(edited) and bool(edited["sites"] & g["fns"])
        row["edited_gold_file"] = bool(edited) and bool(
            set(edited["files"]) & g["files"]
        )
        rows.append(row)
    return rows


def summarise(rows, label):
    usable = [r for r in rows if "skipped" not in r]
    lo = [r for r in usable if r["locate_called"]]
    first = [r["locate"][0] for r in lo]
    ranks = [r["gold_fn_rank"] for r in first if r.get("gold_fn_rank")]
    ed_ranks = [r["edited_fn_rank"] for r in first if r.get("edited_fn_rank")]
    edit_s = [r["first_edit_s"] for r in usable if r.get("first_edit_s") is not None]
    tools = Counter()
    for r in usable:
        tools.update(r["calls"])
    return {
        "label": label,
        "tasks": len(usable),
        "skipped": len(rows) - len(usable),
        "resolved": sum(r["resolved"] for r in usable),
        "submitted_nonempty_patch": sum(1 for r in usable if r["patch_size"] > 0),
        "tasks_with_edit": len(edit_s),
        "mean_first_edit_s": round(sum(edit_s) / len(edit_s), 1) if edit_s else None,
        "median_first_edit_s": round(sorted(edit_s)[len(edit_s) // 2], 1)
        if edit_s
        else None,
        "locate_called": len(lo),
        "locate_as_first_call": sum(r["first_locate_is_first_call"] for r in lo),
        "locate_via": dict(Counter(r["locate"][0]["via"] for r in lo)),
        "mean_query_chars": round(
            sum(r["locate"][0]["query_chars"] for r in lo) / len(lo)
        )
        if lo
        else None,
        "wrapper_candidate_seen": sum(
            r["locate"][0].get("wrapper_candidates") or 0 for r in lo
        ),
        "locate_top5_had_gold_fn": sum(r["locate_top5_had_gold_fn"] for r in lo),
        "locate_gold_fn_rank1": sum(1 for x in ranks if x == 1),
        "locate_gold_fn_rank_found": len(ranks),
        "locate_gold_fn_rank_median": sorted(ranks)[len(ranks) // 2] if ranks else None,
        "locate_candidates_had_gold_file": sum(
            r["locate_candidates_had_gold_file"] for r in lo
        ),
        "locate_top5_had_edited_fn": sum(r["locate_top5_had_edited_fn"] for r in lo),
        "edited_fn_rank_found": len(ed_ranks),
        "gold_fn_in_top5_but_agent_edited_elsewhere": sum(
            r["gold_fn_in_top5_not_edited"] for r in lo
        ),
        "edited_gold_fn": sum(r["edited_gold_fn"] for r in usable),
        "edited_gold_file": sum(r["edited_gold_file"] for r in usable),
        "tool_mix": dict(tools),
        "first_call": dict(Counter(r["first_call"] for r in usable)),
    }


def paired_table(all_rows):
    """Rows joined on instance ids present in every arm."""
    if len(all_rows) < 2:
        return []
    ids = set.intersection(
        *[{r["instance_id"] for r in rows} for rows in all_rows.values()]
    )
    out = []
    for iid in sorted(ids):
        line = {"instance_id": iid, "arms": {}}
        for label, rows in all_rows.items():
            r = next(x for x in rows if x["instance_id"] == iid)
            first = r.get("locate", [None])[0] if r.get("locate") else None
            line["arms"][label] = {
                "resolved": r["resolved"],
                "n_calls": r.get("n_calls_trace"),
                "first_edit_s": r.get("first_edit_s"),
                "locate": bool(r.get("locate")),
                "locate_top5_gold_fn": r.get("locate_top5_had_gold_fn"),
                "locate_top5_edited_fn": r.get("locate_top5_had_edited_fn"),
                "edited_gold_fn": r.get("edited_gold_fn"),
                "gold_fn_rank": (first or {}).get("gold_fn_rank") if first else None,
            }
        out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--gold", required=True)
    ap.add_argument("--json")
    ap.add_argument(
        "--only-ids", help="file of instance ids to restrict to (e.g. a paired set)"
    )
    ap.add_argument("--label", action="append", help="label per run dir, in order")
    a = ap.parse_args()

    gold = load_gold(Path(a.gold))
    only = None
    if a.only_ids:
        only = {
            l.strip() for l in Path(a.only_ids).read_text().splitlines() if l.strip()
        }

    all_rows, summaries = {}, {}
    for i, d in enumerate(map(Path, a.dirs)):
        label = a.label[i] if a.label and i < len(a.label) else d.name
        rows = run_dir(d, gold, only)
        all_rows[label] = rows
        summaries[label] = summarise(rows, label)

    for label, rows in all_rows.items():
        print("=" * 100)
        print(f"# {label}")
        for r in rows:
            if "skipped" in r:
                print(f"{r['instance_id']:15} skipped ({r['skipped']})")
                continue
            first = r["locate"][0] if r["locate"] else None
            loc = "-"
            if first:
                g = first.get("gold_fn_rank")
                e = first.get("edited_fn_rank")
                loc = (
                    f"via={first['via'][:6]} idx={first['call_index']} n={first['n_candidates']} "
                    f"gold_fn_rank={g} edited_fn_rank={e}"
                )
            print(
                f"{r['instance_id']:15} {'PASS' if r['resolved'] else 'fail'} "
                f"calls={r.get('n_calls_trace')} first={str(r.get('first_call'))[:18]:18} "
                f"first_edit_s={r.get('first_edit_s')} "
                f"edited_gold_fn={int(bool(r.get('edited_gold_fn')))} locate={loc}"
            )
    print("=" * 100)
    print(json.dumps(summaries, indent=1))
    paired = paired_table(all_rows)
    if paired:
        print("=" * 100)
        print(
            f"# paired subset: instance ids present in every arm ({len(paired)} tasks)"
        )
        for line in paired:
            cells = []
            for label in all_rows:
                arm = line["arms"][label]
                cells.append(
                    f"{label}: {'PASS' if arm['resolved'] else 'fail'} "
                    f"loc={'Y' if arm['locate'] else 'n'} "
                    f"gold5={'Y' if arm['locate_top5_gold_fn'] else 'n'} "
                    f"edit5={'Y' if arm['locate_top5_edited_fn'] else 'n'} "
                    f"editgold={'Y' if arm['edited_gold_fn'] else 'n'} "
                    f"rank={arm['gold_fn_rank']}"
                )
            print(f"{line['instance_id']:15} " + " | ".join(cells))
    if a.json:
        Path(a.json).write_text(
            json.dumps(
                {
                    "summaries": summaries,
                    "paired": paired,
                    "rows": {k: v for k, v in all_rows.items()},
                },
                indent=1,
            )
        )
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
