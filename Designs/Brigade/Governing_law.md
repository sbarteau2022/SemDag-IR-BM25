# Governing Law of the Snapshot-Backed Brigade

Status: **PROPOSED CONSTITUTION**  
Packet: `BRIGADE-DESIGN-001`  
Precedence: competition rules and harness enforcement override this document.

## Article I — Non-negotiable competition law

1. Every agent uses `gemma-4-e4b-it-qat-w4a16-ct`; adapters, if any, target that base.
2. Runtime behavior uses only registered harness tools, declared `agent_tool` agents, and admitted skill tools/scripts.
3. Runtime is offline. Submission files stay inside the archive, use allowed extensions, contain no symlinks or traversal, and total less than 3 GiB unpacked.
4. The aggregate patch campaign stays within 12 hours. Per-task activity terminates when any harness budget is exhausted.
5. Tests and runner configuration are not patch targets. Scratch artifacts live in `/tmp`.
6. `submit_patch` is invoked once, by the finalizer, after verification and cleanup.

## Article II — Order of authority

Authority descends in this order:

1. Competition rules and executing harness.
2. Fresh bytes from the task workspace and the frozen base commit, checked at the point of use.
3. Immutable C7 relational snapshot, valid only while its workspace preimages still match.
4. Deterministic judge receipts and direct tool output.
5. Admitted claims derived from the snapshot.
6. Synthesis outline.
7. Model proposal.

Lower authority may not overwrite higher authority. A model assertion that conflicts with exact snapshot evidence is rejected.

## Article III — Required execution order

The binding DAG is `C1 → C2 → C7 → {C3,C5,C6} → C4 → S → I → C8 → F`. Only C3, C5, and C6 may run concurrently. A lane begins only when all dependencies have passed or carry an explicit permitted fallback.

## Article IV — Storage law

1. Each task owns one ledger root and one unique state namespace.
2. Every lane writes only its declared compartment. Parallel lanes never share a writable record.
3. Records are append-only until S freezes the decision packet. Corrections append a superseding record; they do not silently rewrite evidence.
4. Exact source remains in C7. Derived lanes store references, not altered copies presented as source.
5. The runtime ledger lives outside `/workspace` and must not enter the scored patch.
6. No cross-task evidence, model conversation, or state key is inherited.

## Article V — Hash law

1. Content identities use lowercase SHA-256 hex over exact bytes. Do not normalize newlines, Unicode, whitespace, or encoding before hashing.
2. For JSON envelopes, hash UTF-8 canonical JSON with sorted keys, compact separators, `ensure_ascii=false`, and the envelope's own `*_sha256` field removed. Reject duplicate JSON keys and non-finite numbers before canonicalization.
3. A source excerpt uses the exact concatenation of inclusive 1-based lines from `splitlines(keepends=True)`. The full-file hash is computed from workspace bytes, not inferred from a truncated `read_file` response.
4. Source records bind task, repository, base commit, relative path, inclusive line range, full-file digest, excerpt digest, and a capture time. Relations bind two captured file references and a relation kind; unresolved endpoints are marked missing.
5. The implementer recomputes affected full-file hashes immediately before editing. Mismatch yields `stale` and invalidates dependent claims. It may relocalize once within budget; it may not patch against stale source.
6. C8 records preimage, postimage, unified-patch, command, exit-code, and output digests. A digest without the bytes or a retrievable artifact location is insufficient for rollback.
7. Hash agreement proves identity only. It never upgrades a claim to semantic truth.

## Article VI — Budget and lane law

1. The controller reserves finalization capacity before exploration.
2. Lane weights and call ceilings come from a named, precommitted task budget profile. The scored task cannot infer remaining hidden tasks or global time. A lane may consume less, never silently more.
3. Exhausted lanes return `budget_exhausted` with partial evidence; they do not fabricate completion.
4. Unused budget returns to the controller. Borrowing requires a recorded reason and cannot consume finalization reserve.
5. Parallel width is at most three read-only derivation agents in the proposed profile. Increasing width requires a measured throughput and quality admission test; 4 × 24 GiB GPU memory is not four 24 GiB task containers.
6. `get_status` is the source of live task limits. The proposed controller must enforce a monotonic local deadline and counted-call ledger; a prompt request alone is not enforcement.

## Article VII — S lane protocol

Exactly one S lane is permitted. S may validate, deduplicate, order, compare, and disposition admitted evidence. S may not inspect new repository data, edit source, execute tests, introduce uncited facts, or convert missing evidence into confidence. Every outline claim receives one verdict: `supported`, `contradicted`, `missing`, or `stale`.

Critical `contradicted`, `missing`, or `stale` claims prevent implementation. One relocalization cycle is permitted if budget remains. A second failure triggers Strike 2.

## Article VIII — Implementation law

1. One implementer owns all source edits.
2. Before editing, it checks current hashes and attempts to falsify the outline against C7.
3. It applies the smallest contract-satisfying source change and avoids unrelated refactors.
4. It cannot change tests, runner configuration, the ledger, or the decision packet to make itself pass.
5. It never self-approves and never calls `submit_patch`.

## Article IX — Quality and honest audit

1. Every claim is labeled `VERIFIED`, `REPORTED`, `INFERRED`, or `PROPOSED`. A model-generated `VERIFIED` label remains an assertion until an independent deterministic witness check passes.
2. `INFERRED` claims name where evidence ends. `PROPOSED` claims cannot satisfy a correctness gate.
3. Every failure, waiver, malformed output, timeout, no-diff result, and missing dependency is recorded per item.
4. No aggregate success statement may hide failed items. No paper number is admitted without a stored run, denominator, task ids, configuration digest, and regeneration command.
5. The ledger is workflow evidence, not hidden-test proof. C8 Phase-1 checks and Phase-2 competition verification remain distinct.

## Article X — Release

A brigade variant may enter evaluation only after schemas validate, hostile fixtures are dispositioned, the baseline remains reproducible, and no active experiment was mutated. It may enter a candidate submission only after a matched-budget held-out run beats the baseline on the pre-registered primary measure without increasing invalid patches or violating the 12-hour campaign cap. Secondary advantages are reported separately; they cannot replace a failed primary gate after results are seen. Human approval remains required for Kaggle submission.

## Article XI — Restore, rollback, and reset

- **Restore:** reconstruct source from the task base commit, verify preimage hashes, and apply the admitted patch; the ledger is not restoration authority. If the full evidence package was exported to a host trace, validate its digest and schema before using it for audit.
- **Rollback:** apply the recorded reverse diff or recreate the clean task snapshot. Verify resulting hashes against C7 preimages.
- **Reset:** destroy the task container and ledger, clear session state, and allocate a new empty namespace. Keep the shared model server running unless the run protocol explicitly ends it.
- **Release failure:** retain receipts and failed artifacts outside the scored patch; revert the candidate configuration to the last admitted version.

## Article XII — Failure doctrine

Strike 1 requires reading the receipt and changing the approach so the retry signature changes. Strike 2 blocks dependents and requires explicit escalation plus a micro pre-registration before any third attempt. Identical retries are protocol violations.

## Article XIII — Contradictions and no-patch outcomes

The controller distinguishes `implement`, `relocalize`, `fallback`, and `no_patch`. `implement` requires supported critical claims and a fresh C7. `relocalize` is permitted once. `fallback` routes the same sole implementer through the predeclared baseline behavior within the remaining task budget; it does not make unsupported brigade claims true. `no_patch` emits an honest empty result and reason. A critical unsupported claim cannot be waived by S or by the implementer.

## Article XIV — Evidence export and audit custody

The in-container ledger is disposable. A workflow proof accompanying a fix exists only if the host trace captures the decision packet, C7 snapshot, lane outputs, judge receipts, exact patch, and hash manifest before Container A is destroyed. The export must be outside the scored patch, keyed by task and run id, and checked against a deterministic manifest. If the official runner cannot expose such an export hook, the local brigade may still run, but it must not claim a durable submitted proof or cross-task rollback from `/tmp` state alone.

## Article XV — Change control

Freeze the schema, agent graph, prompts, budgets, and judge versions before each evaluation. Record changes as a new candidate manifest. Never revise an ongoing Paper Track generation run, its matcher, or the 8123 server to accommodate this design. A reviewer who did not author the packet must disposition the design checklist before promotion beyond draft; this document does not grant its own approval.
