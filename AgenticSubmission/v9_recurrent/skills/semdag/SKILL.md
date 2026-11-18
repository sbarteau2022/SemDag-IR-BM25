---
name: semdag
description: Recurrent repository graph tools for /workspace. Ranks the functions to edit for an issue, shows a function's loops, recursion and callers, checks a change before submit (what the patch will contain, what it breaks, which test to run), and rescues a failed edit_file call.
---

Four calls through `run_skill_script` with `skill_name: semdag`. They share one hybrid recurrent graph of the repository: functions, classes, loops and recursion cycles, with calls, instantiation, inheritance, imports, loop and recursion edges kept in both directions.

1. Localize. `file_path: scripts/repo_eval.py`, `args`: a list holding one string, the whole issue text. Prints compact JSON:
   - `top_edit_sites`: ranked functions with `file`, `line`, `end_line`, `qualname`, `risk` (AST risk signals), `fan_in` (library callers), and when present `loops`, `recursive` (size of its call cycle) and `callers`.
   - `tests_near_sites`: existing test files that exercise the top sites.
   - `hubs`: the three highest-scoring nodes of any kind, with `fan_in` and `importers`.
   - `walk_paths`: for each hub, the nodes reached in 1 to 3 hops (`h1`, `h2`, `h3`) over `calls`, `contains` and `imports`.

2. Flow. `file_path: scripts/repo_eval.py`, `args`: `["--flow", "Class.method"]` (a `qualname` from step 1, or `file.py::Class.method`). Prints the function's `loops` (lines, kind, depth, `carried` variables, `exits`, `calls` inside the loop), `recursion` (cycle size and members), `calls`, `callers` and `topo_rank`.

3. Verify. `file_path: scripts/repo_eval.py`, `args`: `["--verify"]`. Reads the change from git and prints:
   - `patch`: `files` the patch will carry, `stripped` test and config files the harness removes, `new_files`, and `empty`.
   - `syntax_errors`, `undefined_names`, `removed_still_used`, `signature_breaks`: breakages in the changed code.
   - `callers_to_check`: callers of the changed functions.
   - `tests_to_run` and `test_cmd`: the existing tests closest to the change.
   - `recurrence`: re-check notes when a changed function is recursive or has loops.
   - `next`: the single most important next step.

4. Rescue an edit. `file_path: scripts/fix_edit.py`, `args`: `[filepath, old_string, new_string]`. Applies the edit if the text matches apart from whitespace. Otherwise it writes nothing and prints the closest real block with line numbers and a reference such as `@1`. Then `args`: `[filepath, "@1", new_string]` replaces exactly that block. `[filepath, "L120-126", new_string]` replaces a line range. It refuses test and config files and any edit that would stop a Python file from parsing.

The scripts find the repository from the harness wrapper's own location, so they work in both sandbox backends. They keep their cache in the temp directory, so nothing they write enters the patch.
