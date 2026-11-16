"""Hardened executor for repo-derived code. Mirrors the harness's no-Docker mode (isolated interpreter, new process group,
killed on timeout) plus rlimits and a scrubbed env. Interpreter = Python 3.13 to match python:3.13-slim (swebench-sandbox).
For the authoritative run, docker_verify.sh re-executes the validator inside the real image with --network none."""
import json, os, resource, signal, subprocess, sys, tempfile
from pathlib import Path
RUNNER = str(Path(__file__).with_name("_runner.py"))
PY = os.environ.get("LORA_PY") or sys.executable

def _limits():
    os.setsid()
    resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

def run(src, fname, calls, trace=False, timeout=25):
    with tempfile.TemporaryDirectory(prefix="lorasbx_") as cwd:
        p = subprocess.Popen([PY, "-I", RUNNER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                             cwd=cwd, env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0", "HOME": cwd, "TMPDIR": cwd}, preexec_fn=_limits)
        try:
            out, _ = p.communicate(json.dumps({"src": src, "fname": fname, "calls": calls, "trace": trace}), timeout=timeout)
            return json.loads(out) if p.returncode == 0 else None
        except Exception:
            try: os.killpg(p.pid, signal.SIGKILL)
            except Exception: pass
            return None
