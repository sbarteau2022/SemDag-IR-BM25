"""Render raw trajectories into chat-format SFT records, dedupe and split.

usage: python render.py <raw_dir> <out_dir> [--system prompts/system.md]

Outputs (JSONL, one conversation per line):
  train.jsonl     training split
  val.jsonl       in-distribution validation (same repos, different bugs)
  test_ood.jsonl  held-out repos never seen in training
  stats.json      counts used by DATASHEET.md

Observation formats are set in one place (render_result) so they can be
matched exactly to HARNESS_README.md before training.
"""
import argparse
import collections
import glob
import hashlib
import json
import os
import random

from config import EXCLUDED_REPOS

OOD_REPOS = {"cachetools", "xmltodict", "python-slugify", "isodate", "glom"}
VAL_FRACTION = 0.06
MAX_TOKENS = 12000          # stay well below the 14,336-token compaction point
CHARS_PER_TOKEN = 3.6       # rough for code-heavy text with the Gemma tokenizer

DEFAULT_SYSTEM = """You are an autonomous software engineer fixing one issue in the repository at /workspace. You have a small budget of tool calls and about 5 minutes, so work like a careful expert who is also fast.

Tactics:
1. Reproduce first. Put the issue's snippet in /tmp/repro.py with a heredoc via run_command, or run the single failing test by node id. Never write scratch files inside /workspace, because every new file there ends up in the patch.
2. Localize from evidence. An exception traceback points at the innermost library frame. A wrong value with no traceback means finding the API the snippet calls (grep -rn "def name") and following its calls.
3. Read narrowly. Use read_file with start_line/end_line around the function you need, not whole files.
4. State one concrete hypothesis before editing: which line is wrong, and why it explains the observed output.
5. Make the minimal edit with edit_file. old_string must match exactly once, so include a neighbouring line when the line is not unique. Never edit tests or test config.
6. Verify: re-run the repro or the failing test, then only the related test file (never the whole suite). Prefix commands with timeout.
7. Submit with submit_patch as soon as the targeted checks pass, then give a one-line summary."""

TOOLS = [
    {"type": "function", "function": {"name": "run_command", "description": "Execute a shell command with /bin/bash -c inside /workspace. Output is truncated to 5000 characters.",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file from /workspace with 1-indexed inclusive line slicing (max 150 lines per call).",
     "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, "required": ["filepath"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Replace old_string with new_string in an existing non-empty file inside /workspace.",
     "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}, "allow_multiple": {"type": "boolean"}}, "required": ["filepath", "old_string", "new_string"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Create or overwrite a file at /workspace/<filepath>, creating parent directories.",
     "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "content": {"type": "string"}}, "required": ["filepath", "content"]}}},
    {"type": "function", "function": {"name": "get_status", "description": "Return live budget consumption and patch status.",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "submit_patch", "description": "Stage untracked files (git add -N .) and capture git diff HEAD from /workspace. Ends the session.",
     "parameters": {"type": "object", "properties": {}}}},
]


def render_result(tool, res):
    if tool == "run_command":
        out = res["output"].rstrip("\n") or "(no output)"
        if res.get("truncated"):
            out += "\n[output truncated]"
        if res["exit_code"] != 0:
            out += f"\n[exit code: {res['exit_code']}]"
        return out
    if tool == "read_file":
        if "error" in res:
            return json.dumps({"status": "error", "message": res["error"]})
        s = res["start_line"]
        body = "\n".join(f"{s + i:>6}\t{l}" for i, l in enumerate(res["lines"]))
        return f"{res['filepath']} (lines {s}-{res['end_line']} of {res['total_lines']})\n{body}"
    if tool in ("edit_file", "write_file"):
        if "error" in res:
            return json.dumps({"status": "error", "message": res["error"]})
        return json.dumps(res)
    if tool == "submit_patch":
        return json.dumps({k: res[k] for k in ("status", "patch_size", "files_changed")})
    return json.dumps(res)


def to_messages(rec, system):
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": rec["issue"]}]
    for i, s in enumerate(rec["steps"]):
        cid = f"call_{i + 1}"
        thought = s["thought"]
        msgs.append({"role": "assistant", "content": thought,
                     "tool_calls": [{"id": cid, "type": "function",
                                     "function": {"name": s["tool"], "arguments": s["args"]}}]})
        content = render_result(s["tool"], s["result"])
        msgs.append({"role": "tool", "tool_call_id": cid, "name": s["tool"], "content": content})
        if s.get("post_note"):
            # pre-existing failure note is folded into the next thought
            nxt = rec["steps"][i + 1] if i + 1 < len(rec["steps"]) else None
            if nxt is not None:
                nxt["thought"] = s["post_note"].strip() + " " + nxt["thought"]
    msgs.append({"role": "assistant", "content": rec["final"]})
    return msgs


def chain_grounded(r):
    """The read of the intermediate API must actually show the call to the buggy function."""
    reads = [s for s in r["steps"] if s["tool"] == "read_file"]
    callee = r["bug"]["func"].split(".")[-1]
    import re as _re
    for s in reads[:-1]:
        if any(_re.search(r"\b%s\s*\(" % _re.escape(callee), l) for l in s["result"].get("lines", [])):
            return True
    return False


def approx_tokens(msgs):
    n = sum(len(m.get("content") or "") + len(json.dumps(m.get("tool_calls", ""))) for m in msgs)
    return int(n / CHARS_PER_TOKEN)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--system")
    ap.add_argument("--seed", type=int, default=20261113)
    a = ap.parse_args()
    system = open(a.system).read().strip() if a.system else DEFAULT_SYSTEM
    rng = random.Random(a.seed)
    raw = []
    for p in sorted(glob.glob(os.path.join(a.raw_dir, "*.jsonl"))):
        raw += [json.loads(l) for l in open(p) if l.strip()]
    drops = collections.Counter()
    seen_bug, seen_patch, seen_issue = set(), set(), set()
    kept = []
    for r in raw:
        if r["repo"] in EXCLUDED_REPOS:
            drops["excluded_repo"] += 1
            continue
        bkey = (r["repo"], r["bug"]["file"], r["bug"]["start"], r["bug"]["op"])
        phash = hashlib.sha1("".join(l for l in r["patch"].split("\n") if l[:1] in "+-").encode()).hexdigest()
        ihash = hashlib.sha1(r["issue"].split("\n\n", 1)[-1].encode()).hexdigest()
        if bkey in seen_bug or (r["repo"], phash) in seen_patch or ihash in seen_issue:
            drops["duplicate"] += 1
            continue
        seen_bug.add(bkey); seen_patch.add((r["repo"], phash)); seen_issue.add(ihash)
        if r["meta"]["route"] == "call_chain" and not chain_grounded(r):
            drops["chain_not_grounded"] += 1
            continue
        msgs = to_messages(r, system)
        blob = json.dumps(msgs)
        if "claude-0" in blob or "/tmp/claude" in blob or "/work/ws/" in blob:
            drops["env_path_leak"] += 1
            continue
        if r["meta"]["mode"] == "ci":
            msgs[-1]["content"] = msgs[-1]["content"].replace("the repro and", "the failing test and")
        tok = approx_tokens(msgs)
        if tok > MAX_TOKENS:
            drops["too_long"] += 1
            continue
        kept.append({"id": r["id"], "messages": msgs, "tools": TOOLS,
                     "metadata": {"repo": r["repo"], "github": r["github"], "license": r["license"],
                                  "base_commit": r["base_commit"], "bug_op": r["bug"]["op"],
                                  "bug_family": r["bug"]["family"], "bug_file": r["bug"]["file"],
                                  "mode": r["meta"]["mode"], "route": r["meta"]["route"],
                                  "edit_retry": r["meta"].get("edit_retry", False),
                                  "hint": r["meta"].get("hint", False),
                                  "preexisting_failures": r["meta"].get("preexisting_failures", 0),
                                  "n_tool_calls": r["n_tool_calls"], "approx_tokens": tok,
                                  "fail_to_pass": r["fail_to_pass"], "n_pass_to_pass": r["n_pass_to_pass"],
                                  "gold_patch": r["patch"]}})
    rng.shuffle(kept)
    ood = [k for k in kept if k["metadata"]["repo"] in OOD_REPOS]
    ind = [k for k in kept if k["metadata"]["repo"] not in OOD_REPOS]
    n_val = max(1, int(len(ind) * VAL_FRACTION))
    val, train = ind[:n_val], ind[n_val:]
    os.makedirs(a.out_dir, exist_ok=True)
    for name, rows in (("train", train), ("val", val), ("test_ood", ood)):
        with open(os.path.join(a.out_dir, name + ".jsonl"), "w") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    def dist(rows, key):
        return dict(collections.Counter(r["metadata"][key] for r in rows).most_common())
    toks = sorted(k["metadata"]["approx_tokens"] for k in kept)
    calls = sorted(k["metadata"]["n_tool_calls"] for k in kept)
    stats = {"raw": len(raw), "kept": len(kept), "drops": dict(drops),
             "splits": {"train": len(train), "val": len(val), "test_ood": len(ood)},
             "ood_repos": sorted(OOD_REPOS),
             "by_repo": dist(kept, "repo"), "by_family": dist(kept, "bug_family"),
             "by_op": dist(kept, "bug_op"), "by_mode": dist(kept, "mode"), "by_route": dist(kept, "route"),
             "edit_retry": sum(k["metadata"]["edit_retry"] for k in kept),
             "with_hint": sum(k["metadata"]["hint"] for k in kept),
             "with_preexisting_failures": sum(1 for k in kept if k["metadata"]["preexisting_failures"]),
             "tool_calls": {"min": calls[0], "median": calls[len(calls) // 2], "max": calls[-1]} if calls else {},
             "approx_tokens": {"min": toks[0], "median": toks[len(toks) // 2], "p95": toks[int(len(toks) * .95)], "max": toks[-1]} if toks else {},
             "licenses": dict(collections.Counter(k["metadata"]["license"] for k in kept))}
    json.dump(stats, open(os.path.join(a.out_dir, "stats.json"), "w"), indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
