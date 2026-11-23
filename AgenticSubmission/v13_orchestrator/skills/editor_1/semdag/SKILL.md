---
name: semdag
description: Native managed edit workflow. Use scripts/run.py; static role authorizes only view/edit/status.
---

Every native call is run_skill_script with three keys: skill_name "semdag", file_path "scripts/run.py", args as a list of strings. Do not use a shell, positional_args, helper paths or a different skill name. Engine assets are readable dependencies, not executable skill scripts.

Editor actions (fixed slot 1):
- ["--status"] gets your prepared assignment, handle and numbered view; unprepared means stop and report EDIT_FAILED.
- ["--view", HANDLE, "--lines", "A-B"] narrows within your assignment and returns a new handle.
- ["--edit", HANDLE, "--text", REPLACEMENT] replaces exactly that view and returns a new handle.
Do not prepare, finalize, change roles or access another slot. Return EDIT_READY NEW_HANDLE after an edit, or EDIT_FAILED with the exact error. The root performs verification and finalization. Edit success alone is not test success.

Handles bind task, slot, file, span and source version. Never reuse old handles. Wrong-role actions, stale or unknown handles and off-assignment edits fail without mutation. Required official tool-envelope keys remain mandatory. E4B and four-minute/default-token budgets are unchanged. These action checks do not prevent every premature delegation/submit or establish full host confinement.


Exact status-call JSON (passed to the tool named run_skill_script):
{"skill_name":"semdag","file_path":"scripts/run.py","args":["--status"]}
Use one layer of JSON string delimiters; the values do not contain extra quote characters. args may also be a dictionary of long-option names without hyphens and their explicit values. A complete JSON string array serialized as one argument is accepted by native code; missing outer skill_name/file_path fields, quoted skill names, unknown actions and wrong roles are not repaired.
