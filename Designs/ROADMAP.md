# Roadmap — grounded in current state (2026-11-12 → Dec 2)

## Where we are (facts, not plans)
- Designs locked: E4B + multi-LoRA ($10k tier); SFT-seed → RL-with-verifiable-
  rewards; repo_eval = verifier + reward + data-filter; reason-first→temp-0;
  abstain gate; native memory.md. Docs: LORA_TRAINING_DESIGN, MODEL_DECISION,
  NVIDIA_ASSETS, this file.
- Harness data complete: 129 tasks, snapshots, graphs, embeddings, wheels, Docker.
- sample_submission wired LoopAgent(coder,verifier) + semdag; adapters/ EMPTY.
- venvs: .venv-harness (swegemma+torch), .venv-mlx. ~290 NVIDIA skills installed.
- NOT done: no baseline score; eval_config still 1min/10call; no training data;
  no LoRA; nemo-relay not run; repo_eval not tested inside swegemma sandbox.

## Guiding rule
Measure before training. Every phase has an exit GATE; don't advance without it.
~20 days, solo. If time compresses, Phases 1–3 alone are a credible submission.

---

## Phase 0 — Baseline & budget (Day 1) — HIGHEST PRIORITY
Goal: a real number to beat; stop self-sabotaging the budget.
- Raise our `eval_config.yaml` off the 1-min/10-call sample → ~30 min / ~60
  calls / 500 turns (within harness ceiling §7.1).
- Run `swegemma eval` (stock E4B, current LoopAgent, NO adapter) over ~10–15
  tasks, then the full 129 if stable.
GATE: baseline resolution_rate recorded in results/. Nothing trains until we have it.

## Phase 1 — repo_eval end-to-end in the sandbox (Days 1–3)
Goal: the verifier actually runs as a tool inside Container A, not just locally.
- Wire repo_eval as a run_command invocation the coder/verifier call; confirm
  parity + localization + verify-after-edit work on real snapshots in-sandbox.
- Decide repo_eval's role vs built-in graph tools (NVIDIA_ASSETS): keep the
  verify gate + parity; lean on built-in search_similar_code/get_code_neighbors
  for raw localization to save tool calls.
GATE: one task solved end-to-end where repo_eval verdict gated the submit.

## Phase 2 — Prompt/harness tuning (no weights yet) (Days 3–7)
Goal: lift baseline with behavior alone — cheapest points.
- Install + run nemo-relay (skills present); trace the 129, get grounded
  telemetry (tool-calls/task, localization misses, blind-retries, budget burn).
- Tighten coder/verifier prompts to: reason-first→temp-0 act, localize-once,
  single-edit, verify, ABSTAIN/minimal-diff when nothing goes green, NO blind
  retry. Use multi-LoRA tree shape (coder + read-only analyzer AgentTool).
GATE: measurable lift over Phase 0 baseline on a held-out slice (not the 129).

## Phase 3 — Submission hardening (Days 5–9, overlaps P2)
Goal: a zip that won't crash in the judges' Docker.
- Dry-run the exact docker/Dockerfile.public path: offline wheels resolve,
  <3 GiB, no symlinks, YAML compiles vs closed registries, 32k ceiling.
- Lock a submit-ready zip of the BEST prompt-only version as a safety floor.
GATE: clean Docker run + valid submission.parquet from the sealed zip.

## Phase 4 — Training data (Days 7–14)
Goal: verified, deduped, decontaminated trajectories (LORA_TRAINING_DESIGN §3/§4).
- D1 first (self-defect harness on permissive repos) — most verified data/hour.
- Gate every example on repo_eval + repo tests; decontaminate vs the 129.
- Tools: Data Designer (synth), Curator (dedup/decontam — pull its skill), User
  Sim (multi-turn). Harvest failed→switch→pass episodes for D4.
GATE: N verified trajectories with receipts + a written dataset manifest.

## Phase 5 — Train the LoRA (Days 12–18)
Goal: E4B adapter that beats the prompt-only floor.
- SFT seed on D1 trajectories (AutoModel PEFT on qat-unquantized base).
- Then RL with verifiable reward (NeMo Gym env + NeMo RL): reward = repo_eval
  green; shape in abstain / no-blind-retry / minimal-diff / budget adherence.
- Export adapter → adapters/main_lora (<3 GiB, QAT-precision match).
GATE: trained submission beats Phase 2 floor on held-out; else ship the floor.

## Phase 6 — Final eval, lock, submit (Days 18–20)
- Full 129 eval of best config; behavioral checks (abstain rate, approach-switch
  on failure, memory writes, budget).
- Re-verify Docker, lock zip, submit EARLY. Never at the buzzer.
GATE: submitted + confirmed accepted on Kaggle.

---

## Critical path & fallbacks
- Hard dependency chain: P0 baseline → everything.
- P4→P5 is the risky long pole. If it slips, Phases 0–3 (tuned stock E4B +
  disciplined verify/abstain loop) is a legitimate standalone submission and
  still wins the smaller-model tier.
- Floor-first: always keep a sealed, Docker-verified zip of the best current
  version so we can submit at any moment.
```
