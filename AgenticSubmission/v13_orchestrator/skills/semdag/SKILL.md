---
name: semdag
description: Typed task IR for /workspace. Locates the lines to edit for an issue from the issue's own traceback, literals and names, edits by line range, and blocks a patch that misses the located span.
---


## v13 managed execution

Use `run_skill_script` with all required keys: `skill_name: "semdag"`, `file_path: "scripts/edit_tx.py"`, and `args` as a list of strings. This script cannot repair an invalid official tool envelope. Do not use `positional_args` or execute skill paths with run_command.

- Prepare: args `["--prepare", ISSUE, "--remaining", SECONDS_FROM_GET_STATUS, "--slot", "1"]`. Localizes, runs the baseline check with its real exit status, creates an independent slot and returns a numbered view, edit handle, alternatives and remaining time. Slot 2 selects the first distinct BM25 alternative when one exists; otherwise it refuses.
- Edit: args `["--edit", HANDLE, "--slot", SLOT, "--text", REPLACEMENT]`. Replaces exactly that view; requires matching file/slot/source version and valid Python/imports. Returns a fresh handle and compact diff. Old handles cannot be replayed. Only replace source you have seen.
- Narrow/read: args `["--view", HANDLE, "--slot", SLOT, "--lines", "A-B"]`. Must stay inside the assignment. A truncated view must be narrowed before editing.
- Finalize (orchestrator): args `["--finalize", HANDLE, "--slot", SLOT]`. Checks unchanged central base and scope, tests an independent copy of central with the candidate overlaid, then atomically applies and runs central checks and diff analysis. Outside failure does not apply; central failure rolls back only bytes still belonging to this transaction. A competing write is preserved and reported as failure.

`ok:true` from edit means an edit applied in the slot, not that task tests passed. Only finalization's `ok:true,state:applied,clean:true` establishes the native apply/check gate. The official hidden tests still determine task success.

Legacy workspace_mgr spawn/apply route through the transaction guards. `fix_edit.py` can still read numbered ranges in managed slots and returns the current handle. Managed range writes without a handle are refused because coordinates alone cannot prove which version the caller read. Unmanaged source helpers remain available for comparison. No new model API or harness tool is added.

State and verification copies live in the sandbox temporary directory. These helpers guard their own paths; run_command and model agent_tool calls remain broader capabilities, not an unbypassable policy boundary. E4B and owner budgets are unchanged.
