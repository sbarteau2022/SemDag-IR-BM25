"""Ingest one swegemma results directory into the telemetry SQLite store (post-run only).

Reads the harness's own output and nothing else:
  task_results.jsonl, traces/trace_<id>.json (ATIF-v1.7), patches/<id>.patch,
  test_outputs/<id>.log, and run_meta.json written by Tools/run_eval_seatbelt.sh.
Optionally reads the public tasks.jsonl for gold files (analysis only; never training data).

Usage:
  ingest.py RESULTS_DIR --db results/telemetry.sqlite --run-id ID [--arm NAME]
            [--tasks DataSets/public/data/tasks.jsonl]
            [--tokenizer ~/models/gemma-4-e4b-it-qat-w4a16-mlx/tokenizer.json]
            [--functions]   # function-level gold match via Tools/trace_report.py (slower)

Definitions (all per task unless noted):
  tool ok           observation JSON `status` != "error" (a nonzero shell exit is recorded
                    separately as exit_code, it is not a tool failure)
  depth             0 for the root agent's steps, 1 for any other agent author (sub-agent)
  nested_steps      for an agent_tool call: the sub-agent steps that ran before the root
                    agent's next step ("steps within a tool call")
  thinking_tokens   the step's thinking text re-tokenized with the model tokenizer
  over budget       thinking_tokens > sampling thinking_budget (scorer's vLLM enforces it,
                    local MLX does not, so this measures what the scorer would cut)
  context_frac      step prompt_tokens / 32768
  compactions       steps with event_type == "compaction" (only when compaction is configured)
  ran_tests         a run_command mentioning pytest, or repo_eval.py called with --test
  repro_before_edit a /tmp script written or run before the first successful edit
  destructive_write write_file over an existing source file that the patch then modifies
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import db as tdb  # noqa: E402

CONTEXT_WINDOW = 32768
BUILTIN_TOOLS = {
    "run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch",
    "get_code_neighbors", "search_similar_code", "get_code_subgraph",
    "load_skill", "load_skill_resource", "run_skill_script",
}
MISSING_DEP = re.compile(r"No module named '(inline_snapshot|dirty_equals)'")
TEST_PATH = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")
DIFF_FILE = re.compile(r"^diff --git a/\S+ b/(\S+)|^\+\+\+ b/(\S+)", re.M)


def patch_files(patch: str) -> list[str]:
    """Non-test files touched by a unified diff.

    Reads both `diff --git a/X b/Y` headers (agent patches) and `+++ b/Y` lines (the public
    tasks' gold patches have no git header). Deleted files (`+++ /dev/null`) do not match.
    """
    files = []
    for git_b, plus_b in DIFF_FILE.findall(patch or ""):
        b = git_b or plus_b
        if not TEST_PATH.search(b) and b not in files:
            files.append(b)
    return files


def parse_obs(obs) -> dict:
    content = (obs or {}).get("content") if isinstance(obs, dict) else None
    if not isinstance(content, str):
        return {"raw": content, "chars": len(str(content or ""))}
    try:
        payload = json.loads(content)
    except ValueError:
        return {"raw": content, "chars": len(content)}
    if not isinstance(payload, dict):
        return {"raw": content, "chars": len(content)}
    payload["chars"] = len(content)
    return payload


def load_tokenizer(path: str | None):
    if not path:
        return None
    p = Path(path).expanduser()
    if not p.exists():
        return None
    try:
        from tokenizers import Tokenizer
    except ImportError:
        return None
    return Tokenizer.from_file(str(p))


def count_tokens(tok, text: str) -> int | None:
    if tok is None or not text:
        return 0 if not text else None
    return len(tok.encode(text, add_special_tokens=False).ids)


def classify(t: dict) -> str:
    """Single failure class, first match wins. Resolved tasks are 'resolved'."""
    if t["resolved"]:
        return "resolved"
    if t["error"] and "timeout" in t["error"].lower():
        return "timeout"
    if t["error"]:
        return "harness_error"
    if not t["patch_bytes"]:
        return "no_patch"
    if t["test_env_missing_dep"]:
        return "test_env_missing_dep"
    if t.get("destructive_write"):
        return "destructive_write"
    if t["touched_gold_file"] is None:
        return "unresolved_unclassified"
    if t["touched_gold_file"] == 0:
        return "wrong_file"
    if t["touched_gold_function"] == 0:
        return "right_file_wrong_function"
    if t["touched_gold_function"] == 1:
        return "right_function_wrong_fix"
    return "right_file_unresolved"


def ingest_task(con, run_id, rd: Path, r: dict, gold: dict, tok, budget, functions):
    iid = r["instance_id"]
    trace_p = rd / "traces" / f"trace_{iid}.json"
    patch_p = rd / "patches" / f"{iid}.patch"
    test_p = rd / "test_outputs" / f"{iid}.log"
    patch = patch_p.read_text(errors="replace") if patch_p.exists() else ""
    trace = json.loads(trace_p.read_text()) if trace_p.exists() else {"steps": []}
    steps = trace.get("steps") or []

    root = next(((s.get("extra") or {}).get("author") for s in steps
                 if s.get("source") == "agent" and (s.get("extra") or {}).get("author")), None)
    con.execute("DELETE FROM steps WHERE run_id=? AND instance_id=?", (run_id, iid))
    con.execute("DELETE FROM tool_calls WHERE run_id=? AND instance_id=?", (run_id, iid))

    seq = 0
    agg = dict(prompt=0, completion=0, cached=0, peak=0, think_chars=0, think_tokens=0,
               over=0, tool_errors=0, edit_errors=0, writes=0, skills=0, sub_calls=0,
               sub_steps=0, compactions=0, nudges=0, agent_steps=0, ran_tests=0)
    first_edit_s = None
    repro_before_edit = 0
    written_paths: set[str] = set()
    open_agent_tool = None  # (seq) of the root agent_tool call collecting nested steps
    nested: dict[int, int] = {}
    ts_all = []

    for s in steps:
        ex = s.get("extra") or {}
        author = ex.get("author")
        et = ex.get("event_type")
        depth = 0 if (author in (None, root) or s.get("source") != "agent") else 1
        m = s.get("metrics") or {}
        pt, ct, cached = m.get("prompt_tokens"), m.get("completion_tokens"), m.get("cached_tokens")
        if ex.get("timestamp"):
            ts_all.append(ex["timestamp"])
        agg["prompt"] += pt or 0
        agg["completion"] += ct or 0
        agg["cached"] += cached or 0
        agg["peak"] = max(agg["peak"], pt or 0)
        if et == "compaction":
            agg["compactions"] += 1
        if et == "continuation_nudge":
            agg["nudges"] += 1
        think = ""
        if s.get("source") == "agent":
            agg["agent_steps"] += 1
            if et == "thinking":
                think = str(s.get("message") or "")
        tt = count_tokens(tok, think)
        over = int(bool(budget and tt and tt > budget))
        agg["think_chars"] += len(think)
        agg["think_tokens"] += tt or 0
        agg["over"] += over

        if depth == 1 and open_agent_tool is not None:
            nested[open_agent_tool] = nested.get(open_agent_tool, 0) + 1
            agg["sub_steps"] += 1
        elif depth == 0 and s.get("source") == "agent":
            open_agent_tool = None

        tcs = s.get("tool_calls") or []
        obs = parse_obs(s.get("observation"))
        first_tc = tcs[0] if tcs else {}
        tdb.insert(con, "steps", {
            "run_id": run_id, "instance_id": iid, "step_id": s.get("step_id"),
            "source": s.get("source"), "author": author, "depth": depth, "event_type": et,
            "ts": ex.get("timestamp"), "elapsed_s": ex.get("elapsed_s"),
            "prompt_tokens": pt, "completion_tokens": ct, "cached_tokens": cached,
            "context_frac": round(pt / CONTEXT_WINDOW, 4) if pt else None,
            "thinking_chars": len(think), "thinking_tokens": tt, "over_thinking_budget": over,
            "n_tool_calls": len(tcs), "llm_call_count": s.get("llm_call_count"),
            "thinking_text": think or None,
            "tool_name": first_tc.get("function_name"),
            "tool_args": json.dumps(first_tc.get("arguments"))[:20000] if tcs else None,
            "observation": (str((s.get("observation") or {}).get("content"))[:20000]
                            if s.get("observation") else None),
        })

        for tc in tcs:
            seq += 1
            name = tc.get("function_name")
            args = tc.get("arguments") or {}
            tex = tc.get("extra") or {}
            status = obs.get("status")
            ok = int(status != "error")
            skill_name = args.get("skill_name") if name in ("run_skill_script", "load_skill") else None
            script = args.get("file_path") if name == "run_skill_script" else None
            exit_code = obs.get("exit_code", obs.get("returncode"))
            if not ok:
                agg["tool_errors"] += 1
                if name == "edit_file":
                    agg["edit_errors"] += 1
            if name == "write_file":
                agg["writes"] += 1
                fp = str(args.get("filepath") or "")
                if fp and not fp.startswith("/tmp"):
                    written_paths.add(fp.lstrip("/").removeprefix("workspace/"))
            if name in ("run_skill_script", "load_skill", "load_skill_resource"):
                agg["skills"] += 1
            argtext = json.dumps(args)
            if name == "run_command" and "pytest" in argtext:
                agg["ran_tests"] = 1
            if script and "repo_eval" in script and "--test" in argtext:
                agg["ran_tests"] = 1
            if first_edit_s is None and "/tmp/" in argtext and name in ("write_file", "run_command"):
                repro_before_edit = 1
            if name == "edit_file" and ok and first_edit_s is None:
                first_edit_s = tex.get("elapsed_s")
            if name not in BUILTIN_TOOLS and depth == 0:
                agg["sub_calls"] += 1
                open_agent_tool = seq
            tdb.insert(con, "tool_calls", {
                "run_id": run_id, "instance_id": iid, "step_id": s.get("step_id"), "seq": seq,
                "name": name, "skill_name": skill_name, "skill_script": script,
                "author": author, "depth": depth, "ok": ok, "status": status,
                "error_type": obs.get("error_type"),
                "error_message": (obs.get("error_message") or obs.get("error") or None)
                if not ok else None,
                "exit_code": exit_code if isinstance(exit_code, int) else None,
                "elapsed_s": tex.get("elapsed_s"), "args_chars": len(argtext),
                "obs_chars": obs.get("chars"), "nested_steps": None,
            })
    for s_seq, n in nested.items():
        con.execute("UPDATE tool_calls SET nested_steps=? WHERE run_id=? AND instance_id=? AND seq=?",
                    (n, run_id, iid, s_seq))

    edited = patch_files(patch)
    g = gold.get(iid) or {}
    gfiles = g.get("files") or None  # empty gold file list means unknown, not "no file"
    touched_file = None if gfiles is None or not edited else int(bool(set(edited) & set(gfiles)))
    ef = gf = None
    touched_fn = None
    if functions and gfiles is not None and patch:
        ef, gf, touched_fn = function_match(iid, patch, g.get("patch", ""))
    test_log = test_p.read_text(errors="replace") if test_p.exists() else ""
    row = {
        "run_id": run_id, "instance_id": iid, "repo": r.get("repo"),
        "resolved": int(bool(r.get("resolved"))), "error": r.get("error") or None,
        "test_exit_code": r.get("test_exit_code"), "duration_s": r.get("duration_seconds"),
        "patch_bytes": r.get("agent_patch_size", len(patch.encode())),
        "harness_tool_calls": r.get("tool_calls"), "harness_llm_calls": r.get("total_llm_calls"),
        "steps": len(steps), "agent_steps": agg["agent_steps"], "nudges": agg["nudges"],
        "compactions": agg["compactions"],
        "prompt_tokens": agg["prompt"], "completion_tokens": agg["completion"],
        "cached_tokens": agg["cached"], "peak_prompt_tokens": agg["peak"],
        "peak_context_frac": round(agg["peak"] / CONTEXT_WINDOW, 4),
        "thinking_chars": agg["think_chars"],
        "thinking_tokens": agg["think_tokens"] if tok is not None else None,
        "thinking_calls_over_budget": agg["over"] if tok is not None else None,
        "tool_calls": seq, "tool_errors": agg["tool_errors"], "edit_errors": agg["edit_errors"],
        "write_file_calls": agg["writes"], "skill_calls": agg["skills"],
        "subagent_calls": agg["sub_calls"], "subagent_steps": agg["sub_steps"],
        "first_edit_s": first_edit_s, "ran_tests": agg["ran_tests"],
        "repro_before_edit": repro_before_edit,
        "edited_files": json.dumps(edited), "gold_files": json.dumps(gfiles) if gfiles else None,
        "touched_gold_file": touched_file,
        "edited_functions": json.dumps(ef) if ef is not None else None,
        "gold_functions": json.dumps(gf) if gf is not None else None,
        "touched_gold_function": touched_fn,
        "test_env_missing_dep": int(bool(MISSING_DEP.search(test_log))),
        # whole-file overwrite of a source file the patch then modifies (not a new file)
        "destructive_write": int(any(w in edited and "new file mode" not in _file_block(patch, w)
                                     for w in written_paths)),
        "t_start": min(ts_all) if ts_all else None, "t_end": max(ts_all) if ts_all else None,
    }
    row["failure_class"] = classify(row)
    tdb.insert(con, "tasks", row)
    return row


def _file_block(patch: str, path: str) -> str:
    """The part of a unified diff that belongs to one file (empty if absent)."""
    start = patch.find(f"diff --git a/{path} b/{path}")
    if start < 0:
        return ""
    nxt = patch.find("\ndiff --git ", start + 1)
    return patch[start:] if nxt < 0 else patch[start:nxt]


def function_match(iid: str, patch: str, gold_patch: str):
    """Function-level match using the shared snapshot logic in Tools/trace_report.py."""
    try:
        sys.path.insert(0, str(HERE.parent))
        import trace_report as tr  # noqa: E402
    except Exception:
        return None, None, None
    e = tr.edited_sites(iid, patch)
    g = tr.edited_sites(iid, gold_patch)
    if not e or not g:
        return None, None, None
    es = sorted(f"{p}::{q}" for p, q in e["sites"])
    gs = sorted(f"{p}::{q}" for p, q in g["sites"])
    return es, gs, int(bool(set(es) & set(gs)))


def attach_llm_calls(con, run_id: str, lead_s: float = 5.0) -> int:
    """Assign proxy rows to tasks by wall clock (tasks run one at a time, concurrency 1).

    A call belongs to the latest task whose first trace timestamp is at most `lead_s`
    after the call started, provided the call started before that task's last trace
    timestamp. Calls outside every task window stay unassigned (instance_id NULL).
    """
    tasks = con.execute(
        "SELECT instance_id, t_start, t_end FROM tasks WHERE run_id=? AND t_start IS NOT NULL "
        "ORDER BY t_start", (run_id,)).fetchall()
    calls = con.execute("SELECT call_id, wall_start FROM llm_calls WHERE run_id=?",
                        (run_id,)).fetchall()
    n = 0
    for c in calls:
        owner = None
        for t in tasks:
            if t["t_start"] - lead_s <= c["wall_start"]:
                owner = t
            else:
                break
        iid = owner["instance_id"] if owner and c["wall_start"] <= owner["t_end"] + 1 else None
        con.execute("UPDATE llm_calls SET instance_id=? WHERE call_id=?", (iid, c["call_id"]))
        n += iid is not None
    con.commit()
    return n


def ingest_run(db_path, results_dir, run_id, arm=None, tasks_path=None, tokenizer=None,
               functions=False):
    rd = Path(results_dir)
    con = tdb.connect(db_path)
    meta = json.loads((rd / "run_meta.json").read_text()) if (rd / "run_meta.json").exists() else {}
    sampling = meta.get("sampling") or {}
    budget = (sampling.get("thinking_config") or {}).get("thinking_budget")
    gold = {}
    if tasks_path and Path(tasks_path).exists():
        for line in Path(tasks_path).read_text().splitlines():
            t = json.loads(line)
            gold[t["instance_id"]] = {"files": patch_files(t.get("patch", "")),
                                      "patch": t.get("patch", "")}
    tok = load_tokenizer(tokenizer)
    tdb.insert(con, "runs", {
        "run_id": run_id, "arm": arm or meta.get("arm"),
        "submission_dir": meta.get("submission_dir"),
        "submission_sha256": meta.get("submission_sha256"), "git_head": meta.get("git_head"),
        "sandbox": meta.get("sandbox"), "seatbelt": meta.get("seatbelt"),
        "model": meta.get("model"), "budget_json": json.dumps(meta.get("budget")),
        "sampling_json": json.dumps(sampling), "started_utc": meta.get("started_utc"),
        "ingested_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "notes": meta.get("notes"),
    })
    rows = []
    res = rd / "task_results.jsonl"
    for line in (res.read_text().splitlines() if res.exists() else []):
        if line.strip():
            rows.append(ingest_task(con, run_id, rd, json.loads(line), gold, tok, budget,
                                    functions))
    con.commit()
    attached = attach_llm_calls(con, run_id)
    return {"tasks": len(rows), "llm_calls_attached": attached}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir")
    ap.add_argument("--db", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arm")
    ap.add_argument("--tasks")
    ap.add_argument("--tokenizer")
    ap.add_argument("--functions", action="store_true")
    a = ap.parse_args()
    out = ingest_run(a.db, a.results_dir, a.run_id, a.arm, a.tasks, a.tokenizer, a.functions)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
