# run_18: fastapi local-grading environment check (not a lane result)

Status: **LIVE-MEASURED**, environment check only. One task (fastapi_11194), v7, oMLX, `TASKS=DataSets/local_overlay/data/tasks.jsonl` (arm64 pydantic_core overlay). Raw files: `results/run_18_fastapi_envcheck/`.

## Result

- **The pydantic-core fix works.** The grader no longer fails with `pydantic-core version ... is incompatible` (run_11 failed that way on all 15 fastapi tasks). `test_env_broken = 0`.
- **A second environment break shows up.** Every test fails at collection:
  `fastapi/routing.py:844 ... TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'`.
- Cause, read from the harness source:
  - `swegemma/harness/container_setup.py::_deduplicate_wheels` keeps "the highest version per normalized distribution name". The wheel pool has 56 starlette wheels, up to `starlette-1.6.0`, so local Docker installs 1.6.0.
  - The snapshot's `pyproject.toml` pins `starlette>=0.40.0,<0.49.0`.
  - Starlette 1.x removed `on_startup` from `Router`, so `FastAPI()` cannot be built.
- The task outcome (`right_function_wrong_fix`) therefore **cannot be trusted**: no patch could pass locally.

## What this means

- Local Docker grading of fastapi is still not faithful. Per `CLAUDE.md`, the scorer uses the subprocess sandbox, which skips test-dependency injection and runs in the image's own environment. That environment is unknown here, so this break says nothing about the scorer.
- Possible local fix (not built): a fastapi-only overlay that leaves out starlette wheels at or above 0.49, so dedup picks the newest version the pin allows.

## Agent behaviour (for the record)

The patch edits `fastapi/dependencies/utils.py::_extract_form_body`: it checks the per-field `field_info` instead of `first_field_info`. 28 model calls, 0 proxy errors.
