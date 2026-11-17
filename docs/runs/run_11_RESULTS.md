# run_11 results: v6.1, 25 unseen public tasks, local MLX, no-network seatbelt

Run 2026-11-17 09:40–11:11 CST (17:11 UTC), 91 minutes. Preregistration: `run_11_PREREG.md` (committed before the run as `4e61288`). Evidence: **LIVE-MEASURED** (local MLX stand-in). Full report: `results/run_11_v6_1_seatbelt25/TELEMETRY.md`. Image: `gemma4-e4b-telemetry:run-11-v6-1` (Docker Desktop, 439 MB, base layers shared with `swebench-sandbox`).

## Result

**Resolved 1/25.** This is not a valid agent score: 15 of the 16 fastapi tasks could not be graded locally (see the environment defect below).

| Class | Tasks |
|---|---|
| test_env_broken | 15 (fastapi) |
| timeout | 3 (fastapi_11194, rich_3718, rich_3469) |
| right_file_wrong_function | 3 (rich_3942, 3777, 3470) |
| right_function_wrong_fix | 1 (rich_3480) |
| wrong_file | 1 (rich_3953) |
| no_patch | 1 (rich_4079) |
| resolved | 1 (rich_3905) |

On the 9 rich tasks: 1/9 resolved. For comparison, v6 resolved 4/9 rich tasks in run_10. Those were different tasks, so this is not a paired comparison.

## Environment defect found (local only)

- Every fastapi test log ends in `SystemError: The installed pydantic-core version (2.50.4) is incompatible with the current pydantic version, which requires 2.46.4`.
- Cause: the public wheel cache (`DataSets/public/data/wheels/`) ships `pydantic_core-2.46.4` only as **x86_64** wheels. The `swebench-sandbox` image built on this Mac is arm64, so pip resolved an arm64 pydantic-core 2.50.4 from PyPI at image build time.
- The scorer runs x86_64, so it is not affected.
- Locally it makes **all 67 fastapi tasks (52% of the public set) ungradable**, and the agent's own pytest calls fail the same way: 11 of 16 fastapi tasks show the error in a tool observation (`agent_saw_env_broken`).
- Fix options (owner decision): build the sandbox image for `linux/amd64` under emulation (slower), or add the arm64 `pydantic_core 2.46.4` wheel to a local wheel overlay (one download).

## Telemetry (all from `results/telemetry.sqlite`, run_id `run_11_v6_1`)

### Per task

- Duration median 217 s, p90 331 s.
- Steps median 20, max 44.
- Tool calls median 12, max 32.
- Peak context median 44%, max **99%** (fastapi_13207: 32,401 of 32,768 tokens).

### Per model call (419)

- TTFT p50 0.36 s, p90 0.78 s, max 4.67 s.
- Decode 51.2 tok/s p50.
- Finish reasons: 374 tool_calls, 44 stop, 1 length. The single length stop was the new 8,192-token cap, in fastapi_14262, which then timed out.

### Thinking

- Per step p50 210, p90 1,067, max 4,610 tokens.
- 1 of 412 steps went over the 4,096 budget. The scorer's vLLM would have cut that step; local MLX did not.

### Tools

- **`edit_file` failed 30 of 65.** 25 were "old_string not found", 4 non-unique matches, 1 a no-op.
- 12 of the 31 edits made by the `code_editor_agent` sub-agent failed, and 18 of the 34 made by the root agent.
- `run_command`: 17 of 35 returned `CommandError`. These are nonzero exits, mostly failing pytest runs, which the harness reports as errors. That is not a tool malfunction.
- Sub-agents: 27 `agent_tool` calls (code_editor 24, code_analyzer 3) containing 156 nested steps (max 12 per call). run_10 had 0 sub-agent calls.
- Graph tools: 10 `search_similar_code` calls, 1 `get_code_neighbors`.
- **0 of 25 tasks** wrote a reproduction to `/tmp` before editing. 0 destructive writes.

### Timing

Tasks that hit the 5-minute cap ended at 330–333 s, about 30 s past `max_time_minutes`. The 12-hour arithmetic should use 5.5 min per task, not 5.0 (worst case 120 × 5.5 = 660 min plus setup).

## Falsifier checks (all preregistered)

| Check | Result |
|---|---|
| Proxy calls vs harness `total_llm_calls` within 5% | 419 vs 412 (1.7%). **Pass.** |
| A trace for every task | 25/25. **Pass.** |
| Proxy completion tokens agree with trace step metrics | Every task without a timeout matches exactly. The 7 timed-out tasks each have exactly one extra proxy call: the in-flight generation the timeout cancelled, which never reached the trace. **Pass, with that explanation.** |
| External network blocked under the seatbelt | Profile probe: external HTTP refused (exit 7). During the run, LiteLLM's GitHub fetch failed with `Operation not permitted`. **Pass.** |

## Limits

Local MLX on Apple silicon, not L4/vLLM. No events compaction locally. Docker installs test deps the scorer lacks. One run, 25 tasks, no repeat seeds. These are failure modes, not leaderboard estimates.
