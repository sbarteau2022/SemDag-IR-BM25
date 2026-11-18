"""Build AgenticSubmission/v8_ensemble from v7's skill and the v8 sources in Tools/v8_ensemble.

    .venv-harness/bin/python Tools/v8_ensemble/build_v8.py

Owner design (2026-11-17): army script + 4 implementers (4k hard output cap each, parallel),
4 adversarial reviewers (4k each, parallel), a coordinator (6k: pytest, static typecheck, code
review over every candidate) and a final implementer (6k: adopt, fix, last test run, submit).
Thinking (owner, 2026-11-18): every thinking role has thinking_budget 0, so the harness sends no
thinking_token_budget (vllm-metal rejects it), and a literal <|think|> as the first line of the role
instruction turns Gemma 4 thinking on. The hard output cap (4096 / 6144) is the only bound.
Implementers edit only through scripts/edit.py, which always writes into their own copy.
The generated directory is overwritten on every build; edit the sources here, not the output.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(__file__).resolve().parent
V7 = ROOT / "AgenticSubmission" / "v7_brigade_lite"
OUT = ROOT / "AgenticSubmission" / "v8_ensemble"
MODEL = "gemma-4-e4b-it-qat-w4a16-ct"
K = 4

SKILL_MD = """---
name: semdag
description: Deterministic scripts for the v8 ensemble - fork (army), audit, review_pack, save_cex, gate, adopt - plus meta and repo_eval.
---

All calls go through `run_skill_script` with `skill_name: semdag`. Every script prints one compact JSON object and never raises. Caches live in the temp directory, so nothing enters the patch.

| file_path | args | Use |
|---|---|---|
| `scripts/fork.py` | `["<k>", "<problem statement>"]` | Implementer k: own copy at `.git/wt_<k>`, start site with exact source, `run_prefix`, `test_cmd`, `audit_args` |
| `scripts/edit.py` | `["<k>", "<file>", "<old>", "<new>"]` | Implementer k's only edit tool: always writes into `.git/wt_<k>` (rescue refs `@1`, `L120-126` as fix_edit) |
| `scripts/audit.py` | `["--wt", "<k>", "--repro", cmd]` or `["--repro", cmd]` | Sign-off for copy k, or for the main workspace. `decision`: submit / submit_best / revise |
| `scripts/review_pack.py` | `["<k>"]` | Reviewer: candidate k's diff, files and self-audit |
| `scripts/save_cex.py` | `["<k>", "<python code>"]` | Reviewer: save a counterexample (asserts the correct behaviour) |
| `scripts/gate.py` | `[]` | Coordinator: pytest + static typecheck + code review + counterexamples on all candidates, ranked |
| `scripts/adopt.py` | `["<k>"]` | Final implementer: apply candidate k to `/workspace` and audit it |
| `scripts/fix_edit.py` | `[filepath, old, new]` | Whitespace-tolerant edit rescue |

Repro files belong in `/tmp`, created with `run_command` (heredoc). `write_file` to `/tmp/...` lands inside the repository, because the harness strips the leading `/`.
"""

THINK = "<|think|>\n"

IMPLEMENTER = THINK + """You are implementer {k} of 4. All four fix the same issue independently, each in its own copy of the repository; the best copy wins. You have at most 10 tool calls.

1. Call run_skill_script(skill_name="semdag", file_path="scripts/fork.py", args=["{k}", "<the whole problem statement>"]). It creates your copy `.git/wt_{k}` and gives your start site with its exact source, `run_prefix`, `test_cmd` and `audit_args`.
2. Reproduce: create `/tmp/repro_{k}.py` with run_command (heredoc), importing the package and asserting the CORRECT behaviour from the issue. Run it with `run_prefix` (e.g. `<run_prefix>python /tmp/repro_{k}.py`). It must fail now.
3. Fix: read the exact lines of your copy with read_file(".git/wt_{k}/<file>"), then change them ONLY with run_skill_script(skill_name="semdag", file_path="scripts/edit.py", args=["{k}", "<file path as in the repo>", "<exact old text>", "<new text>"]). It always writes into your copy. If it answers with a block reference such as "@1", call it again with "@1" as the old text. Make the smallest change at the root cause. Never edit test files.
4. Run the repro again with `run_prefix`. It must pass.
5. Call run_skill_script(skill_name="semdag", file_path="scripts/audit.py", args=<audit_args from fork>). If the decision is `revise` and you have calls left, fix once more and audit again.
6. End with exactly one line: CANDIDATE {k} <audit decision> <one-sentence summary of the change>.

Rules: change code only with edit.py; never run the full test suite (use `test_cmd`); create files only under /tmp and only with run_command."""

ADVERSARY = THINK + """You are adversarial reviewer {k}. Your target is candidate {k}, a fix for the issue written by implementer {k}. You have at most 3 tool calls and you never edit files.

1. Call run_skill_script(skill_name="semdag", file_path="scripts/review_pack.py", args=["{k}"]).
2. If the candidate is empty, end with: NONE {k} empty.
3. Otherwise find where this change is still wrong: an input or case the issue describes that the change does not handle, another code path with the same bug, or behaviour that worked before and now breaks.
4. Write ONE counterexample: a short standalone Python script that imports the package and asserts the CORRECT behaviour from the issue on that input. Save it with run_skill_script(skill_name="semdag", file_path="scripts/save_cex.py", args=["{k}", "<the code>"]). If it reports a syntax error, fix it and save once more.
5. End with exactly one line: CEX {k} <what the counterexample checks>, or NONE {k} <why no counterexample exists>."""

COORDINATOR = THINK + """You are the coordinator. Four implementers wrote candidate fixes in `.git/wt_1` .. `.git/wt_4`, and four adversarial reviewers saved counterexamples. You make one tool call and never edit files.

1. Call run_skill_script(skill_name="semdag", file_path="scripts/gate.py", args=[]). It runs pytest, the static typecheck and the code review on every candidate, runs every counterexample against every candidate, and ranks them.
2. Answer with:
   - first line: WINNER <k> (the gate's winner, unless its data clearly shows another candidate is better), or WINNER none if every candidate is empty;
   - then at most 5 short lines: the winner's open problems (static errors, review issues, failing tests, failing counterexamples) and which other candidate, if any, handled them, so the final implementer can fix them."""

FINALIZER = THINK + """You are the final implementer. The coordinator's verdict:

{gate_verdict?}

You work in the main workspace (paths WITHOUT `.git/wt_`). You have at most 12 tool calls.

1. If the verdict says WINNER none, call run_skill_script(skill_name="semdag", file_path="scripts/audit.py", args=[]) and end with: NO PATCH.
2. Call run_skill_script(skill_name="semdag", file_path="scripts/adopt.py", args=["<winner k>"]). It applies the winning candidate to the main workspace and audits it with the candidate's repro. If it cannot apply, adopt the next candidate from the ranking.
3. If the decision is `submit` or `submit_best`, call submit_patch, then end with: SUBMITTED <k>.
4. If the decision is `revise`, fix the listed problems directly in the main workspace: read_file the exact lines, then a small edit_file. Then run audit.py with args ["--repro", "<the repro command from adopt, run from /workspace>"] as the last test run. If the decision is now `submit` or `submit_best`, call submit_patch.
5. Call submit_patch at most once. Never edit test files. End with one line: SUBMITTED <k> or NO PATCH <reason>."""

SAMPLING = {
    "sampling_implement.yaml": ("Implementers: diverse (temperature 1.0), 4k hard output cap; thinking via <|think|>, no thinking_token_budget.",
                                "temperature: 1.0\ntop_p: 0.95\npresence_penalty: 0.3\nfrequency_penalty: 0.2\nmax_output_tokens: 4096\nthinking_config:\n  thinking_budget: 0\n  include_thoughts: true\n"),
    "sampling_adversary.yaml": ("Adversarial reviewers: 4k hard output cap; thinking via <|think|>.",
                                "temperature: 0.2\ntop_p: 0.95\nmax_output_tokens: 4096\nthinking_config:\n  thinking_budget: 0\n  include_thoughts: true\n"),
    "sampling_coordinator.yaml": ("Coordinator: 6k hard output cap; thinking via <|think|>.",
                                  "temperature: 0.0\ntop_p: 1.0\nmax_output_tokens: 6144\nthinking_config:\n  thinking_budget: 0\n  include_thoughts: true\n"),
    "sampling_final.yaml": ("Final implementer: 6k hard output cap; thinking via <|think|>.",
                            "temperature: 0.0\ntop_p: 1.0\nmax_output_tokens: 6144\nthinking_config:\n  thinking_budget: 0\n  include_thoughts: true\n"),
}


def write(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def agent_yaml(name, desc, prompt, sampling, tools, output_key, include_none=False):
    lines = [f"name: {name}", f"description: {json.dumps(desc)}", f"model: {MODEL}",
             f"instruction: !include ../prompts/{prompt}"]
    if include_none:
        lines.append("include_contents: none")
    lines += [f"output_key: {output_key}", "tools:"] + [f"  - {t}" for t in tools]
    lines += ["skills:", "  - skills/semdag",
              f"generate_content_config: !include ../configs/{sampling}"]
    return "\n".join(lines) + "\n"


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(V7 / "skills", OUT / "skills",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "audit.py", "meta.py"))
    for f in sorted((SRC / "scripts").glob("*.py")):
        shutil.copy2(f, OUT / "skills" / "semdag" / "scripts" / f.name)
    write("skills/semdag/SKILL.md", SKILL_MD)
    for k in range(1, K + 1):
        write(f"prompts/implementer_{k}.md", IMPLEMENTER.format(k=k) + "\n")
        write(f"prompts/adversary_{k}.md", ADVERSARY.format(k=k) + "\n")
        write(f"sub_agents/implementer_{k}.yaml", agent_yaml(
            f"implementer_{k}", f"Implementer {k} of 4: fixes the issue in its own copy .git/wt_{k}.",
            f"implementer_{k}.md", "sampling_implement.yaml",
            ["read_file", "run_command"], f"cand_{k}"))
        write(f"sub_agents/adversary_{k}.yaml", agent_yaml(
            f"adversary_{k}", f"Adversarial reviewer {k}: writes a counterexample for candidate {k}.",
            f"adversary_{k}.md", "sampling_adversary.yaml", ["read_file"], f"cex_{k}"))
    write("prompts/coordinator.md", COORDINATOR + "\n")
    write("prompts/finalizer.md", FINALIZER + "\n")
    write("sub_agents/implementers.yaml",
          "name: implementers\ndescription: \"Four implementers in parallel, each in its own copy.\"\n"
          "agent_class: ParallelAgent\nsub_agents:\n"
          + "".join(f"  - config_path: implementer_{k}.yaml\n" for k in range(1, K + 1)))
    write("sub_agents/adversaries.yaml",
          "name: adversaries\ndescription: \"Four adversarial reviewers in parallel, one per candidate.\"\n"
          "agent_class: ParallelAgent\nsub_agents:\n"
          + "".join(f"  - config_path: adversary_{k}.yaml\n" for k in range(1, K + 1)))
    write("sub_agents/coordinator.yaml", agent_yaml(
        "coordinator", "Runs the gate (pytest, static typecheck, code review, counterexamples) and names the winner.",
        "coordinator.md", "sampling_coordinator.yaml", ["get_status"], "gate_verdict",
        include_none=True))
    write("sub_agents/finalizer.yaml", agent_yaml(
        "finalizer", "Adopts the winner into /workspace, fixes open problems, last test run, submits once.",
        "finalizer.md", "sampling_final.yaml",
        ["read_file", "edit_file", "run_command", "submit_patch", "get_status"], "final_note",
        include_none=True))
    for name, (comment, body) in SAMPLING.items():
        write(f"configs/{name}", f"# {comment}\n{body}")
    write("agent.yaml",
          "agent_class: SequentialAgent\nname: v8_ensemble\n"
          "description: >\n  Army fork + 4 parallel implementers -> 4 parallel adversarial reviewers ->\n"
          "  coordinator gate (pytest, static typecheck, code review) -> final implementer.\n"
          "sub_agents:\n  - config_path: sub_agents/implementers.yaml\n"
          "  - config_path: sub_agents/adversaries.yaml\n"
          "  - config_path: sub_agents/coordinator.yaml\n  - config_path: sub_agents/finalizer.yaml\n")
    write("eval_config.yaml",
          "# Owner rules 2026-11-17: 4 min per task; command timeout and tool calls/turns at the\n"
          "# competition defaults (the ensemble needs ~50 tool calls).\n"
          "evaluation:\n  timeout_seconds: 300\n  max_tool_calls: 100\n  max_time_minutes: 4\n"
          "  max_turns: 500\n")
    write("README.md", "# v8_ensemble\n\nGenerated by `Tools/v8_ensemble/build_v8.py`; do not edit here.\n"
          "Design: `docs/runs/v8_PREREG.md`.\n")
    return OUT


if __name__ == "__main__":
    print(build())
