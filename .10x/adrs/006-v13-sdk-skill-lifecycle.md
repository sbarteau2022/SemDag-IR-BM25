# ADR-006: Align discovery with the unmodified SDK lifecycle

Status: Accepted within owner-authorized protocol/policy repair; no new tool or permission.

Captured system messages append the SDK requirement to load a relevant skill before proceeding. Our root instead prescribed direct prepare and left inventory discovery implicit. Captured/replayed E4B responses guess skill_name dask; greedy first-turn replay does the same, so no sampling intervention is adopted.

Decision: root first lists skills (no arguments), then loads the exact registered name from that response, then queries budget and calls typed native prepare. Editors load their known role skill before native actions. Descriptions truthfully state that the single skill supports repository work regardless of repository name. No hidden context changes or invented SDK fields. Native authorization and budgets unchanged. This adds explicit discovery/loading; no end-to-end call savings claimed from it.

Alternative: continue direct execution despite SDK's appended lifecycle. Rejected for observed inconsistency. Renaming fields/normalizing guesses in a host wrapper is rejected. Training or broader architecture remains outside this repair.

Fixed case remains dask__dask-8801. The preregistered shorter dask__dask-8820 fails its original reference-fix gate (six dependency/environment failures); it is excluded, not weakened or substituted. Freeze source after tests and run one SDK-aligned typed-ABI trial. Require actual prepare, managed edit and verified apply; report resolution separately. Preserve all failures.
