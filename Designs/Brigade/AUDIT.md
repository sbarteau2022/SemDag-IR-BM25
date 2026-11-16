# Honest Audit

Date: 2026-11-10  
Packet: `BRIGADE-DESIGN-001`

## Verified

- The project is not a Git worktree at the current root.
- The requested OPS_BOARD path and `DOCUMENTATION STANDARDS.MD` were absent.
- The requested goal script was absent; the built-in thread goal mechanism was used instead.
- No callable Atoma Hole service was exposed. Work was staged in `/tmp/gemma-brigade-hole.YtFyom` as a recoverable isolation fallback.
- The active Phase 2 generator and port 8123 were not restarted or edited.

## Proposed, not verified

- The brigade improves patch quality or resolution rate.
- Three concurrent derivation agents are throughput-optimal.
- A 100-tool-call profile is affordable on the final hidden task count.
- The final model can reliably falsify an outline from the compiled packet.
- Local trace retention is sufficient to preserve the full ledger after container destruction.

## Known limitations

- Same-model specialists have correlated errors.
- Graph seeds can be empty or wrong.
- Source-to-IR conversion is lossy unless every claim remains anchored to C7.
- SHA-256 establishes identity, not correctness.
- Phase-1 tests do not predict all hidden tests.
- A ledger stored only in `/tmp` disappears after the task.
- Competition scoring transfers only the patch to verification; proof artifacts are not part of the scored result.
- The current one-minute/ten-call baseline budget cannot execute this brigade.

## Admission decision

The documents, schemas, and validator may be merged as a design artifact after their judges pass. The brigade must not replace or modify `AgenticSubmission/v0_baseline` until a separate implementation packet passes baseline, adversarial, and held-out evaluation gates.

## Corrections protocol

Corrections append a dated entry naming the superseded claim, reason, and replacement. Silent historical rewrites are prohibited once an evaluation cites this packet.

## 2026-11-11 correction and current audit

- The earlier statement that the documentation standards file was absent refers to the requested `OPS_BOARD` path. A relevant standards document was later supplied at `N3/DOCUMENTATION_STANDARDS.md` in the GlobalHack repository. The brigade Markdown files still lack its required metadata and full section structure; documentation compliance is **open**.
- The current validator passes its fixtures and added hostile mutations. It cannot establish full-file hash agreement against a live workspace because fixture excerpts are not full files; that remains a runtime gate.
- The Phase 2 generator PID 34956 was absent when inspected on 2026-11-11. Port 8123 was live under PID 19501. Absence of that PID alone does not prove the campaign completed; generation status requires inspection of its output manifest/process lineage before any conclusion. Neither service nor results were changed.

## 2026-11-11 Phase 2 read-only verification

The generator command was absent from the live process list. `PaperTrack/phase2/out/completions/` contained 96 files, and `score.json` reported 48 O and 48 C completions with zero errors. This supports completion of the recorded 96-completion generation campaign. The port-8123 server remained live under PID 19501; it and the Phase 2 outputs were not modified. The brigade work remains independent of that result.

## Remaining machine-contract gaps

- The generic evidence schema constrains required payload keys but not each lane's full payload shape; C1–C6 and C8 need versioned payload schemas or equivalent `oneOf` rules.
- Controller-ledger, host-export-manifest, implementation-result, and command-receipt schemas now exist and pass synthetic fixture checks. Per-lane payload schemas remain absent.
- The validator checks fixture hashes but cannot validate live full-file preimages or timed controller behavior.
- All lane runbooks now have stepwise procedures. They are draft operational instructions; no controller currently enforces calls or deadlines.

## 2026-11-11 four-role decision

`roles-and-skills.md` and `contracts/roles.yaml` specify a candidate lead/localizer/analyst/verifier roster while retaining all eleven logical lanes. The offline validator checks unique role authority and complete lane coverage. A separate `AgenticSubmission/v1_brigade/` package now exists and passes `validate_directory`; its three skills load through the ADK skill loader. Agent-tree compilation, skill-script execution in a sandbox, a task smoke, and matched-budget role ablation have not occurred. The eleven-agent contract remains a comparator and must not be mistaken for the admitted runtime roster.

## 2026-11-11 custody-contract update

Added controller and host-export schemas plus semantic checks for sequence gaps, monotonic counter regressions, missing committed artifact hashes, path traversal, duplicate export paths, and patch/ledger identity binding. The fixture is synthetic. No host trace hook has been observed, so a durable workflow proof remains unverified.

## 2026-11-11 source and command receipt update

Added implementation-result and command-receipt schemas. Offline validation binds task, packet, snapshot, base commit, allowed paths, and patch identity; hostile cases reject a protected implementation path and a command receipt for a different patch. Docker was unavailable at the local socket when inspected, so no Docker task smoke was performed. This does not establish runtime skill execution, patch correctness, or host export.

## 2026-11-11 structural-context audit

The new Rust `context` command was inspected and challenged with a three-function fixture. Its earlier output counted public-function type issues as vulnerabilities and marked an isolated zero-in-degree function reachable by treating it as a source. The code now emits only `vuln_flag` rows, uses heuristic entry points rather than all graph roots, chooses the innermost containing function, and computes related-hole hints after all paths are known. It separates uncalibrated score from probability language and turns unproven closure assertions into review candidates. The release build and fixture rerun passed; no five-repository post-change benchmark has run. The source-name and call-edge heuristics remain broad and can produce false paths or misses.
