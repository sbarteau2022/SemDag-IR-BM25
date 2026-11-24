# ADR-012: State-derived continuations and an explicit finalizer program

Status: Accepted as a native control-ABI repair within owner-authorized workflow completion. Same root finalize authority, no new edit/role/model permission.

Observed: E4B makes a compilable private-slot edit, root retrieves the current handle, then calls generic run.py with task prose or the handle as the first positional argument, omitting finalize. Do not infer that intent from malformed calls or make status mutate source.

Decision: expose actual state in view replies. Root edited-state status publishes next_execution containing the real skill name, registered finalize.py path and actual handle; root still chooses/sends the call. Root alone registers scripts/finalize.py, a fixed-operation endpoint accepting exactly one handle. Its operation is selected explicitly by file_path, and the slot is read from the validated handle/state, not guessed. Editors do not register this program. Generic run.py malformed calls remain errors. Helpers/assets remain non-executable via SDK lookup.

Applied-state replies publish next_tool=submit_patch with empty args. Prepared-state delegation remains with the root; no worker prompt is generated. Failed verification is recorded by candidate hash so status recommends the candidate’s statically bound owner for the existing one-final-retry count, rather than asking editor_1 to change editor_2’s slot. This corrects owner-routing consistency without changing retry count. These are API affordances, not automatic dispatch/model-output repair. No callbacks/SDK patches, time/token changes or early source apply.

Tests: compiled resource surfaces, editor finalizer-path denial, strict one-handle errors, actual root status->published execution record->outside/central apply->submit affordance, role/hash/marker and failed-candidate retry links. Full regression/official validation then same unchanged task. Require genuine model-selected verified apply; grade resolution separately and retain failures/performance-gate failure.
