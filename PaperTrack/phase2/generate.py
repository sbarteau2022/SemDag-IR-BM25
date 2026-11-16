#!/usr/bin/env python3
"""Phase 2 generation. Frozen before any completion is read. Do not retune.

Question
    Same weights, one sample, two contexts, Rich only. Does the span that won
    Phase 1 (ZP) let Gemma 4 E4B cover more gold added lines than the one-hop
    call neighborhood, when both code sections have the same character budget?

Why ZP, not the residual arm
    The pre-registered winner rule on non-Rich selected ZP. Rich did not enter
    that choice. Context O is that winner. Residual ranking (arm R) is not put
    back into the prompt after the gate.

Contexts
    O  ZP node texts. Order: seeds in resolve_seeds order, then each seed's
       children (class seed) or siblings (other seed) in graph child-list
       order, skipping duplicates and seeds.
    C  one-hop call list in edge order (the Phase 1 `_call_list`).
    Both are rendered as "### {node id}\\n{node text}" blocks separated by a
    blank line. O is cut at MAX_CODE_CHARS. C is then cut so its rendered
    length is at most O's rendered length. Whole nodes are kept from the
    front. If the first node alone exceeds the budget, its block is cut on
    a character boundary. An empty O gives both arms an empty code section.

    MAX_CODE_CHARS is 24000. It is a memory cap for the already-running MLX
    server on this 48 GB machine. It is not fit to gold overlap.

Prompt
    The instruction string is identical for both arms. The issue text is the
    problem_statement. hints_text, test_patch, and the gold patch are not
    placed in the prompt. The patch is scoring only.

Sampling
    One completion per (task, arm). temperature 0.2, top_p 0.95, max_tokens
    16384, seed 0, enable_thinking true.
    The server default and the first launch used 4096, matching
    Tools/serve_e4b_mlx.sh. The first completion (rich_4070 O) returned
    completion_tokens 4096, reasoning_chars 15424, and content "". Thinking
    consumed the cap, so the empty answer was a censored decode, not a
    localization result. max_tokens is now the competition
    configs/sampling.yaml max_output_tokens of 16384. mlx-lm still has no
    separate thinking budget. Temperature, top_p, seed, and the prompts
    are unchanged. The censored completion is not a score.

Score
    Primary: multiset overlap of stripped substantive gold added lines in
    .py hunks with the stripped substantive added lines of the unified diff
    parsed from message.content. Thinking text is not scored. A transport
    failure that survives one retry counts as 0 and is flagged. No diff
    counts as 0.
    The context build, before any completion, showed 30 of 48 Rich tasks
    have an empty code span, and one of those holds 11939 of the gold added
    lines. The scorer also reports the with-span subset and the empty-span
    subset. The primary number stays the all-task micro overlap. When the
    two prompts are byte-identical, arm C copies arm O's completion and is
    flagged. Seed 0 makes that the same sample.

Pytest
    Not this script. The sandbox probe is `python generate.py pytest`.
    Ten Rich tasks are attempted only if Docker answers. Otherwise write STOP.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE1 = HERE.parent / "phase1" / "measure.py"
OUT = HERE / "out"
PROMPTS = OUT / "prompts"
COMPLETIONS = OUT / "completions"

MAX_CODE_CHARS = 24000
TEMPERATURE = 0.2
TOP_P = 0.95
MAX_TOKENS = 16384
SEED = 0
ENDPOINT = "http://127.0.0.1:8123/v1/chat/completions"
MODEL = "/Users/stewartbarteau/models/gemma-4-e4b-it-qat-w4a16-mlx"
TIMEOUT_S = 900

INSTRUCTION = (
    "Fix the issue. The code spans are the only repository text available. "
    "Reply with a unified diff and no other text."
)


def load_phase1():
    spec = importlib.util.spec_from_file_location("phase1_measure", PHASE1)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {PHASE1}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_blocks(graph, nodes: list[str]) -> str:
    parts = [f"### {ident}\n{graph.text[ident]}" for ident in nodes]
    return "\n\n".join(parts)


def cut_nodes(graph, nodes: list[str], budget: int) -> tuple[str, list[str], bool]:
    """Return rendered text, kept ids, and whether a character cut was used."""
    if budget <= 0 or not nodes:
        return "", [], False
    kept: list[str] = []
    used = 0
    for ident in nodes:
        block = f"### {ident}\n{graph.text[ident]}"
        extra = 2 if kept else 0
        need = extra + len(block)
        if used + need <= budget:
            kept.append(ident)
            used += need
            continue
        if not kept:
            return block[:budget], [ident], True
        break
    return render_blocks(graph, kept), kept, False


def ordered_zp(graph, seeds: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def take(ident: str) -> None:
        if ident in seen or ident not in graph.idset:
            return
        seen.add(ident)
        ordered.append(ident)

    for ident in seeds:
        take(ident)
    for ident in seeds:
        if graph.kind.get(ident) == "class":
            pool = graph.children.get(ident, [])
        else:
            parent = graph.parent.get(ident)
            pool = graph.children.get(parent, []) if parent else []
        for other in pool:
            if other in set(seeds):
                continue
            take(other)
    return ordered


def build_prompt(issue: str, code: str) -> str:
    return f"{INSTRUCTION}\n\n## Issue\n{issue}\n\n## Code\n{code}\n"


def gold_added(measure, patch: str) -> list[str]:
    lines: list[str] = []
    for hunk in measure.parse_hunks(patch):
        if not str(hunk["path"]).endswith(".py"):
            continue
        for line in hunk["added"]:
            if measure.substantive(line):
                lines.append(line.strip())
    return lines


def extract_diff(content: str) -> str:
    if not content:
        return ""
    fence = content.find("```")
    if fence >= 0:
        rest = content[fence + 3 :]
        if rest.startswith("diff"):
            rest = rest[4:]
        end = rest.find("```")
        body = rest if end < 0 else rest[:end]
        if "diff --git " in body or body.lstrip().startswith("--- ") or "\n@@" in body:
            return body.strip()
    at = content.find("diff --git ")
    if at >= 0:
        return content[at:].strip()
    at = content.find("\n--- ")
    if at >= 0:
        return content[at + 1 :].strip()
    if content.lstrip().startswith("--- "):
        return content.strip()
    return ""


def added_from_diff(measure, diff: str) -> list[str]:
    if not diff:
        return []
    lines: list[str] = []
    for hunk in measure.parse_hunks(diff):
        for line in hunk["added"]:
            if measure.substantive(line):
                lines.append(line.strip())
    return lines


def overlap(gold: list[str], pred: list[str]) -> int:
    have = Counter(pred)
    got = 0
    for line, count in Counter(gold).items():
        got += min(count, have[line])
    return got


def rich_tasks(measure) -> list[dict]:
    rows = []
    for line in measure.TASKS.read_text().splitlines():
        if not line.strip():
            continue
        task = json.loads(line)
        if measure.repo_short(task["repo"]) == "rich":
            rows.append(task)
    return rows


def build(measure) -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    PROMPTS.mkdir(parents=True, exist_ok=True)
    cache: dict[str, object] = {}
    manifest = []
    for task in rich_tasks(measure):
        instance = task["instance_id"]
        short = measure.repo_short(task["repo"])
        commit = task["base_commit"]
        gpath = measure.GRAPHS / f"{short}_{commit}.json"
        epath = measure.EMBEDS / f"{short}_{commit}.npz"
        if not gpath.exists() or not epath.exists():
            raise SystemExit(f"missing graph for {instance}")
        key = str(gpath)
        if key not in cache:
            cache[key] = measure.Graph(gpath, epath)
            print(f"loaded {gpath.name} nodes={len(cache[key].ids)}", file=sys.stderr)
        graph = cache[key]
        seeds = measure.resolve_seeds(graph, task["problem_statement"])
        resid, usable = measure.residual_matrix(graph)
        arms = measure.arm_sets(graph, seeds, resid, usable)
        call = list(arms["_call_list"])
        zp = ordered_zp(graph, seeds)
        uncapped = render_blocks(graph, zp)
        o_text, o_ids, o_cut = cut_nodes(graph, zp, min(MAX_CODE_CHARS, len(uncapped)))
        budget = len(o_text)
        c_text, c_ids, c_cut = cut_nodes(graph, call, budget)
        issue = task["problem_statement"]
        gold = gold_added(measure, task["patch"])
        row = {
            "instance_id": instance,
            "base_commit": commit,
            "n_seeds": len(seeds),
            "zp_nodes": len(zp),
            "call_nodes": len(call),
            "o_nodes_kept": len(o_ids),
            "c_nodes_kept": len(c_ids),
            "o_chars": len(o_text),
            "c_chars": len(c_text),
            "uncapped_o_chars": len(uncapped),
            "o_char_cut": o_cut,
            "c_char_cut": c_cut,
            "issue_chars": len(issue),
            "gold_added": len(gold),
            "empty_span": budget == 0,
        }
        for arm, code in (("O", o_text), ("C", c_text)):
            prompt = build_prompt(issue, code)
            path = PROMPTS / f"{instance}_{arm}.txt"
            path.write_text(prompt)
            row[f"{arm}_prompt_chars"] = len(prompt)
            row[f"{arm}_prompt"] = str(path)
        manifest.append(row)
        print(
            f"{instance} seeds={len(seeds)} O={len(o_text)}/{len(zp)} C={len(c_text)}/{len(call)} gold_added={len(gold)}",
            file=sys.stderr,
        )
    (OUT / "contexts.jsonl").write_text("".join(json.dumps(row) + "\n" for row in manifest))
    chars_o = [row["o_chars"] for row in manifest]
    chars_c = [row["c_chars"] for row in manifest]
    uncapped = [row["uncapped_o_chars"] for row in manifest]

    def pct(values: list[int], q: float) -> int:
        if not values:
            return 0
        ordered = sorted(values)
        idx = min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))
        return ordered[idx]

    summary = {
        "tasks": len(manifest),
        "empty_span": sum(1 for row in manifest if row["empty_span"]),
        "o_chars_p50": pct(chars_o, 0.5),
        "o_chars_p90": pct(chars_o, 0.9),
        "o_chars_max": max(chars_o) if chars_o else 0,
        "c_chars_p50": pct(chars_c, 0.5),
        "c_chars_max": max(chars_c) if chars_c else 0,
        "uncapped_o_p50": pct(uncapped, 0.5),
        "uncapped_o_max": max(uncapped) if uncapped else 0,
        "o_over_cap": sum(1 for n in uncapped if n > MAX_CODE_CHARS),
        "gold_added_lines": sum(row["gold_added"] for row in manifest),
        "max_code_chars": MAX_CODE_CHARS,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "seed": SEED,
    }
    (OUT / "contexts_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return manifest


def post(prompt: str) -> dict:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "seed": SEED,
        "chat_template_kwargs": {"enable_thinking": True},
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 1:
                time.sleep(2)
                continue
            raise
    raise RuntimeError(last_error)


def message_of(payload: dict) -> tuple[str, str]:
    choice = payload["choices"][0]["message"]
    content = choice.get("content") or ""
    reasoning = choice.get("reasoning") or ""
    return content, reasoning


def generate(measure, limit: int | None) -> None:
    COMPLETIONS.mkdir(parents=True, exist_ok=True)
    manifest = [json.loads(line) for line in (OUT / "contexts.jsonl").read_text().splitlines() if line.strip()]
    if limit is not None:
        manifest = manifest[:limit]
    gold_by_id = {task["instance_id"]: gold_added(measure, task["patch"]) for task in rich_tasks(measure)}
    for row in manifest:
        instance = row["instance_id"]
        gold = gold_by_id[instance]
        for arm in ("O", "C"):
            dest = COMPLETIONS / f"{instance}_{arm}.json"
            if dest.exists():
                print(f"skip {instance} {arm}", file=sys.stderr)
                continue
            prompt = Path(row[f"{arm}_prompt"]).read_text()
            if arm == "C":
                other = COMPLETIONS / f"{instance}_O.json"
                o_prompt = Path(row["O_prompt"]).read_text()
                if other.exists() and prompt == o_prompt:
                    copied = json.loads(other.read_text())
                    copied["arm"] = "C"
                    copied["copied_from_identical_prompt"] = True
                    dest.write_text(json.dumps(copied) + "\n")
                    print(f"copy {instance} C from identical O", file=sys.stderr)
                    continue
            started = time.time()
            record: dict = {"instance_id": instance, "arm": arm, "started": started, "copied_from_identical_prompt": False}
            try:
                payload = post(prompt)
                content, reasoning = message_of(payload)
                diff = extract_diff(content)
                pred = added_from_diff(measure, diff)
                record.update(
                    {
                        "ok": True,
                        "seconds": round(time.time() - started, 3),
                        "content": content,
                        "reasoning_chars": len(reasoning),
                        "diff": diff,
                        "no_diff": diff == "",
                        "gold_added": len(gold),
                        "pred_added": len(pred),
                        "overlap": overlap(gold, pred),
                        "usage": payload.get("usage"),
                    }
                )
            except Exception as exc:  # transport or shape; counted as 0
                record.update(
                    {
                        "ok": False,
                        "seconds": round(time.time() - started, 3),
                        "error": f"{type(exc).__name__}: {exc}",
                        "content": "",
                        "reasoning_chars": 0,
                        "diff": "",
                        "no_diff": True,
                        "gold_added": len(gold),
                        "pred_added": 0,
                        "overlap": 0,
                    }
                )
            dest.write_text(json.dumps(record) + "\n")
            print(
                f"{instance} {arm} ok={record['ok']} overlap={record['overlap']}/{record['gold_added']} "
                f"no_diff={record['no_diff']} seconds={record['seconds']}",
                file=sys.stderr,
            )
    score(measure)


def score(measure) -> None:
    gold_by_id = {task["instance_id"]: gold_added(measure, task["patch"]) for task in rich_tasks(measure)}
    files = sorted(COMPLETIONS.glob("*.json"))
    by_arm: dict[str, list[dict]] = {"O": [], "C": []}
    for path in files:
        row = json.loads(path.read_text())
        by_arm.setdefault(row["arm"], []).append(row)
    report: dict = {"arms": {}, "pairs": 0}
    instances = {row["instance_id"] for rows in by_arm.values() for row in rows}
    paired = [
        inst
        for inst in instances
        if any(r["instance_id"] == inst for r in by_arm.get("O", []))
        and any(r["instance_id"] == inst for r in by_arm.get("C", []))
    ]
    report["pairs"] = len(paired)
    for arm, rows in by_arm.items():
        covered = sum(row["overlap"] for row in rows)
        gold = sum(row["gold_added"] for row in rows)
        report["arms"][arm] = {
            "completions": len(rows),
            "errors": sum(1 for row in rows if not row["ok"]),
            "no_diff": sum(1 for row in rows if row["no_diff"]),
            "overlap": covered,
            "gold_added": gold,
            "recall": (covered / gold) if gold else None,
            "task_hits": sum(1 for row in rows if row["overlap"] > 0),
            "tasks_with_gold": sum(1 for row in rows if row["gold_added"] > 0),
        }
    # Paired micro on tasks where both arms finished. Errors stay as overlap 0.
    both_gold = 0
    both = {"O": 0, "C": 0}
    hits = {"O": 0, "C": 0}
    for inst in paired:
        gold = gold_by_id.get(inst, [])
        both_gold += len(gold)
        for arm in ("O", "C"):
            row = next(r for r in by_arm[arm] if r["instance_id"] == inst)
            both[arm] += row["overlap"]
            if row["overlap"] > 0:
                hits[arm] += 1
    empty = set()
    if (OUT / "contexts.jsonl").exists():
        for line in (OUT / "contexts.jsonl").read_text().splitlines():
            if line.strip():
                ctx = json.loads(line)
                if ctx.get("empty_span"):
                    empty.add(ctx["instance_id"])

    def subset(name: str, pred) -> dict:
        chosen = [inst for inst in paired if pred(inst)]
        gold_n = 0
        ov = {"O": 0, "C": 0}
        hit = {"O": 0, "C": 0}
        for inst in chosen:
            gold_n += len(gold_by_id.get(inst, []))
            for arm in ("O", "C"):
                row = next(r for r in by_arm[arm] if r["instance_id"] == inst)
                ov[arm] += row["overlap"]
                if row["overlap"] > 0:
                    hit[arm] += 1
        return {
            "tasks": len(chosen),
            "gold_added": gold_n,
            "O": ov["O"],
            "C": ov["C"],
            "O_recall": (ov["O"] / gold_n) if gold_n else None,
            "C_recall": (ov["C"] / gold_n) if gold_n else None,
            "O_task_hits": hit["O"],
            "C_task_hits": hit["C"],
        }

    report["paired"] = {
        "tasks": len(paired),
        "gold_added": both_gold,
        "O": both["O"],
        "C": both["C"],
        "O_recall": (both["O"] / both_gold) if both_gold else None,
        "C_recall": (both["C"] / both_gold) if both_gold else None,
        "O_task_hits": hits["O"],
        "C_task_hits": hits["C"],
        "with_span": subset("with_span", lambda inst: inst not in empty),
        "empty_span": subset("empty_span", lambda inst: inst in empty),
    }
    (OUT / "score.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def pytest_probe() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    import shutil
    import subprocess

    docker = shutil.which("docker")
    if docker is None:
        text = "STOP\nDocker is not on PATH. Pytest was not run. Gold-line overlap does not need the sandbox.\n"
        (OUT / "pytest_stop.txt").write_text(text)
        print(text, end="")
        return
    try:
        proc = subprocess.run([docker, "info"], capture_output=True, text=True, timeout=8)
    except (subprocess.TimeoutExpired, OSError) as exc:
        text = f"STOP\nDocker did not answer ({type(exc).__name__}: {exc}). Pytest was not run.\n"
        (OUT / "pytest_stop.txt").write_text(text)
        print(text, end="")
        return
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = err[-3:] if err else ["docker info failed"]
        text = "STOP\n" + "\n".join(tail) + "\nPytest was not run.\n"
        (OUT / "pytest_stop.txt").write_text(text)
        print(text, end="")
        return
    text = "SANDBOX_UP\nDocker answered. Ten-task pytest is not launched by this probe.\n"
    (OUT / "pytest_stop.txt").write_text(text)
    print(text, end="")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    if mode == "pytest":
        pytest_probe()
        return
    measure = load_phase1()
    if mode == "build":
        build(measure)
        return
    if mode == "generate":
        limit = None
        if "--limit" in sys.argv:
            limit = int(sys.argv[sys.argv.index("--limit") + 1])
        if not (OUT / "contexts.jsonl").exists():
            build(measure)
        generate(measure, limit)
        return
    if mode == "score":
        score(measure)
        return
    raise SystemExit(f"unknown mode {mode}")


if __name__ == "__main__":
    main()
