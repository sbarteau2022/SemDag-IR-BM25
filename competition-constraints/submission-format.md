# Submission Format

Tags: see [README.md](README.md). [HR §n] quotes are verbatim from HARNESS_README.md.

## 1. Archive and root config

- [OV, Evaluation] "You must provide a zip archive (`submission.zip`) that contains your Agent Config: system prompts, custom tools, skills, and LoRA adapters. An `agent.yaml` file must be at the root of the archive."
- [HR §2.2] "Exactly one root config (`agent.yaml`, `agent.yml`, `root_agent.yaml`, or `root_agent.yml`) must exist in the submission root. Having zero root files raises `MissingRootConfigError`; having more than one raises `MultipleRootConfigsError`."
- [HR §2.1] "Competitors **do not** submit Python code entrypoints (`agent.py` or `agent_fn`)." Everything is declared in YAML and resolved against closed host registries (`ToolRegistry`, `ModelRegistry`, `SkillRegistry`, `CallbackRegistry`).
- [S] The zip is built by a Kaggle notebook at `/kaggle/working/submission.zip`.

### Layout [HR §2.2]

```text
submission/
├── agent.yaml          # REQUIRED (or root_agent.yaml; .yml also accepted)
├── eval_config.yaml    # Optional: per-task budget & timeout overrides
├── configs/sampling.yaml
├── prompts/system.md, analyzer.md
├── sub_agents/code_analyzer.yaml
├── adapters/<name>/adapter_config.json + adapter_model.safetensors
└── skills/<skill>/SKILL.md   (+ scripts/, resources/ per [OV])
```

## 2. Hard limits [HR §2.4]

> "aside from security sandboxing (no symlinks, no path traversal, declarative YAML only), the primary hard constraint is a total unpacked submission size of `< 3 GiB` (`3,221,225,472` bytes), including all `adapters/` weights"

| Limit | Value |
|---|---|
| Total unpacked size | < 3 GiB, adapters included |
| Files | 10,000 |
| YAML files | 1,000 |
| YAML size | 50 MiB per file / cumulative `!include` expansion |
| Skill directory size | 50 MiB each |
| Instruction length | 1,000,000 chars per agent; 10,000,000 total |
| Agents | 500 |
| Nesting depth (`sub_agents` + `agent_tool`) | 50 |
| Skills | 1,000 |
| `LoopAgent` iterations | 500 (range 1..500) |
| **Allowed extensions** | "`.yaml`, `.yml` (agent/eval configs), `.md`, `.txt` (prompts & `SKILL.md`), `.py` (ADK skill scripts), `.json` (`adapter_config.json`), and `.safetensors` (`adapter_model.safetensors`). Pickle-based weights (`.bin`, `.pt`, `.pth`) and other binary/archive extensions are rejected." |

Watch for: `.sh` is **not** in the list, though the Overview says skills can hold "Python or bash scripts". Also `.DS_Store`, `.gitkeep`, `.bak` files (e.g. `agent.yaml.bak-precoeval` in `sample_submission/`), and `README` with no extension. Strip them before zipping. See open-questions Q2.

## 3. `!include` [HR §2.2]

- `.md` and `.txt` load as raw UTF-8 strings. `.yaml` and `.yml` are parsed recursively (max depth 10, with cycle detection).
- Paths resolve relative to the file containing the tag. [OV]
- "Absolute paths, null bytes, `..` traversal components, and symlinks resolving outside the submission root are strictly blocked (`PathTraversalError`)."

**Correction (2026-11-17, verified in code and by a live load):** the quoted rule blocks `..` that *escapes* the root, not `..` as such. `adk_submission/yaml_loader.py::_resolve_include_path` joins the path to the including file's directory and passes it to `validate_sandboxed_path(base_dir=root)`, which only rejects targets outside the root, symlinks, missing files and other extensions. So `sub_agents/x.yaml` **may** use `!include ../prompts/x.md` (the official sample does), while `../../outside.md` and `/abs/path` are rejected.

## 4. Agent schema [HR §2.3]

`agent_class` is one of `LlmAgent` (the default), `SequentialAgent`, `ParallelAgent` or `LoopAgent`.

`LlmAgent` fields: `name` (required), `model` (required), `adapter`, `description`, `instruction` (supports `{problem_description}`, `{hints}`, custom `output_key` vars), `tools` (tool names, `agent_tool: {config_path: ..., skip_summarization: true}`, or inline agents), `skills` (relative paths), `sub_agents` (`{config_path: ...}`), `output_key`, `include_contents` (`"default"` | `"none"`), `disallow_transfer_to_parent` / `disallow_transfer_to_peers`, `generate_content_config`.

### `generate_content_config` [HR §2.4]

- Allowed: `temperature`, `top_p`, `top_k`, `max_output_tokens` (1 to 32,768, default 16,384), `presence_penalty`, `frequency_penalty`, `stop_sequences`, `response_mime_type`, `seed`, `thinking_config` (`thinking_budget` 0 to 32,768, `thinking_level`, `include_thoughts`).
- **Forbidden** (validation error): "`tools`, `system_instruction`, `http_options`, `safety_settings`, or `response_schema` inside `generate_content_config`".
- With vLLM + LoRA: "omit `thinking_level` and configure `include_thoughts: true` + `thinking_budget: 4096` instead".

## 5. LoRA adapters [HR §3.4, §3.1]

- "Place PEFT LoRA directories (containing `adapter_config.json` and `adapter_model.safetensors`) inside `adapters/<adapter_name>/`. Adapter names must match `[A-Za-z0-9][A-Za-z0-9._-]*`."
- Reference with `adapter: <adapter_name>` on any `LlmAgent`. Different agents may use different adapters.
- `max_lora_rank <= 128` (vLLM is sized to the max detected rank).
- `.safetensors` only.
- All adapters must be trained on the same single base model (E4B for this project).

## 6. Skills [OV, Tool, Prompt, and Skill Rules]

- "each skill is a directory with a `SKILL.md` that has YAML frontmatter (`name: <skill-name>`)."
- Scripts run via `run_skill_script` "execute in the competition's persistent Docker container, share filesystem access with `run_command`, and count against your time budget."
- Domain files are read with `load_skill_resource`.
- Max 50 MiB per skill directory. [HR §2.4]

## 7. Pre-zip checklist

- [ ] Exactly one root config file
- [ ] Every `model:` is `gemma-4-e4b-it-qat-w4a16-ct`
- [ ] Only allowed extensions; no `.bak`, `.DS_Store`, `.sh`, `.bin`
- [ ] No symlinks; every `!include` resolves inside the submission root
- [ ] Unpacked size < 3 GiB
- [ ] Adapter dirs named per regex, rank ≤ 128, `.safetensors`
- [ ] No forbidden keys in `generate_content_config`
- [ ] `eval_config.yaml` budgets set deliberately (see tools-and-sandbox.md)
