# ADR-010: Metadata header plus raw source; native failure exit status

Status: Accepted as participant-native tool I/O correctness repair within owner-authorized edit execution work. No model-output rewrite or new permission.

Observed: editors reach real assignments and supply edit_lines, but copied Python quoting/docstrings contain extra backslashes and compilation rejects them. Source is embedded in native JSON stdout, which the SDK then embeds in its JSON result; this adds an avoidable source escape layer. Separately native operation failure currently exits 0, so the SDK can label a failed operation success despite ok:false.

Decision: participant role entry stdout begins with a JSON metadata header, followed (for views) by a delimited raw numbered-source block. Native state/lease semantics and internal view_result stay unchanged. Do not put source code into nested JSON text for the model. Role main returns its normal dictionary for host callers; actual CLI entry exits nonzero on ok:false and emits structured errors on stderr. Tests parse the documented frame, not an altered runtime adapter. No SDK patch, source escaping repair, quote stripping or indentation inference.

Root delegates intent/slot, not regenerated source/handles. Editors load then read authoritative native status/view before writing. Native edits still use explicit code lines, handles, compilation, scope/hash checks and outside/central verification. Wrong-role calls remain denied. Raw stdout content and metadata must match the real source bytes/lines; error exit semantics must be visible through actual SDK status. Full suite/official validation precede the same-case live trial. Preserve all negatives and failed performance gate.

Framing uses LF-delimited metadata/body; Unicode line-separator characters inside Python string literals are not physical Python lines. Native edit/view/scope slicing and test-frame parsing use physical LF lines, preserving Unicode content. Metadata uses ASCII JSON escapes to stay one physical header line; raw source remains UTF-8.
