# CHECKPOINT — LoRA render gate (2026-11-12)

> **Status 2026-11-17: DEMOTED** to an auxiliary/ablation pool. Do not train the submission adapter on it. See `Designs/LORA_TRAINING_DESIGN.md` banner and `Designs/FAILURE_DRIVEN_DATASET.md`.

## Objective
Build the raw->final renderer for the E4B LoRA dataset: Gemma-4 chat template, `enable_thinking=true`,
`preserve_thinking=true`, assistant-only loss masking, with every row gated (schema, contamination,
split law, dedup, near-dup, caps, verifier re-check) before it is rendered.

## Verified this session
- **`LoRAData/gen/render.py` written and working** (CLI: `run` | `selftest`, flags `--families
  --limit --out --no-sandbox --no-near-dup --no-preserve-thinking --repo-cap --unit-cap
  --max-tokens --dump`).
- **selftest passes** (`render.py selftest`): parallel tool calls, a `train:false` turn, tools block.
  Proves opener masked, tool responses masked, wrong turn masked, trainable turns all target.
- **Full run**: 7147 raw -> **6874 final** (train 4688 / dev 849 / test 1337), 6.09M tokens,
  1.39M targets, target ratio 0.2284, len p50 735 / p95 2163 / max 3440. 9.4 s.
- **`LoRAData/final/audit_final.py` passes**: 0 unit-cap violations (max group exactly 40), 0
  repo-cap breaches, **0 real tasks spanning splits**, 0 mask violations over all 6874 rows,
  0 duplicate ids/texts, 0 mask breaches on 1719 sampled rows.
- `preserve_thinking` passed as a real flag (the default-false trap is avoided and recorded).
- `parse_spec` round-trip: all 1920 synth specs parse and every answer re-derives exactly.
  Fixed `arrows` `(no dependencies)` handling; full re-check now passes with 0 rejects.
- **`gen/g_py.py` was broken on disk** (process() body over-indented, unparseable). Repaired by
  dedent; verified by import + `full()`/`process()` identity. The `raw_py.jsonl` on disk predates
  the breakage and is unaffected.

## Bugs found and fixed in the render gate (each one silently wrong before)
1. `render_row` used the **full prefix text** as the turn delta -> opener never matched -> opener
   was left as a training target. Now uses `full[a:b]`.
2. `near_dup_drops` returned **row indices** but the caller filtered on ids -> the near-dup gate
   dropped nothing while reporting 96 drops. Now returns ids; 96 rows actually drop.
3. `check_synth_dag` passed the **forward** deps map to `kahn` (which wants dep->dependent) ->
   KeyError on cyclic-adjacent rows. Now builds the reverse adjacency like `build_order`.
4. `char_span` straddle check is correct; the selftest's own span usage was wrong (1-char span
   ending mid-token), fixed to anchor on the opener literal.
5. Receipt gates were mislabelled (`after_exact_dedup` held the post-near-dup count). Now each
   stage is named for what it is: loaded / schema / dedup / near-dup / verify / caps / rendered.

## Decisions (with the reason)
- **Canonical split = `source.task_split`**, verified against `split_map(load_tasks())`.
  `split:row_level_reassigned: 2343` rows had a function/line/node-level split that disagreed with
  their task — those are now re-split, so no task crosses a boundary.
- **Near-dup leakage rule**: within a cluster, test/dev wins and the train copy is dropped, so a
  near-duplicate cannot straddle the boundary. 40 straddling clusters found and resolved this way.
- **Synthetic rows** keep their rng-seeded split (they share no task); the receipt records that
  `task=="synthetic"` spans splits by design and the near-dup gate covers them globally.
- **IDs synthesized** for every tool call (`call_<msg>_<j>`) + matching `tool_call_id`: the template
  resolves a response's name by `id == tool_call_id`, and with no ids every response resolves to the
  first call — wrong for the parallel family. Not rendered, so single-call output is unchanged.

## Known gap (reported, not fixed)
- **`exec` and `pyedit` are train-only** (33 + 46 rows; 0 dev, 0 test). Cause: all 102 `py` rows
  come from 12 tasks that are all train-split, because `build_family.py` feeds train-split snapshots
  first and `g_py`'s global function-hash dedup lets them claim every pure function. So dev/test
  cannot estimate the deepest-Python capabilities. Fix = widen `py` (next step already planned).
- **Execution re-checks skipped on darwin**: `gen/sandbox.py`'s preexec hardening (`os.setsid`,
  `RLIMIT_AS`) is not permitted on this Mac, recorded in `receipt.settings.platform_note`. The 102
  exec-backed rows therefore carry stored labels un-re-executed; graph/ir/synth/edit rows (7012)
  are all re-verified by recomputation with 0 rejects.
- `topo`/`layers` still produce 0 rows (cyclic neighborhoods; needs SCC condensation).
- Parallel tool-call trajectories: 0 rows exist yet (the selftest proves the render path works).

## Files
- `LoRAData/gen/render.py` — the gate + masker (~1190 lines)
- `LoRAData/final/{train,dev,test}.jsonl` — trainer-lean rows (id, split, family, subtype, repo,
  task, path, unit, source, text, input_ids, labels, n_tokens, n_targets)
- `LoRAData/final/receipt.json` — settings, env (sha256 of template+tokenizer), gate counts,
  rejects, token stats, per-family, repo shares
- `LoRAData/final/manifest.json` — row catalog
- `LoRAData/final/audit_final.py` — independent audit of the written files
- `LoRAData/gen/g_py.py` — repaired (was unparseable)
- `LoRAData/gen/g_synth.py` — `parse_spec` implemented (round-trip verified)

## Next step
1. Widen `py` past 102 rows so exec/pyedit appear in dev/test too (closure filter + per-split quota).
2. New families: `g_tactic.py` (counterfactual), parallel tool calls in `g_agent`, `g_struct.py`
   (pure-AST), `g_rev.py` (tests_to_impl), `g_triage.py` (both readings), `topo`/`layers` via SCC.
3. Re-run `render.py`, then re-run `audit_final.py` and paste both receipts.
