# Gemma 4 Developer Agent Competition: Mandatory Constraints

Compiled 2026-11-13 for the main track at https://www.kaggle.com/competitions/gemma-4-developer-agent
Home base: `~/Desktop/Gemma4DevAgentCompetitionKaggle/competition-constraints/`

## Sources and tags

| Tag | Source | Trust |
|---|---|---|
| **[HR §n]** | `DataSets/public/HARNESS_README.md` (official harness guide from the Kaggle dataset), section n | **Official, verbatim** |
| **[OV]** | `Rules/Overview/Evaluation_Rules_Full.md` (Overview tab, copied 2026-11-10) | **Official, lightly reworded copy** |
| **[DD]** | `DataSets/public/DATASET_DESCRIPTION.md` (Data tab, copied 2026-11-10) | **Official copy** |
| **[AUD]** | `Rules/Overview/Competition_Audit.md` (summary of the Rules tab read 2026-11-10) | Summary, not verbatim |
| **[S]** | Third-party web summaries | Unverified |

The full Rules tab text has not been saved verbatim anywhere in the base folder. Legal-style rules (licensing, external data, eligibility) come from [AUD] and need a check against the Rules tab. See [open-questions.md](open-questions.md).

## Files

| File | Covers |
|---|---|
| [submission-format.md](submission-format.md) | Zip layout, root config, allowed extensions, size limits, agent schema, adapters, skills, `!include` |
| [tools-and-sandbox.md](tools-and-sandbox.md) | 9 tools, budgets, `eval_config.yaml`, 12-hour limit, containers, patch extraction, grading |
| [eligibility-and-deadlines.md](eligibility-and-deadlines.md) | Model list, single-model rule, E2B/E4B bonus, deadlines, teams, prizes, what you cannot do |
| [open-questions.md](open-questions.md) | Ambiguities and conflicts |

## Top constraints

1. **Exactly one root config** (`agent.yaml`, `agent.yml`, `root_agent.yaml` or `root_agent.yml`) at the zip root. Zero raises `MissingRootConfigError`, more than one raises `MultipleRootConfigsError`. [HR §2.2]
2. **One base model for every agent and sub-agent**, from `gemma-4-31b-it-qat-w4a16-ct`, `gemma-4-12b-it-qat-w4a16-ct`, `gemma-4-e4b-it-qat-w4a16-ct`, `gemma-4-e2b-it-qat-w4a16-ct`. Anything else raises `ParticipantVisibleError`. [HR §3.2]
3. **Unpacked size < 3 GiB (3,221,225,472 bytes), adapters included.** [HR §2.4]
4. **Allowed file extensions only:** `.yaml .yml .md .txt .py .json .safetensors`. `.bin .pt .pth` and archives are rejected. [HR §2.4]
5. **LoRA:** PEFT, `adapters/<name>/adapter_config.json` + `adapter_model.safetensors`, name matching `[A-Za-z0-9][A-Za-z0-9._-]*`, rank ≤ 128. [HR §3.1, §3.4]
6. **No absolute paths, `..`, null bytes, or symlinks outside the root** in `!include` (`PathTraversalError`). Declarative YAML only; no Python entrypoints. [HR §2.1, §2.2]
7. **12 hours total for all tasks**, including sandbox setup, excluding validation. [OV, Issue Scoring]
8. **Per-task budgets come from `eval_config.yaml`.** The sample config is `max_time_minutes: 1`, `max_tool_calls: 10`. Shipping it unchanged would cripple the agent. [HR §7.1]
9. **Edits to tests and runner config are stripped from the patch**: `test_*.py`, `*_test.py`, `tests/`, `conftest.py`, `pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg`, `*.pth` and others. Fix library code only. [HR §8.1, §8.2]
10. **Scratch files in `/workspace` end up in the patch.** Put them in `/tmp`. [HR §10.3]
11. **Context is 32,768 tokens**; `max_output_tokens` and `thinking_budget` ≤ 32,768. [HR §2.4]
12. **Sandbox is offline**, with 4 GiB RAM and 2 vCPUs per container. A process over 4 GiB is killed with exit code 137. [HR §3.1, §4.1]
13. **Deadlines (23:59 UTC):** entry and team merger **Nov 25**, final submission **Dec 2**. The Small Model bonus deadline is also **Dec 2**, confirmed by a host on the forum. [Rules/Verbatim/prizes.md; forum 751104]
16. **Tasks run sequentially in one 12-hour job, and going over 12 hours errors the whole submission.** Keep `max_time_minutes` ≤ 5. [forum, Ryan Holbrook]
17. **Skill scripts must be `.py`.** `.sh` is rejected by the validator. [harness source]
18. **Frontier-model trajectories are allowed for training** if the provider's license allows it and the result can be released under Apache 2.0. [forum 742807, staff]

Verbatim Kaggle Rules, pages and all staff forum posts: `../Rules/Verbatim/`.
14. **E4B bonus:** the E4B submission must be one of the team's 2 selected finals. [OV, Prizes]
15. **1 submission per day**, 2 final selections, teams of up to 5. [AUD]
