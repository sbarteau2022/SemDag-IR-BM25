"""Tiny pytest plugin: write {nodeid: outcome} to $NODEID_OUT as JSON."""
import json
import os

_results = {}


def pytest_runtest_logreport(report):
    nid = report.nodeid
    if report.when == "call":
        _results[nid] = report.outcome
    elif report.when == "setup" and report.outcome != "passed":
        _results[nid] = "error" if report.failed else report.outcome
    elif report.when == "teardown" and report.failed:
        _results[nid] = "error"


def pytest_collectreport(report):
    if report.failed:
        _results["__collect__::" + report.nodeid] = "error"


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("NODEID_OUT")
    if out:
        with open(out, "w") as fh:
            json.dump(_results, fh)
