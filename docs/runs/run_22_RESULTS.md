# run_22 results: v8 with the lead going first, one task (oMLX)

Status: **LIVE-MEASURED**, one task. Commit `f1d2baf` (4 adversaries; the single-adversary change came after this run).
- Setup: rich_3468, subprocess sandbox under seatbelt, no Docker. Raw files: `results/run_22_v8_lead/`.
- Server provenance: the runner reused the oMLX instance from the `<|think|>` check. It had been started under `no_network.sb` with the runner's flags, except its SSD cache directory.
- 36 model calls, 0 errors, 0 `finish_reason=length`. Decode 42.0 tok/s, mean TTFT 1.39 s, peak prompt 12,711 tokens.

## Outcome

**Not resolved: 4-minute timeout** (241.7 s, 26 harness tool calls). Stage timeline:

| agent | active (s) | what it did |
|---|---|---|
| lead | 3–28 | 1 `plan.py` call, then 4 ASSIGN lines |
| implementer_1 | 37–234 | 6 identical `run_skill_script` calls, all rejected by the harness: `file_path` placed inside `args` ("Argument 'file_path' is required") |
| implementer_2 | 37–137 | 3 reads, 5 `edit.py`, 1 command |
| implementer_3 | 62–166 | 1 read, 5 `edit.py`, 1 audit |
| implementer_4 | 40–217 | 2 reads, 2 `edit.py`, 1 command, 2 audits |
| adversaries, finalizer | — | never started |

## Findings

1. **Lead-first works mechanically.** The lead finished in 28 s, and the implementers started already assigned, with copies made and no setup calls. They now reach `edit.py` and `audit.py`, which they never did in run_20 or run_21.
2. **Localization is the weak point.** All four assignments pointed at the wrong code: `traceback.safe_str`, `pretty.BrokenRepr.__repr__`, `_win32_console`, and so on. Rich's BrokenPipe handling belongs in the console write path. The plan's ranked sites were off, and the lead built on them.
3. **Harness-level argument shape still costs whole implementers.** implementer_1 repeated one malformed call 6 times. That error happens before our script runs, so only the prompt (an exact call shape) or a different tool can fix it.
4. **Stage 1 still ends at about 234 s**, so the adversary and the final implementer never run inside 4 minutes locally (7/7 ensemble tasks so far).

## Changes since this run

- The adversarial stage is now **one** agent (owner correction): `review_pack.py` with no args shows all candidates, and up to 3 counterexamples are saved in total. Rebuilt; suite 117 passed.
