# Preregistration: Frontier Loop Small-Model Coding

- Date: 2026-11-15
- Model: gemma-4-e4b-it-qat-w4a16-ct only.
- Baseline: AgenticSubmission/v6_impact on paired dev tasks.
- Intervention: Viewer/Editor decomposition + edit-format GRPO LoRA (if training data available) + dense reward shaping.
- Primary metric: resolved rate on held-out dev tasks, paired by instance_id, same sampling (temp 0.2, top_p 0.95, 4096 max).
- Pre-registered failure criteria: no +2pp gain on first 10 tasks; revert.
- Tools only harness nine; no internet at runtime.
- Evidence stored in results/ with traces.
