# Exact-fragment edit adversarial review

Scope: ADR-015. Model supplies current handle, literal old fragment and replacement source through a statically bound editor-only endpoint. No new path/model/network/source authority. Root registration excludes replace.py; editors cannot select another slot or finalize. Missing SDK fields remain errors.

One exact occurrence, including overlapping starts, is required inside the current view. No fuzzy match, regex, whitespace correction, autoindent, quote decoding or implicit action. Anchor bounds16 physical lines/2048 characters are checked before source mutation. Replacement is applied through the existing locked edit validator; intervening view/source changes fail stale checks instead of rebasing. Compilation/import/source-hash/scope/single-use guards remain active, followed by root outside/central verification and rollback.

Actual compiled SDK tests cover both positive owners and root/sibling/malformed denial. Real-source replay preserves untouched header/docstring bytes; Unicode, LF/CRLF, BOM, no-final-newline, explicit deletion, missing/ambiguous/overlapping/outside/stale fragments and intervening views are covered. Treat the one initial decoded BOM as an encoding marker only; never alter bytes or strip embedded/double markers. Raw live captures remain local. Security/component approval is not task-resolution proof.
