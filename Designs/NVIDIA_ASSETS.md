# NVIDIA Assets — what we pulled in & what's usable (2026-11-12)

## 1. Installed: ~290 NVIDIA skills → repo `.claude/skills/`
(`npx skills add NVIDIA/skills --agent claude-code`). On-target subsets:

- **nemo-relay-* (10)** — our dev/trace/behavior bench, now local skills:
  `install`, `get-started`, `instrument-calls`, **`instrument-context-isolation`**
  (= our AgentTool-analyzer plan), `instrument-typed-wrappers`,
  `plugin-observability`, `plugin-adaptive-tuning`, `plugin-build`,
  `debug-runtime-integration`, `migrate-from-flow`. Dev/train-time only; never ships.
- **Training:** `nemo-rl-*`, `launch-nemo-rl`, `nemo-automodel-distributed-training`,
  `nemo-mbridge-perf-*` (memory tuning, parallelism, MoE). For LoRA/RL training box.
- **Orchestration/serving patterns:** `dynamo-router-starter`, `dynamo-recipe-runner`,
  `dynamo-interconnect-check` (L4/no-NVLink check), `dynamo-troubleshoot`.
- **NemoClaw:** `nemoclaw-user-guide`. See §3.
- **CUDA kernels (not needed for comp, offline forbids binaries):** tilegym (cuTile),
  warp, cudaq, nvshmem, compute-sanitizer. Ignore for submission.
- **Security-adjacent:** `doca-argus` (DPU threat detection), `doca-hardware-safety` —
  not the container-vuln blueprint; that's cloud-only (§2).

## 2. Blueprint harvest — "Vulnerability Analysis for Container Security"
Built on NeMo Agent Toolkit (DEPRECATED) + Nemotron 550B/30B NIMs + Tavily web
search + crane. **None of that ships in our offline comp.** We harvest the
ORCHESTRATION LOGIC, not the stack. The design VALIDATES ours.

Transferable logic → our SWE patch agent:
1. **Deterministic pre-triage → early exit, LLM only for ambiguous cases**
   (Exploitability Analyzer: verify package presence/version deterministically,
   exit early when clearly N/A; LLM reachability only when ambiguous).
   → OUR MAP: `repo_eval` parity/syntax/localization is the deterministic gate;
   LLM edit-reasoning only on genuinely ambiguous localization; **abstain/no-op
   when no edit site is reachable.** This is NVIDIA confirming our thesis.
2. **Role split with isolated phases** (Container Analyzer: web-research phase
   then filesystem phase, isolated) → our coder / analyzer / verifier split +
   context isolation (AgentTool, `nemo-relay instrument-context-isolation`).
3. **Filesystem = ground truth, not SBOM** → repo-as-ground-truth via `repo_eval`,
   not a drifting external summary.
4. **Precedence-ordered decision flowchart + recorded decision trace**
   (VEX Categorizer) → our submit/abstain gate as a FIXED decision tree with a
   recorded reasoning trace. The trace is training data (D3/D4).
5. **Verdict taxonomy** (NOT APPLICABLE / NOT REACHABLE / MITIGATED /
   CONDITIONALLY EXPLOITABLE / EXPLOITABLE) → our patch-confidence taxonomy:
   no-change-needed / can't-localize / localized-uncertain / verified-green,
   driving the abstain rule.
6. **On-disk cache, resumable** → our content-hash KV cache + persistent `repo_eval`.
7. **`nat eval` + benchmark dataset; "validation datasets are critical"**
   → our held-out eval discipline (never the 129).

## 3. BIGGER FIND — "NemoClaw for Agent Optimization" blueprint
"Find agent failures in agent traces, build task-specific evaluations, and
validate harness changes before shipping them." This is our EXACT dev loop:
trace the `swegemma` agent over the 129 → mine failures → build targeted evals →
validate prompt/LoRA/harness changes before the Dec 2 submission. Pairs with
`nemoclaw-user-guide` + `nemo-relay-*`. Use as the offline optimization harness.
(Other NemoClaw blueprints: Hermes Agent, OpenClaw, LangChain Deep Agents Code.)

## 4. Fit boundary (unchanged, restated)
Submission runtime is FIXED: vLLM TP=4 on 4×L4, gemma4 parsers, offline, YAML +
PEFT only, <3 GiB. NOTHING NVIDIA here ships inside the submission — no NeMo
Agent Toolkit, no NIMs, no Nemotron, no Relay binary, no Tavily, no crane, no
CUDA kernels. Everything above is DEV/TRAIN-TIME: instrument + optimize offline,
then distill the winning policy into the ADK YAML + E4B LoRA that actually ship.

## 4b. CUDA-X libs triage (cuVS / cuGraph / cuDF / cuOpt) — all train-time

- **cuVS** (GPU vector search): train-time only, largely redundant — comp ships
  `embeddings/*.npz` + `search_similar_code` built-in. Use ONLY to accelerate
  nearest-neighbor mining of D1/D5 localization training examples at scale.
- **cuGraph:** optional GPU accel for the PPR localization pass while GENERATING
  training data. Not shipped (inference uses built-in graph tools).
- **cuDF / cuML:** data-prep accel; same role as Curator. Train-time.
- **cuOpt — SKIP.** GPU combinatorial-optimization solver (routing/LP/MILP). No
  SWE-patch-resolution role; optimizing a ~5-call budget with it is over-eng.
- Nothing here ships: offline, fixed vLLM+YAML+PEFT. Train-time accelerators only.

## 4c. Per-tool skill packs (pull individually if the bundle missed one)
Curator, Data Designer, Gym, RL, Evaluator each ship their own `.claude/skills`.
The big bundle installed data-designer/nemo-rl/launch-nemo-rl/automodel/mbridge
but NOT Curator — pull `NVIDIA-NeMo/Curator/.claude/skills` directly if needed.

## 5. Next session, first moves
1. `nemo-relay-install` + `nemo-relay-get-started` → wrap a `swegemma eval`
   baseline over ~10 of the 129, read telemetry (tool-calls/task, localization
   misses, blind-retries, budget burn).
2. Read `nemoclaw-user-guide` → stand up the trace→eval→validate loop.
3. Fold the blueprint's deterministic-pretriage + decision-trace + verdict-
   taxonomy into LORA_TRAINING_DESIGN.md's reasoning schema (D3/D4) and the
   abstain gate.
