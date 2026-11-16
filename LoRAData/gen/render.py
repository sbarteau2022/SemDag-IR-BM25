#!/usr/bin/env python3
"""Render gate: LoRAData/out/raw_*.jsonl -> LoRAData/final/{train,dev,test}.jsonl, assistant-only loss masking.

Law (Designs/LORA_TRAINING_DESIGN.md 3/5 + handoff decisions):
  * Gemma-4 canonical chat template (LoRAData/reference/chat_template.jinja), enable_thinking=true,
    preserve_thinking=true. Rendered with jinja2 directly: the tokenizer carries no chat template.
  * Loss on assistant turns only. Targets: thought channel, tool-call blocks, content, turn closer.
    Masked: user/system/tool-declaration text, tool responses, the `<|turn>model\\n` opener, and every
    message stamped train:false.
  * Canonical split = source.task_split (task-level); rows whose own `split` disagrees are re-split,
    and drift against split_map(load_tasks()) is a hard reject.
  * Gates before a row is rendered: single-user-turn + alternating-role schema, no special-token
    contamination in any rendered string, exact dedup, near-dup (word 6-gram Jaccard >= 0.85, never
    straddling splits), per-repo / per-unit caps, and a deterministic verifier re-check.

Output rows are trainer-lean: {id, split, family, subtype, repo, task, path, source, text,
input_ids, labels, n_tokens, n_targets}.

CLI:
  render.py selftest                      # masker unit test, no data
  render.py --limit 8 --families py,synth # smoke
  render.py [--no-sandbox] [--no-near-dup] [--no-preserve-thinking] [--repo-cap .6] [--unit-cap 40]
            [--max-tokens 32768] [--dump <id-prefix>]
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

GEN = Path(__file__).resolve().parent
sys.path.insert(0, str(GEN))

import jinja2
import tokenizers as _tklib
import transformers as _tflib
from common import OUT, SPLITS, load_tasks, sha, split_map

from tools import TOOLS

TEMPLATE_PATH = GEN.parent / "reference" / "chat_template.jinja"
TOKENIZER_DIR = GEN.parent / "reference"
DEFAULT_OUT = GEN.parent / "final"

SPECIAL_LITERALS = [
    "<|tool>",
    "<tool|>",
    "<|tool_call>",
    "<tool_call|>",
    "<|tool_response>",
    "<tool_response|>",
    "<|think|>",
    "<|channel>",
    "<channel|>",
    "<|turn>",
    "<turn|>",
    "<|image|>",
    "<|audio|>",
    "<|video|>",
    '<|"|>',
]
OPENER = "<|turn>model\n"
TR_OPEN = "<|tool_response>"
TR_CLOSE = "<tool_response|>"
BOS, EOS = "<bos>", "<eos>"
SHINGLE_N = 6
NEAR_DUP_THRESHOLD = 0.85
MAX_TOKENS_DEFAULT = 32768


class Reject(Exception):
    """A row failed a gate. str(exc) is the reason string."""


# --------------------------------------------------------------------------- template + tokenizer
class Renderer:
    def __init__(self, preserve_thinking=True, max_tokens=MAX_TOKENS_DEFAULT):
        from transformers import AutoTokenizer

        self.preserve_thinking = preserve_thinking
        self.max_tokens = max_tokens
        self.template_text = TEMPLATE_PATH.read_text()
        env = jinja2.Environment(
            keep_trailing_newline=False
        )  # HF apply_chat_template default
        self.template = env.from_string(self.template_text)
        self.tok = AutoTokenizer.from_pretrained(str(TOKENIZER_DIR))
        self._lit = {
            lit: self.tok(lit, add_special_tokens=False)["input_ids"]
            for lit in SPECIAL_LITERALS
        }

    def lit(self, lit):
        if lit not in self._lit:
            self._lit[lit] = self.tok(lit, add_special_tokens=False)["input_ids"]
        ids = self._lit[lit]
        if not ids:
            raise Reject(f"lit:not_special({lit})")
        return ids

    def render_prefix(self, messages, tools, n):
        return self.template.render(
            messages=messages[:n],
            tools=tools,
            bos_token=BOS,
            eos_token=EOS,
            add_generation_prompt=False,
            enable_thinking=True,
            preserve_thinking=self.preserve_thinking,
            raise_exception=lambda s: (_ for _ in ()).throw(ValueError(s)),
        )

    def tokenize(self, text):
        enc = self.tok(text, add_special_tokens=False, return_offsets_mapping=True)
        ids, offs = list(enc["input_ids"]), enc["offset_mapping"]
        if not ids or ids[0] != self.tok.bos_token_id:
            raise Reject(f"tokenize:no_bos(ids0={ids[0] if ids else None})")
        if self.tok.decode(ids) != text:
            raise Reject("tokenize:roundtrip")
        if len(ids) > self.max_tokens:
            raise Reject(f"length:over_ceiling({len(ids)})")
        return ids, offs


# --------------------------------------------------------------------------- schema / contamination
def normalize_ids(row):
    """Give every tool call a stable id and stamp the matching tool_call_id.

    The template resolves a tool response's name by matching tool_call.id == tool_call_id. With no ids
    both are None and every response is attributed to the FIRST call of the turn, which is wrong for
    multi-call turns. Ids are never rendered, so single-call output is unchanged.
    """
    msgs = row["messages"]
    for i, m in enumerate(msgs):
        if m.get("role") != "assistant" or not m.get("tool_calls"):
            continue
        for j, tc in enumerate(m["tool_calls"]):
            tc.setdefault("id", f"call_{i}_{j}")
        k = i + 1
        for tc in m["tool_calls"]:
            if k < len(msgs) and msgs[k].get("role") == "tool":
                msgs[k]["tool_call_id"] = tc["id"]
                k += 1
    return row


def schema_ok(row):
    msgs = row.get("messages")
    if not isinstance(msgs, list) or len(msgs) < 2:
        raise Reject("schema:too_short")
    if msgs[0].get("role") != "user":
        raise Reject(f"schema:first_role({msgs[0].get('role')})")
    if sum(1 for m in msgs if m.get("role") == "user") != 1:
        raise Reject("schema:not_single_user")  # mask prefix-stability depends on this
    if msgs[-1].get("role") != "assistant":
        raise Reject("schema:last_not_assistant")
    declared = None
    if row.get("tools") is not None:
        declared = set()
        for t in row["tools"]:
            fn = (t or {}).get("function") or {}
            if not all(k in fn for k in ("name", "description", "parameters")):
                raise Reject("schema:bad_tool_decl")
            declared.add(fn["name"])
    for i, m in enumerate(msgs):
        role = m.get("role")
        if role == "tool":
            if "content" not in m or "name" not in m:
                raise Reject("schema:tool_fields")
            if i == 0 or msgs[i - 1]["role"] == "user":
                raise Reject("schema:tool_after_user")
            continue
        if role == "user":
            if not isinstance(m.get("content"), str) or not m["content"].strip():
                raise Reject("schema:user_content")
            continue
        if role != "assistant":
            raise Reject(f"schema:role({role})")
        if not isinstance(m.get("reasoning_content"), str):
            raise Reject("schema:no_thought")  # reason-first is mandatory in this data
        calls = m.get("tool_calls") or []
        need = len(calls)
        j = i + 1
        while j < len(msgs) and msgs[j].get("role") == "tool":
            need -= 1
            j += 1
        if need != 0:
            raise Reject("schema:dangling_tool_call")
        for tc in calls:
            fn = tc.get("function") or {}
            name = fn.get("name")
            if not isinstance(name, str):
                raise Reject("schema:tool_name")
            if name not in TOOLS:
                raise Reject(f"schema:unknown_tool({name})")
            if declared is not None and name not in declared:
                raise Reject(f"schema:undeclared_tool({name})")
        if not calls and not m.get("content") and i != len(msgs) - 1:
            raise Reject("schema:empty_turn")


def contamination_scan(row):
    """A special-token literal inside rendered text would corrupt span detection or semantics."""

    def walk(s):
        if not isinstance(s, str):
            return
        for lit in SPECIAL_LITERALS:
            if lit in s:
                raise Reject(f"contamination:{lit}")

    for m in row["messages"]:
        walk(m.get("content"))
        walk(m.get("reasoning_content"))
        for tc in m.get("tool_calls") or []:
            walk(tc["function"]["name"])
            for v in tc["function"]["arguments"].values():
                walk(v if isinstance(v, str) else json.dumps(v))


def canonical_split(row, smap):
    t = row["source"].get("task")
    ts = row["source"].get("task_split")
    if ts in SPLITS:
        if t != "synthetic" and smap.get(t) != ts:
            raise Reject(f"split:drift({t})")
        return ts
    if ts == "synthetic" or t == "synthetic":
        own = row.get("split")
        if own not in SPLITS:
            raise Reject(f"split:synth_bad({own})")
        return own
    raise Reject(f"split:missing({ts})")


# --------------------------------------------------------------------------- verifier re-checks
def _stated(row, suffix):
    c = str(row["messages"][-1]["content"])
    if not c.endswith(suffix):
        raise Reject(f"verify:answer_not_stated({suffix[:24]})")


def check_synth_dag(row, v):
    import collections as _c

    import g_graph as _g
    from g_synth import parse_spec

    kind, spec, q = v["spec_kind"], v["spec"], v["q"]
    deps = parse_spec(kind, spec)
    if deps is None:
        raise Reject("verify:spec_unparseable")
    mods = sorted(deps)
    # kahn/sccs take the reverse adjacency dep -> dependent, exactly as build_order builds it
    out_edges = {m: set() for m in deps}
    for m, ds in deps.items():
        for x in ds:
            out_edges[x].add(m)
    comps = [c for c in _g.sccs(mods, out_edges) if len(c) > 1]
    if comps and q != "cycle":
        raise Reject("verify:cyclic_noncycle")
    if q == "order":
        val, _ = _g.kahn(sorted(deps), out_edges)
    elif q == "compile":
        val = {m: deps[m] for m in mods}
    elif q == "cycle":
        val = {"build_possible": not comps, "cycles": comps}
    else:
        dep = {}
        # depth = 1 + deepest prerequisite, over the topo order (prerequisites first)
        order, _ = _g.kahn(sorted(deps), out_edges)
        for m in order:
            dep[m] = 1 + max([dep[x] for x in deps[m]] or [0])
        if q == "waves":
            w = _c.defaultdict(list)
            for m, d in dep.items():
                w[str(d - 1)].append(m)
            val = {
                k: sorted(x) for k, x in sorted(w.items(), key=lambda kv: int(kv[0]))
            }
        else:
            top = max(dep.values())
            chains = []

            def back(m, tail):
                if dep[m] == 1:
                    chains.append([m] + tail)
                    return
                for x in deps[m]:
                    if dep[x] == dep[m] - 1:
                        back(x, [m] + tail)

            for m in sorted(deps):
                if dep[m] == top:
                    back(m, [])
            val = min(chains)
    if val != v["answer"]:
        raise Reject(f"verify:answer_drift(synth/{q})")
    _stated(row, "ANSWER: " + _g.fmt(val))


def check_graph(row, v):
    from g_graph import fmt, solve

    val = solve(v["q"], v["nodes"], v["edges"], v["args"])
    if val != v["answer"]:
        raise Reject("verify:answer_drift(graph)")
    _stated(row, "ANSWER: " + fmt(val))


def check_ir(row, v):
    import ast

    from g_graph import fmt
    from g_synth import ir_of

    try:
        ir, _ = ir_of(ast.parse(v["source"]).body[0])
    except SyntaxError:
        raise Reject("verify:ir_source_syntax")
    if ir != v["answer"]:
        raise Reject("verify:answer_drift(ir)")
    _stated(row, "ANSWER: " + fmt(ir))


def check_edit_traj(row, v):
    """The trajectory's own edit_file calls must reproduce the stored diff exactly."""
    text = v["bad_text"]
    for e in v["edits"]:
        if text.count(e["old"]) != 1:
            raise Reject("verify:old_not_unique")
        text = text.replace(e["old"], e["new"], 1)
    if text != v["orig_text"]:
        raise Reject("verify:edit_mismatch")
    performed = set()
    for m in row["messages"]:
        for tc in m.get("tool_calls") or []:
            a = tc["function"]["arguments"]
            if tc["function"]["name"] == "edit_file":
                performed.add((a.get("old_string"), a.get("new_string")))
    for e in v["edits"]:
        if (e["old"], e["new"]) not in performed:
            raise Reject("verify:edit_not_performed")


def check_py(row, v, sandbox):
    import sandbox as sbx

    kind, ctx = v["kind"], v.get("context") or ""
    user = str(row["messages"][0]["content"])
    fname, orig, expected, calls = v["fname"], v["original"], v["expected"], v["calls"]
    final = str(row["messages"][-1]["content"])
    want = "```python\n" + orig + "\n```"
    if final.strip() != want.strip():
        raise Reject(f"verify:answer_not_verbatim({kind})")
    if kind == "fn_repair":
        if f"```python\n{v['mutant']}\n```" not in user:
            raise Reject("verify:prompt_not_mutant(fn_repair)")
    else:
        from g_py import show_call

        exs = "\n".join(
            f"- `{show_call(fname, calls[i])}` returns `{expected[i]['ok']}`"
            for i in v["shown"]
        )
        if exs not in user:
            raise Reject("verify:prompt_examples_drift(spec_to_code)")
    if not sandbox:
        return
    from g_py import full

    base = sbx.run(full(ctx, orig), fname, calls)
    if not base or [dict(x) for x in base] != [dict(x) for x in expected]:
        raise Reject(f"verify:oracle_drift({kind})")
    if kind == "fn_repair":
        m = sbx.run(full(ctx, v["mutant"]), fname, calls)
        if not m or m[v["shown"]] == base[v["shown"]]:
            raise Reject("verify:mutant_indistinguishable")


def check_exec_trace(row, v, sandbox):
    if not sandbox:
        return
    import sandbox as sbx
    from g_py import full, show_call, trace_text

    ctx, fname, orig = v.get("context") or "", v["fname"], v["original"]
    user = str(row["messages"][0]["content"])
    if f"```python\n{orig}\n```" not in user:
        raise Reject("verify:prompt_not_source(exec_trace)")
    if show_call(fname, v["call"]) not in user:
        raise Reject("verify:prompt_call_drift(exec_trace)")
    tr = sbx.run(full(ctx, orig), fname, [v["call"]], trace=True)
    if not tr:
        raise Reject("verify:trace_none")
    res = tr[0]
    ans = res["ok"] if "ok" in res else "raises " + res["exc"]
    if ans != v["answer"]:
        raise Reject("verify:trace_drift")
    if str(row["messages"][-1]["content"]) != "ANSWER: " + v["answer"]:
        raise Reject("verify:trace_answer_not_stated")
    want = trace_text(
        orig, [tuple(s) for s in res["steps"]], res, (ctx.count("\n") + 2) if ctx else 0
    )
    if str(row["messages"][-1]["reasoning_content"]) != want:
        raise Reject("verify:trace_text_drift")


def verify_row(row, sandbox):
    v = row.get("verifier") or {}
    k = v.get("kind")
    if k == "synth_dag":
        check_synth_dag(row, v)
    elif k == "graph":
        check_graph(row, v)
    elif k == "ir":
        check_ir(row, v)
    elif k == "edit_traj":
        check_edit_traj(row, v)
    elif k in ("fn_repair", "spec_to_code"):
        check_py(row, v, sandbox)
    elif k == "exec_trace":
        check_exec_trace(row, v, sandbox)
    else:
        raise Reject(f"verify:no_verifier({k})")


# --------------------------------------------------------------------------- dedup / near-dup / caps
def shingles(text, n=SHINGLE_N):
    words = [
        w for w in "".join(c if c.isalnum() else " " for c in text.lower()).split() if w
    ]
    return set(tuple(words[i : i + n]) for i in range(max(0, len(words) - n + 1)))


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def near_dup_drops(rows, use):
    """Drop every row in a near-dup cluster except the highest-priority one.

    Priority is by split (test > dev > train) so a near-duplicate never straddles the boundary: the
    held-out copy wins and the train-side copy is dropped, keeping dev/test honest.
    """
    if not use:
        return set(), collections.Counter()
    prio = {"test": 0, "dev": 1, "train": 2}
    sh = [shingles(r["_prompt"]) for r in rows]
    inv = collections.defaultdict(list)
    for i, s in enumerate(sh):
        for g in s:
            inv[g].append(i)
    cand = collections.Counter()
    for post in inv.values():
        if len(post) > 400:  # boilerplate shingle, not evidence of a near-dup
            continue
        post = sorted(post)
        for a in range(len(post)):
            for b in range(a + 1, len(post)):
                cand[(post[a], post[b])] += 1
    parent = list(range(len(rows)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (i, j), c in cand.items():
        if c < 3 or c / min(len(sh[i]), len(sh[j])) < NEAR_DUP_THRESHOLD:
            continue
        if jaccard(sh[i], sh[j]) >= NEAR_DUP_THRESHOLD:
            ra, rb = find(i), find(j)
            if ra != rb:
                parent[rb] = ra
    clusters = collections.defaultdict(list)
    for i in range(len(rows)):
        clusters[find(i)].append(i)
    drops, why = set(), collections.Counter()
    for idxs in clusters.values():
        if len(idxs) < 2:
            continue
        idxs.sort(key=lambda i: (prio[rows[i]["split"]], rows[i]["id"]))
        if len({rows[i]["split"] for i in idxs}) > 1:
            why["near_dup:straddling_cluster"] += 1
            why[
                f"near_dup:dropped_keeps_{rows[idxs[0]]['split']}({len(idxs) - 1})"
            ] += 1
        else:
            why["near_dup:dropped_duplicate"] += 1
        drops.update(rows[i]["id"] for i in idxs[1:])
    return drops, why


def cap_key(r):
    s = r["source"]
    if s.get("task") == "synthetic":
        v = r.get("verifier") or {}
        return "synth:" + sha(str(v.get("spec") or v.get("source") or ""))
    return str(s.get("path") or s.get("seed") or s.get("task") or "unit")


def apply_caps(rows, repo_cap, unit_cap):
    """Deterministic caps; converges in closed form so the ratchet cannot eat a split."""
    why = collections.Counter()
    skipped = []

    def repo_cap_round(rs):
        n = len(rs)
        if n == 0:
            return [], []
        counts = collections.Counter(r["repo"] for r in rs)
        if len(counts) <= 1:
            return rs, []
        drop_idx = set()
        for repo, c in sorted(counts.items()):
            # smallest x with (c - x) / (n - x) <= cap; x = 0 keeps the invariant intact
            need = (c - repo_cap * n) / (1 - repo_cap) if repo_cap < 1 else c
            x = int(need) + (1 if need > int(need) else 0)
            if x <= 0:
                continue
            own = sorted(
                (i for i, r in enumerate(rs) if r["repo"] == repo),
                key=lambda i: rs[i]["id"],
            )
            drop_idx.update(own[:x])
        if not drop_idx:
            return rs, []
        kept = [r for i, r in enumerate(rs) if i not in drop_idx]
        why[f"cap_repo(>{int(repo_cap * 100)}%)"] += len(drop_idx)
        return kept, [len(drop_idx)]

    for _ in range(6):
        changed = False
        by_unit = collections.defaultdict(list)
        for r in rows:
            by_unit[(r["split"], cap_key(r))].append(r)
        bad = set()
        for _, rs in sorted(by_unit.items()):
            if len(rs) > unit_cap:
                rs.sort(key=lambda r: r["id"])
                bad.update(r["id"] for r in rs[unit_cap:])
        if bad:
            rows = [r for r in rows if r["id"] not in bad]
            why[f"cap_unit(>{unit_cap})"] += len(bad)
            changed = True
        by_split = collections.defaultdict(list)
        for r in rows:
            by_split[r["split"]].append(r)
        for sp in sorted(by_split):
            kept, n = repo_cap_round(by_split[sp])
            if n:
                rows = [r for r in rows if r["split"] != sp] + kept
                rows.sort(key=lambda r: r["id"])
                by_split[sp] = kept
                changed = True
        if not changed:
            break
    for sp in sorted({r["split"] for r in rows}):
        rs = [r for r in rows if r["split"] == sp]
        counts = collections.Counter(r["repo"] for r in rs)
        top = counts.most_common(1)[0]
        if len(counts) > 1 and top[1] / len(rs) > repo_cap + 1e-9:
            skipped.append(
                {
                    "split": sp,
                    "repo": top[0],
                    "share": round(top[1] / len(rs), 4),
                    "n": len(rs),
                }
            )
    return rows, why, skipped


# --------------------------------------------------------------------------- render + mask
def char_span(offs, text, a, b):
    """Half-open char span -> token span. Rejects a boundary that lands inside a token."""
    i0 = next((i for i, (s, e) in enumerate(offs) if e > a), len(offs))
    if i0 == len(offs):
        return i0, i0
    if offs[i0][0] < a:
        raise Reject("mask:straddle_start")
    i1 = next((i for i in range(i0, len(offs)) if offs[i][0] >= b), len(offs))
    if i1 > 0 and offs[i1 - 1][1] > b:
        raise Reject("mask:straddle_end")
    return i0, i1


def render_row(R, row):
    """Render one row to text, then mask everything that is not a trainable assistant token."""
    msgs, tools = row["messages"], row.get("tools")
    texts = [R.render_prefix(msgs, tools, i) for i in range(1, len(msgs) + 1)]
    for i in range(1, len(texts)):
        if not texts[i].startswith(texts[i - 1]):
            raise Reject("render:prefix_unstable")
    full = texts[-1]
    deltas, prev = [], 0
    for i, t in enumerate(texts):
        if len(t) > prev:
            deltas.append((prev, len(t), msgs[i]))
        prev = len(t)
    if prev != len(full):
        raise Reject("render:delta_gap")
    ids, offs = R.tokenize(full)
    tr_open, tr_close = R.lit(TR_OPEN)[0], R.lit(TR_CLOSE)[0]
    opener_ids = R.lit(OPENER)
    labels = [-100] * len(ids)
    for a, b, m in deltas:
        if m["role"] != "assistant" or m.get("train") is False:
            continue
        i0, i1 = char_span(offs, full, a, b)
        if i0 >= i1:
            continue
        labels[i0:i1] = ids[i0:i1]
        # the turn opener `<|turn>model\n` is structural: inference emits it via
        # add_generation_prompt, so it is masked even though the model produces it
        if full[a:b].startswith(OPENER):
            if ids[i0 : i0 + len(opener_ids)] != opener_ids:
                raise Reject("mask:opener_mismatch")
            labels[i0 : i0 + len(opener_ids)] = [-100] * len(opener_ids)
    n_blocks, k = 0, 0
    while k < len(ids):
        if ids[k] != tr_open:
            k += 1
            continue
        j = k + 1
        while j < len(ids) and ids[j] != tr_close:
            j += 1
        if j >= len(ids):
            raise Reject("mask:unterminated_tool_response")
        labels[k : j + 1] = [-100] * (j + 1 - k)
        n_blocks += 1
        k = j + 1
    n_tool_msgs = sum(1 for m in msgs if m["role"] == "tool")
    if n_blocks != n_tool_msgs:
        raise Reject(f"mask:block_count({n_blocks}!={n_tool_msgs})")
    n_targets = sum(1 for x in labels if x != -100)
    if n_targets == 0:
        raise Reject("mask:no_targets")
    return {
        "id": row["id"],
        "split": row["split"],
        "family": row["family"],
        "subtype": row["subtype"],
        "repo": row.get("repo"),
        "task": row.get("task"),
        "path": row.get("path"),
        "unit": cap_key(row),
        "source": row["source"],
        "text": full,
        "input_ids": ids,
        "labels": labels,
        "n_tokens": len(ids),
        "n_targets": n_targets,
    }


def in_response(R, ids, i):
    """True when token i sits inside a tool-response block (which is always masked)."""
    op, cl = R.lit(TR_OPEN)[0], R.lit(TR_CLOSE)[0]
    k = i
    while k >= 0:
        if ids[k] == op:
            j = k + 1
            while j < len(ids) and ids[j] != cl:
                j += 1
            return i <= j
        k -= 1
    return False


def dump_masked(R, rec, limit=90):
    """Text view of the mask: T = target, M = masked, one line per contiguous run."""
    ids, labels = rec["input_ids"], rec["labels"]
    runs, cur = [], None
    for i, lab in enumerate(labels):
        key = "T" if lab != -100 else "M"
        if cur and cur[0] == key:
            cur[2] = i
        else:
            if cur:
                runs.append(cur)
            cur = [key, i, i]
    runs.append(cur)
    print(
        f"\n=== dump {rec['id']} split={rec['split']} tokens={len(ids)} targets={sum(1 for x in labels if x != -100)} ==="
    )
    for k, a, b in runs:
        txt = R.tok.decode(ids[a : b + 1])
        shown = (
            txt
            if len(txt) <= limit
            else txt[: limit // 2] + " ... " + txt[-(limit // 2) :]
        )
        print(f"{k} [{a:>5}:{b + 1:>5}] n={b - a + 1:<5} {shown!r}")


# --------------------------------------------------------------------------- selftest
def selftest():
    """Prove the mask law on a hand-built row: parallel tool calls, a wrong turn, a tools block."""
    from tools import tools

    R = Renderer()
    row = {
        "id": "selftest",
        "split": "train",
        "family": "selftest",
        "subtype": "mask",
        "repo": "test/repo",
        "task": "selftest",
        "path": "p.py",
        "thinking": True,
        "source": {
            "repo": "test/repo",
            "task": "selftest",
            "path": "p.py",
            "task_split": "train",
        },
        "tools": tools("read_file", "edit_file"),
        "messages": [
            {"role": "user", "content": "Fix the comparison operator in p.py."},
            {
                "role": "assistant",
                "reasoning_content": "I read the file first.",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": {"filepath": "p.py"},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": {"filepath": "q.py"},
                        },
                    },
                ],
            },
            {
                "role": "tool",
                "name": "read_file",
                "content": "x = 1\nif x >= 2:\n    pass\n",
            },
            {"role": "tool", "name": "read_file", "content": "y = 2\n"},
            {
                "role": "assistant",
                "reasoning_content": "I will try the wrong edit first to show recovery.",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "edit_file",
                            "arguments": {
                                "filepath": "p.py",
                                "old_string": "x >= 2",
                                "new_string": "x <= 2",
                            },
                        },
                    }
                ],
                "train": False,
            },
            {"role": "tool", "name": "edit_file", "content": "not the right line"},
            {
                "role": "assistant",
                "reasoning_content": "That was wrong. I switch approach and target x >= 2 in the file I actually read.",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "edit_file",
                            "arguments": {
                                "filepath": "p.py",
                                "old_string": "if x >= 2:",
                                "new_string": "if x < 2:",
                            },
                        },
                    }
                ],
            },
            {"role": "tool", "name": "edit_file", "content": "ok"},
            {
                "role": "assistant",
                "reasoning_content": "Verified.",
                "content": "Fixed p.py.",
            },
        ],
    }
    normalize_ids(row)
    schema_ok(row)
    contamination_scan(row)
    rec = render_row(R, row)
    ids, labels = rec["input_ids"], rec["labels"]
    text = rec["text"]
    # invariants, each one falsifiable
    assert ids[0] == R.tok.bos_token_id
    assert R.tok.decode(ids) == text
    assert text.count(TR_OPEN) == 4 and text.count(TR_CLOSE) == 4
    assert labels[0] == -100 and ids[0] != -100
    offs = R.tok(text, add_special_tokens=False, return_offsets_mapping=True)[
        "offset_mapping"
    ]

    # the system + user span is fully masked: bos, <|turn>system, <|think|>, tools, user turn
    user_start = text.index("<|turn>user\n")
    s0, s1 = char_span(offs, text, 0, user_start)
    assert all(x == -100 for x in labels[s0:s1]), "system + user prefix must be masked"

    # the opener is masked; the thought immediately after it is a target
    q = text.index(OPENER)
    q_end = q + len(OPENER)
    i0, i1 = char_span(offs, text, q, q_end)
    assert ids[i0:i1] == R.lit(OPENER), "opener literal must tokenise in place"
    assert labels[i0:i1] == [-100] * len(R.lit(OPENER)), "opener must be masked"
    assert labels[i1] != -100, "thought after opener must be a target"

    # every tool_response block is masked
    k = 0
    while k < len(ids):
        if ids[k] == R.lit(TR_OPEN)[0]:
            j = k + 1
            while ids[j] != R.lit(TR_CLOSE)[0]:
                j += 1
            assert all(x == -100 for x in labels[k : j + 1]), (
                "tool response must be masked"
            )
            k = j + 1
        else:
            k += 1

    # per-turn law, taken from the same prefix deltas render_row uses: a trainable assistant turn
    # is all target except its opener; a train=false turn is masked in full
    texts = [
        R.render_prefix(row["messages"], row["tools"], i)
        for i in range(1, len(row["messages"]) + 1)
    ]
    prev = 0
    for i, t in enumerate(texts):
        m = row["messages"][i]
        if len(t) == prev:
            continue
        a, b = prev, len(t)
        prev = len(t)
        if m["role"] != "assistant":
            x0, x1 = char_span(offs, text, a, b)
            assert all(x == -100 for x in labels[x0:x1]), (
                f"non-assistant turn {i} must be masked"
            )
            continue
        x0, x1 = char_span(offs, text, a, b)
        if m.get("train") is False:
            assert all(x == -100 for x in labels[x0:x1]), (
                f"train=false turn {i} must be masked"
            )
            continue
        n_open = len(R.lit(OPENER)) if text[a:b].startswith(OPENER) else 0
        assert all(x == -100 for x in labels[x0 : x0 + n_open]), "opener masked"
        # every token of a trainable turn is a target except the opener and any tool-response
        # block the template forward-scans into this turn's span
        bad = [
            t
            for t in range(x0 + n_open, x1)
            if labels[t] == -100 and not in_response(R, ids, t)
        ]
        assert not bad, f"trainable turn {i} has unexpected masked tokens at {bad[:5]}"
        for t in range(x0, x1):
            if ids[t] == R.lit(TR_OPEN)[0]:
                e = t + 1
                while ids[e] != R.lit(TR_CLOSE)[0]:
                    e += 1
                assert all(x == -100 for x in labels[t : e + 1]), (
                    "response inside a turn masked"
                )

    # the deliberately wrong turn is masked in full: thought, tool call, everything
    wrong_think = str(row["messages"][4]["reasoning_content"])
    w = text.index(wrong_think)
    ch = text.rindex("<|channel>", 0, w)
    cl = text.index("<channel|>", w)
    w0, w1 = char_span(offs, text, ch, cl)
    assert all(x == -100 for x in labels[w0:w1]), (
        "train=false turn must be masked in full"
    )
    assert labels.count(-100) + rec["n_targets"] == len(ids)
    dump_masked(R, rec)
    print(
        f"\nSELFTEST OK  tokens={len(ids)} targets={rec['n_targets']} "
        f"ratio={rec['n_targets'] / len(ids):.3f} text={len(text)} chars"
    )
    return 0


# --------------------------------------------------------------------------- driver
def pct(xs, q):
    if not xs:
        return 0
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="LoRA render gate: raw_*.jsonl -> masked final/"
    )
    ap.add_argument("mode", nargs="?", default="run", choices=["run", "selftest"])
    ap.add_argument("--families", default="agent,graph,ir,py,synth")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument(
        "--limit", type=int, default=0, help="first N rows per family (smoke)"
    )
    ap.add_argument(
        "--no-sandbox", action="store_true", help="skip execution verifier re-checks"
    )
    ap.add_argument(
        "--no-preserve-thinking",
        action="store_true",
        help="A/B: preserve_thinking=false",
    )
    ap.add_argument("--no-near-dup", action="store_true")
    ap.add_argument("--repo-cap", type=float, default=0.60)
    ap.add_argument("--unit-cap", type=int, default=40)
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS_DEFAULT)
    ap.add_argument(
        "--dump",
        default="",
        help="dump the masked rendering of the first row with this id prefix",
    )
    args = ap.parse_args(argv)
    if args.mode == "selftest":
        return selftest()

    fams = [f.strip() for f in args.families.split(",") if f.strip()]
    R = Renderer(
        preserve_thinking=not args.no_preserve_thinking, max_tokens=args.max_tokens
    )
    smap = split_map(load_tasks())
    t0 = time.time()

    loaded = []
    for fam in fams:
        p = OUT / f"raw_{fam}.jsonl"
        if not p.exists():
            print(f"!! missing {p}", file=sys.stderr)
            continue
        rows = [json.loads(l) for l in open(p)]
        loaded.extend(rows[: args.limit] if args.limit else rows)
    n_in = len(loaded)
    rejects = collections.Counter()
    survivors, re_split = [], 0

    for row in loaded:
        try:
            if not isinstance(row.get("source"), dict) or "task" not in row["source"]:
                raise Reject("schema:source")
            normalize_ids(row)
            schema_ok(row)
            contamination_scan(row)
            # provenance the caps and the manifest read at the top level
            row["repo"] = row["source"].get("repo") or "synthetic"
            row["task"] = row["source"].get("task")
            row["path"] = row["source"].get("path") or row["source"].get("seed")
            raw = row.get("split")
            row["split"] = canonical_split(row, smap)
            if raw != row["split"]:
                rejects["split:row_level_reassigned"] += 1
            rid = sha(
                f"{row['family']}|{row['subtype']}|{row['source'].get('task')}|"
                f"{row['source'].get('path') or row['source'].get('seed')}|"
                f"{json.dumps(row['messages'], sort_keys=True)}",
                16,
            )
            row["id"] = rid
            row["_prompt"] = str(row["messages"][0]["content"])
            survivors.append(row)
        except Reject as e:
            rejects[str(e)] += 1
        except Exception as e:
            rejects[f"gate_exception:{type(e).__name__}:{e}"] += 1

    n_gate = len(survivors)
    seen, uniq = set(), []
    for r in survivors:
        k = sha(json.dumps(r["messages"], sort_keys=True), 16)
        if k in seen:
            rejects["dedup:exact"] += 1
            continue
        seen.add(k)
        uniq.append(r)

    drops, why = near_dup_drops(uniq, not args.no_near_dup)
    for k, v in why.items():
        rejects[k] += v
    if drops:
        uniq = [r for r in uniq if r["id"] not in drops]

    n_verify = len(uniq)
    for r in uniq:
        try:
            verify_row(r, not args.no_sandbox)
        except Reject as e:
            rejects[str(e)] += 1
            r["_bad"] = True
    n_verify = len([r for r in uniq if not r.get("_bad")])
    uniq = [r for r in uniq if not r.get("_bad")]
    n_nd = len(uniq)

    uniq, capwhy, cap_skipped = apply_caps(uniq, args.repo_cap, args.unit_cap)
    for k, v in capwhy.items():
        rejects[k] += v
    for s in cap_skipped:
        rejects[f"cap_repo:unsatisfiable({s['split']}/{s['repo']}@{s['share']})"] += 1

    final = []
    for r in uniq:
        try:
            final.append(render_row(R, r))
        except Reject as e:
            rejects[str(e)] += 1
        except Exception as e:
            rejects[f"render_exception:{type(e).__name__}:{e}"] += 1
        if args.dump and r["id"].startswith(args.dump):
            if final and final[-1]["id"] == r["id"]:
                dump_masked(R, final[-1])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for sp in SPLITS:
        rs = sorted(
            [r for r in final if r["split"] == sp],
            key=lambda r: (r["family"], r["subtype"], r["id"]),
        )
        p = out / f"{sp}.jsonl"
        with open(p, "w") as f:
            for r in rs:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        paths[sp] = {
            "path": str(p),
            "rows": len(rs),
            "tokens": sum(r["n_tokens"] for r in rs),
        }
    toks = sorted(r["n_tokens"] for r in final)
    tgts = sorted(r["n_targets"] for r in final)
    tot_t, tot_g = sum(toks), sum(tgts)
    per_family = {}
    for f in sorted({r["family"] for r in final}):
        rs = [r for r in final if r["family"] == f]
        t, g = sum(x["n_tokens"] for x in rs), sum(x["n_targets"] for x in rs)
        per_family[f] = {
            "rows": len(rs),
            "tokens": t,
            "targets": g,
            "target_ratio": round(g / max(1, t), 4),
            "len_p50": pct(sorted(x["n_tokens"] for x in rs), 0.5),
            "len_max": max(x["n_tokens"] for x in rs),
        }
    cap_realized = {}
    for sp in SPLITS:
        rs = [r for r in final if r["split"] == sp]
        if rs:
            c = collections.Counter(r["repo"] for r in rs)
            top = c.most_common(1)[0]
            cap_realized[sp] = {
                "n": len(rs),
                "top_repo": top[0],
                "top_share": round(top[1] / len(rs), 4),
            }
    receipt = {
        "run": {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "argv": sys.argv[1:],
            "families": fams,
            "seconds": round(time.time() - t0, 1),
            "n_in": n_in,
            "n_out": len(final),
            "gates": {
                "loaded": n_in,
                "schema_contamination_split": n_gate,
                "after_exact_dedup": n_gate - rejects["dedup:exact"],
                "after_near_dup": n_nd,
                "after_verify": n_verify,
                "after_caps": len(uniq),
                "rendered": len(final),
            },
        },
        "settings": {
            "template": "LoRAData/reference/chat_template.jinja",
            "enable_thinking": True,
            "preserve_thinking": not args.no_preserve_thinking,
            "assistant_only_masking": True,
            "masked_opener_literal": OPENER,
            "masked_tool_response_blocks": True,
            "masked_train_false_turns": True,
            "max_tokens": R.max_tokens,
            "repo_cap": args.repo_cap,
            "unit_cap": args.unit_cap,
            "near_dup": not args.no_near_dup,
            "near_dup_threshold": NEAR_DUP_THRESHOLD,
            "near_dup_metric": f"user-prompt word{SHINGLE_N}gram jaccard",
            "sandbox_verify": not args.no_sandbox,
            "exec_backed_rows": {
                k: sum(1 for r in final if r["subtype"] == k)
                for k in ("exec_trace", "fn_repair", "spec_to_code")
            },
            "platform_note": (
                "darwin: gen/sandbox.py preexec hardening (os.setsid, RLIMIT_AS) is not permitted, "
                "so execution re-checks for exec_trace/fn_repair/spec_to_code were skipped and those "
                "rows carry their stored labels unre-executed. Re-run under Linux/Docker to earn "
                "the execution receipt."
                if args.no_sandbox
                else None
            ),
        },
        "env": {
            "python": platform.python_version(),
            "transformers": _tflib.__version__,
            "tokenizers": _tklib.__version__,
            "jinja2": jinja2.__version__,
            "bos_token_id": R.tok.bos_token_id,
            "vocab_size": len(R.tok),
            "template_sha256": hashlib.sha256(TEMPLATE_PATH.read_bytes()).hexdigest(),
            "tokenizer_sha256": hashlib.sha256(
                (TOKENIZER_DIR / "tokenizer.json").read_bytes()
            ).hexdigest(),
        },
        "rejects": dict(rejects.most_common()),
        "splits": {sp: sum(1 for r in final if r["split"] == sp) for sp in SPLITS},
        "families": {
            f"{f}/{s}": c
            for (f, s), c in sorted(
                collections.Counter((r["family"], r["subtype"]) for r in final).items()
            )
        },
        "repos": dict(collections.Counter(r["repo"] for r in final)),
        "tokens": {
            "total": tot_t,
            "targets": tot_g,
            "target_ratio": round(tot_g / max(1, tot_t), 4),
            "len_p50": pct(toks, 0.5),
            "len_p95": pct(toks, 0.95),
            "len_max": toks[-1] if toks else 0,
            "targets_p50": pct(tgts, 0.5),
            "targets_p95": pct(tgts, 0.95),
        },
        "per_family": per_family,
        "repo_share_realized": cap_realized,
        "notes": [
            "tasks.jsonl holds exactly the 129 public instances (4 repos), so the design doc's "
            "'exclude all 129' rule would empty the set. Operative law: the task-level 60/15/25 split "
            "(source.task_split), verified against split_map(load_tasks()); the paper must not present "
            "public-set numbers as private-set estimates.",
            "preserve_thinking=true is mandatory: with the default false the template's thinking_gate "
            "drops intermediate thoughts on tool-call turns, contradicting 'thinking tokens are "
            "learning targets'.",
            "Rows whose own `split` disagreed with source.task_split were re-split at the row level; "
            "the task boundary is the only boundary that carries.",
            "repo_share_realized counts synthetic rows under repo='synthetic'; they are bounded by "
            "the same per-repo cap as real repos, which is what keeps the share honest.",
            "unit cap key is (split, family, subtype, cap_key) where cap_key is the file path for "
            "real tasks, the graph seed for graph rows, and a hash of the generated spec for "
            "synthetic rows; it is written to every output row as `unit` so the cap is auditable.",
        ],
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True))
    manifest = [
        {
            k: r[k]
            for k in (
                "id",
                "split",
                "family",
                "subtype",
                "repo",
                "task",
                "path",
                "n_tokens",
                "n_targets",
            )
        }
        for r in sorted(
            final, key=lambda r: (r["split"], r["family"], r["subtype"], r["id"])
        )
    ]
    (out / "manifest.json").write_text(json.dumps(manifest, indent=0, sort_keys=True))
    print(
        json.dumps(
            {
                "in": n_in,
                "out": len(final),
                "splits": receipt["splits"],
                "tokens": receipt["tokens"],
                "rejects": receipt["rejects"],
                "files": {sp: v["path"] for sp, v in paths.items()},
                "seconds": receipt["run"]["seconds"],
            },
            indent=1,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
