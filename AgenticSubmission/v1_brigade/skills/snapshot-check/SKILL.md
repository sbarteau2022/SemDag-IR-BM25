---
name: snapshot-check
description: Compute the exact SHA-256 and line range of a task-workspace source file before trusting a relational snapshot.
---

Use `run_skill_script` with `skill_name: snapshot-check`, `file_path: scripts/check.py`, and positional arguments `PATH START_LINE END_LINE`. The script reads only a relative path inside `/workspace`, rejects traversal and symlinks, and returns full-file and exact-excerpt digests. Compare its output to the C7 record. A match proves byte identity, not behavioral truth. Re-run on affected files immediately before editing.
