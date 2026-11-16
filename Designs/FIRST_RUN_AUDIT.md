# First-Run Audit and Roadmap

Audited 2026-11-13 against the official harness code (`DataSets/public/wheelhouse/*.whl`), `competition-constraints/`, and `Rules/Verbatim/`. Every "valid" below comes from running the real `adk_submission.validate_directory` plus the single-model check on a copy of each folder.

## 1. Where the system stands

| Piece | State | Evidence |
|---|---|---|
| `v0_baseline` (E4B, official prompt) | Valid. Local run: 4/23 resolved | `results/reports/paired.json` |
| `v2_bm25` (BM25 locate skill) | Valid. Local run: **7/23 resolved**, 162 s/task mean | `paired.json` |
| `v4_semdag` (BM25 + typed SemDAG walk skill) | Valid. **Never run through the model harness.** Only offline localization, parity, and adversarial checks | `CHECKPOINT.md` |
| `v1_brigade`, `v3_attack` | Valid, unmeasured | — |
| LoopAgent coder→verifier "automaton loop" | Exists only in `DataSets/public/data/sample_submission/` (edited in place). **Fails validation**, and won't work as wired (see §2) | validator run |
| LoRA for E4B | None. The only adapter config targets 31B | `AGENTS.md` |
| Kaggle notebook for our agent | None. Only the official getting-started notebook (2 tasks, stock sample) | `DataSets/public/notebooks/` |
| Python-best-practices binding | Not present in any prompt or skill | grep |
| Adversarial Python olympiad skill | Not in the base folder. The Zed original is outside the folder I can read | — |
| Kaggle submissions made | 0 | `CHECKPOINT.md` |

Local numbers come from the MLX 4-bit stand-in on the Mac, with no thinking budget and Docker sandbox. They are not the scorer's L4/vLLM setup.

## 2. Blockers found

1. **`v4_semdag/eval_config.yaml` is `max_time_minutes: 8`.** The scorer runs about 120 tasks one after another, with no default limit, and errors the whole submission past 12 hours. 8 min × 120 = 16 h worst case. **Set it to 5 or less.** v1, v2 and v3 are already at 5.
2. **The loop automaton isn't wired correctly:**
   - It calls `python semdag/repo_eval.py` through `run_command`. Skill scripts don't live in `/workspace`. They're only reachable through `run_skill_script`, and coder/verifier declare no `skills:`, so neither agent can reach the automaton.
   - It declares `gemma-4-31b-it-qat-w4a16-ct` with `adapter: main_lora` / `tool_lora` (dummy 31B adapters). That's the wrong base for the E4B bonus.
   - It contains `agent.yaml.bak-precoeval` and `prompts/system.md.bak-precoeval`, which the validator rejects (`File has disallowed extension '.bak-precoeval'`).
   - It lives inside the official dataset copy. It should move to `AgenticSubmission/v5_semdag_loop/`.
3. **No real-scorer timing.** We need one E4B run on Kaggle L4x4 to measure seconds per task, vLLM start-up, and LoRA slowdown before trusting any budget.
4. **The verifier's test command is free text** (`--test "<repo test cmd>"`). A 4-iteration loop with full test runs can burn the 5-minute budget. Use targeted tests only, with `timeout_seconds` ≤ 120.

Correction to `competition-constraints/submission-format.md`: `!include ../prompts/x.md` **is allowed**, as long as the resolved path stays inside the submission root. The official sample does this, and `yaml_loader._resolve_include_path` only blocks escapes from the root. The README's wording overstates the rule.

## 3. Roadmap to a first run (ordered)

### Step 1: Fix the budget (5 min)
- `v4_semdag/eval_config.yaml` → `timeout_seconds: 120, max_tool_calls: 40, max_time_minutes: 5, max_turns: 60`.

### Step 2: Build `v5_semdag_loop` (SemDag + automaton in the loop)
- Root: `LoopAgent` with `max_iterations: 3`, running `[coder, verifier]`. All agents use `gemma-4-e4b-it-qat-w4a16-ct` with no adapter.
- coder: `skills: [skills/semdag]`. Iteration 1 calls `run_skill_script(semdag, scripts/repo_eval.py, [issue])` and edits the top site.
- verifier: `skills: [skills/semdag]`, tools `run_command`, `submit_patch`, `get_status`. It calls `repo_eval.py --verify --test "<targeted test>"` and only calls `submit_patch` on `clean: true`. **On the last iteration it submits anyway if the diff is non-empty.** The harness would grade the diff even without the call, but an explicit submit ends the loop early and saves time.
- "Math is tight": I'll add property tests for `retriever.py`. The walk weights must sum to 1, damping must stay in [0, 1], the ranking must be deterministic for the same input, and ties must break stably. I'll also add a parity check that the graph built from the frozen baseline matches byte for byte.
- No new file types: `.py` scripts only. Validate with the real validator before zipping.

### Step 3: Bind it to Python best practices
- Add a short `prompts/python_rules.md` included by the coder. It covers:
  - Minimal diffs that match the surrounding style.
  - Keeping public signatures and exact error messages and types.
  - No bare `except`, and no mutable default arguments.
  - Type hints that match the file.
  - Edits that pass `python -m py_compile`.
  - No new dependencies, since the sandbox is offline.
- Add a deterministic `py_compile` + `pyflakes`-style check (standard library only, AST-based) to `repo_eval --verify`. Syntax errors already block. Undefined names and unused imports introduced by the edit would block too.

### Step 4: Adversarial Python olympiad skill
- **Needs from you:** the Zed skill file to mimic. It isn't in the base folder. Copy it in, or tell me its path (probably under `~/.config/zed/` or `~/.agents/skills/`).
- Plan: build `skills/py_olympiad/` with `SKILL.md`, `scripts/challenge.py` and `resources/*.md`. After an edit, the script generates adversarial inputs (edge values, empty/None, unicode, large sizes, type confusion) for the changed functions, runs them in `/tmp`, and reports crashes or regressions against baseline behavior. The verifier treats a new crash as `clean: false`.
- Keep it within budget: one call, ≤ 30 s, standard library only.

### Step 5: Kaggle baseline notebook
- `notebooks/gemma4_e4b_baseline.ipynb`, adapted from the official getting-started notebook. It:
  1. Uses the dataset and wheelhouse inputs, with internet off on L4x4.
  2. Builds `submission.zip` from a chosen `AgenticSubmission/vN` and runs the validator plus a size and extension check.
  3. Starts vLLM on E4B with the official flags.
  4. Runs `Evaluator` over N public tasks (default 129) with the submission's `eval_config.yaml`, timing each task.
  5. Writes `summary.json`, per-task timings, a projected 120-task wall time against 12 h, and the zip to `/kaggle/working/`.
- It runs v0, v2, v4 and v5 for a paired baseline on the same tasks.

### Step 6: First run
- Run the notebook on Kaggle for v2 (current best) and v5 (new) over the full 129 public tasks.
- **Gate:** projected 120-task time ≤ 10 h, and v5 ≥ v2. If that passes, submit v5 as the first daily submission. That needs your go-ahead, and you must accept the rules by Nov 25.

### After the first run
- Use the paired traces to target edit-application and verification failures.
- Then LoRA. The SFT seed can use frontier-model trajectories, which staff allowed subject to provider terms and Apache 2.0. Train on L4x4 and target the E4B base.

## 4. What's left before a first run (short list)

1. Lower v4's per-task time to ≤ 5 min.
2. Build `v5_semdag_loop` with the automaton reachable through skills, all E4B, with no `.bak` files.
3. Add the Python-rules prompt and AST lint gate.
4. Get the Zed olympiad skill from you, then build `py_olympiad`.
5. Build the Kaggle notebook and do one L4x4 timing run.
6. Accept the competition rules on Kaggle before Nov 25 (you, by hand).
