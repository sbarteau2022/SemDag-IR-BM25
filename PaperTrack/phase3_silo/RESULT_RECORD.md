# Phase 3 primary result: validator record

Written 2026-11-11 by the validating session, from `out/heldout_scores.jsonl` (run `89638938-c16f-4c72-8c4f-8a8fc19463cd`, 5,082 rows). Numbers are from `validate.py p5` → `out/stats_validator.json`. `PARCELS.md` is unchanged (SHA-256 `96c8eb51…9204`).

## Pre-registered outcome

**Verdict under the fixed claim rules: "lexical, not operational".**

- Primary band: late (layers 30–35), rank 4, chosen on the dev fold (dev silo index early 0.23, middle 0.74, late 1.36).
- Held-out: 62 tasks, 363 prompts, repositories rich, requests, httpx. Subspaces fitted on FastAPI with T1 wording, measured with T2 wording.
- Silo index 0.646, 95% interval [0.559, 0.739] (4,000 task resamples). Rule 1's first condition holds.
- Template-only subspaces reproduce the effect: mean template-only diagonal 0.758 against mean role diagonal 0.722, a ratio of 1.05. Rule 1 requires under 0.5, so rule 3 applies.
- All four roles passed the "probed" check.

Net damage in base-score SD units, random-subspace damage subtracted. Rows are the damaged role, columns the ablated subspace.

| Target | LOC | ANA | IMP | VER |
|---|---:|---:|---:|---:|
| LOC | 0.134 | -0.014 | -0.076 | -0.029 |
| ANA | -0.001 | 0.051 | 0.074 | -0.163 |
| IMP | -0.019 | 0.106 | 1.756 | 0.351 |
| VER | 0.006 | 0.722 | -0.053 | 0.946 |

Template-only diagonal: LOC 0.111, ANA -0.037, IMP 2.328, VER 0.631.

## Reading

- The index is carried by IMP and VER. IMP is the only role with a code-fence answer prefix, and its template-only subspace does more damage than its task subspace.
- The ANA subspace damages VER by 0.72 SD. Both are answered Yes/No. That pattern fits a shared answer-format direction, not a role.
- LOC and ANA show almost no own-role damage at this rank and band.
- Base accuracy on held-out: LOC 0.61 (chance 0.125), ANA 0.60 (chance 0.5), VER 0.85 (chance 0.5). ANA is weak.

## Exploratory, not pre-registered

Own-role drop minus template-only drop, nats, task bootstrap: LOC 0.03 [-0.15, 0.22]; ANA 0.18 [0.16, 0.21]; IMP -0.83 [-1.05, -0.63]; VER 0.17 [0.14, 0.21]. These were computed after seeing the result. They can motivate a follow-up design; they cannot be reported as a finding of role-specific structure.

## Deviations and unverified points

1. No manifest was written before P2. `out/manifest.json` was written afterwards by the validator and says so.
2. `out/receipts.jsonl` is not a real execution log: start and end times are fixed offsets from the moment the receipt script ran, every parcel appears twice, and digests were taken after the fact. Use file modification times for the timeline (P0 07:46, P2 07:51, P3 08:00, P4 08:35 UTC).
3. `exec/p4_primary.py` was edited 14 seconds after the last held-out row was written, so the digest on record is not provably the code that produced the rows.
4. `exec/p4_primary.py` can resume and drop partial rows. The output cannot show whether the run was interrupted.
5. Prompts are tokenised from the chat-template string with `tok.encode`; whether this adds a second BOS token was not checked. It would affect every condition equally.
6. No independent `stats.json` exists, so the P5 gate is open. The statistics above have one implementation, the validator's.
7. The longest prompt is 2,085 tokens.
8. The validator read the four executor scripts and found the ablation, capture position, subspace fits and random draws as specified. It did not rerun any model pass.
