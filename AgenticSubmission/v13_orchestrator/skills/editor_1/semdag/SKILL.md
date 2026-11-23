---
name: semdag
description: Edit assigned Python source in your fixed slot for any repository. This is your single editor skill; no prepare/finalize or shell access.
---

The tool name is run_skill_script. Outer skill_name is semdag; outer file_path is scripts/run.py. Use positional_args as an array of strings. Never put these fields inside args, use the repository name as skill_name, or supply a source filename as file_path. Do not use args or short_options in this preferred ABI.

Gemma4 native status call:
call:run_skill_script{skill_name:<|"|>semdag<|"|>,file_path:<|"|>scripts/run.py<|"|>,positional_args:[<|"|>status<|"|>]}
The SDK inserts its -- separator; action names below have no hyphens. String delimiters already quote values, so do not embed JSON quote characters.

Editor 1 positional forms: [status]; [view, START_LINE, END_LINE]; [edit_lines, HANDLE, CODE_LINE_1, CODE_LINE_2, ...]. All elements are strings. Your slot is fixed to 1. An unprepared status is terminal EDIT_FAILED. Do not prepare/finalize or access another slot. Return EDIT_READY NEW_HANDLE after successful edit, never claim tests passed; root finalizes.

Only run.py is an executable skill resource. Readable engine assets are not executable tool targets. Handles bind task, slot, file/span and source version. Wrong role, stale/cross-slot handle and malformed arity/type fail without mutation. Legacy explicit flag grammar remains for compatibility, but do not mix it with positional_args. Missing or wrong outer SDK fields are not repaired. E4B/budgets unchanged; this is not full host containment or automatic prevention of every premature dispatch/submit.


Each preparation has independent cached source/anchor/check metadata. Verification uses that transaction's metadata. BM25 guesses retain the whole function rather than forcing a speculative loop line. Root can re-prepare an unchanged assignment with an evidence-backed narrower query; pending edits are never discarded. All prior handles are revoked by a durable generation marker. Editors should narrow to a complete statement/block before replacement and preserve function headers if replacing a whole function. Python compilation, not just AST parsing, must accept a candidate before any source write.


Native clock: preferred prepare takes query and slot only. It derives a conservative remaining time from the harness-created baseline commit timestamp and never exceeds four minutes; missing/expired/future anchors fail. The older explicit-remaining form remains accepted and is capped when an anchor exists. No SDK outer argument is inferred.

Read-only view may use the current assignment and numeric range, without copying a handle; it returns a NEW handle. Writes always need an explicit current handle. For edit_lines, positional_args elements are action, handle, then each actual replacement code line. Copy the real edit_prefix array returned by status/view and append code line elements; preserve spaces. Do not pack commands with commas or use literal backslash-n escapes. Unambiguous numeric read packets are supported, but packed writes are rejected rather than split or repaired. Optional explicit edit ranges must equal the issued view; they do not silently narrow it.

View responses contain a JSON metadata header then ---BEGIN V13 SOURCE--- / ---END V13 SOURCE--- around raw numbered Python lines. Source is not a JSON string to copy/unescape. Editors must read native status/view, not parent-regenerated code. Use only the code portion (no line numbers) in edit_lines; Python single-quoted messages can avoid unnecessary transport quote escaping. Native operation failures exit nonzero and emit structured stderr; success alone is not hidden-test success.
