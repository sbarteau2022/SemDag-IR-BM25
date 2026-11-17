"""meta: deterministic preflight for the brigade loop. One compact JSON report on stdout.

args: [issue text]   (the whole problem statement; a stringified list is also accepted)

What it does, with no model reasoning involved:
  1. readiness   - can pytest and the usual test-only dependencies be imported here
  2. checkpoint  - which git baseline the harness patch is taken against
  3. localize    - repo_eval locate: typed graph, parity, ranked edit sites, nearest tests
  4. source      - the exact current text of the top 3 sites, so the first edit can quote it
  5. baseline    - the nearest tests, run once, time-boxed, with collected/passed/failed counts
                   and the reason for any red (assertion vs collection/import error)

"Check the instrument": a green exit code with 0 collected tests is reported as
`no_tests_collected`, never as green. The report is cached (temp dir, outside the patch), so
a second call returns it without re-running anything. The script never raises.
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wsroot  # noqa: E402
os.environ["SEMDAG_CACHE"] = wsroot.cache_root()
import cache  # noqa: E402
import impact  # noqa: E402
import repo_eval  # noqa: E402

BUDGET = 6000            # characters of JSON printed (about 2k tokens)
SRC_LINES = 40           # lines of source shown per site
SRC_CHARS = 1600         # characters of source shown per site
SITES_WITH_SOURCE = 3
PYTEST_TIMEOUT = 60
TEST_FILES = 2
OPTIONAL_DEPS = ("pytest", "inline_snapshot", "dirty_equals")
COUNT = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")
ENV_BROKEN = re.compile(r"No module named '([\w.]+)'|pydantic-core version \(\S+\) is incompatible")
COLLECT_ERR = re.compile(r"ERROR collecting|ImportError|ModuleNotFoundError|SyntaxError|"
                         r"IndentationError|errors? during collection")


def _dumps(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def readiness():
    return {name: importlib.util.find_spec(name) is not None for name in OPTIONAL_DEPS}


def run_env():
    """Environment for child processes: no bytecode written into the repository, and `python`
    resolves to the interpreter running this script."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    return env


def pytest_cmd(files):
    return "python -m pytest " + " ".join(files) + " -q -x -p no:cacheprovider"


def run_pytest(repo, files, timeout=PYTEST_TIMEOUT):
    """Run the given test files once; return counts and why any red happened."""
    res = {"cmd": pytest_cmd(files), "rc": None, "collected": 0, "passed": 0, "failed": 0,
           "errors": 0, "skipped": 0, "red_reason": None, "env_broken": None, "tail": ""}
    if not files:
        res["red_reason"] = "no_test_files"
        return res
    argv = [sys.executable, "-m", "pytest", *files, "-q", "-x", "-p", "no:cacheprovider"]
    try:
        p = subprocess.run(argv, cwd=repo, capture_output=True, text=True, timeout=timeout,
                           env=run_env())
        out, res["rc"] = (p.stdout or "") + (p.stderr or ""), p.returncode
    except subprocess.TimeoutExpired as ex:
        out = (ex.stdout or "") if isinstance(ex.stdout, str) else ""
        res["red_reason"] = "timeout"
        res["tail"] = out[-600:]
        return res
    except OSError as ex:
        res["red_reason"] = "pytest_unavailable"
        res["tail"] = str(ex)[:200]
        return res
    for n, kind in COUNT.findall(out):
        key = "errors" if kind.startswith("error") else kind
        if key in res:
            res[key] += int(n)
    res["collected"] = res["passed"] + res["failed"] + res["errors"] + res["skipped"]
    env = ENV_BROKEN.search(out)
    if env:
        res["env_broken"] = env.group(0)[:120]
    if res["rc"] == 0 and res["collected"] > 0:
        res["red_reason"] = None
    elif res["collected"] == 0 and not res["errors"]:
        res["red_reason"] = "no_tests_collected" if "No module named pytest" not in out \
            else "pytest_unavailable"
    elif COLLECT_ERR.search(out) and res["failed"] == 0:
        res["red_reason"] = "collection_error"
    elif res["failed"]:
        res["red_reason"] = "assertion" if ("AssertionError" in out or "assert " in out) \
            else "test_failure"
    else:
        res["red_reason"] = "nonzero_exit"
    lines = [ln for ln in out.splitlines() if ln.strip()]
    res["tail"] = "\n".join(lines[-12:])[-900:]
    return res


def site_source(repo, site):
    path = os.path.join(repo, site["file"])
    try:
        with open(path, errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None, None
    a = max(1, int(site.get("line") or 1))
    b = min(len(lines), int(site.get("end_line") or a))
    shown_b = min(b, a + SRC_LINES - 1)
    text = "\n".join(lines[a - 1:shown_b])
    if len(text) > SRC_CHARS:
        text = text[:SRC_CHARS]
        shown_b = a + text.count("\n")
    return text, (a, shown_b, b)


def preflight(argv):
    t0 = time.time()
    ms = {}
    opt = repo_eval.parse_args(argv)
    repo, cid, issue = opt["repo"], opt["container"], opt["issue"]
    key = hashlib.sha256(issue.encode()).hexdigest()[:16]
    try:
        cached = cache.read(cid, "meta.json")
        if cached.get("issue_key") == key or not issue:
            cached["cached"] = True
            return cached
    except (OSError, ValueError):
        pass
    if not issue:
        return {"error": "no issue text was passed", "hint": "args: [the whole problem statement]"}

    report = {"mode": "preflight", "issue_key": key, "ready": readiness(),
              "checkpoint_ref": impact.baseline_ref(repo)}
    ms["ready"] = int((time.time() - t0) * 1000)

    loc = repo_eval.locate(opt)
    ms["localize"] = int((time.time() - t0) * 1000) - sum(ms.values())
    if loc.get("error"):
        report["localize_error"] = loc["error"]
    sites = loc.get("top_edit_sites") or []
    shown = []
    for s in sites[:SITES_WITH_SOURCE]:
        text, span = site_source(repo, s)
        item = {"rank": s["rank"], "file": s["file"], "qualname": s["qualname"],
                "lines": f"{s['line']}-{s['end_line']}"}
        if text is not None:
            item["source_start_line"] = span[0]
            item["source"] = text
            if span[1] < span[2]:
                item["source_truncated_at_line"] = span[1]
        shown.append(item)
    report["sites"] = shown
    report["other_sites"] = [f"{s['file']}:{s['line']} {s['qualname']}" for s in sites[3:8]]
    tests = (loc.get("tests_near_sites") or [])[:TEST_FILES]
    report["tests_near_sites"] = tests

    if report["ready"]["pytest"] and tests:
        report["baseline_tests"] = run_pytest(repo, tests)
    else:
        report["baseline_tests"] = {"red_reason": "pytest_unavailable" if not report["ready"]["pytest"]
                                    else "no_test_files"}
    ms["baseline_tests"] = int((time.time() - t0) * 1000) - sum(ms.values())
    report["test_cmd"] = pytest_cmd(tests) if tests else None
    report["next"] = _advise(report)
    report["ms"] = ms

    try:
        cache.write(cid, "meta.json", report)
    except OSError:
        pass
    return report


def _advise(r):
    bt = r.get("baseline_tests") or {}
    if not r.get("sites"):
        return "No edit site ranked. Search the identifiers from the issue with read_file."
    if bt.get("env_broken") or bt.get("red_reason") in ("pytest_unavailable", "collection_error"):
        return ("Tests cannot be trusted here; verify with a /tmp repro script run via "
                "run_command, plus the audit's syntax and name checks.")
    return ("Write a /tmp repro (run_command heredoc) that fails now, edit the top site, "
            "make the repro pass, then let the audit run test_cmd.")


def _trim(out):
    while len(_dumps(out)) > BUDGET:
        srcs = [s for s in out.get("sites", []) if len(s.get("source", "")) > 300]
        if out.get("other_sites"):
            out["other_sites"].pop()
        elif srcs:
            longest = max(srcs, key=lambda s: len(s["source"]))
            longest["source"] = longest["source"][: len(longest["source"]) * 3 // 4]
            longest["source_truncated"] = True
        elif out.get("baseline_tests", {}).get("tail"):
            out["baseline_tests"]["tail"] = out["baseline_tests"]["tail"][-300:]
            if len(_dumps(out)) > BUDGET:
                out["baseline_tests"]["tail"] = ""
        else:
            break
    return out


def main(argv=None):
    try:
        out = preflight(sys.argv[1:] if argv is None else argv)
        out = _trim(dict(out))
    except Exception as ex:  # never hand the model a traceback
        out = {"error": f"{type(ex).__name__}: {ex}"[:300],
               "hint": "args: [the whole problem statement]"}
    print(_dumps(out))
    return out


if __name__ == "__main__":
    main()
