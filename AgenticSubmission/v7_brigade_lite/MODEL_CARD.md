# Model card: v7_brigade_lite

- **Base model:** `gemma-4-e4b-it-qat-w4a16-ct` for every role.
- **Adapters:** none. The LoRA Bank comes later, one adapter per lane, only after the Kaggle gate.
- **Architecture:** `LoopAgent` with up to 3 rounds of planner → executor → auditor.
  - Every role has `include_contents: none`. ADK then shows each role only the latest message from the previous role, plus that role's own calls in the current turn, so no role carries the whole history. That keeps each prompt short and, by design, below the scorer's 14,336-token compaction trigger.
  - State carries memory between roles: `plan`, `exec_note`, `verdict`.

## Roles

| Role | Sees | Tools | Sampling | What the model sees per tool, and cost |
|---|---|---|---|---|
| planner (think lane) | harness task prompt (round 1) or the last verdict; `{plan?}`, `{verdict?}` | `run_skill_script` (meta.py, round 1 only), `read_file` (≤ 2) | temp 1.0, top_p 0.95 (top_k left to the model default, 64), presence 0.3, frequency 0.2, thinking 4096, output ≤ 6144 | meta.py report ≤ 6,000 chars (~2k tokens); `read_file` ≤ 150 lines |
| executor (code lane) | the planner's PLAN message | `read_file`, `edit_file`, `run_command`, `run_skill_script` (fix_edit.py); no `write_file` | temp 0.0, top_p 1.0, no penalties, thinking 1024, output ≤ 4096 | tool outputs ≤ 5,000 chars each; ≤ 10 calls |
| auditor | the executor's DONE line; `{plan?}` | `run_skill_script` (audit.py), `submit_patch`, `get_status` | temp 0.0, thinking off, output ≤ 1024 | audit verdict ≤ 2,600 chars |

## Why these settings

- **Temperature:** the owner's split, temp 1.0 to think and temp 0.0 to act.
- **No penalties for the executor.** `edit_file` must copy `old_string` exactly, and a repetition penalty would corrupt that copy (run_11: 30/65 edits failed with "old_string not found").
- **Penalties for the planner.** It writes no code, so penalties there only dampen looping thoughts.
- **`min_p` and `repetition_penalty`** are not settable: ADK's `GenerateContentConfig` rejects them.
- **No `write_file` for the executor.** That removes destructive whole-file rewrites (run_10: 2 tasks) and scratch files landing inside `/workspace`.

## Status

**PROPOSED.** No run yet. Loop 1 measures it per lane against v6.1.
