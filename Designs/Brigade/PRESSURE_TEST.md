# Pressure-Test Record

Status: **DESIGN-TIME DISPOSITION**  
Execution receipts are produced by `tools/validate_contracts.py`; runtime assaults remain pending implementation.

| ID | Edge vocabulary | Hostile input | Expected disposition |
|---|---|---|---|
| E01 | Input & Validation | Missing task id or schema version | Schema reject. |
| E02 | Input & Validation | Invalid compartment `0`, `9`, or string | Schema reject. |
| E03 | Input & Validation | Uppercase/short/non-hex digest | Schema reject. |
| E04 | Data & Consistency | Claim cites absent snapshot reference | Cross-validator reject. |
| E05 | Data & Consistency | File changes after C7 freeze | Implementer recomputes hash; verdict `stale`; block edit. |
| E06 | Data & Consistency | Two parallel lanes write one key/path | Contract validator rejects duplicate `output_key` or write scope. |
| E07 | API & Network | Agent attempts internet access | Tool surface has no network; runtime offline. Record failure. |
| E08 | Timeouts & budgets | Lane exhausts allocation mid-record | Emit `budget_exhausted`; preserve partial evidence; no fabricated pass. |
| E09 | Byte/context caps | Compiled packet exceeds cap | Deterministic dedupe/prune; preserve exact target source; otherwise fallback. |
| E10 | Concurrency | Eight simultaneous long generations | Forbidden by default width; admission requires measured stress run. |
| E11 | Empty localization | C1/C2 return no candidate | One materially different retry, then single-agent fallback. |
| E12 | Correlated error | All specialists repeat unsupported target | S requires exact C7 anchors and competing hypothesis; unsupported claim rejected. |
| E13 | Protected files | Implementer edits test/config file | Q4 reject; reset source from preimage. |
| E14 | Double submit | Any non-finalizer calls `submit_patch` | Agent contract validation reject. |
| E15 | Restore | Ledger exists but patch/preimage mismatch | Restore from base commit; ledger cannot override source identity. |
| E16 | Verification | Targeted tests unavailable/missing dependency | Record exact failure; do not mark verified; retain unresolved risk. |
| E17 | Unicode/path safety | Unicode or traversal in path | Relative normalized path only; traversal schema/runtime reject. |
| E18 | Malformed model output | Non-JSON or truncated section | Lane status `malformed`; one different retry; otherwise fallback. |

No waiver is currently granted. Runtime items E05, E08–E12, E15–E18 remain unverified until an executable brigade exists.

## 2026-11-11 validator assault

The offline validator was run after adding five semantic hostile mutations. Each mutation recalculates its envelope digest, so rejection depends on the violated rule rather than an incidental checksum failure.

| Case | Result | Boundary checked |
|---|---|---|
| Derived C5 omits the C7 digest | Rejected | Dependency identity |
| C5 repeats a claim identifier | Rejected | Unique evidence identity |
| C5 names a file excerpt as a relation | Rejected | Reference kind |
| S names a relation edge as its target file | Rejected | Target kind |
| S permits an edit under `tests/` | Rejected | Protected path |

`validate_contracts.py` exited 0 on the complete fixture set. This is design-time validation only; the runtime edge cases in the table above still need executable receipts.

The custody-contract fixture also rejected a controller sequence gap and a host-export traversal path. Its positive case passed schema and semantic checks. This does not establish that the official runner exports a ledger before task-container destruction.

The v1 packet skill's parser was directly challenged with duplicate JSON keys, `NaN`, and `Infinity`; all three were rejected. This checks parsing only. The skill has not been executed through ADK's `run_skill_script` in the task sandbox.

The snapshot and pre-submit skill path helpers directly rejected `../escape.py`, `a/../b.py`, `a//b.py`, `./x.py`, absolute paths, backslashes, and empty paths; a normal `pkg/module.py` passed. The snapshot script also now checks symlinked path components. These checks do not replace a sandbox execution receipt.

The implementation receipt hostile fixture changed an admitted source path to `tests/test_module.py` and was rejected after its envelope digest was recomputed. The command receipt hostile fixture changed the patch digest and was rejected after recomputing its receipt digest. Both are offline semantic tests, not observed task outcomes.
