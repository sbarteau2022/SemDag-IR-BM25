---
name: semdag
description: Typed task IR for /workspace. Locates the lines to edit for an issue from the issue's own traceback, literals and names, edits by line range, and blocks a patch that misses the located span.
---

Three calls through `run_skill_script` with `skill_name: semdag`.

1. Locate. `file_path: scripts/repo_eval.py`, `args`: a list holding one string, the whole issue text. Prints plain text, one action:
   - `edit FILE:A-B QUALNAME (anchor: traceback|literal|qualname|bm25: evidence)`: the span to change. bm25 is a guess and comes with an `alt` line.
   - `loop KIND LINES carries NAMES test: COND`: only when the issue names a variable the anchor's loop carries; the span then covers the loop and the lines that initialise those names.
   - `read fix_edit.py ["FILE LA-B"]`, `check CMD` (one test node), `forbid ...`.

2. Read and edit. `file_path: scripts/fix_edit.py`. `args` `["FILE LA-B"]` prints those lines numbered. `args` `["FILE LX-Y\n<new lines>"]` (or `[FILE, "LX-Y", NEW_TEXT]`) replaces exactly lines X to Y with the new lines, re-indented to the block, and refuses an edit that would stop a Python file from parsing or that touches a test or config file.

3. Verify. `file_path: scripts/repo_eval.py`, `args`: `["--verify"]`. Reads the change from git and prints `patch` (files, stripped, empty), `syntax_errors`, `undefined_names`, `removed_still_used`, `signature_breaks`, `tests_to_run`, `clean` and `next`. `next` starts with `blocked:` when the located loop span is not in the diff or when the change deletes most of a file.

`args ["--flow", "Class.method"]` on repo_eval.py prints one function's loops (condition, carried names, guarded exits), recursion and callers as JSON.

The scripts find the repository from the harness wrapper's own location, so they work in both sandbox backends. They keep their cache in the temp directory, so nothing they write enters the patch.
