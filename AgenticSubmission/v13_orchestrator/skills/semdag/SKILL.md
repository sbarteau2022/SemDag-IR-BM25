---
name: semdag
description: Handle Python software issues in any repository through native prepare/finalize/status. This is the single root skill for all repository work; repository names are not skill names.
---

The tool name is run_skill_script. Outer skill_name is semdag; outer file_path is scripts/run.py. Use positional_args as an array of strings. Never put these fields inside args, use the repository name as skill_name, or supply a source filename as file_path. Do not use args or short_options in this preferred ABI.

Gemma4 native status call:
call:run_skill_script{skill_name:<|"|>semdag<|"|>,file_path:<|"|>scripts/run.py<|"|>,positional_args:[<|"|>status<|"|>]}
The SDK inserts its -- separator; action names below have no hyphens. String delimiters already quote values, so do not embed JSON quote characters.

Root positional forms: [prepare, WHOLE_ISSUE, REMAINING_SECONDS, SLOT]; [status, SLOT]; [finalize, HANDLE, SLOT]. All elements are strings. Prepare must succeed before dispatching an editor. Preserve the existing BM25-alternative second-editor and one-final-retry policy. Finalize performs outside and central checks; only ok true/state applied confirms application. Root cannot edit/view through editor actions.

Only run.py is an executable skill resource. Readable engine assets are not executable tool targets. Handles bind task, slot, file/span and source version. Wrong role, stale/cross-slot handle and malformed arity/type fail without mutation. Legacy explicit flag grammar remains for compatibility, but do not mix it with positional_args. Missing or wrong outer SDK fields are not repaired. E4B/budgets unchanged; this is not full host containment or automatic prevention of every premature dispatch/submit.
