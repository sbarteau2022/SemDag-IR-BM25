---
name: packet-check
description: Reject malformed or unsupported brigade decision packets before source edits.
---

Use `run_skill_script` with `skill_name: packet-check`, `file_path: scripts/check.py`, and positional argument `PACKET_PATH`. The path must be inside `/tmp/gemma-brigade/`. The script checks the canonical packet digest, safe edit paths, and critical claim verdicts. It does not certify that the cited source is true; the lead must recheck the C7 snapshot against live workspace bytes.
