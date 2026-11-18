# v7.1 preregistration: bounded thinking + executor/auditor fixes

Frozen 2026-11-17, before any v7.1 file is built or run. Changes after this point go in dated amendments with new arm IDs.
Status: **PROPOSED**.
Inputs: lane runs 15–17 (`docs/runs/run_15/16/17_RESULTS.md`), `docs/SCORER_PARITY.md`, `results/server_bench/vllm_metal/THINK_INJECTION.md`, and the owner's framing (2026-11-17): thinking must be a budget the model plans within, not a hard cap that cuts it off mid-thought.

## 1. Questions

- **Q1.** Do the four lane-derived fixes stop the time sink? In runs 15–17, 6/11 tasks hit the 5-minute cap, and the executor took 63–69% of each lane's time.
- **Q2.** Does a bounded thinking budget (prompt allowance + safety-net cap) keep thinking inside its allowance without hard-cutting it?
- **Q3.** Does the uncapped variant (`<|think|>` in the role prompt, `thinking_budget: 0`) do as well as Q2 without runaway thinking?

## 2. Arms (same tasks, same order, one seed each)

| arm | submission | thinking setup |
|---|---|---|
| **R** | `v7_brigade_lite`, unchanged | planner cap 4096, executor cap 1024, auditor off (current) |
| **A** | `v7_1_bounded_cap` | prompt allowance (planner ~2,000, executor ~1,000 tokens) + hard cap as a safety net: planner 4096, **executor 2048** |
| **B** | `v7_1_bounded_think` | same prompt allowances; `thinking_budget: 0` plus a literal `<|think|>` at the top of the planner and executor instructions, so no `thinking_token_budget` is sent; ceilings come from `max_output_tokens` (planner 6144 → **4096**, executor 4096) |

R is rerun here because runs 15–17 had no thinking enforcement and no compaction, so they are not comparable with parity runs (lanes amendment 2026-11-17).

## 3. Changes shared by A and B (from runs 15–17)

1. **Executor checks only:** the executor runs only meta's `test_cmd` (nearest tests) or its `/tmp` repro, never the full suite. At most **2 verification commands after its last edit**, then it hands over. (Evidence: 6644 and 3672 timed out on reruns.)
2. **Edit recovery:** after 2 `edit_file` failures, the executor must `read_file` the exact lines before trying again. It must not retry the same `old_string`. (7502: 0/5.)
3. **Audit-gated submit:** the auditor calls `submit_patch` only in the same turn as an `audit.py` result of `submit` or `submit_best`, then ends its turn with no more tool calls. (7505 submitted unaudited; 7433 submitted 4 times.)
4. **Loop guard:** the planner prompt says that if `{verdict?}` says submitted, it must output `DONE` and nothing else. `max_iterations` stays 3. (`submit_patch` exits only after the turn: HR §5.3.)
5. **Decision-first thinking:** the planner and executor prompts state their thinking allowance and say to stop thinking once the next action is clear.

Nothing else changes: same skills and scripts, same tools, `eval_config.yaml` 120 s / 40 calls / 5 min / 60 turns, same temperatures and top_p, penalties unchanged.

## 4. Environment (all arms)

- oMLX 0.7.0, started by the runner under seatbelt (no reused server), on the competition MLX repack. Docker Desktop with `network_mode=none`.
- Parity on: `eval_parity.py` compaction 14,336 tokens; the proxy copies `thinking_token_budget` into oMLX's field.
- **Parity step P1 (before any arm):** the proxy fills `top_k: 64` when a request has no `top_k`, the same as vLLM `--generation-config auto` on the scorer. Gate: a unit test, plus one live request whose proxy row shows the injected value.
- **Parity step P2 (before arm B):** a 3-request smoke on oMLX showing that `<|think|>` in the system prompt produces parsed reasoning with no budget sent, as on vllm-metal. If it fails on oMLX, arm B runs on vllm-metal for **all three arms** (`Tools/local/serve_vllm_metal_kaggle.sh`, with the proxy copying the budget for A and R unchanged). If neither server works, arm B is dropped and the reason is recorded.

## 5. Tasks

The 11 lane tasks, in this order: requests_7427, requests_7502, requests_7505, requests_7433, requests_6644, rich_3468, rich_3180, rich_3296, rich_3043, rich_3052, httpx_3672 (`results/lane_*_ids.txt`). Concurrency 1. These are training-repo tasks, so they are diagnostic only. Generalization to unseen repos is checked separately on the fresh dev set (owner decision, 2026-11-17).

## 6. Metrics (from `results/telemetry.sqlite`, `lane_report.py`)

- Resolved / 11; failure class; broke_at.
- Timeouts / 11.
- Per role: time share, completion tokens, thinking tokens (p50, p90, max).
- **Cap-hit rate:** thinking steps with `thinking_tokens ≥ cap − 8` / thinking steps (A, R).
- **Runaway rate:** calls with `finish_reason=length` / calls.
- Edit success; repro runs; audit decisions; `submit_patch` count per task.

## 7. Gates and falsifiers (decided now)

| ID | Gate | Pass |
|---|---|---|
| G1 | Fixes 1–4 work | A and B each: timeouts ≤ 3/11 (R baseline measured in this run); `submit_patch` ≤ 1 per task on every task; 0 unaudited submits |
| G2 | Bounded budget holds (A) | cap-hit rate < 2% of planner+executor thinking steps; executor thinking p50 ≤ 1,000 |
| G3 | Uncapped variant is safe (B) | runaway rate ≤ R's runaway rate; no task with > 1 `finish_reason=length` call |
| G4 | No regression | resolved(A) ≥ resolved(R) and resolved(B) ≥ resolved(R) |

**Falsifiers:**
- F1: if A misses G1, the fixes did not address the time sink; redesign the executor role before more runs.
- F2: if B fails G3, uncapped thinking is rejected for submission.
- F3: if both A and B fail G4, v7.1 is not kept.

**Decision rule:** keep the arm that passes G1–G4 (G3 for B, G2 for A) with the higher resolved count; on a tie, keep A (it has a safety net). None of this unlocks a Kaggle run: that gate stays at ~18/23 with clean exits, floor 12–15 (owner, 2026-11-17).

## 8. Limits

- 11 tasks × 1 seed: a 1–2 task difference is noise.
- These runs are local MLX, not 4×L4 vLLM, so wall-clock times are not the scorer's.
- `include_thoughts` and compaction handling of injected thinking (arm B) are unverified until this run.
- Training-repo tasks only; unseen-repo generalization is not tested here.

## 9. Cost

33 task runs at about 5 min plus setup, roughly 3 h of machine time. Run as three sequential lane passes (R, A, B) with a lane report after each.

## Amendment 2026-11-17 (owner rule on budgets, before any v7.1 build or run)

Owner rule: output and thinking budgets stay at the competition defaults, and the owner is not to be asked again. Every arm now uses:
- `max_output_tokens: 16384` for every role, and `thinking_budget: 4096` for every role that thinks. The auditor keeps thinking off by design.
- `eval_config`: `timeout_seconds 300` (competition default; the harness caps it at the time left), `max_tool_calls 40`, `max_time_minutes 5` (from the 12 h limit), `max_turns 60`.

Effect on the arms:
- **R** = v7 with these budgets (committed to `v7_brigade_lite`). The executor cap rises from 1024 to 4096, and output limits rise to 16384.
- **A** = prompt allowances (planner ~2,000, executor ~1,000) with the 4096 cap as a safety net. This replaces "executor 2048".
- **B** = `thinking_budget: 0` + `<|think|>` + prompt allowances, with `max_output_tokens 16384` (not 4096). Gate G3 is unchanged.
- **G2** now reads: cap-hit rate (thinking ≥ 4088) < 2% of planner+executor thinking steps; executor thinking p50 ≤ 1,000.

Evidence that 16384 is safe at a 32,768 context: vLLM 0.33 (vllm-metal) clamps `max_tokens` to the remaining context. A 20,014-token prompt with `max_tokens 16384` returned HTTP 200, and `max_tokens 32768` on a short prompt also returned 200. The scorer runs a patched vLLM 0.19.1 (staff); its `get_max_tokens` also clamps (source at tag v0.19.1).

## Amendment 2026-11-17 (b): per-task time 4 min (owner)

Every arm runs with `max_time_minutes: 4` (was 5). The rest of `eval_config` is unchanged: `timeout_seconds 300`, `max_tool_calls 40`, `max_turns 60`. Gate G1's timeout threshold stays at ≤ 3/11.
