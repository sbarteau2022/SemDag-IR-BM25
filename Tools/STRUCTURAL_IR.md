# Structural IR — submission-safe (Python, stdlib only)

`Tools/structural_ir.py` is the **submittable** implementation for the Gemma 4
competition. It is pure Python 3 stdlib (`ast`, `hashlib`, `json`, `re`,
pathlib, `collections`), needs no network and no compilation, and runs inside
the harness through `run_command` as a skill script.

## Usage

```bash
python3 Tools/structural_ir.py --out-dir .ir_py snapshot  <repo-root>
python3 Tools/structural_ir.py --out-dir .ir_py analyze   <repo-root>
python3 Tools/structural_ir.py --out-dir .ir_py decompose <repo-root>
python3 Tools/structural_ir.py --out-dir .ir_py context   <repo-root>
```

Flags before the subcommand. Each command prints exactly one compact JSON
receipt line and writes full artifacts to `<repo-root>/<out-dir>/`.

## Artifacts

| Stage | Artifact | Contents |
|---|---|---|
| snapshot | `snapshot.box` + `snapshot.index.json` | contiguous bytes + path/size/offset/SHA-256 index |
| analyze | `analyze.json` | confidence-ranked flags + `flag_count_key` + dependency roots |
| decompose | `decompose.json` | nodes (file/module/class/function) + edges (contains/imports/calls) |
| context | `context_prob.json` | per-flag `contextual_probability`, `reachability_paths`, `needed_closures`, `related_holes` |

## Notes

- The snapshot stage excludes the output directory by construction: a snapshot
  must never ingest a previous run's `snapshot.box` or `*.json`.
- Dependencies are absolute import roots only; relative imports are intra-repo.
- Flag detection is AST-based. A line-based scan for `eval(` matched 12 files in
  fastapi_11194 while AST inspection found 0 call sites — do not regress to text
  matching.
- `Tools/repo_structural_ir/` is a Rust reference implementation used only as a
  cross-language fidelity oracle for snapshot digests. **It cannot be shipped**:
  the competition admits no compiled binaries and has no network at runtime.

## Measured (2026-11-12, Python 3.15, arm64)

Five SWE-task snapshots; full four-stage pipeline 0.45–3.07 s; snapshot digests
match the Rust implementation byte-for-byte on all five corpora. Details in
`PaperTrack/Structural_IR_Preprint.md` §5.1.
