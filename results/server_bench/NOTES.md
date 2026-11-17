# Local server bench: rapid-mlx 1.0.0 vs mlx_lm.server 0.32.2 (2026-11-17)

Same checkpoint (`~/models/gemma-4-e4b-it-qat-w4a16-mlx`), same no-network seatbelt, same `Tools/telemetry/check_proxy_equivalence.py`. Evidence: **LIVE-MEASURED**, short prompts only.

| Server | Mode | Output | Decode tok/s | TTFT | Equivalence (direct vs proxied) |
|---|---|---|---|---|---|
| mlx_lm.server 0.32.2 | default | coherent, with reasoning | 58–60 | 0.07 s | 2/2 MATCH |
| rapid-mlx 1.0.0 | `--no-mllm` (text-only) | **garbage**: multilingual token soup to the length limit. The log reports `weights=0.5GB` for a ~10 GB checkpoint, so the weights are not loaded correctly. | 64 | 0.04 s | content differs |
| rapid-mlx 1.0.0 | MLLM (default) | coherent, but **no reasoning**: thinking is off unless requested (`--default-reasoning-effort` or per-request `enable_thinking`) | 62 | 0.07 s | 1/2 MATCH (tool-call case differs; not yet diagnosed) |

## Conclusions

- A single stream on this Mac decodes at about 60 tok/s on either server. The limit is memory bandwidth, so changing server does not close the gap to the scorer's estimated ~100 tok/s on 4×L4 (estimate, not measured).
- rapid-mlx's advantage is continuous batching (parallel roles) and prefix caching. It needs MLLM mode, a thinking default, and a passing equivalence check before any run uses it.
- Runner default stays `SERVER=mlx_lm`. `SERVER=rapid` is available but unverified.
