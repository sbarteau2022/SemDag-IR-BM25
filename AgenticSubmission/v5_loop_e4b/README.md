# v5_loop_e4b: LoopAgent baseline on E4B (LOCAL MEASUREMENT ONLY)

**Never zip or submit this directory.** Its `eval_config.yaml` (30 min, 60 calls, 500 turns, 300 s commands) is the generous
local baseline budget from `Designs/ROADMAP.md` Phase 0. At 30 min per task, ~120 hidden tasks would need up to 60 h,
and the scorer errors the whole submission past 12 h. `tests/test_submission_budgets.py` enforces this: only directories
listed there as local-only may exceed 5 min per task.

Origin: the coder→verifier `LoopAgent` from `DataSets/public/data/sample_submission/` (`max_iterations: 4`), changed only
where it could not run on E4B (see `Designs/FIRST_RUN_AUDIT.md` §2):

- every agent declares `gemma-4-e4b-it-qat-w4a16-ct` (was the 31B model); no `adapter:` lines and no `adapters/` (the
  sample's adapters were 217 KB dummies for the 31B base);
- the `.bak-precoeval` files are dropped (the validator rejects them);
- `skills/semdag` (copied from `v6_1_budget`) is attached to coder and verifier, and the prompts call `repo_eval.py`
  through `run_skill_script`, because the sample's `python semdag/repo_eval.py` via `run_command` points at a path that
  does not exist in `/workspace`;
- `sub_agents/code_analyzer.yaml` is kept (unreferenced) with the model switched, because the single-model check scans
  every standalone agent YAML.

Sampling is the stock competition config (max_output_tokens 16384, thinking_budget 4096). No adapter.
