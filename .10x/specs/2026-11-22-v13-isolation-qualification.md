# v13 sandbox qualification and isolation repair

Approved direction: qualify v13_orchestrator using only Gemma E4B and macOS Seatbelt/subprocess; no Docker. Do not tune on public competition tasks. Preserve frozen v6 and original v13 receipt.

Measured fault: reports/v13_qualification_2026-11-22/baseline.json. Hardlinked workspaces permit slot edits to mutate central/sibling bytes, then collect sees no change. Editor config uses 8192/2048 instead of owner 16384/4096.

Implementation: independent file copies, strict slot/path validation, task-local workspace directory using tempfile.gettempdir(), symlink rejection at workspace boundary, and fixed owner budgets. Preserve CLI and collection/apply behavior. Repair subagent skill paths if official load demonstrates a failure. Do not change retrieval/prompt architecture without new evidence.

Gate before model run: changing slot 1 must leave central and slot 2 byte-identical; collect returns a nonempty patch; apply changes central only when requested; reset cannot remove anything outside its task slot; invalid slot/path and symlinks refused; no test/config file application; official package validation and host regression suite pass. Repeat on real v13 script source. Component proof is not SWE resolution proof.

Evaluation: stock v13 preserved under report original/; repaired v13 is tested against reproducible real external issues if available, first qualifying empty patch fails and reference patch passes. Record hardware, dataset provenance, hashes, real time/tool use, grading errors separately. No hosted/non-E4B fallback. Local Metal thinking-budget enforcement remains a known gap. If external task environments cannot qualify, report that exact blocker; never replace with fabricated task-success claims.
