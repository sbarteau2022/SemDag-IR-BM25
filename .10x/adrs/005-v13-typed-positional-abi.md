# ADR-005: Use the SDK's declared string-array ABI

Status: Accepted within owner-authorized tool-protocol repair; no new permissions.

Evidence: actual captured requests contain the expected system/tool list. SDK args.anyOf renders type empty in the identical CT/MLX checkpoint template. SDK positional_args is type array/items string and its wrapper deliberately inserts -- before the supplied values. Fixed status probes with raw generation/chat both pass, so a universal parser bug is not established. The schema gap is a contributor hypothesis, not a proved sole cause.

Decision: retain legacy flag/serialized-array grammar; add a strict production for SDK -- followed by explicit action/data positions. Model instructions use positional_args only, not args/short_options, and native format guidance replaces JSON-call examples. All action arities/types/slot/role/hash checks remain. Do not rewrite missing outer keys, skill names or model outputs, patch SDK/template, add tools, or change budgets/dispatch counts. This is ordinary parsing of a documented typed SDK input, not inferred intent.

Grammar: prepare ISSUE SECONDS SLOT; edit HANDLE CODE; view HANDLE A-B; finalize HANDLE SLOT; status [SLOT]. The editor slot is still statically bound and explicit cross-slot requests fail. Reject missing/extra fields and unauthorized actions before mutation. Preserve the failed requests and original source hashes.

Gates before same-case E4B retry: actual SDK typed-array rendering, all current compiled denial/lifecycle cases plus new positional positive/negative cases, full suite and official validator. Live gate remains prepare -> managed editor edit -> verified apply, resolution separate. No threshold change or success claim based on component fixtures. Deeper architecture/training changes remain outside this repair.

Alternative: normalize args.anyOf in a host adapter or strip output quotes. Rejected because it changes scorer behavior or model intent. The existing declared positional_args field needs neither.
