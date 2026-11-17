# run_13 (FAILED, wiring): v7 requests lane

2026-11-17 20:04 UTC. All 30 model calls returned HTTP 400 from `mlx_lm.server`: `{"error": "top_k must be of type int"}`. ADK's `GenerateContentConfig` serializes `top_k: 64` as `64.0`. No agent step ran (5 tasks, 0 tool calls), so the run measures nothing about the agent and is kept in the failure ledger only.

Fix: `top_k` removed from `configs/sampling_think.yaml`; the model default (64) applies on vLLM. Rerun as run_14 with the same preregistration (`lanes_PREREG.md`).

The telemetry did its job: the proxy recorded every 400 with its body, which made the failure obvious within one minute.
