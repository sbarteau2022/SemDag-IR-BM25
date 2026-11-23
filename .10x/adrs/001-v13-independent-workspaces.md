# ADR-001: Independent task-local workspace copies

Status: Accepted within approved qualification/bug repair scope.

Context: live component reproduction shows hardlinks mutate central/sibling source before apply and erase collected diffs.

Decision: use independent copies and task-local slot roots. Keep CLI boundaries; refuse unsafe paths/symlinks.

Alternative: hardlinks plus editor atomic replacement. Rejected because run_command can write in place and isolation cannot rely on editor discipline.

Consequences: more disk/copy cost, but edits are isolated. Measure copy time and model task budget; no resolution-gain claim from component tests.
