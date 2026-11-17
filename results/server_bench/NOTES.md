# Local server bench: rapid-mlx 1.0.0 vs mlx_lm.server 0.32.2 (2026-11-17)

Same checkpoint (`~/models/gemma-4-e4b-it-qat-w4a16-mlx`), same no-network seatbelt, same `Tools/telemetry/check_proxy_equivalence.py`. Evidence: **LIVE-MEASURED**, short prompts only.

| Server | Mode | Output | Decode tok/s | TTFT | Equivalence (direct vs proxied) |
|---|---|---|---|---|---|
| mlx_lm.server 0.32.2 | default | coherent, with reasoning | 58–60 | 0.07 s | 2/2 MATCH |
| rapid-mlx 1.0.0 | `--no-mllm` (text-only) | **garbage**: multilingual token soup to the length limit. The log reports `weights=0.5GB` for a ~10 GB checkpoint, so the weights are not loaded correctly. | 64 | 0.04 s | content differs |
| rapid-mlx 1.0.0 | MLLM (default) | coherent, but **no reasoning**: thinking is off unless requested (`--default-reasoning-effort` or per-request `enable_thinking`) | 62 | 0.07 s | 1/2 MATCH (tool-call case differs; not yet diagnosed) |

| oMLX 0.7.0 | `serve --model-dir` (symlink to the E4B checkpoint) | coherent; thinking honoured per request (`reasoning_content`) | 59–60 | 0.08 s | **2/2 MATCH** |

oMLX extra measurements (same checkpoint, stdlib client):
- 600-token generation: 59–60 tok/s, with thinking on or off.
- 16,005-token prompt: 4.2 s total (≈3,800 tok/s prompt processing), correct answer.
- 4 concurrent requests: 136 tok/s aggregate (2.3× a single stream).

The harness sends `extra_body.chat_template_kwargs.enable_thinking` and `thinking_token_budget` on every request (proxy log: 4096 planner, 1024 executor, none for the thinking-off auditor), so per-request thinking is what matters. A server default is not needed.

## Conclusions

- A single stream on this Mac decodes at about 60 tok/s on either server. The limit is memory bandwidth, so changing server does not close the gap to the scorer's estimated ~100 tok/s on 4×L4 (estimate, not measured).
- rapid-mlx's advantage is continuous batching (parallel roles) and prefix caching. It needs MLLM mode, a thinking default, and a passing equivalence check before any run uses it.
- **oMLX passes:** equivalence 2/2, per-request thinking, a 16k prompt, and continuous batching (2.3× aggregate with 4 streams). It is usable as `SERVER=omlx`; parallel brigade roles can be exercised locally with it.
- No local server changes single-stream speed (about 60 tok/s on all three).
- Runner default stays `SERVER=mlx_lm` until the owner picks. `SERVER=rapid` remains unverified.
