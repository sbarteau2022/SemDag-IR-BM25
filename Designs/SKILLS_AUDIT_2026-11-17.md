# Skills audit: `~/Desktop/skills to audit` (2026-11-17)

Scope: decide what ships to the E4B agent (runtime, inside the 5-min task) versus what governs our own dev loop (Claude-side), versus what is out of scope.

Runtime packaging rules:
- `.py` and `.md` only, stdlib, offline.
- `SKILL.md` under 4 KB.
- Bounded JSON outputs.
- No repo names, HTTP endpoints or external services: agnostic to whichever repository is under `/workspace`.

| Source | Verdict | What carries over | What is dropped |
|---|---|---|---|
| 01 runbook-plan-and-judges | **Runtime (compiled into prompts)** | PLAN lane (think high) vs CODE lane (think off) = our temp 1.0 planner / temp 0.0 executor. The plan is a single "packet" with a deterministic judge (a repro or test command). No self-graded completion. | DAG of 512 packets, HTTP endpoints, `mind.tail` (no time or API for them in a 5-min task) |
| 02 two-strike-tactical-escalation | **Runtime (enforced in `audit.py`)** | Strike 1: the retry must change approach. A signature of edited file + function + diff hash is kept in `/tmp`, and an identical retry is rejected. Strike 2: stop, submit the best non-red candidate or abstain. | T0–T4 levels, orchestrator guidance, HTTP 400/409 |
| 03 kv-cache-and-continuity | **Runtime (structural)** | Stable first, volatile last: static role contracts first, `{report}/{plan}/{verdict}` state at the tail (the scorer enables vLLM prefix caching). Continuity via structured `output_key` state instead of 60% checkpoints. | Landauer framing, block-identity hashing |
| 04 hole-isolation-and-verification | **Runtime (adapted)** | Hole → git checkpoint: commit a green candidate, `git reset` on a failed attempt (after checking the `_swegemma_baseline` ref). Diff inspection before submit. | Merkle roots, merge-request HTTP API (the harness sandbox is already the hole) |
| 05 rust-tokio-systems-engineering | **Out of scope** | none (Python tasks) | all |
| 06 agent-experience-and-tool-design | **Both** | SKILL.md < 4 KB, bounded outputs with stable ids, a "what the model sees + token cost" note per tool (goes in `MODEL_CARD.md`). PPC with KEEP_BASE = our loop rule (keep v6.1 unless the gate passes). | none |
| 07 delivery-runbook | **Dev-side** + runtime shape | Calibrate → smallest slice → checkers → adversarial review is the brigade-lite step order. Dev-side: every loop follows it. | holes HTTP |
| 08 research-runbook | **Dev-side** | claim labels, provenance rows (already used in run docs) | — |
| 09 intake-runbook | **Dev-side** | registering "SWE-Python agent" as a governed adapter | — |
| 10 pressure-test-runbook | **Runtime-lite (optional, measured)** | Hostile inputs for the changed functions only (empty/None/unicode/oversize/type confusion), run from `/tmp`, ≤ 20 s, inside `audit.py`. Kept only if a loop shows it catches regressions without costing solves. | UI/auth/network edge sections |
| 11 release-runbook | **Dev-side** (`Tools/release_gate.py`) | Done-gate for a zip: validator, budget guard test, pytest, pasted outputs, dated sign-off. Runtime analog = `audit.py` sign-off. | `discipline.py` web adapter |
| 12 incident-runbook | **Runtime (core of the fix loop)** | Reproduce (repro fails deterministically) → isolate → fix the root cause → repro green. The "regression guard" stays in `/tmp`, because test files are stripped from the patch. This is the F1 repro-first family. | Failures.md post-mortem (dev-side) |
| ENGINEERING-GOVERNANCE (8 laws) | **Dev-side law** (PENDING ratification) | DECLARE / GATE / PROVE / "coders never self-approve" → the auditor is a script, never the executor. PARTITION → brigade lanes. | — |
| kimi-frontend-kit (14 skills, hooks, fonts, CSV) | **Out of scope** | Only the pattern: contract-first, parallel coders with non-overlapping file ownership, a QA critic last. Already reflected in the brigade design. | Everything else. It is frontend/TypeScript, and much of it is banned in a submission (`.sh`, `.ttf`, `.csv`, `.cjs`, `.coverage`). |

## What the agent gets (loop 1, `v7_brigade_lite`)

1. `skills/preflight/scripts/meta.py` → `report.json`:
   - readiness;
   - IR/graph/walk top 3 sites with their exact current source;
   - targeted pytest baseline;
   - baseline-ref check;
   - suggested repro/test command.
2. `skills/audit/scripts/audit.py` → verdict JSON:
   - `repo_eval --verify` checks, targeted pytest, scope check;
   - two-strike signature, so an identical retry is rejected and the second red verdict stops the loop;
   - optional hostile-input probe.
3. Role contracts (prompt wrappers):
   - **planner**: PLAN lane from 01 + reproduce/isolate from 12;
   - **executor**: CODE lane, small edits, `fix_edit` rescue, git checkpoint;
   - **auditor**: calls `audit.py`, submits only on green.
4. `MODEL_CARD.md`: per-role sampling plus "what the model sees / token cost" per tool (06).

Dev-side: 07/08/09/11 and the governance laws shape how each loop is preregistered, run, reviewed and signed off.

## Addendum: `~/Desktop/PhyEngLastExam/Skills:Plugins` (282 SKILL.md, 44 plugins)

That folder also holds a copy of `skills to audit` (verdicts above unchanged). Triage was done by name and description for all plugins, and by full read for the candidates below.

### Runtime (compiled into the agent's scripts and role contracts)

| Source | What carries over | Where it lands |
|---|---|---|
| AI Skills: `debugging-and-error-recovery` | Check the instrument before believing it: a green pytest that collected 0 tests proves nothing, so check the count, not the exit code. Stop-the-line: preserve evidence, guard first (repro red), then fix. "Two bumps = guessing." | `meta.py` + `audit.py` require `collected > 0` and that the named target test actually ran. Planner contract requires a red repro before an edit plan. |
| AI Skills: `tdd-skill` | Red for the right reason: an assertion failure, not an import or collect error. Prove the fix is load-bearing: temporarily revert it, the repro must go red with the same symptom, then restore. | `audit.py` classifies red reasons (assertion vs import/collect error). Optional load-bearing check (`git stash` → repro red → `git stash pop`, one extra repro run). |
| Engineering: `debug` | Reproduce → isolate → diagnose → fix, with a fixed report (expected / actual / repro / root cause / fix) | Planner output schema |
| Agent Engineering: `verify-change` + `workflow-contract` | Phase boundaries: each phase stops at its own completion condition (planner never edits, executor never submits, auditor never edits). Independent oracle. Gaps are reported, never silently passed. | Role contracts. The auditor is a script, and its verdict lists gaps explicitly. |

### Dev-side (how we build, train and judge; nothing ships)

- **Brigade orchestration** (Agent Army, 10x-Team, AI Skills `orchestration` / `adversarial-review`, Decision Council pre-mortem): loop design, adversarial review of each candidate, and the Kaggle parallel-planner / critic pattern.
- **LoRA Bank training** (huggingface `trl-training`, `huggingface-llm-trainer`, `huggingface-trackio`): SFT / GRPO recipes for the per-lane adapters, run on Kaggle L4×4 offline. HF Jobs is not used, because training must run in the competition notebook.
- **Environment fix** (docker-skills): building the amd64 sandbox image, one of the two options for local fastapi grading.
- **Memory plugins** (memory-toolkit, Cognee, agent-memory, Memory Bank, Project Memory): no cross-task memory exists at runtime. Session continuity on our side is already covered by Continuity and project memory.

### Out of scope

- Frontend, design, marketing, app-store, i18n, grant and SageMaker skills.
- Meta Discipline Physics.
- `pyright-lsp`: pyright needs Node and is not in the offline sandbox, and `/wheels` holds no type checker or linter (checked: no mypy, pyright, pyflakes, pylint or ruff), so type checking stays AST-based in `audit.py`.
