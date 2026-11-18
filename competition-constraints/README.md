# Gemma 4 Developer Agent Competition: Mandatory Constraints

Compiled 2026-11-13; updated 2026-11-17 with the scorer-parity findings. Main track: https://www.kaggle.com/competitions/gemma-4-developer-agent
Home base: `~/Desktop/Gemma4DevAgentCompetitionKaggle/competition-constraints/`

## Sources and tags

| Tag | Source | Trust |
|---|---|---|
| **[HR §n]** | `DataSets/public/HARNESS_README.md` (official harness guide from the Kaggle dataset), section n | **Official, verbatim** |
| **[OV]** | `Rules/Overview/Evaluation_Rules_Full.md` (Overview tab, copied 2026-11-10) | **Official, lightly reworded copy** |
| **[DD]** | `DataSets/public/DATASET_DESCRIPTION.md` (Data tab, copied 2026-11-10) | **Official copy** |
| **[AUD]** | `Rules/Overview/Competition_Audit.md` (summary of the Rules tab read 2026-11-10) | Summary, not verbatim |
| **[STAFF]** | Staff and host forum posts, verbatim in `../Rules/Verbatim/forum-staff-posts.md` and `forum-findings.md` | **Official** |
| **[SRC]** | Installed harness source in `.venv-harness` (swegemma 0.2.11, adk_submission 0.2.13) | Read in code |
| **[S]** | Third-party web summaries | Unverified |

Verbatim Kaggle Rules, pages and all staff forum posts: `../Rules/Verbatim/`. Legal-style rules (licensing, external data, eligibility) come from [AUD] and need a check against the Rules tab. See [open-questions.md](open-questions.md).

## Files

| File | Covers |
|---|---|
| [submission-format.md](submission-format.md) | Zip layout, root config, allowed extensions, size limits, agent schema, adapters, skills, `!include` |
| [tools-and-sandbox.md](tools-and-sandbox.md) | 9 tools, budgets, `eval_config.yaml`, 12-hour limit, containers, patch extraction, grading |
| [eligibility-and-deadlines.md](eligibility-and-deadlines.md) | Model list, single-model rule, E2B/E4B bonus, deadlines, teams, prizes, what you cannot do |
| [open-questions.md](open-questions.md) | Ambiguities and conflicts |
| [../docs/SCORER_PARITY.md](../docs/SCORER_PARITY.md) | What the scoring notebook runs (vLLM flags, compaction, sandboxes) and where local runs differ |

## Submission

1. **Exactly one root config** (`agent.yaml`, `agent.yml`, `root_agent.yaml` or `root_agent.yml`) at the zip root. Zero raises `MissingRootConfigError`, more than one raises `MultipleRootConfigsError`. [HR §2.2]
2. **One base model for every agent and sub-agent**, from `gemma-4-31b-it-qat-w4a16-ct`, `gemma-4-12b-it-qat-w4a16-ct`, `gemma-4-e4b-it-qat-w4a16-ct`, `gemma-4-e2b-it-qat-w4a16-ct`. Anything else raises `ParticipantVisibleError`. [HR §3.2]
3. **Unpacked size < 3 GiB (3,221,225,472 bytes), adapters included.** [HR §2.4]
4. **Allowed file extensions only:** `.yaml .yml .md .txt .py .json .safetensors`. `.bin .pt .pth`, archives and `.pyc` are rejected. [HR §2.4]
5. **Skill scripts must be `.py`.** `.sh` is rejected by the validator. [SRC]
6. **LoRA:** PEFT, `adapters/<name>/adapter_config.json` + `adapter_model.safetensors`, name matching `[A-Za-z0-9][A-Za-z0-9._-]*`, rank ≤ 128. The scorer sets `max_lora_rank` to the largest adapter rank found. [HR §3.1, §3.4]
7. **No absolute paths, null bytes, or symlinks** in `!include`. `..` is allowed only if the resolved path stays inside the submission root (`PathTraversalError` otherwise). Declarative YAML only; no Python entrypoints. [HR §2.1, §2.2; SRC]

## Scoring run

8. **~120 hidden tasks** (about 60 public + 60 private) from **private repos, not the training repos**. fastapi, rich, requests and httpx are never scored, so tune for unseen repos. [STAFF Holbrook 2026-09-24, Markowitz 2026-11-04]
9. **Tasks run sequentially in one 12-hour job, which includes vLLM start-up and every task's container setup** (validation is separate, about 2 h). Going over 12 hours errors the whole submission; the "unfinished = 0" fix was withdrawn. 12 h ÷ 120 tasks = **6.0 min per task gross**, before start-up and setup, so `max_time_minutes` must stay ≤ 5; our setting is **4** (owner rule 2026-11-17). [OV; STAFF 2026-09-24, 2026-10-07, 2026-10-15]
10. **Per-task budgets come from `eval_config.yaml`** (`max_time_minutes`, `max_tool_calls`, `max_turns`, `timeout_seconds`). The sample config is `max_time_minutes: 1`, `max_tool_calls: 10`; shipping it unchanged would cripple the agent. The per-task clock starts **after** container setup. [HR §7.1]
11. **Concurrency:** a `ParallelAgent` may make concurrent LLM calls; **tool calls run one at a time**. [STAFF 2026-09-28, 2026-10-11]
12. **Sandbox:** a **private Docker sandbox** with the same base image as the public one but its own installed dependencies ("same sandbox but different wheels"). **The package set is fixed and cannot be modified**; submissions cannot ship wheels (`.whl` is not an allowed extension). [STAFF 2026-09-27, 2026-10-12] Offline, 4 GiB RAM and 2 vCPUs per container; a process over 4 GiB is killed with exit code 137. The public subprocess-sandbox dependency gaps (`inline_snapshot`, `dirty_equals`) do not apply. [STAFF Holbrook 2026-09-27; HR §4.1]
13. **`submit_patch` exits only after the current agent turn ends.** Inside a LoopAgent the loop keeps running to its end. Without a submit, the harness still verifies the working-tree diff. [HR §5.3, §8.1]
14. **Edits to tests and runner config are stripped from the patch**: `test_*.py`, `*_test.py`, `tests/`, `conftest.py`, `pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg`, `*.pth` and others. Fix library code only. [HR §8.1, §8.2]
15. **Scratch files in `/workspace` end up in the patch.** Put them in `/tmp`. [HR §10.3]
16. **Verification:** fixed 300 s pytest timeout. Resolved iff exit code 0, passed > 0, failures = 0, errors = 0, and every required test passed. [HR §8.2; STAFF 2026-09-24]

## Model server and sampling

17. **Context is 32,768 tokens**; `max_output_tokens` and `thinking_budget` ≤ 32,768. Events compaction at 14,336 tokens (interval 15, retention 5), run by the harness, not the server. [HR §2.4, §7.2]
18. **Patched vLLM 0.19.1 on 4×L4** [STAFF 2026-09-28, 2026-10-15]: tensor parallel 4, `gpu_memory_utilization` 0.90, gemma4 tool and reasoning parsers, reasoning markers `<|channel>` / `<channel|>`, `--no-scheduler-reserve-full-isl`. [HR §3.1; SRC `adk_submission/server.py`]
19. **Unset sampling fields fall back to the checkpoint's `generation_config.json`:** temperature 1.0, **top_k 64**, top_p 0.95. ADK does not send `top_k`, so every scorer call samples with top_k 64. [SRC; vLLM `--generation-config auto`]
20. **The thinking budget is a hard cut.** A positive `thinking_budget` makes the harness send `thinking_token_budget`; at the limit vLLM forces `<channel|>` with no wrap-up. Gemma 4's chat template has an on/off switch only (`<|think|>`), with no budget or effort variable, so a *bounded* budget must come from the role prompt. A literal `<|think|>` in a role prompt with `thinking_budget: 0` turns thinking on with no hard cut (vllm-metal smoke, `../results/server_bench/vllm_metal/THINK_INJECTION.md`). [SRC; vLLM docs]

## Deadlines, prizes, teams

21. **Deadlines (23:59 UTC):** entry and team merger **Nov 25**, final submission **Dec 2**. The Small Model bonus deadline is also **Dec 2**, confirmed by a host on the forum. [Rules/Verbatim/prizes.md; forum 751104]
22. **E4B bonus:** the E4B submission must be one of the team's 2 selected finals. [OV, Prizes]
23. **1 submission per day**, 2 final selections, teams of up to 5. [AUD]
24. **Frontier-model trajectories are allowed for training** if the provider's license allows it and the result can be released under Apache 2.0. [forum 742807, staff]
