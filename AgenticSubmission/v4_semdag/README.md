# v4_semdag: source retrieval on a typed repository graph

- Base model: `gemma-4-e4b-it-qat-w4a16-ct`; no adapter and no second model.
- Runtime: standard-library Python, offline, shipped as the ADK skill `skills/semdag` so it is
  reachable inside the sandbox through `run_skill_script`. `scripts/repo_eval.py` snapshots the
  live repository, builds file/class/function nodes, resolves conservative
  `contains`, `calls`, and repository `imports` edges, and checks byte parity.
- Retrieval: BM25 over non-test function source supplies the restart
  distribution. A damping-0.15 walk adds structural context without replacing
  the source signal. Scores remain full precision until deterministic sorting.
- Agent contract: call the localizer first, inspect ranked source, make a
  minimal edit, run a targeted repository test, and submit a non-empty patch.
- The returned ranking is evidence to inspect against source and tests; this
  package has not yet been compared against another agent in paired full-task runs.

Validation:

```bash
python3 -c "from pathlib import Path; from adk_submission import validate_directory; from swegemma.config import build_submission_limits; validate_directory(Path('AgenticSubmission/v4_semdag'), limits=build_submission_limits()[0])"
PYTHONDONTWRITEBYTECODE=1 python3 PaperTrack/phase4_semdag/adversarial_check.py
```

Offline localization measurements come from
`PaperTrack/phase4_semdag/measure_v2.py`, which imports the same production
`retriever.py`. The directory-validation command requires the official harness
packages; the structural check and production retriever use only the Python
standard library. No scored CUDA run or Kaggle submission has been made.
