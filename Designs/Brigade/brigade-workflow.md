# Brigade Workflow

Status: **PROPOSED**  
The governing rules in `Governing_law.md` override this explanatory workflow.

## Task initialization

1. Create a fresh task sandbox and baseline commit.
2. Allocate `/tmp/gemma-brigade/current/`; fail if it already contains records.
3. Record task identity, base commit, declared model, configured budgets, and schema versions.
4. Reserve finalization headroom before any model call.

## Ordered execution

1. **C1 — Graph seeds:** resolve issue nouns and exact identifiers. Record misses as evidence.
2. **C2 — Graph relations:** gather neighbors, candidate subgraphs, and competing targets.
3. **C7 — Relational snapshot:** freeze exact source for the target hypothesis and its dependencies; hash every source.
4. **C3/C5/C6 — Parallel derivation:** independently derive structural IR, relational invariants, and API contracts from C7.
5. **C4 — Risk/compliance:** assault the combined hypothesis for protected-file, budget, compatibility, and hidden-test risks.
6. **S — Synthesis:** deterministic validation followed by adversarial outline verdicts. No new evidence.
7. **I — Implementation:** recheck hashes, falsify the outline, apply the smallest source edit, and do not submit.
8. **C8 — Verification:** record diff, pre/post hashes, targeted tests, and adverse cases.
9. **F — Finalization:** clean scratch files, inspect the exact patch, call `submit_patch` once and last.

## Budget controller

The scored task sees its own `get_status` totals, not the campaign's remaining hidden task count. Select one named `eval_config.yaml` profile before evaluation; the controller may not compute a new cap from unavailable global state. The fixed lane weights below divide that admitted per-task profile. The 12-hour aggregate is checked offline against a full representative campaign, including setup, model service contention, and tail tasks. For 129 public tasks, 12 hours divided by 129 is about 5.58 minutes per task; this is only a planning bound, not an authorized scored timeout or a prediction of hidden task count.

| Lane | Time weight | Tool-call ceiling (100-call profile) |
|---|---:|---:|
| Controller/overhead | 5% | 6 |
| C1 seeds | 8% | 6 |
| C2 graph relations | 12% | 12 |
| C7 snapshot | 15% | 12 |
| C3 structural IR | 10% | 6 |
| C5 edges/invariants | 10% | 6 |
| C6 API | 8% | 5 |
| C4 risk/compliance | 7% | 5 |
| S synthesis | 10% | 4 |
| I implementation | 10% | 18 |
| C8/F verify/finalize | 5% | 20 |

The last 5% belongs to C8 and F together; it is reserved before exploration. Controller overhead has a separate 5%. The call ceilings allocate 94 counted calls to lanes and reserve six for controller recovery in a 100-call experimental profile. `get_status` and `submit_patch` are currently uncounted, but wall-clock limits still apply. Unused time returns to the controller only while the verification/finalization reserve remains intact. Lane time includes model generation, tool latency, and parallel contention; concurrent lane weights are allocations, not a promise of additive wall time.

The current baseline profile of one minute and ten tool calls cannot host this design honestly. Brigade evaluation requires a separately named experimental budget profile and a matched baseline with the same cap. The controller must maintain a monotonic deadline from the harness session clock; prompts alone cannot enforce a deadline. Until a deterministic controller/skill script is implemented and qualified, these lane ceilings remain design contracts rather than runtime guarantees.

## Quality gates

- **Q0 Contract:** schemas, single-model rule, declared tools, and budget plan pass.
- **Q1 Localization:** at least one exact symbol and one competing hypothesis, or an explicit fallback.
- **Q2 Snapshot:** hashes match current files; every admitted exact claim has a source anchor.
- **Q3 Coherence:** S dispositions every outline claim; no critical contradiction or stale evidence.
- **Q4 Patch:** implementation touches allowed source files only and matches the admitted contract.
- **Q5 Verification:** diff is nonempty, targeted checks are exit-recorded, and all hostile edges are dispositioned.
- **Q6 Finalization:** scratch state is outside `/workspace`; exact patch inspected; `submit_patch` is last.

## Early exits

- Empty localization after two materially different attempts: record the failure and hand the task to the sole implementer in baseline mode, with the same total task budget and no fabricated C7 snapshot. This branch is an experimental variant, not a validated submission behavior.
- Snapshot cannot cover the causal chain: reject the outline and relocalize once.
- Packet exceeds its cap: deterministically prune duplicate/supporting evidence; never truncate exact target source mid-token.
- Remaining headroom reaches finalization reserve: stop exploration and either verify the current safe patch or finalize an explicit empty patch. `submit_patch` may capture an empty diff; the result must be recorded as `no_patch`, never as a verified fix.
- Second failure of the same gate: record Strike 2 and block dependent lanes; no identical third retry.

## Reset and next task

After patch extraction, Container A and its ledger are destroyed under the default non-reuse lifecycle. Container B starts from the original snapshot and receives only the patch. After verification, it is destroyed. If container reuse is enabled, the harness must prove its workspace and temporary-directory reset before a brigade task is admitted. The shared model server remains running; its internal sequence KV is reclaimed by the serving layer. The next task receives a new empty ledger and must not inherit summaries, hashes, or state keys. A persistent audit copy requires an explicit host trace/export path; `/tmp` alone cannot provide a post-task rollback proof.
