# C1 — Graph Seeds

Purpose: translate issue nouns, symbols, filenames, and errors into candidate graph identifiers.

- Inputs: problem statement, hints when present, graph availability.
- Tools: `search_similar_code`, `get_code_neighbors`, bounded `read_file`.
- Output: compartment 1 with resolved candidates, misses, and resolution method.
- Required adversary: include at least one competing candidate when evidence permits.
- Stop: exact candidate set established, tool ceiling reached, or two materially different resolution methods fail.
- Forbidden: source edits, broad repository sweeps, certainty without exact identifier evidence.
- Gate: at least one candidate or explicit empty-localization fallback receipt.

## Procedure and receipt

1. Extract literal filenames, symbols, errors, and behavioral nouns from the issue. Keep original spans; do not treat a paraphrase as an exact identifier.
2. Search exact identifiers first, then use one semantically different similarity query if needed. Record query, tool, returned graph ID, score, and miss reason for each attempt.
3. Read only a bounded candidate excerpt to confirm the identifier exists. Keep at least one plausible competing candidate when the evidence permits; distinguish graph similarity from source confirmation.
4. Emit compartment 1 with `candidates` and `misses`, including explicit empty arrays. An empty result triggers the declared second method or the fallback receipt, not a fabricated target.
5. Hash and atomically publish `01-graph-seeds.json`; Q1 checks query provenance, candidate IDs, and status against the tool ceiling.
