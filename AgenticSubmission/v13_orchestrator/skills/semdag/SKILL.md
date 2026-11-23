---
name: semdag
description: Native managed edit workflow. Use scripts/run.py; static role authorizes only prepare/finalize/status.
---

Every native call is run_skill_script with three keys: skill_name "semdag", file_path "scripts/run.py", args as a list of strings. Do not use a shell, positional_args, helper paths or a different skill name. Engine assets are readable dependencies, not executable skill scripts.

Root actions:
- ["--prepare", WHOLE_ISSUE, "--remaining", SECONDS_FROM_GET_STATUS, "--slot", "1"]
- ["--status", "--slot", SLOT]
- ["--finalize", HANDLE, "--slot", SLOT]
Root cannot edit or view through editor actions. Prepare returns the numbered view and handle; pass these to the editor. Prepare slot 2 only for the existing BM25-alternative condition. Only successful finalization verifies/applies a candidate. Keep the existing one-final-retry rule.

Handles bind task, slot, file, span and source version. Never reuse old handles. Wrong-role actions, stale or unknown handles and off-assignment edits fail without mutation. Required official tool-envelope keys remain mandatory. E4B and four-minute/default-token budgets are unchanged. These action checks do not prevent every premature delegation/submit or establish full host confinement.
