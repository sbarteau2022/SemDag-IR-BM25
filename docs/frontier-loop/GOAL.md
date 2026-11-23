# Frontier Goal: validate every model implementation top-to-bottom and run the merged one

Owner: autonomous agent. One objective: confirm each submission under `AgenticSubmission/` is structurally valid, identify the canonical merged entry (`v12_merged` = v11 hardening + v6 tools/sub-agents), and run it on a 3-task SWE slice to capture traces (fails + tool calls + issues).

Scope order (top -> bottom = v0 -> v12):

1. v0_baseline, v1_brigade, v2_bm25, v3_attack, v4_semdag, v5_loop_e4b,
   v6_impact, v6_1_budget, v7_brigade_lite, v8_ensemble, v9_recurrent,
   v10_edit_rescue, v11_task_ir, v12_merged.
2. Gate for each: adk_submission validate_directory (limits from swegemma.config.build_submission_limits()[0]).
   Record per-version status, fatal errors, and tool set.
3. Gate the merged entry alone: all authorized tools present, eval_config defaults,
   adapters dir absent (no adapter yet — placeholders), prompts !include resolve.
4. Bring up the local model (vllm-metal 8124) and telemetry proxy (8125) if not already,
   then run v12_merged on a 3-task slice of DataSets/swe_traj_v1/data/test_ood.jsonl
   (or, failing that, the 129-task public set via Tools/run_eval_seatbelt.sh).
5. Capture telemetry into out/frontier-loop/YYYYMMDD-traces/ and a summary .json (fails, tool calls, issues).

Deferred until the adapter exists (not in this goal): LoRA training on L4x4.

## Exit criteria (all must hold, each with a receipt)

- Every version's validation status recorded in docs/frontier-loop/VALIDATION.md.
- v12_merged validation passes with 0 fatals.
- A trace artifact written (3+ tasks) OR a dated, filed blocker in BLOCKERS.md explaining why hardware could not be reached.
- CLAIMS_REGISTER updated with the loop result.
