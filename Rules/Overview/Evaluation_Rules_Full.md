# Evaluation, Prizes, and Harness Rules (copied from the Kaggle Overview tab, 2026-11-10)

## Evaluation

You must provide a zip archive (`submission.zip`) that contains your Agent Config: system prompts, custom tools, skills, and LoRA adapters. An `agent.yaml` file must be at the root of the archive.

```
submission.zip
├── agent.yaml                  # REQUIRED: Root agent config
├── configs/
│   └── sampling.yaml           # Optional: Generation parameters loaded via !include
├── prompts/
│   ├── system.md               # Optional: System instructions loaded via !include
│   └── analyzer.md
├── sub_agents/
│   └── code_analyzer.yaml      # Optional: Sub-agent or AgentTool YAML configurations
├── adapters/                   # Optional: Fine-tuned PEFT LoRA adapters or model weights
│   ├── main_lora/
│   │   ├── adapter_config.json
│   │   └── adapter_model.safetensors
│   └── tool_lora/
│       ├── adapter_config.json
│       └── adapter_model.safetensors
└── skills/                     # Optional: ADK Skill directories
    └── repo_navigation/
        ├── SKILL.md
        ├── scripts/            # Python or bash scripts executed in a sandbox
        └── resources/          # Domain knowledge markdown files
```

The config language follows the [Google ADK Agent Config](https://adk.dev/agents/config/) spec, with extra restrictions to prevent code execution outside a sandbox. Submissions are compiled into ADK agents for evaluation.

## Issue Scoring

Like [SWE-Bench](https://www.swebench.com/SWE-bench/), each patch is scored PASS/FAIL. For each issue, the patch is applied to that issue's repository and the issue's validation tests are run. Your overall score is the percentage of patched repositories that pass.

You have 12 hours to submit patches for all tasks, including sandbox setup time but excluding validation. You may set per-task time limits in `eval_config.yaml`.

## Timeline (all 11:59 PM UTC)

- **Sept 23, 2026:** start.
- **Nov 12, 2026 (optional):** research paper deadline.
- **Nov 25, 2026:** entry deadline (accept rules before this date) and team merger deadline.
- **Dec 2, 2026:** final submission deadline.

The organizers may update the timeline.

## Prizes

**Total: $110,000**

- Gemma 4 Developer Agent Competition: $65,000 (1st $37,000, 2nd $18,000, 3rd $10,000).
- Paper Submission Award: $35,000. Topics: parameter-efficient fine-tuning and RL for SWE agents; code-graph generation and embedding; new tasks, datasets, or benchmarks for code structure; LLM reasoning over large graphs. Enter via the [paper track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper).
- **Small Model Bonus: $10,000.** Highest-ranking submission using Gemma E2B or E4B as the base model.
  - Must be one of the team's two selected final submissions.
  - LoRA fine-tuning is allowed, as on the main track.
  - A daily notebook shows filtered standings for eligible entries.
  - Eligible entries remain eligible for general awards and the paper track.
  - Deadline: Nov 12, 2026, 11:59 PM UTC (the page also says "same as main track"; the explicit date is Nov 12).

Top submissions will be highlighted at a Google-hosted event (such as a NeurIPS expo workshop). Using the released graph and embedding data is encouraged, not required.

## Model Selection and LoRA Adapters

Allowed base models:
- `gemma-4-31b-it-qat-w4a16-ct`
- `gemma-4-12b-it-qat-w4a16-ct`
- `gemma-4-e4b-it-qat-w4a16-ct`
- `gemma-4-e2b-it-qat-w4a16-ct`

- Every agent and subagent must use the same model. Mixing is not allowed.
- LoRA adapters are optional. Place each one in `adapters/<adapter_name>/` with `adapter_config.json` and `adapter_model.safetensors`.
- Reference an adapter with `adapter: <adapter_name>` on any `LlmAgent` in `agent.yaml` or `sub_agents/*.yaml`. Different agents may use different adapters.

## Tool, Prompt, and Skill Rules

- **`!include`** resolves paths relative to the file that contains the tag. In `agent.yaml`, `!include prompts/system.md` loads `prompts/system.md`.
- **Sandboxing:** path traversal outside the submission root (`../` or symlinks) is not allowed.
- **Allowed tools:** only the harness tools and custom subagents defined with `agent_tool`.
- **Skills:** each skill is a directory with a `SKILL.md` that has YAML frontmatter (`name: <skill-name>`). Scripts run via `run_skill_script` execute in the competition's persistent Docker container, share filesystem access with `run_command`, and count against your time budget. Agents read domain files with `load_skill_resource`.

Predefined tools:
1. `run_command(command)`: shell command in `/bin/bash -c` inside `/workspace`.
2. `submit_patch()`: stages untracked files (`git add -N .`) and captures `git diff HEAD`.
3. `get_status()`: live budget and patch status.
4. `read_file(filepath, start_line?, end_line?)`: 1-indexed inclusive slices.
5. `edit_file(filepath, old_string, new_string, allow_multiple=False)`.
6. `write_file(filepath, content)`: creates parent directories as needed.
7. `get_code_neighbors(node, edge_type?, max_neighbors=50)`.
8. `search_similar_code(query, k=10)`.
9. `get_code_subgraph(nodes)`.

See `HARNESS_README.md` in the dataset for the full submission format and execution environment.

## Upgraded Accelerators

- L4x4 machines with 96 GB GPU memory are available to notebooks attached to this competition.
- Notebooks with L4x4 use GPU quota at twice the rate of T4x2 and P100. Kaggle may raise this rate.
- L4 sessions are restricted to this competition's notebooks. Circumventing that can lead to team or account bans.
- **All L4 sessions must have internet disabled.**

## Citation

Elan Markowitz, Bryan Perozzi, Benedek Rózemberczki, Glenn Cameron, Hadi Hemmati, Yuchen Li, Michael Galkin, Majid Farhadi, Ryan Holbrook, and Ashley Oldacre. *Google - The Gemma 4 Developer Agent Competition.* https://www.kaggle.com/competitions/gemma-4-developer-agent, 2026. Kaggle.
