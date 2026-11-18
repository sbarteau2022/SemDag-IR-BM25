# run_21 results: v8 ensemble, one task end to end (vllm-metal, `<|think|>`, edit.py isolation)

Status: **LIVE-MEASURED**, one task. Commit `4a4b02f`.
- Setup: vllm-metal 0.33 with the scorer's flags, subprocess sandbox under seatbelt, no Docker. The task is rich_3468.
- Raw files: `results/run_21_v8_one/`. Finished 2026-11-18T15:51:46Z.

## Outcome

**Not resolved: 4-minute timeout** (241.8 s, 17 harness tool calls). As in run_20, only stage 1 ran.

- Implementer activity: implementer_1 13–161 s, implementer_2 11–231 s, implementer_3 12–60 s, implementer_4 13–168 s.
- No adversary, coordinator or final-implementer call happened.
- **Isolation held:** 0 edits to the main workspace (`edit_file` was removed). No implementer reached `edit.py` either.

## Why stage 1 used the whole budget

1. **Tool-call argument errors on the first try, in 4/4 implementers.** The model:
   - omitted `skill_name` (harness error: "Argument 'skill_name' is required");
   - wrapped values in literal quotes (`"\"semdag\""` gives SKILL_NOT_FOUND; `"\"3\""`);
   - nested the args list (`[["\"3\"", ...]]`);
   - dropped its implementer number.

   Implementers made 2–4 `fork.py` calls before getting a copy, and one called `list_skills`.
2. **Long thinking per call.** With `<|think|>` and no thinking budget, single calls produced up to 2,028 completion tokens (9,167 reasoning characters). Three calls exceeded 1,300 tokens.
3. **vllm-metal ran slower than in the bench on real prompts.** Under four concurrent streams with 3k–10k-token prompts, decode averaged **19.4 tok/s per call**. The bench measured 50.8 tok/s per stream on short prompts, and run_20 on oMLX averaged 37.3 tok/s. TTFT averaged 0.94 s. 23 model calls, 0 errors, 0 `finish_reason=length`.

## Fixes this points to (not built)

- **Arguments:** make every v8 script accept sloppy arguments: nested lists, quoted values, and a missing `k` (fork assigns the next free copy and returns the number). The harness-level `skill_name` errors need the prompt to show one literal call shape with no quotes inside values.
- **Server:** on this Mac, oMLX is faster than vllm-metal for this workload. vllm-metal stays the parity reference for request handling, not for speed.
- **Stage 1 time:** stage 1 alone exceeds 4 minutes locally in 6/6 ensemble tasks (run_20 + run_21). The local evidence says 4 parallel implementers do not fit. L4 throughput is still unmeasured.

## Limitations

One task, one seed, on a local stand-in. Diagnostic only.
