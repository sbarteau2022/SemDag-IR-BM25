# ENGINEERING-GOVERNANCE.md — The Invariant Core

Status: PENDING GLOBAL LAW (proposed 2026-10-30; effective on Stewart's ratification). Date: 2026-10-30.
Scope: ALL engineering work, every domain — once ratified. Domain specifics live in adapters; THIS file is the discipline itself.

## Ratification (blocks stone-tablet status)

- [ ] Stewart sits with it — open questions recorded below, none resolved by assumption
- [ ] Any open question closed with a dated entry (amendment or rejection-with-reason)
- [ ] Status flipped PENDING → MANDATED here AND in `~/.config/zed/AGENTS.md` §9 in the same change
- [ ] Ratification recorded in `web-development/docs/Successes.md` with date

Open questions (added 2026-10-30, none answered yet):

- None recorded. Add each as a dated line; do not ratify with an empty-handed silence — an unasked question is not a closed one.

## The core (8 laws, one line each — memorizable by design)

1. **DECLARE** — state intent and bounds before acting. Every task opens with one calibration line.
2. **RETRIEVE** — one canonical source per decision; link, never duplicate.
3. **FORBID** — negative contracts with exact values. Ban-lists over taste lectures.
4. **GATE** — contracts before fan-out; checks before done. Serialization points are reviewed, never assumed.
5. **PARTITION** — decompose into many small partitions; one mind owns each partition front-to-back. Siloed swarms bound by contract — a REQUIREMENT, not a suggestion. Small and focused is how we win.
6. **PROVE** — checker output pasted, never summarized. Coders never self-approve; only gates and critics pass work.
7. **RECORD** — label every claim; append corrections, never rewrite; log failures. A recorded failure beats an asserted success.
8. **WAIVE-OR-OBEY** — comply, or hold a dated, scoped, rule-numbered waiver recorded BEFORE the work. Nothing else exists. Speed, size, prototype status, and model judgment are never waivers.

## What is core vs adapter (the boundary test)

A law belongs in THIS file iff it survives domain-stripping: delete every noun naming a technology, language, framework, or artifact — if the sentence still constrains behavior, it is core. If it names a tool, value, or file type, it is adapter paint.

- Core says: "declare before generating." Adapter says which dials (`DESIGN_VARIANCE` vs `PERF_BUDGET/CORRECTNESS_BAR` vs `DATA_SENSITIVITY/REPRODUCIBILITY_SEED`).
- Core says: "negative contracts with exact values." Adapter says which values (`!important` vs `unwrap()` vs unpinned images).
- Core says: "checks before done." Adapter says which checkers (`tsc` vs `cargo clippy` vs `pytest`).

## The judge rule (what keeps the core honest)

Every mandated rule — core or adapter — has exactly one of: an executable gate, a pasted-output requirement, or a named human sign-off. **A rule with no judge is cut, not kept.** Decoration teaches contempt for rules; contempt kills the system faster than any missing rule.

## The adapter contract (how a domain earns the mandate)

No domain claims governance until it ships, executable on disk:

1. A rules table (exact values, severities, fixes) — one table shared by live gates and batch audit.
2. A structural gate (`discipline.py` equivalent: files exist, skeletons in order, no floating pins).
3. A release checklist (pasted checker output, calibration line, contract gate, stop-gate status).
4. A skill-file set in the mandated skeleton (full-tier for generative areas, flat-tier for convention areas).
5. A compliance map entry pointing at the canonical rule locations.

Until then the domain runs on the core alone, honestly labeled as ungoverned-domain — never on borrowed adapter rules from another domain.

## Adapter registry

| #   | Domain                                                                                            | Adapter location                    | Status                            |
| --- | ------------------------------------------------------------------------------------------------- | ----------------------------------- | --------------------------------- |
| 1   | Web development (frontend, backend, middleware, design language, data, API, devops, QA, security) | `~/Desktop/skills/web-development/` | PROPOSED (gates green 2026-10-30) |
| 2   | — reserved: OpenDesign app backend (next real work)                                               | —                                   | unclaimed                         |

## Corrections

- None yet. Append dated entries; never rewrite history.
