# Model Decision — E4B + multi-LoRA (locked)

**Date:** 2026-11-12. **Deadline:** Dec 2. **Decision:** build on
`gemma-4-e4b-it-qat-w4a16-ct`, not the 31B.

## Why E4B

1. **$10k smaller-model prize tier** — decisive. The 31B forfeits it.
2. **VRAM headroom → real multi-agent tree.** Single-model rule (HARNESS §3.2):
   all agents share one base model, so the win is *room*, not more models.
   E4B ~3–4 GB vs 31B ~16–18 GB across 4×L4 (96 GB) frees ~13 GB for KV cache
   and concurrent `ParallelAgent` branches that otherwise wouldn't fit under the
   32k context ceiling.
3. **Multi-LoRA specialization (§3.4).** Co-resident adapters routed per agent:
   `main_lora` (coder), `tool_lora` (read-only analyzer AgentTool), optional
   verifier adapter — all < 3 GiB total. This is the architecture design.md
   already assumes; E4B is what makes it affordable.

## What E4B does NOT buy (don't over-rotate)

- Subagents multiply **throughput + specialization**, NOT per-task reasoning
  budget. Each task is still one 32k window, one time/tool budget.
- Leverage comes from **context isolation**: cheap read-only analyzer agents
  (AgentTool, `skip_summarization: true`, §10.4) keep exploration tokens out of
  the coder's context; parallel branches test two localization hypotheses at once.
- Design the tree around context isolation, not "more agents."

## The 31B tradeoff we're accepting

- Leaderboard ~0.29 is almost certainly the **31B stock, no fine-tune**. We give
  up that free higher floor. We bet that E4B + trained adapters + a disciplined
  verify loop closes the gap AND wins the smaller-model tier.

## Corrections to fold into LORA_TRAINING_DESIGN.md

1. **Raise our `eval_config.yaml` budgets.** The sample's 1-min / 10-call cap is
   self-imposed, not the harness limit (ceiling: 60 min / 100 calls / 500 turns /
   32k ctx, §7.1). The deliberate reason→act→verify→re-reason loop needs that room.
2. **Don't rebuild the built-in code-intelligence tools.** `get_code_neighbors`,
   `search_similar_code`, `get_code_subgraph` (§6.3) are bound tools over the
   shipped `graphs/*.json` + `embeddings/*.npz`. Point `repo_eval` at what the
   built-ins can't do: parity check, syntax/type gates, and the persistent
   verify-after-every-edit verdict. That gate is the edge; raw localization is
   partly already provided.

## NVIDIA infra scan (2026-11-12) — what's usable

Submission runtime is FIXED (vLLM TP=4 on 4×L4, gemma4 parsers, offline, YAML
only). NVIDIA infra can't change what runs at judging; it helps at TRAIN time
and as orchestration patterns only.

- **NeMo Relay (`nemo_relay`) — USE IT, dev/train-time only, never ship.**
  Rust agent runtime (Apache-2.0, Python/Node/Go bindings) that wraps model+tool
  calls with observability + policy middleware. **Speaks Google ADK natively**
  (also Claude Code/Codex) — our submission IS an ADK tree, so Relay wraps our
  local `swegemma` runs with zero agent changes.
  - CANNOT ship: compiled binary, offline rule forbids it, and the harness owns
    the call layer (`CallbackRegistry` closed/host-only). Do not package it.
  - DO use it offline for: (1) grounded telemetry over the 129 tasks
    (tool-calls/task, localization misses, budget burn, blind-retry detection) =
    the baseline measurement layer; (2) prototype-enforce target behaviors via
    middleware (no-repeat-failed-action, budget gates, abstain rule), watch
    resolution_rate move, then distill the winning policy into prompts + LoRA;
    (3) capture full ATIF-style traces of accepted trajectories as D1/D4/D5
    training data.
  - Mental model: Relay = offline lab bench + trajectory recorder; ADK YAML +
    LoRA = the sealed product. Install: `pip install "nemo-relay[cli]"`.
  - (NeMo *Agent Toolkit* — different thing — is deprecated Oct 2026; ignore it.)
- **L4 has NO NVLink + forced TP=4 → tempers the multi-agent fan-out plan:**
  - TP all-reduce crosses PCIe (slower than NVLink) — wide `ParallelAgent`
    fan-out has real per-token latency cost.
  - Under TP, each GPU replica holds the FULL adapter footprint (adapters ×4);
    `--fully-sharded-loras` is off by default (only half the LoRA compute sharded).
  - For E4B this is still fine (r16 ≈ 110–220 MB → sub-GB ×4), BUT: keep adapter
    count modest (2–3: coder, analyzer, verifier), prefer sequential
    context-isolation (AgentTool analyzer) over heavy ParallelAgent fan-out, and
    benchmark `max_loras` / `max_cpu_loras` / TP on real L4s before assuming room.
  - Spend E4B's freed VRAM on KV cache / longer trajectories, NOT maximal concurrency.

## Submission shape (locked)

E4B base · multi-LoRA (coder + analyzer + verifier) · AgentTool read-only
analyzer for context isolation · `repo_eval` deterministic verify gate in a
LoopAgent · reason-first → temp-0 execute · no-blind-retry dynamic iteration ·
native memory.md.
