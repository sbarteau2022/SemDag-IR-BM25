---
name: semdag
description: Edit small exact fragments of assigned Python source in fixed slot 2, preserving surrounding code. No shell, preparation or finalization.
---

Load this skill, then get the authoritative assignment using run_skill_script: OUTER skill_name semdag, file_path scripts/run.py, positional_args [status]. Fields must be outer fields and positional_args must be an array of strings. Repository source filenames are not executable skill programs.

## Exact fragment edit

Status/view returns replace_execution containing skill_name semdag, file_path scripts/replace.py, positional_args [CURRENT_HANDLE]. Append EXACT_OLD_TEXT and replacement code line(s). No action verb. Old text is one literal source fragment, no numbered prefix, matching exactly once within the current view; maximum16 lines/2048 characters. Replacement elements join with LF. Preserve all spaces/indentation; an explicit empty replacement deletes the fragment. No quote unescape, fuzzy match, autoindent, guessed fields or generated fix. Unrelated source is copied natively, so do not reproduce headers/docstrings for a small change.

The handle is single-use and binds task/slot/file/span/source version. Static slot is 2. A new view/edit invalidates the old handle. Syntax/import/scope/source-hash checks run before atomic private write. Root independently verifies and applies later. Use scripts/run.py [view, START_LINE, END_LINE] to narrow ambiguous/truncated source, then copy the new replace_execution. Outside-assignment context is readonly and grants no edit handle. If unprepared, stop EDIT_FAILED; root must prepare. If the real fix is outside your assignment, return the precise symbol/file address and evidence, not a symptom-only guard.

Only run.py and replace.py are executable here. Engine assets are readable dependencies, not executable tool targets. Root has no replace.py. Whole-view edit/edit_lines forms remain for compatibility but require the full selected source including any function header; prefer exact fragment edits. Missing SDK fields are never repaired. E4B, default budgets, no-network/source isolation and root finalization are unchanged. Return EDIT_READY new handle after accepted private edit, never claim verification passed.
