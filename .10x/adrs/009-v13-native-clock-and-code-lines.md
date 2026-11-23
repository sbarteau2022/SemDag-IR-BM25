# ADR-009: Native deadline and explicit line edits

Status: Accepted as a compatible native interface repair within owner-authorized edit/tool workflow work. Same roles, protected paths, hash/scope checks and four-minute global limit.

Observed: root repeatedly supplies prepare QUERY SLOT without remaining; editors supply read selectors such as view,435,438 and ambiguous comma-packed edit packets. Do not guess missing SDK fields or write intent.

Decision: preferred prepare QUERY SLOT derives a conservative remaining duration from the harness-owned _swegemma_baseline commit timestamp. Installed agent_runner creates it before start_agent_session. Use at most 240 seconds from that anchor; reject missing/expired/future anchors. The original explicit-remaining form remains compatible and is capped by the native clock when available. No model performs clock arithmetic; the outer harness still enforces its own four-minute limit.

Editor edit_lines HANDLE LINE... joins explicit supplied chunks with newline boundaries, preserving each chunk's bytes; it uses the same edit authorization, lease, scope and compilation checks. No automatic backslash-n unescaping or indentation guesses. Existing edit HANDLE TEXT remains. Read-only view START END or view RANGE resolves the current assigned lease then narrows and returns a fresh handle; root remains forbidden from editor view actions. Unambiguous one-string numeric read selectors may be parsed. Comma-packed writes are rejected with a specific format error rather than splitting code or inferring fields. A range-bearing edit form is accepted only if it exactly equals the issued view.

SDK required outer fields remain untouched. Each editor response with a current view may show the actual edit_lines prefix [edit_lines, current_handle] as API metadata; it is not executed without code. No fake placeholder fix is generated. Prefix-only writes fail. Preserve all previous negative receipts.

Gates: compiled SDK tests for native clock, positional forms, role/cross-slot denial, exact-view ranged edits, ambiguous write rejection, line-code preservation, and legitimate lifecycle; full suite and official validation before the same unmodified external case. Live prepare/edit/verified apply and hidden-test resolution remain separate, unchanged. Performance microgate remains failed until remeasured; do not remove safety checks to satisfy it.
