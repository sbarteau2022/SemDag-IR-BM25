---
name: presubmit-check
description: Check changed workspace paths and protected-file rules before the sole submit_patch call.
---

Use `run_skill_script` with `skill_name: presubmit-check`, `file_path: scripts/check.py`, and positional arguments listing the allowed relative source paths. The script reads Git status in `/workspace` and rejects any changed or untracked path outside that allowlist, including test and runner files. It cannot know the exact patch bytes that the harness will extract; review the diff separately and retain C8's patch receipt. Call `submit_patch` once and last after all checks.
