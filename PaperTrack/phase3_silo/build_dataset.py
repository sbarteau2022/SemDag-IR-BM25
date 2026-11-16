#!/usr/bin/env python3
"""P1: deterministic probe-dataset builder for the Phase 3 role-silo probe.

Reads tasks.jsonl and the per-task code graphs. Never reads hints_text or
test_patch (both keys are deleted at load). Uses no model and no tokenizer.

Usage (from the project root):
  PYTHONDONTWRITEBYTECODE=1 python3 PaperTrack/phase3_silo/build_dataset.py
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DataSets/public/data"
OUT = Path(__file__).resolve().parent / "out"
SEED = 0
FIT_REPO = "fastapi/fastapi"
DEV_N = 20
LETTERS = "ABCDEFGH"
ISSUE_CAP = 1600
DIFF_CAP = 2600
CODE_CAP = 2500
ROLES = ("LOC", "ANA", "IMP", "VER")

TEMPLATES = {
    ("LOC", "T1"): "You are locating where a reported issue must be fixed.\n\nIssue:\n{issue}\n\nCandidate files:\n{cands}\n\nWhich one file has to change to resolve the issue? Reply with a single letter.",
    ("LOC", "T2"): "Bug report for the repository {repo}:\n\n{issue}\n\nOptions:\n{cands}\n\nPick the option naming the source file whose code must be edited. Give only the letter.",
    ("ANA", "T1"): "You are analysing call relationships in source code.\n\nFunction `{f}`:\n```python\n{code}\n```\n\nDoes `{f}` directly call `{g}`? Reply Yes or No.",
    ("ANA", "T2"): "Read this definition taken from {repo}.\n\n```python\n{code}\n```\n\nThe definition above is `{f}`. Is `{g}` invoked directly inside its body? One word: Yes or No.",
    ("IMP", "T1"): "You are implementing a fix.\n\nIssue:\n{issue}\n\nFile `{path}`, code just before the point of change:\n```python\n{window}\n```\n\nWrite the first new line of the fix, exactly as it should appear in the file.",
    ("IMP", "T2"): "Repository {repo}. A change is needed for this report:\n\n{issue}\n\nExisting lines in `{path}` leading up to the edit:\n```python\n{window}\n```\n\nGive the next line to insert. Output that one line of code only.",
    ("VER", "T1"): "You are verifying a proposed patch.\n\nIssue:\n{issue}\n\nPatch:\n```diff\n{diff}\n```\n\nDoes this patch address the issue? Reply Yes or No.",
    ("VER", "T2"): "Report filed against {repo}:\n\n{issue}\n\nA candidate change:\n```diff\n{diff}\n```\n\nIs this change a fix for the report above? One word: Yes or No.",
}
# Assistant-turn prefix placed after the chat template's generation prompt.
PREFIX = {"LOC": "Answer:", "ANA": "Answer:", "VER": "Answer:", "IMP": "```python\n"}
CANDS = {"LOC": [" " + c for c in LETTERS], "ANA": [" Yes", " No"], "VER": [" Yes", " No"], "IMP": None}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rng_for(*parts: str) -> random.Random:
    return random.Random(int(sha(":".join((str(SEED),) + parts))[:16], 16))


def is_test_path(p: str) -> bool:
    parts = p.split("/")
    name = parts[-1]
    return (
        any(x in ("tests", "test", "testing") for x in parts[:-1])
        or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
    )


def is_test_node(name: str) -> bool:
    parts = name.split(".")
    return parts[0] in ("tests", "test", "testing") or any(p.startswith("test_") or p == "conftest" for p in parts)


def squeeze(text: str, cap: int) -> str:
    text = text.strip()
    if len(text) <= cap:
        return text
    half = (cap - 7) // 2
    return text[:half] + "\n[...]\n" + text[-half:]


def cut_lines(text: str, cap: int, marker: str) -> str:
    if len(text) <= cap:
        return text
    out, n = [], 0
    for line in text.split("\n"):
        if n + len(line) + 1 > cap:
            break
        out.append(line)
        n += len(line) + 1
    return "\n".join(out + [marker])


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_patch(patch: str) -> list[dict]:
    files, cur, hunk = [], None, None
    lines = patch.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            path = lines[i + 1][4:].strip()
            path = path[2:] if path.startswith("b/") else path
            cur = {"path": path, "hunks": [], "raw": [line]}
            files.append(cur)
            hunk = None
            continue
        if cur is None:
            continue
        cur["raw"].append(line)
        m = HUNK.match(line)
        if m:
            hunk = {"old_count": int(m.group(2) or "1"), "lines": []}
            cur["hunks"].append(hunk)
        elif hunk is not None and line[:1] in (" ", "+", "-") and not line.startswith("+++ "):
            hunk["lines"].append(line)
    return files


def source_files(files: list[dict]) -> list[dict]:
    return [f for f in files if f["path"].endswith(".py") and not is_test_path(f["path"])]


def substantive(line: str) -> bool:
    return len(line.strip()) >= 3


def load_tasks() -> list[dict]:
    tasks = []
    for line in (DATA / "tasks.jsonl").open(encoding="utf-8"):
        t = json.loads(line)
        t.pop("hints_text", None)
        t.pop("test_patch", None)
        t["files"] = parse_patch(t["patch"])
        tasks.append(t)
    return tasks


def load_graph(t: dict) -> dict:
    name = t["repo"].split("/")[1]
    return json.loads((DATA / "graphs" / f"{name}_{t['base_commit']}.json").read_text(encoding="utf-8"))


def make_split(tasks: list[dict]) -> dict[str, str]:
    fit_ids = sorted((t["instance_id"] for t in tasks if t["repo"] == FIT_REPO), key=lambda i: sha(i))
    dev = set(fit_ids[:DEV_N])
    return {t["instance_id"]: ("heldout" if t["repo"] != FIT_REPO else "dev" if t["instance_id"] in dev else "fit") for t in tasks}


def loc_item(t, pool, skips):
    src = source_files(t["files"])
    if not src:
        return skips.append((t, "LOC", "no non-test .py file in patch")) or []
    gold = next((f for f in src if any(h["old_count"] > 0 for h in f["hunks"])), src[0])["path"]
    own = {f["path"] for f in t["files"]}
    others = sorted(p for p in pool[t["repo"]] if p not in own)
    if len(others) < 7:
        return skips.append((t, "LOC", f"only {len(others)} distractor files in repo pool")) or []
    r = rng_for(t["instance_id"], "LOC")
    r.shuffle(others)
    cands = others[:7] + [gold]
    r.shuffle(cands)
    listing = "\n".join(f"{LETTERS[i]}. {p}" for i, p in enumerate(cands))
    return [{"item": "0", "fields": {"cands": listing}, "gold": " " + LETTERS[cands.index(gold)], "shuffle": ["cands"]}]


def ana_items(t, skips):
    g = load_graph(t)
    nodes = {n["id"]: n for n in g["nodes"] if n.get("text")}
    callees = defaultdict(set)
    for e in g["edges"]:
        if e.get("type") == "calls" and e["source"] in nodes and e["target"] in nodes and e["source"] != e["target"]:
            if not is_test_node(e["source"]) and not is_test_node(e["target"]):
                callees[e["source"]].add(e["target"])
    fs = sorted(f for f in callees if 150 <= len(nodes[f]["text"]) <= CODE_CAP)
    if not fs:
        return skips.append((t, "ANA", "no eligible caller node")) or []
    r = rng_for(t["instance_id"], "ANA")
    f = r.choice(fs)
    pos = r.choice(sorted(callees[f]))
    parent = pos.rsplit(".", 1)[0]
    non = [n for n in sorted(nodes) if n != f and n not in callees[f] and not is_test_node(n)]
    near = [n for n in non if n.rsplit(".", 1)[0] == parent]
    if not non:
        return skips.append((t, "ANA", "no negative node")) or []
    neg = r.choice(near or non)
    base = {"f": f, "code": nodes[f]["text"]}
    return [
        {"item": "pos", "fields": {**base, "g": pos}, "gold": " Yes", "shuffle": ["code"]},
        {"item": "neg", "fields": {**base, "g": neg}, "gold": " No", "shuffle": ["code"]},
    ]


def imp_item(t, skips):
    for f in source_files(t["files"]):
        for h in f["hunks"]:
            if h["old_count"] == 0:
                continue
            window = []
            for line in h["lines"]:
                if line.startswith("+"):
                    if substantive(line[1:]) and len([w for w in window if w.strip()]) >= 2:
                        return [{"item": "0", "fields": {"path": f["path"], "window": "\n".join(window)},
                                 "gold": line[1:] + "\n", "shuffle": ["window"]}]
                    break
                window.append(line[1:])
    return skips.append((t, "IMP", "no modified-file hunk with >=2 prior lines before a substantive added line")) or []


def own_diff(t) -> str:
    return cut_lines("\n".join("\n".join(f["raw"]).rstrip("\n") for f in t["files"] if not is_test_path(f["path"])), DIFF_CAP, "[diff truncated]")


def ver_items(t, by_repo, skips):
    mine = own_diff(t)
    others = sorted((o for o in by_repo[t["repo"]] if o["instance_id"] != t["instance_id"] and own_diff(o).strip()), key=lambda o: o["instance_id"])
    if not mine.strip():
        return skips.append((t, "VER", "patch has no non-test file")) or []
    if not others:
        return skips.append((t, "VER", "no other task in repo for a negative")) or []
    other = rng_for(t["instance_id"], "VER").choice(others)
    return [
        {"item": "pos", "fields": {"diff": mine}, "gold": " Yes", "shuffle": ["diff"]},
        {"item": "neg", "fields": {"diff": own_diff(other)}, "gold": " No", "shuffle": ["diff"], "neg_source": other["instance_id"]},
    ]


def scramble(text: str, r: random.Random) -> str:
    words = text.split()
    r.shuffle(words)
    return " ".join(words)


def main() -> None:
    tasks = load_tasks()
    split = make_split(tasks)
    by_repo, pool = defaultdict(list), defaultdict(set)
    for t in tasks:
        by_repo[t["repo"]].append(t)
        pool[t["repo"]].update(f["path"] for f in source_files(t["files"]))

    rows, skips = [], []
    for t in sorted(tasks, key=lambda t: t["instance_id"]):
        sp = split[t["instance_id"]]
        issue = squeeze(t["problem_statement"], ISSUE_CAP)
        items = {"LOC": loc_item(t, pool, skips), "ANA": ana_items(t, skips), "IMP": imp_item(t, skips), "VER": ver_items(t, by_repo, skips)}
        for role in ROLES:
            for it in items[role]:
                item_id = f"{t['instance_id']}|{role}|{it['item']}"
                variants = [("T1", "task"), ("T1", "tmpl")] if sp == "fit" else [("T2", "task")]
                for tmpl, kind in variants:
                    fields = {"issue": issue, "repo": t["repo"], **it["fields"]}
                    if kind == "tmpl":
                        r = rng_for(item_id, "tmpl")
                        for key in ["issue"] + it["shuffle"]:
                            fields[key] = scramble(fields[key], r)
                    text = TEMPLATES[(role, tmpl)].format(**fields)
                    rows.append({
                        "prompt_id": f"{item_id}|{tmpl}|{kind}", "item_id": item_id, "instance_id": t["instance_id"],
                        "repo": t["repo"], "split": sp, "role": role, "template": tmpl, "kind": kind,
                        "user_text": text, "assistant_prefix": PREFIX[role], "candidates": CANDS[role],
                        "gold": it["gold"], "neg_source": it.get("neg_source"),
                        "n_chars": len(text), "n_tokens_est": round(len(text) / 3.5),
                    })

    OUT.mkdir(exist_ok=True)
    (OUT / "prompts.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    (OUT / "skips.jsonl").write_text("".join(json.dumps({"instance_id": t["instance_id"], "repo": t["repo"], "split": split[t["instance_id"]], "role": role, "reason": why}, sort_keys=True) + "\n" for t, role, why in skips), encoding="utf-8")
    manifest = {
        "seed": SEED, "fit_repo": FIT_REPO, "dev_n": DEV_N,
        "split": dict(sorted(split.items())),
        "counts": {f"{s}|{ro}|{k}": c for (s, ro, k), c in sorted(Counter((r["split"], r["role"], r["kind"]) for r in rows).items())},
        "tasks_sha256": hashlib.sha256((DATA / "tasks.jsonl").read_bytes()).hexdigest(),
        "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "prompts_sha256": hashlib.sha256((OUT / "prompts.jsonl").read_bytes()).hexdigest(),
    }
    (OUT / "split.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("counts", "prompts_sha256")}, indent=1))
    print("rows", len(rows), "skips", len(skips), file=sys.stderr)


if __name__ == "__main__":
    main()
