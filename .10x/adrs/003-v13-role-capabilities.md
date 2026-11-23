# ADR-003: Role-bound native skill surfaces

Status: Accepted (owner approved).

Decision: root exposes prepare/finalize/status; editor 1 and editor 2 expose view/edit/status with static slot binding. Remove run_command from all three agent tool lists. Register only scripts/run.py per role; materialize unchanged native engine dependencies as readable assets. Native code validates actions/slot before mutation; no role flag can elevate privileges. Do not modify the official SDK or infer missing model arguments. Keep E4B, budgets, editor count/ambiguity and retry rules unchanged.

Alternative: prose instructions plus generic shell already failed in the measured Stage 1 smoke. A host output adapter changes scorer behavior and is rejected.

Limits: agent_tool and submit_patch still callable; this does not force preparation before model dispatch or prevent empty submit. It is an action/call surface boundary, not full host confinement. Prove compiler separation and actual SDK script lookup denials before live testing. No numeric policy thresholds without successful editor timings.
