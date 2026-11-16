# AGENTS.md: Gemma 4 Developer Agent Competition

Solo entry in Kaggle's "Google - The Gemma 4 Developer Agent Competition" plus the Paper Track.
Goal: top 3 on the main leaderboard and a strong paper. Resume from [CHECKPOINT.md](CHECKPOINT.md).

## Deadlines (11:59 PM UTC)
- Paper Track: **Nov 12, 2026**.
- Main entry and team merge: Nov 25. Final submission: **Dec 2, 2026**.
- Small Model Prize deadline is unconfirmed (page says Nov 12 and "same as main track"; participants say Dec 2).

## Hard rules from the competition
- Base model is `gemma-4-e4b-it-qat-w4a16-ct` only. One model across every agent and sub-agent. No mixing.
- Agents may call only the nine harness tools: `run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`. Extra behavior goes in prompts, sub-agents (`agent_tool`), or skill scripts.
- No internet at runtime. Submission under 3 GiB unpacked. Allowed files: `.yaml .yml .md .txt .py .json .safetensors`. No symlinks, no `../` paths.
- 12 hours total for all patches. A LoRA adapter makes tasks about 29% slower, so budget per-task time to fit.
- One submission per day, two finals selected. No private code sharing outside the team.
- Winners must open-source code and model (Apache 2.0) and ship training and inference code.

## Competition sampling (configs/sampling.yaml)
temperature 0.2, top_p 0.95, max_output_tokens 16384, thinking_budget 4096, include_thoughts true.
Local stand-in uses `--max-tokens 4096` and reasoning effort low (mlx-lm has no thinking budget).

## Layout
- `DataSets/public/data/`: extracted dataset (tasks.jsonl, snapshots, graphs, embeddings, wheels, docker, sample_submission).
- `DataSets/public/wheelhouse/`: swegemma, adk_submission, adk_eval_core wheels (from Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse`).
- `AgenticSubmission/v0_baseline/`: baseline agent (E4B, no adapters). `v0_baseline_submission.zip` is its package.
- `Models/`: symlink to the CUDA checkpoint. MLX copy: `~/models/gemma-4-e4b-it-qat-w4a16-mlx`.
- `Tools/convert_ct_to_mlx.py`: lossless repack of the compressed-tensors checkpoint to MLX 4-bit.
- `Tools/serve_e4b_mlx.sh`: starts the local OpenAI-compatible server on `127.0.0.1:8123`.
- `PaperTrack/`: paper draft and ideas. `Rules/Overview/`: rules audit. `Designs/Paperwork/Plan_of_Attack.md`: plan.
- `.venv-harness` (swegemma, Python 3.13) and `.venv-mlx` (mlx-vlm, mlx-lm). Do not mix them.

## Commands
```bash
# serve the local model (competition sampling defaults)
Tools/serve_e4b_mlx.sh
# validate a submission directory
.venv-harness/bin/python -c "from pathlib import Path; from adk_submission import validate_directory; from swegemma.config import build_submission_limits; validate_directory(Path('AgenticSubmission/v0_baseline'), limits=build_submission_limits()[0])"
# evaluate locally (needs a model endpoint; Docker Desktop must be running)
.venv-harness/bin/swegemma eval --tasks DataSets/public/data/tasks.jsonl --snapshots-dir DataSets/public/data/snapshots --submission-dir AgenticSubmission/v0_baseline --results-dir results/run_01 --sandbox docker --concurrency 1
```
Docker has 8 GB RAM and each task container gets 4 GiB, so keep concurrency at 1 or 2.

## Gotchas
- Scratch files go in `/tmp`, never `/workspace`: `submit_patch` includes every untracked file there.
- Never edit `/workspace/pytest.ini`, `conftest.py`, or test files; the harness strips those diffs.
- Scored runs use the subprocess sandbox, which skips test-dependency install (about 35 tasks hit missing `inline_snapshot` and `dirty_equals`). Local Docker runs avoid that, so local pass rates look better.
- Port 8000 is taken on this machine; use 8123 for the model server.
- LoRA adapters must target the E4B base. The 31B adapter config in `LoRA Adapters/` is unusable.
- Training needs CUDA: use a Kaggle L4x4 notebook (no internet there), not the Mac.

## Do not
- Do not submit to Kaggle, accept terms, or download large data without asking.
- Do not print or commit credentials (`~/.kaggle/access_token`, any `*apiKey*.csv`).
- Do not touch `/Users/stewartbarteau/Desktop/Qwen3.6Cyber` or its frontier goal; the user said to ignore it here.
- Do not invent numbers for the paper. Every result needs a run behind it.

## Host-side verified research memory

- During design and paper research, query the canonical local Qdrant Edge shard at `/Users/stewartbarteau/Desktop/Ai Research and Preprint Vault/qdrant-edge-research-v1` before repeating literature searches.
- After opening and verifying primary sources, ingest full extracted text or exact relied-upon passages through `/Users/stewartbarteau/Desktop/Fraud-Predict Comp/src/rag_ingest.py`, including URL, title, year, and an evidence note.
- Ingest verified public research only. Never ingest competition snapshots, task data, model outputs, private code, credentials, unpublished scores, or hidden-test evidence.
- Preserve existing dense vectors and the scored text index. Use payload-only deterministic points, the shard lock, hash verification, live retrieval checks, and a receipt under this project's research documentation.
- This is a host-side research facility only. The scored Gemma runtime has no internet and may call only the nine allowed harness tools; never package the Edge shard or expose `rag_ingest` as an additional submission-runtime tool.
