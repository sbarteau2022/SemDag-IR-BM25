# ADR-014: Reuse immutable Git baseline reads within one verification

Status: Accepted within the approved native edit-execution optimization.

Evidence: cProfile of the fixed-source transaction benchmark attributes 0.125s to repo_eval.verify, including eight Git subprocess calls. Baseline discovery and the same original file are redundantly read by impact analysis and destructive/locus checks. The last preregistered lifecycle timing gate failed at +15.44%; retain that result.

Decision: resolve the baseline label and immutable commit ID once per verification, pass an operation-local baseline object through analysis/destructive/locus checks, and reuse original file text only against that immutable object ID. Working-tree diffs remain fresh; no global/persistent memoization, no checks removed. Each new verification resolves the baseline again. Public reports retain the original baseline label.

Alternative: skip outside/central verification or cache entire verification verdicts. Rejected: stale/missing safety checks. Another alternative is retain redundant subprocesses; safe but measured avoidable execution overhead.

Pressure gates: same analysis and gates on real tracked/untracked/protected source changes; changed baseline and worktree across calls must be observed; old immutable snapshot remains coherent if a tag moves mid-operation; read-error behavior and nongit fallback stay unchanged. Full suite and official validation, then the existing seven-pair alternating lifecycle benchmark with identical output and unchanged <=10% overhead criterion. Do not benchmark concurrently with E4B inference. This is a native execution optimization and cannot repair malformed SDK calls or establish task resolution.
