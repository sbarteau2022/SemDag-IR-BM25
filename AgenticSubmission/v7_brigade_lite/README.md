# v7_brigade_lite

Brigade-lite agent, loop 1. Design and rationale: `MODEL_CARD.md`. Skill sources and verdicts: `Designs/SKILLS_AUDIT_2026-11-17.md`.

- **What's new versus v6.1:**
  - `skills/semdag/scripts/meta.py`: deterministic preflight report.
  - `skills/semdag/scripts/audit.py`: deterministic sign-off, two-strike rule, collected-count check, red-reason classification.
  - Three role prompts and per-role sampling.
- **Unchanged from v6.1:** the `repo_eval` / `fix_edit` / IR scripts.
- **Tests:** `tests/test_v7_skill_scripts.py`, which runs both scripts against a throwaway git repository.
- **Budget:** 120 s per command, 40 tool calls, 5 min, 60 turns (submittable).
