"""Core helpers: repo layout, test running, harness-tool emulation."""
import ast
import json
import os
import re
import shutil
import subprocess
import tempfile

from config import REPOS_DIR, VENV, WS_DIR

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(VENV, "bin", "python")
SITE = os.path.join(VENV, "lib", "python3.13", "site-packages")
TEST_DIR_NAMES = {"tests", "test", "testing"}
SKIP_DIRS = {".git", "docs", "doc", "examples", "benchmarks", "bench", "build",
             "dist", ".tox", "venv", "scripts", "tasks", "tools", "ci", ".github",
             "json", "fuzz", "perf", "tutorials"}


# ---------------------------------------------------------------- layout
def is_test_path(rel):
    parts = rel.split(os.sep)
    base = parts[-1]
    if base.startswith("test_") or base.endswith("_test.py") or base == "conftest.py":
        return True
    return any(p in TEST_DIR_NAMES for p in parts[:-1])


def layout(repo_dir):
    """Return (import_root_rel, [source .py rel paths], [test .py rel paths])."""
    src_root = "src" if os.path.isdir(os.path.join(repo_dir, "src")) else ""
    sources, tests = [], []
    for root, dirs, files in os.walk(repo_dir):
        rel_root = os.path.relpath(root, repo_dir)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith(".egg-info")
                   and not d.startswith(".")]
        for f in files:
            if not f.endswith(".py"):
                continue
            rel = os.path.normpath(os.path.join(rel_root, f))
            if is_test_path(rel):
                if f.startswith("test_") or f.endswith("_test.py"):
                    tests.append(rel)
                continue
            if rel in ("setup.py", "noxfile.py", "fabfile.py", "conftest.py") or f.startswith("_version"):
                continue
            if src_root and not rel.startswith("src" + os.sep):
                continue
            if not src_root and rel_root == "." and f not in _single_module_ok(repo_dir):
                continue
            sources.append(rel)
    return src_root, sorted(sources), sorted(tests)


def _single_module_ok(repo_dir):
    # top-level single-module libraries (bottle.py, schema.py, xmltodict.py ...)
    name = os.path.basename(repo_dir).replace("python-", "").replace("-", "_")
    cands = {name + ".py", "bottle.py", "schema.py", "xmltodict.py", "tabulate.py"}
    return {c for c in cands if os.path.exists(os.path.join(repo_dir, c))}


# ---------------------------------------------------------------- env
def make_env(ws, src_root):
    env = dict(os.environ)
    root = os.path.join(ws, src_root) if src_root else ws
    env["PYTHONPATH"] = os.pathsep.join([root, PLUGIN_DIR])
    env["PATH"] = os.path.join(VENV, "bin") + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = VENV
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    env.pop("PYTEST_ADDOPTS", None)
    return env


def scrub(text, ws):
    """Rewrite local paths to what the competition sandbox would show."""
    text = text.replace(ws, "/workspace")
    text = text.replace(SITE, "/usr/local/lib/python3.13/site-packages")
    text = text.replace(os.path.join(VENV, "bin", "python"), "/usr/local/bin/python")
    text = text.replace(VENV, "/usr/local")
    text = re.sub(r"/tmp/claude-0/work/repos/[^/\s]+", "/workspace", text)
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return text


HIDDEN_PYTEST = ["-p", "no:cacheprovider", "-o", "addopts=", "-p", "no:randomly",
                 "-W", "ignore::DeprecationWarning"]


REPO_EXTRA = {"click": ["-m", "not stress"]}


def repo_extra(ws):
    return REPO_EXTRA.get(os.path.basename(ws).split("__")[0], [])


def run_tests(ws, src_root, targets=None, timeout=240):
    """Run pytest with the nodeid reporter; return dict nodeid->outcome."""
    fd, out = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    env = make_env(ws, src_root)
    env["NODEID_OUT"] = out
    cmd = [PY, "-m", "pytest", "-q", "-x" if False else "-q", "-p", "nodeid_reporter",
           "--timeout", "15", "--continue-on-collection-errors"] + HIDDEN_PYTEST + repo_extra(ws) + list(targets or [])
    try:
        subprocess.run(cmd, cwd=ws, env=env, capture_output=True, timeout=timeout)
        with open(out) as fh:
            return json.load(fh)
    except Exception:
        return None
    finally:
        if os.path.exists(out):
            os.unlink(out)


# ---------------------------------------------------------------- workspace
def make_workspace(repo, tag):
    src = os.path.join(REPOS_DIR, repo)
    ws = os.path.join(WS_DIR, f"{repo}__{tag}")
    if os.path.exists(ws):
        shutil.rmtree(ws)
    shutil.copytree(src, ws, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc",
                                                           ".pytest_cache", "*.egg-info"))
    return ws


def git_init(ws):
    g = ["git", "-c", "user.name=dev", "-c", "user.email=dev@example.com",
         "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"]
    subprocess.run(g + ["init", "-q"], cwd=ws, check=True)
    with open(os.path.join(ws, ".git", "info", "exclude"), "a") as fh:
        fh.write("__pycache__/\n*.pyc\n.pytest_cache/\n*.egg-info/\nbuild/\ndist/\n.coverage\n")
    subprocess.run(g + ["add", "-A"], cwd=ws, check=True)
    subprocess.run(g + ["commit", "-q", "-m", "base"], cwd=ws, check=True)


class Harness:
    """Local emulation of the competition tools, with sandbox-like limits."""

    RUN_LIMIT = 5000
    READ_MAX_LINES = 150
    READ_MAX_CHARS = 10000

    def __init__(self, ws, src_root, cmd_timeout=120):
        self.ws = ws
        self.src_root = src_root
        self.env = make_env(ws, src_root)
        self.cmd_timeout = cmd_timeout
        self.calls = 0
        self.tmp = os.path.join(os.path.dirname(WS_DIR), "tmpdirs", os.path.basename(ws))
        os.makedirs(self.tmp, exist_ok=True)

    def _path(self, p):
        p = p.lstrip("/")
        if p.startswith("workspace/"):
            p = p[len("workspace/"):]
        if ".." in p.split("/"):
            raise ValueError("path traversal")
        return os.path.join(self.ws, p)

    def run_command(self, command):
        self.calls += 1
        real = command.replace("/workspace", self.ws).replace("/tmp/", self.tmp + "/")
        # hidden flags keep pytest output stable and independent of repo addopts
        real = re.sub(r"python -m pytest", "python -m pytest " + " ".join(
            "'%s'" % a if (a == "addopts=" or " " in a) else a for a in HIDDEN_PYTEST + repo_extra(self.ws)), real)
        try:
            p = subprocess.run(["/bin/bash", "-c", real], cwd=self.ws, env=self.env,
                               capture_output=True, text=True, timeout=self.cmd_timeout)
            out = (p.stdout or "") + (p.stderr or "")
            code = p.returncode
        except subprocess.TimeoutExpired:
            out, code = f"Command timed out after {self.cmd_timeout}s", 124
        out = scrub(out.replace(self.tmp + "/", "/tmp/"), self.ws)
        truncated = len(out) > self.RUN_LIMIT
        if truncated:
            out = out[: self.RUN_LIMIT]
        return {"output": out, "exit_code": code, "truncated": truncated}

    def read_file(self, filepath, start_line=None, end_line=None):
        self.calls += 1
        fp = self._path(filepath)
        if not os.path.isfile(fp):
            return {"error": f"File not found: {filepath}"}
        with open(fp, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        s = max(1, start_line or 1)
        e = min(len(lines), end_line or len(lines))
        e = min(e, s + self.READ_MAX_LINES - 1)
        chunk = lines[s - 1:e]
        return {"filepath": filepath, "start_line": s, "end_line": e,
                "total_lines": len(lines), "lines": chunk}

    def edit_file(self, filepath, old_string, new_string, allow_multiple=False):
        self.calls += 1
        fp = self._path(filepath)
        if not os.path.isfile(fp) or os.path.getsize(fp) == 0:
            return {"error": f"File not found or empty: {filepath}"}
        if not old_string:
            return {"error": "old_string must not be empty"}
        with open(fp, encoding="utf-8") as fh:
            text = fh.read()
        n = text.count(old_string)
        if n == 0:
            return {"error": f"old_string not found in {filepath}"}
        if n > 1 and not allow_multiple:
            return {"error": f"old_string matches {n} locations in {filepath}; "
                             "add surrounding context to make it unique or set allow_multiple=True"}
        text = text.replace(old_string, new_string) if allow_multiple else text.replace(old_string, new_string, 1)
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(text)
        return {"status": "success", "filepath": filepath, "replacements": n if allow_multiple else 1}

    def write_file(self, filepath, content):
        self.calls += 1
        fp = self._path(filepath)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(content)
        return {"status": "success", "filepath": filepath}

    def submit_patch(self):
        subprocess.run(["git", "add", "-N", "."], cwd=self.ws, capture_output=True)
        p = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=self.ws,
                           capture_output=True, text=True)
        diff = p.stdout
        files = len(re.findall(r"^diff --git", diff, re.M))
        return {"status": "submitted", "patch_size": len(diff), "files_changed": files,
                "patch": diff}
