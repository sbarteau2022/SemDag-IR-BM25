# ADR-004: Diagnose wire protocol before changing agent behavior

Status: Accepted within owner-authorized workflow diagnosis.

Decision: optional exact-byte local request capture in the existing telemetry proxy, off by default; raw completion/chat comparison and unmodified installed parser replay. No SDK or model-output adapter changes. Capture bodies only, owner-readable local files, no headers, no research ingestion/publication of task content. Unit tests verify unchanged request/response behavior and byte-exact capture. Same model, task, roles and budgets for diagnostic E4B run.

Evidence so far: local CT/MLX templates match; actual SDK args.anyOf renders an empty native type; both fixed-call raw/chat probes agree and produce correct status arguments. That rules out a universal parser failure on the probe, not the complete task context. Capture the real context before attributing failures to the model, parser or schema. Existing sources and negative receipts remain.

Alternative: strip quotes/fill missing fields after generation. Rejected: invents/corrects intent outside the agent and changes scorer behavior. Prompt changes alone without raw evidence do not localize the fault.
