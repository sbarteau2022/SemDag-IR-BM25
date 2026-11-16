# Plan of attack: draft

Model: `gemma-4-e4b-it-qat-w4a16-ct` (see [Model_Choice.md](../../Rules/Overview/Model_Choice.md)).
Deadlines: Paper Track **Nov 12**. Main entry and merge **Nov 25**. Final **Dec 2**. All 11:59 PM UTC.

## Phase 0: Setup (Nov 10 to 11)
1. You: join the competition and accept the rules on Kaggle.
2. You: decide whether to download the 22.4 GB dataset now or stream it on Kaggle notebooks.
3. Create `DataSets/public/` and `AgenticSubmission/v0_baseline/`.
4. Read `HARNESS_README.md` and run `sample_submission/` unchanged, to confirm the harness works end to end.

## Phase 1: Baseline (Nov 11 to 14)
1. Run the base E4B agent with a plain system prompt on all 129 public tasks.
2. Record pass rate, failure types (tool errors, wrong file, bad patch, timeout), and average tokens per task.
3. Pick a dev split by repo so the same repo is never in both train and eval.

## Phase 2: Prompt and tool tuning, no training (Nov 14 to 18)
1. Add a navigation strategy: start with `search_similar_code`, expand with `get_code_neighbors`, then read.
2. Tighten the system prompt for patch format and `submit_patch` discipline.
3. Build small helper scripts (run in sandbox) for test runs and diff checks.
4. Re-run baseline. Keep a change only if it beats the prior score on the dev split.

## Phase 3: Training data (Nov 18 to 22)
1. Rejection sampling: run the agent on dev tasks, keep patches that pass `test_patch`.
2. Keep a held-out repo set for final scoring. Do not train on it.
3. Format data as trajectories (tool calls + results + final patch).

## Phase 4: LoRA fine-tune (Nov 22 to 26)
1. Train a LoRA adapter (PEFT) on the kept trajectories. Start small: low rank, few steps.
2. Export to `adapters/<name>/` and reference it in `agent.yaml`.
3. Compare with and without the adapter on the held-out repos. Ship only if it wins.

## Phase 5: Freeze and package (Nov 26 to Dec 1)
1. Pick two final submissions: best held-out score, plus a safer alternate.
2. Verify: no internet calls, no paths outside the root, no symlinks, under 12 h runtime.
3. Write the winner package: training code, inference code, environment notes, reproduction steps.
4. Confirm the license (Apache 2.0 per the rules page).

## Phase 6: Submit (Dec 2)
1. Final submission by Dec 2, 11:59 PM UTC. Aim for Dec 1 to leave margin.

## Parallel track: Paper (Nov 10 to 12)
See [PaperTrack/Paper_Ideas.md](../../PaperTrack/Paper_Ideas.md). Keep it small: one claim, one ablation, honest limits.

## Risks
- **Overfitting to 129 public tasks.** Mitigate with the repo-level held-out split.
- **Time.** Paper deadline is two days out. Main track has 22 days.
- **Compute.** Local iteration on E4B is slow; use L4x4 notebooks for full runs (no internet there).
- **Rules drift.** Re-check the Overview and Rules pages before each phase.

## Decisions (locked)
1. **Solo.** No team merge needed.
2. **Go big:** main leaderboard (target top 3, $65k pool) plus Paper Track, ideally the ablation paper (ideas 1+2) for Overall Best Paper ($15k) and the Small Model bonus ($10k) if E4B qualifies.
3. **Compute:** local iteration on E4B, full runs on L4x4 notebooks (no internet there).

## Immediate next steps (need your OK)
- Join the competition and accept rules on Kaggle (you).
- Approve the 22.4 GB dataset download, or stream it on Kaggle notebooks.
- Confirm the Small Model bonus deadline (Nov 12 vs main track date).
