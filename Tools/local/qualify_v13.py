"""Qualify external-task grading with the official subprocess verifier (no model call).

Run inside macOS Seatbelt using the prepared .venv-v13-eval environment.
The task and snapshot must already exist; no downloads or dependency installs occur here.
An empty patch must fail real assertions, and the reference patch must pass.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
import time

from adk_submission import ModelRegistry
from swegemma.config import EvalConfig
from swegemma.harness.verification import verify_task
from swegemma.models import load_tasks
from swegemma.sandbox.subprocess import SubprocessManager


async def qualify(data: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    tasks_path = data / "data/tasks.jsonl"
    tasks = load_tasks(tasks_path)
    if len(tasks) != 1:
        raise ValueError("qualification requires exactly one explicit external task")
    task = tasks[0]
    if task.repo in {"fastapi/fastapi", "psf/requests", "Textualize/rich", "encode/httpx"}:
        raise ValueError("competition development repositories are excluded")
    cfg = EvalConfig(tasks_path=tasks_path, snapshots_dir=data / "snapshots",
                     results_dir=output, submission_dir=Path("AgenticSubmission/v13_orchestrator"),
                     models=ModelRegistry(), sandbox="subprocess", max_time_minutes=4,
                     max_tool_calls=40, max_turns=60, timeout_seconds=300,
                     verification_timeout_seconds=300)
    manager = SubprocessManager(timeout_seconds=300)
    results = {}
    try:
        for name, patch in [("empty", ""), ("reference", task.patch)]:
            started = time.perf_counter()
            result = await verify_task(manager, cfg, task,
                                       data / "snapshots" / f"{task.instance_id}.tgz",
                                       agent_patch=patch, start_time=started)
            results[name] = result.model_dump(mode="json")
            (output / f"{name}.json").write_text(json.dumps(results[name], indent=2))
            print(name, "resolved=", result.resolved, "exit=", result.test_exit_code,
                  "error=", result.error, flush=True)
    finally:
        manager.cleanup_all()
    empty, reference = results["empty"], results["reference"]
    passed = (not empty["resolved"] and empty["test_exit_code"] == 1
              and "FAILED" in empty.get("test_output", "")
              and reference["resolved"] and reference["test_exit_code"] == 0)
    (output / "gate.json").write_text(json.dumps({"passed": passed,
         "instance_id": task.instance_id, "sandbox": "subprocess+macOS Seatbelt",
         "criterion": "empty assertion failure and reference success", "results": results}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(qualify(args.data.resolve(), args.output.resolve())))
