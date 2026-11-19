# v10_edit_rescue: v9_recurrent with a repaired edit path

Started 2026-11-19 from a copy of `v9_recurrent` (whose README describes the graph and tooling; this
folder keeps those scripts and adds the changes below). Motivation: in run_24 (v9, 2 rich tasks)
6 of 9 main-agent and sub-agent `edit_file` calls failed, `fix_edit.py` was never called and the
`code_editor_agent` sub-agent spent about 67 s of a 240 s budget returning a guessed anchor. Audit:
`docs/audit_2026-11-19.md`.

## Changes against v9_recurrent

- `prompts/system.md`: the root agent edits itself (no mandatory Viewer -> Editor hand-off); after a
  successful edit the next `old_string` must come from the returned diff or a fresh read; after any
  `edit_file` error the next call must be `fix_edit.py` with the same three values; short working
  principles (think first, simplicity, surgical changes, goal-driven checks); `flow` is now part of locate.
- `prompts/editor.md` and `sub_agents/code_editor.yaml`: the editor is a last resort, has the `semdag`
  skill (v9's editor had no skill, so its prompt's fix_edit instruction could not be followed), edits by
  line range through `fix_edit.py` instead of re-typing anchors, and must end with one `EDIT_OK` /
  `EDIT_FAILED` line. The stray `EOF` line at the end of v9's editor prompt is gone.
- `skills/semdag/scripts/fix_edit.py`: a candidate block grows to the whole bracketed statement (a
  one-line match such as `frame = Frame(` now shows and replaces the whole call); `stale: true` when
  old_string is the pre-edit text of the baseline file; `already_edited` on a block that holds an earlier
  edit of this session; an `old_string` with doubled backslashes or a pasted read_file JSON tail is cleaned
  and applied when the cleaned text matches once (run_25 httpx_3672); `reindent` also moves text left.
- `skills/semdag/scripts/repo_eval.py`: locate adds `flow` for the top two ranked sites (loops, carried
  variables, exits, recursion, callers), capped at 1,300 characters so locate stays under the harness's
  5,000-character skill stdout cap.

Tests: `tests/test_v10_edit_rescue.py`. Smoke: `docs/runs/run_25_RESULTS.md` (1/3; run before the last two fixes above).
