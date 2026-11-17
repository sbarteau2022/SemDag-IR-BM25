# Skills/reference: source material, NOT shipped

Reference copies used to write our own agent skills (`AgenticSubmission/v7_*/skills/`). Nothing in this folder goes into a submission zip. The agent ships only our own rewrites, which are standard-library `.py` and short `.md` files. Selection and verdicts: `Designs/SKILLS_AUDIT_2026-11-17.md`.

| Folder | Source | Licence | Used for |
|---|---|---|---|
| `ai-skills/debugging-and-error-recovery`, `ai-skills/tdd-skill` | AI Skills 0.5.0 (Zia Saidi), from `~/Desktop/PhyEngLastExam/Skills:Plugins` | MIT (`ai-skills/LICENSE`, `THIRD_PARTY_NOTICES.md`) | "Check the instrument" (collected-count check), red-for-the-right-reason, load-bearing (revert-to-red) check |
| `agent-engineering/skills/verify-change`, `references/workflow-contract.md` | Agent Engineering 0.3.2 (Otavio Barros) | MIT (`agent-engineering/LICENSE`) | Phase boundaries per role; gaps reported, never passed |
| `owner-runbooks/*` | Owner's own runbooks (`skills to audit`, 2026-10-30) | Owner's material | Plan/judge lanes (01), two-strike (02), stable-first prompts (03), git-checkpoint holes (04), tool-output budgets (06), step order (07), hostile-input probe (10), done-gate (11), reproduce-isolate-fix (12), governance laws |

Not copied:
- The Engineering plugin's `debug` skill: no licence file. Only its idea is used (the planner's expected / actual / repro / root cause / fix report format), written from scratch.
- `ai-skills/tdd-skill/scripts/mutate-check.sh` is kept here as reference only. Submissions cannot contain `.sh`; our load-bearing check is reimplemented in Python inside `audit.py`.
