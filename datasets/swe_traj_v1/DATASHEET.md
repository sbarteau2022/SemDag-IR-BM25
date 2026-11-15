# Datasheet: swe_traj_v1

Verified multi-turn bug-fixing trajectories for LoRA SFT of the Gemma 4 E4B agent (Kaggle Gemma 4 Developer Agent competition). Built 2026-11-13/14.

## What it is

Each record is one complete agent episode in the competition's tool-call format. It starts from an issue, then reproduces the bug, localizes it, makes a minimal edit, verifies, and ends with `submit_patch` and a one-line summary. Every tool result in a record is **real output** from running that exact call against a real repository. Nothing is hand-written or produced by an LLM.

Every kept record passed validation. Its submitted patch was applied to a fresh copy, and all fail-to-pass tests plus every previously-passing test in the run set had to pass.

## How it was made

1. **Sources.** 35 permissively licensed, pure-Python repositories, cloned from GitHub at a pinned commit (`base_commit` is recorded in every record). Only tests that pass on the clean checkout are used.
2. **Bug injection** (`pipeline/mutate.py`), in the style of SWE-smith, AST-guided and LLM-free. 13 operators in 9 families: comparison flips, boolean logic, dropped `not`, off-by-one, augmented-assignment sign, constant flips, index/slice shifts, wrong method or builtin (`startswith`↔`endswith`, `min`↔`max`, ...), swapped call arguments, dropped `return` value, and deleted guard clauses. A mutant is kept only if it breaks 1–20 previously passing tests and does not break imports or collection. Each function gets at most 2 bugs.
3. **Trajectory** (`pipeline/build.py`). The bug is committed as the base of a fresh git repo, so there is no history to peek at. A scripted agent then runs the harness tools for real: `run_command`, `read_file`, `edit_file` and `submit_patch`. Two task modes:
   - **snippet** (SWE-bench-like): the failing tests are *deleted* from the workspace and the issue gives a standalone reproducer. The agent writes it to `/tmp/repro.py` (outside `/workspace`), runs it, fixes the bug and re-runs it.
   - **ci**: the issue is a failing-test report. The agent runs that single test by node id and reads the test body first.
   Localization follows the evidence actually observed. The routes are: the innermost library frame of the traceback (sometimes walking one frame up), or `grep -rn "def <api>"` on the API the reproducer calls, or a two-hop call chain from that API into the buggy helper. When several definitions match, the choice is justified from the issue (class name or module).
4. **Reasoning text** (`pipeline/phrases.py`) is templated, with several paraphrases per slot. Each slot is filled only with facts from real tool output or the bug record: line numbers, code fragments and error messages. Thoughts cover the plan, a hypothesis tied to the observed error, the edit, verification, and budget awareness ("N tool calls used").
5. **Tactics demonstrated:** reproduce before editing; scratch files only in `/tmp`; narrow `read_file` windows; one concrete hypothesis per edit; recovery from a real `edit_file` "matches N locations" error by adding context; `timeout` on every command; targeted tests only (never the full suite); a diff check; submit as soon as checks pass; recognizing pre-existing failures that also fail on the base.
6. **Filtering** (`pipeline/render.py`): validation must pass. Records are deduped on bug site, patch and issue body. Records are dropped if over 12,000 approximate tokens (below the 14,336-token compaction point), if any local build path leaks into the text, or if a call-chain step isn't grounded (the read must visibly show the call).

## Format (JSONL, one conversation per line)

```json
{"id": "...", "tools": [6 tool schemas],
 "messages": [
   {"role": "system", "content": "<agent system prompt>"},
   {"role": "user", "content": "<issue text>"},
   {"role": "assistant", "content": "<reasoning>", "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "run_command", "arguments": {"command": "..."}}}]},
   {"role": "tool", "tool_call_id": "call_1", "name": "run_command", "content": "<real output>"},
   ...,
   {"role": "assistant", "content": "<one-line summary>"}],
 "metadata": {"repo", "github", "license", "base_commit", "bug_op", "bug_family", "bug_file", "mode", "route", "edit_retry", "hint", "n_tool_calls", "approx_tokens", "fail_to_pass", "n_pass_to_pass", "gold_patch"}}
```

This is the standard HF/TRL conversational format with `tools`. It works with `tokenizer.apply_chat_template(messages, tools=tools)` and with `SFTTrainer(assistant_only_loss=True)`. A recipe is in `pipeline/train_lora_recipe.py` (rank 64; untested here, since the build machine has no GPU).

## Splits

| Split | Records |
|---|---|
| train | 648 |
| val | 41 |
| test_ood | 102 |
| **total** | **791** (from 851 validated episodes; 51 duplicates, 8 ungrounded call chains and 1 with a path leak removed) |

- **Repos:** 36. **Bug families:** logic 178, call_args 135, comparison 109, missing_check 98, arithmetic 87, api_misuse 82, indexing 59, constant 33, wrong_return 10
- **Modes:** snippet 128, ci 663. **Localization routes:** traceback 477, direct API 206, two-hop call chain 108.
- **Behaviours:** 48 recover from a non-unique `edit_file`, 162 issues carry a "possibly related to X" hint, and 17 correctly ignore pre-existing test failures.
- **Tool calls per episode:** min 5, median 7, max 11. **Approx tokens:** median 2340, p95 3261, max 5234.


- **train** and **val** share repos but never share a bug.
- **test_ood** holds 5 repos that are entirely absent from train and val (`cachetools`, `glom`, `isodate`, `python-slugify`, `xmltodict`). Use it to check generalization to unseen codebases.

## Sources and licenses

| Repo | GitHub | License | Records |
|---|---|---|---|
| arrow | github.com/arrow-py/arrow | Apache-2.0 | 25 |
| attrs | github.com/python-attrs/attrs | MIT | 26 |
| boltons | github.com/mahmoud/boltons | BSD-3-Clause | 29 |
| bottle | github.com/bottlepy/bottle | MIT | 26 |
| cachetools | github.com/tkem/cachetools | MIT | 24 |
| cerberus | github.com/pyeve/cerberus | ISC | 30 |
| click | github.com/pallets/click | BSD-3-Clause | 13 |
| dacite | github.com/konradhalas/dacite | MIT | 11 |
| funcy | github.com/Suor/funcy | BSD-3-Clause | 27 |
| glom | github.com/mahmoud/glom | BSD-3-Clause | 29 |
| humanize | github.com/python-humanize/humanize | MIT | 28 |
| iniconfig | github.com/pytest-dev/iniconfig | MIT | 12 |
| isodate | github.com/gweis/isodate | BSD-3-Clause | 20 |
| itsdangerous | github.com/pallets/itsdangerous | BSD-3-Clause | 1 |
| jinja | github.com/pallets/jinja | BSD-3-Clause | 28 |
| jsonschema | github.com/python-jsonschema/jsonschema | MIT | 26 |
| markupsafe | github.com/pallets/markupsafe | BSD-3-Clause | 12 |
| marshmallow | github.com/marshmallow-code/marshmallow | MIT | 27 |
| mistune | github.com/lepture/mistune | BSD-3-Clause | 13 |
| more-itertools | github.com/more-itertools/more-itertools | MIT | 22 |
| packaging | github.com/pypa/packaging | Apache-2.0 OR BSD-2-Clause | 9 |
| pluggy | github.com/pytest-dev/pluggy | MIT | 28 |
| prettytable | github.com/jazzband/prettytable | BSD-3-Clause | 28 |
| pydash | github.com/dgilland/pydash | MIT | 29 |
| pyjwt | github.com/jpadilla/pyjwt | MIT | 29 |
| pyparsing | github.com/pyparsing/pyparsing | MIT | 4 |
| python-semver | github.com/python-semver/python-semver | BSD-3-Clause | 29 |
| python-slugify | github.com/un33k/python-slugify | MIT | 15 |
| python-sortedcontainers | github.com/grantjenks/python-sortedcontainers | Apache-2.0 | 27 |
| python-tabulate | github.com/astanin/python-tabulate | MIT | 9 |
| schema | github.com/keleshev/schema | MIT | 26 |
| sqlparse | github.com/andialbrecht/sqlparse | BSD-3-Clause | 27 |
| tomlkit | github.com/python-poetry/tomlkit | MIT | 30 |
| toolz | github.com/pytoolz/toolz | BSD-3-Clause | 29 |
| voluptuous | github.com/alecthomas/voluptuous | BSD-3-Clause | 29 |
| xmltodict | github.com/martinblech/xmltodict | MIT | 14 |

Pinned commits are in each record's `metadata.base_commit`.

All are MIT, BSD-2/3, Apache-2.0 or ISC, which are compatible with releasing the dataset and adapter under Apache 2.0. Records contain short excerpts of these repos' code (read_file output and diffs). Keep this table with the dataset for attribution.

## Not in the data (by design)

- **No competition tasks.** The public tasks come from `fastapi`, `requests` and `rich`. Those repos, plus `httpx`, `starlette`, `pydantic`, `typer`, `flask` and `urllib3`, are excluded in `pipeline/config.py`. No record touches them.
- **No model-generated text.** No Claude, GPT or other model wrote any trajectory, issue or thought, so provider output-license terms don't apply.

## Known limitations (check before training)

1. **Observation formatting is assumed.** The harness's exact string formats are unknown here: line numbering in `read_file`, the exit-code suffix on `run_command`, and the JSON shape of `edit_file`/`submit_patch`. They live in one function, `render_result` in `pipeline/render.py`. Match it to `HARNESS_README.md` and re-render; that takes seconds, because raw episodes are kept in `raw/`.
2. **System prompt.** Records use a compact best-practices prompt. Re-render with the deployed prompt (`render.py raw out --system <submission>/prompts/system.md`) so training and inference match.
3. **Synthetic bugs are simpler than real issues.** Almost all fixes are a 1–3 line revert in one function. That teaches the workflow and tool discipline, not deep feature work. Mix with real-issue data if you get some, and judge success on the OOD split and a real agent run.
4. **The graph tools** (`get_code_neighbors`, `search_similar_code`, `get_code_subgraph`) and skill scripts don't appear, because their output formats couldn't be reproduced faithfully offline.
5. Templated reasoning is less varied than natural text. Watch for the model parroting phrases, and keep epochs low (1–2).

## Rebuild

```bash
cp -r pipeline /some/exec/dir && cd /some/exec/dir   # project-files mount is noexec
# needs a venv with pytest, pytest-timeout and each repo installed editable (see config.py for the list)
bash run_all.sh <raw_out_dir> 30
python render.py <raw_out_dir> <split_out_dir> [--system prompt.md]
```
