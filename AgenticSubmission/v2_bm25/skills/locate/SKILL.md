---
name: locate
description: Rank the functions in /workspace most likely to need editing for an issue, by lexical match between the issue text and each function's source.
---

Use `run_skill_script` with `skill_name: locate`, `file_path: scripts/locate.py`, and `args` set to a list holding one string: the issue text (or its key sentences and identifiers). The script parses every non-test Python file under `/workspace`, scores each function against the text, and prints the top candidates as `path:start-end qualified.name`. Read the first candidates before searching elsewhere. It reads files only and changes nothing.
