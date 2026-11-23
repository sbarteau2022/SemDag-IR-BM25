---
name: semdag
description: Edit assigned Python source in your fixed slot for any repository. This is your single editor skill; no prepare/finalize or shell access.
---

The tool name is run_skill_script. Outer skill_name is semdag; outer file_path is scripts/run.py. Use positional_args as an array of strings. Never put these fields inside args, use the repository name as skill_name, or supply a source filename as file_path. Do not use args or short_options in this preferred ABI.

Gemma4 native status call:
call:run_skill_script{skill_name:<|"|>semdag<|"|>,file_path:<|"|>scripts/run.py<|"|>,positional_args:[<|"|>status<|"|>]}
The SDK inserts its -- separator; action names below have no hyphens. String delimiters already quote values, so do not embed JSON quote characters.

Editor 2 positional forms: [status]; [view, HANDLE, A-B]; [edit, HANDLE, REPLACEMENT_CODE]. All elements are strings. Your slot is fixed to 2. An unprepared status is terminal EDIT_FAILED. Do not prepare/finalize or access another slot. Return EDIT_READY NEW_HANDLE after successful edit, never claim tests passed; root finalizes.

Only run.py is an executable skill resource. Readable engine assets are not executable tool targets. Handles bind task, slot, file/span and source version. Wrong role, stale/cross-slot handle and malformed arity/type fail without mutation. Legacy explicit flag grammar remains for compatibility, but do not mix it with positional_args. Missing or wrong outer SDK fields are not repaired. E4B/budgets unchanged; this is not full host containment or automatic prevention of every premature dispatch/submit.
