# C6 — API Contract

Purpose: preserve externally observable behavior while fixing the defect.

- Inputs: immutable C7 only.
- Output: compartment 6 with exact signatures, types, exceptions, messages, return behavior, and compatibility constraints.
- Required adversary: test whether the proposed change alters a caller-visible contract.
- Stop: all captured public boundaries are dispositioned.
- Forbidden: guessing undocumented public behavior without a labeled inference.
- Gate: exact signatures cite source; compatibility risks are explicit.

## Procedure and receipt

1. Verify the frozen C7 digest. List each captured caller-visible function, class, exception, return shape, and import path that the edit may affect.
2. Quote exact signatures only from C7 source refs. Describe undocumented behavior as inference with its boundary; leave uncaptured contracts `missing`.
3. Challenge the candidate edit against positional/keyword calls, error behavior, return types, mutation, ordering, and compatibility with captured callers and tests.
4. Emit `apis` with source refs, preserved obligations, potential breakage, and unresolved contracts. A missing critical API boundary is sent to C4 and S as a blocker or explicit uncertainty.
5. Hash and publish `06-api-contract.json`; Q3 checks every asserted signature has an exact source anchor and every compatibility risk is dispositioned.
