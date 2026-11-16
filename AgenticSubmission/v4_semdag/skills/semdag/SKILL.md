---
name: semdag
description: Rank the functions in /workspace most likely to need editing for an issue, by BM25 over live function source followed by a light walk over the repository's contains, calls and imports graph.
---

Use `run_skill_script` with `skill_name: semdag`, `file_path: scripts/repo_eval.py`, and `args` set to a list holding one string: the issue text. The script snapshots the repository, builds a typed graph with the standard library, checks byte parity, and prints JSON whose `top_edit_sites` lists candidates as `file`, `line`, `end_line` and `qualname`. It reads `/workspace` only and writes its cache under `/tmp`.
