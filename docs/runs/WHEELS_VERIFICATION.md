# Can we install new wheels for the fastapi tasks? (verified 2026-11-17)

**Answer: not in scoring. In local runs, yes, and it does not touch scoring.**

## Evidence

| Question | Finding | Source |
|---|---|---|
| Can the scoring environment's packages change? | No. "The scoring environment has a fixed set of packages installed which cannot be modified." The wheelhouse is "the authoritative set of packages" | Staff Holbrook, 2026-09-27 (`Rules/Verbatim/forum-staff-posts.md:155-156`) |
| Can a submission ship a wheel? | No. Allowed extensions are `.yaml .yml .md .txt .py .json .safetensors`; `.whl` is rejected by the validator | HR §2.4; `adk_submission` validator |
| Can the agent `pip install` during a task? | Container A is offline (`network_mode=none`), and the harness prompt says dependencies are pre-installed and not to pip install. Anything installed in Container A is gone anyway: verification runs in a fresh Container B, and only the patch carries over | HR §4.1, §5.2, §8.2 |
| Do the scored tasks even include fastapi? | No. "The scoring is done on private repos so does not include these tasks"; the private sandbox is "the same sandbox but different wheels" | Staff Markowitz, 2026-11-04; Holbrook, 2026-10-12 |
| Is the package under test importable when scored? | Yes: "you can rely on the package under test (and its pre-cached test dependencies) being importable in-place in both the agent sandbox and the verification sandbox" | Staff Holbrook, 2026-10-12 |

## What this means for us

- The local wheel overlay (`Tools/local/build_wheel_overlay.py`, arm64 pydantic_core) is a **local grading fix only**. It changes nothing that is submitted or scored, so it is allowed.
- Fixing local fastapi grading further (the starlette 1.6.0 vs pin `<0.49` break, run_18) would only improve local measurement on a repo that is never scored. Not worth doing unless fastapi is used as a local training-data source.
