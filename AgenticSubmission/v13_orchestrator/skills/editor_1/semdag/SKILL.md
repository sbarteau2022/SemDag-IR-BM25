---
name: semdag
description: Edit assigned Python source in your fixed slot for any repository. This is your single editor skill; no prepare/finalize or shell access.
---

The tool name is run_skill_script. Outer skill_name is semdag; outer file_path is scripts/run.py. Use positional_args as an array of strings. Never put these fields inside args, use the repository name as skill_name, or supply a source filename as file_path. Do not use args or short_options in this preferred ABI.

Gemma4 native status call:
call:run_skill_script{skill_name:<|"|>semdag<|"|>,file_path:<|"|>scripts/run.py<|"|>,positional_args:[<|"|>status<|"|>]}
The SDK inserts its -- separator; action names below have no hyphens. String delimiters already quote values, so do not embed JSON quote characters.

Editor 1 positional forms: [status]; [view, HANDLE, A-B]; [edit, HANDLE, REPLACEMENT_CODE]. All elements are strings. Your slot is fixed to 1. An unprepared status is terminal EDIT_FAILED. Do not prepare/finalize or access another slot. Return EDIT_READY NEW_HANDLE after successful edit, never claim tests passed; root finalizes.

Only run.py is an executable skill resource. Readable engine assets are not executable tool targets. Handles bind task, slot, file/span and source version. Wrong role, stale/cross-slot handle and malformed arity/type fail without mutation. Legacy explicit flag grammar remains for compatibility, but do not mix it with positional_args. Missing or wrong outer SDK fields are not repaired. E4B/budgets unchanged; this is not full host containment or automatic prevention of every premature dispatch/submit.


Each preparation has independent cached source/anchor/check metadata. Verification uses that transaction's metadata. BM25 guesses retain the whole function rather than forcing a speculative loop line. Root can re-prepare an unchanged assignment with an evidence-backed narrower query; pending edits are never discarded. All prior handles are revoked by a durable generation marker. Editors should narrow to a complete statement/block before replacement and preserve function headers if replacing a whole function. Python compilation, not just AST parsing, must accept a candidate before any source write.
