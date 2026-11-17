"""Tools/telemetry: SQLite store, stream-reassembling proxy, ingest, export, report."""

from __future__ import annotations

import json
import sqlite3
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import db as tdb
import export_run
import ingest
import llm_proxy
import report
from conftest import diff, step


# ---------------------------------------------------------------- db

def test_connect_is_idempotent(tmp_path):
    p = tmp_path / "t.sqlite"
    tdb.connect(p).close()
    con = tdb.connect(p)
    assert con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "1"
    tdb.insert(con, "runs", {"run_id": "r", "arm": "a"})
    tdb.insert(con, "runs", {"run_id": "r", "arm": "b"})  # replace, not duplicate
    assert [tuple(r) for r in con.execute("SELECT arm FROM runs")] == [("b",)]


# ---------------------------------------------------------------- proxy accumulator

def test_accumulator_reassembles_stream():
    acc = llm_proxy.Accumulator(t0=0.0)
    acc.feed({"id": "x", "model": "m", "created": 1,
              "choices": [{"delta": {"role": "assistant", "reasoning": "think "}}]}, 0.5)
    acc.feed({"choices": [{"delta": {"reasoning": "more"}}]}, 0.6)
    acc.feed({"choices": [{"delta": {"content": "Hi"}}]}, 0.9)
    acc.feed({"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": "c1", "type": "function",
         "function": {"name": "read_file", "arguments": "{\"filepath\": \"a\"}"}}]},
        "finish_reason": "tool_calls"}]}, 1.2)
    acc.feed({"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 5,
                                       "prompt_tokens_details": {"cached_tokens": 3}}}, 1.3)
    r = acc.response()
    msg = r["choices"][0]["message"]
    assert msg["reasoning"] == "think more" and msg["content"] == "Hi"
    assert msg["tool_calls"] == [{"id": "c1", "type": "function",
                                  "function": {"name": "read_file",
                                               "arguments": "{\"filepath\": \"a\"}"}}]
    assert r["choices"][0]["finish_reason"] == "tool_calls" and r["id"] == "x"
    assert r["usage"]["completion_tokens"] == 5
    assert acc.ttft == 0.5 and acc.t_first_reasoning == 0.5 and acc.t_first_action == 0.9
    assert acc.reasoning_chunks == 2 and acc.t_last_reasoning == 0.6


def test_accumulator_empty_stream_defaults():
    r = llm_proxy.Accumulator(0.0).response()
    assert r["choices"][0]["message"]["content"] is None
    assert r["choices"][0]["finish_reason"] == "stop" and "usage" not in r


def test_request_fields_reads_extra_body_budget():
    f = llm_proxy.request_fields({"messages": [1, 2], "tools": [1], "max_tokens": 8192,
                                  "extra_body": {"thinking_token_budget": 4096}, "stream": True})
    assert f == {"req_messages": 2, "req_tools": 1, "req_max_tokens": 8192,
                 "req_thinking_budget": 4096, "req_temperature": None, "client_stream": 1}


# ---------------------------------------------------------------- proxy end to end

class FakeUpstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        data = b'{"data": [{"id": "m"}]}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeUpstream.seen.append(body)
        if body["messages"][0].get("content") == "boom":
            data = b'{"error": "bad"}'
            self.send_response(500)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        chunks = [
            {"id": "u1", "model": "m", "created": 1, "choices": [{"delta": {"reasoning": "r"}}]},
            {"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 4, "completion_tokens": 2}},
        ]
        for c in chunks:
            self.wfile.write(f"data: {json.dumps(c)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True


@pytest.fixture
def proxy(tmp_path):
    FakeUpstream.seen = []
    up = ThreadingHTTPServer(("127.0.0.1", 0), FakeUpstream)
    threading.Thread(target=up.serve_forever, daemon=True).start()
    dbp = tmp_path / "p.sqlite"
    px = llm_proxy.serve(0, f"127.0.0.1:{up.server_address[1]}", str(dbp), "run_t", timeout=10)
    threading.Thread(target=px.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{px.server_address[1]}", dbp
    px.shutdown()
    up.shutdown()


def _post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=10)


def test_proxy_upgrades_to_stream_and_logs(proxy):
    url, dbp = proxy
    r = json.loads(_post(url + "/v1/chat/completions",
                         {"model": "m", "messages": [{"role": "user", "content": "hi"}],
                          "max_tokens": 8192}).read())
    assert r["object"] == "chat.completion"
    assert r["choices"][0]["message"] == {"role": "assistant", "content": "ok", "reasoning": "r"}
    assert FakeUpstream.seen[-1]["stream"] is True
    assert FakeUpstream.seen[-1]["stream_options"] == {"include_usage": True}
    row = sqlite3.connect(dbp).execute(
        "SELECT run_id, ttft_s, completion_tokens, req_max_tokens, client_stream, "
        "reasoning_chunks, upstream_status, error FROM llm_calls").fetchone()
    assert row[0] == "run_t" and row[1] is not None and row[1] >= 0
    assert row[2:] == (2, 8192, 0, 1, 200, None)


def test_proxy_relays_client_stream(proxy):
    url, dbp = proxy
    body = _post(url + "/v1/chat/completions",
                 {"model": "m", "stream": True,
                  "messages": [{"role": "user", "content": "hi"}]}).read().decode()
    assert body.count("data: ") == 4 and body.rstrip().endswith("data: [DONE]")
    assert sqlite3.connect(dbp).execute("SELECT client_stream FROM llm_calls").fetchone()[0] == 1


def test_proxy_forwards_upstream_error_and_records_it(proxy):
    url, dbp = proxy
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(url + "/v1/chat/completions", {"model": "m", "messages": [{"content": "boom"}]})
    assert e.value.code == 500
    row = sqlite3.connect(dbp).execute("SELECT upstream_status, error FROM llm_calls").fetchone()
    assert row[0] == 500 and "bad" in row[1]


def test_proxy_passthrough_get(proxy):
    url, dbp = proxy
    assert json.loads(urllib.request.urlopen(url + "/v1/models", timeout=5).read())["data"]
    assert sqlite3.connect(dbp).execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0] == 0


# ---------------------------------------------------------------- ingest

def test_patch_files_drops_tests():
    p = diff("src/a.py") + diff("tests/test_a.py") + diff("pkg/conftest.py") + diff("b_test.py")
    assert ingest.patch_files(p) == ["src/a.py"]
    assert ingest.patch_files("") == []


def test_patch_files_reads_headerless_gold_patch():
    # public tasks.jsonl gold patches start at '--- a/' with no 'diff --git' header
    gold = ("--- a/src/pkg/_types.py\n+++ b/src/pkg/_types.py\n@@ -1 +1 @@\n-a\n+b\n"
            "--- a/src/pkg/models.py\n+++ b/src/pkg/models.py\n@@ -1 +1 @@\n-a\n+b\n"
            "--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-a\n")
    assert ingest.patch_files(gold) == ["src/pkg/_types.py", "src/pkg/models.py"]
    # a diff --git block also carries a +++ line: no duplicates
    assert ingest.patch_files(diff("src/a.py")) == ["src/a.py"]


def test_empty_gold_is_unknown_not_wrong_file(make_run, tmp_path):
    rd = make_run("r", [{"instance_id": "t", "steps": [], "patch": diff("src/a.py")}])
    tasks = _tasks_jsonl(tmp_path, {"t": ""})
    dbp = tmp_path / "t.sqlite"
    ingest.ingest_run(dbp, rd, "R", tasks_path=tasks)
    row = tdb.connect(dbp).execute("SELECT touched_gold_file, failure_class FROM tasks").fetchone()
    assert tuple(row) == (None, "unresolved_unclassified")


@pytest.mark.parametrize("row,cls", [
    ({"resolved": 1}, "resolved"),
    ({"error": "Agent exceeded session timeout (5 min)"}, "timeout"),
    ({"error": "boom"}, "harness_error"),
    ({"patch_bytes": 0}, "no_patch"),
    ({"test_env_missing_dep": 1}, "test_env_broken"),
    ({"test_env_broken": 1, "error": "Agent exceeded session timeout"}, "test_env_broken"),
    ({"destructive_write": 1, "touched_gold_file": 1}, "destructive_write"),
    ({"touched_gold_file": 0}, "wrong_file"),
    ({"touched_gold_file": 1, "touched_gold_function": 0}, "right_file_wrong_function"),
    ({"touched_gold_file": 1, "touched_gold_function": 1}, "right_function_wrong_fix"),
    ({"touched_gold_file": 1}, "right_file_unresolved"),
    ({}, "unresolved_unclassified"),
])
def test_classify_order(row, cls):
    base = {"resolved": 0, "error": None, "patch_bytes": 10, "test_env_missing_dep": 0,
            "touched_gold_file": None, "touched_gold_function": None}
    assert ingest.classify({**base, **row}) == cls


def _tasks_jsonl(tmp_path, gold):
    p = tmp_path / "tasks.jsonl"
    p.write_text("\n".join(json.dumps({"instance_id": k, "patch": v}) for k, v in gold.items()))
    return p


def _fixture_run(make_run):
    steps_ok = [
        step(1, source="system", event_type="system_instruction", ts=100.0),
        step(2, message="plan the fix", tool="write_file",
             args={"filepath": "/tmp/repro.py"}, ts=101.0, pt=1000),
        step(3, message="edit", tool="edit_file", args={"filepath": "src/a.py"},
             obs={"status": "error", "error_type": "FileEditError", "error_message": "nf"},
             ts=102.0, pt=2000),
        step(4, message="retry", tool="edit_file", args={"filepath": "src/a.py"},
             ts=103.0, elapsed=30.0, pt=3000),
        step(5, message="", tool="run_command", args={"command": "python -m pytest -x"},
             obs={"status": "ok", "exit_code": 1}, ts=104.0, pt=4000),
        step(6, message="ask helper", tool="code_analyzer", args={"request": "x"},
             ts=105.0, pt=5000),
        step(7, author="code_analyzer", message="sub think", tool="read_file",
             args={"filepath": "src/a.py"}, ts=106.0, pt=600),
        step(8, author="code_analyzer", event_type="final", message="done", ts=107.0, pt=700),
        step(9, event_type="compaction", ts=108.0, pt=0, ct=0),
        step(10, event_type="final", message="", tool="submit_patch", ts=109.0, pt=5500),
    ]
    steps_wrong = [step(1, message="t", tool="edit_file", args={"filepath": "src/z.py"},
                        ts=200.0)]
    return make_run("run", [
        {"instance_id": "t_ok", "resolved": False, "steps": steps_ok,
         "patch": diff("src/a.py"), "test_log": "1 failed"},
        {"instance_id": "t_wrong", "resolved": False, "steps": steps_wrong,
         "patch": diff("src/z.py"), "test_log": ""},
        {"instance_id": "t_dep", "resolved": False, "steps": [], "patch": diff("src/a.py"),
         "test_log": "E   ModuleNotFoundError: No module named 'inline_snapshot'"},
        {"instance_id": "t_none", "resolved": False, "steps": None, "patch": ""},
    ])


def test_ingest_end_to_end(make_run, tmp_path):
    rd = _fixture_run(make_run)
    (rd / "run_meta.json").write_text(json.dumps(
        {"arm": "v6.1", "sampling": {"thinking_config": {"thinking_budget": 4096}},
         "budget": {"max_time_minutes": 5}}))
    tasks = _tasks_jsonl(tmp_path, {"t_ok": diff("src/a.py"), "t_wrong": diff("src/a.py"),
                                    "t_dep": diff("src/a.py"), "t_none": diff("src/a.py")})
    dbp = tmp_path / "t.sqlite"
    con = tdb.connect(dbp)
    # two proxy calls inside t_ok's window, one far away
    for i, w in enumerate((101.5, 104.5, 5000.0)):
        tdb.insert(con, "llm_calls", {"run_id": "R", "call_id": f"c{i}", "wall_start": w})
    out = ingest.ingest_run(dbp, rd, "R", tasks_path=tasks)
    assert out == {"tasks": 4, "llm_calls_attached": 2}

    t = {r["instance_id"]: dict(r) for r in con.execute("SELECT * FROM tasks")}
    ok = t["t_ok"]
    assert ok["tool_calls"] == 7 and ok["tool_errors"] == 1 and ok["edit_errors"] == 1
    assert ok["first_edit_s"] == 30.0           # first *successful* edit
    assert ok["repro_before_edit"] == 1 and ok["ran_tests"] == 1
    assert ok["subagent_calls"] == 1 and ok["subagent_steps"] == 2
    assert ok["compactions"] == 1 and ok["peak_prompt_tokens"] == 5500
    assert ok["touched_gold_file"] == 1 and ok["failure_class"] == "right_file_unresolved"
    assert ok["thinking_tokens"] is None        # no tokenizer given
    assert ok["thinking_chars"] == len("plan the fix" "edit" "retry" "ask helper" "sub think")
    assert t["t_wrong"]["failure_class"] == "wrong_file"
    assert t["t_dep"]["failure_class"] == "test_env_broken"
    assert t["t_none"]["failure_class"] == "no_patch" and t["t_none"]["steps"] == 0

    nested = con.execute("SELECT name, nested_steps, depth FROM tool_calls "
                         "WHERE instance_id='t_ok' ORDER BY seq").fetchall()
    assert ("code_analyzer", 2, 0) in [tuple(r) for r in nested]
    assert ("read_file", None, 1) in [tuple(r) for r in nested]
    rc = con.execute("SELECT exit_code, ok FROM tool_calls WHERE name='run_command'").fetchone()
    assert tuple(rc) == (1, 1)                  # nonzero exit is not a tool failure
    st = con.execute("SELECT thinking_text, context_frac FROM steps "
                     "WHERE instance_id='t_ok' AND step_id=2").fetchone()
    assert st[0] == "plan the fix" and st[1] == round(1000 / 32768, 4)

    # re-ingest replaces rows instead of duplicating them
    ingest.ingest_run(dbp, rd, "R", tasks_path=tasks)
    assert con.execute("SELECT COUNT(*) FROM tool_calls WHERE run_id='R'").fetchone()[0] == 8


class _FakeTok:
    def encode(self, text, add_special_tokens=False):
        class E:
            ids = text.split()
        return E()


def test_thinking_budget_flag_with_tokenizer(make_run, tmp_path, monkeypatch):
    long = "w " * 5000
    rd = make_run("r", [{"instance_id": "t", "steps": [
        step(1, message=long, tool="read_file"), step(2, message="short", tool="read_file")],
        "patch": diff("a.py")}])
    (rd / "run_meta.json").write_text(json.dumps(
        {"sampling": {"thinking_config": {"thinking_budget": 4096}}}))
    monkeypatch.setattr(ingest, "load_tokenizer", lambda p: _FakeTok())
    dbp = tmp_path / "t.sqlite"
    ingest.ingest_run(dbp, rd, "R", tokenizer="x")
    con = tdb.connect(dbp)
    row = con.execute("SELECT thinking_tokens, thinking_calls_over_budget FROM tasks").fetchone()
    assert tuple(row) == (5001, 1)
    view = con.execute("SELECT thinking_budget, over_thinking_budget FROM v_thinking_budget "
                       "ORDER BY step_id").fetchall()
    assert [tuple(r) for r in view] == [(4096, 1), (4096, 0)]


def test_ingest_empty_run_dir(tmp_path):
    (tmp_path / "empty").mkdir()
    assert ingest.ingest_run(tmp_path / "t.sqlite", tmp_path / "empty", "E") == \
        {"tasks": 0, "llm_calls_attached": 0}


def test_parse_obs_shapes():
    assert ingest.parse_obs(None)["chars"] == 0
    assert ingest.parse_obs({"content": "plain"}) == {"raw": "plain", "chars": 5}
    assert ingest.parse_obs({"content": "[1, 2]"})["chars"] == 6
    assert ingest.parse_obs({"content": '{"status": "error"}'})["status"] == "error"


# ---------------------------------------------------------------- export + report

def test_export_and_report(make_run, tmp_path):
    rd = _fixture_run(make_run)
    dbp = tmp_path / "t.sqlite"
    ingest.ingest_run(dbp, rd, "R1", arm="a")
    ingest.ingest_run(dbp, rd, "R2", arm="b")
    out_db = tmp_path / "one.sqlite"
    steps_jsonl = tmp_path / "steps.jsonl"
    counts = export_run.export(str(dbp), "R1", str(out_db), str(steps_jsonl))
    assert counts["tasks"] == 4 and counts["runs"] == 1
    one = sqlite3.connect(out_db)
    assert one.execute("SELECT DISTINCT run_id FROM tasks").fetchall() == [("R1",)]
    lines = [json.loads(l) for l in steps_jsonl.read_text().splitlines()]
    assert lines and all(l["run_id"] == "R1" for l in lines)
    assert any(l["thinking_text"] == "plan the fix" for l in lines)

    md = report.build(tdb.connect(dbp), "R1")
    assert "Resolved 0/4" in md and "| edit_file |" in md and "unresolved_unclassified" in md
    assert "Model calls (proxy)" not in md      # no proxy rows for this run


def test_report_percentile_helpers():
    assert report.pct([3, None, 1, 2], 0.5) == 2 and report.pct([], 0.5) is None
    assert report.fmt(None) == "-" and report.fmt(1.234) == "1.23" and report.fmt(3) == "3"


def test_destructive_write_vs_new_file(make_run, tmp_path):
    new_file = ("diff --git a/src/new.py b/src/new.py\nnew file mode 100644\n--- /dev/null\n"
                "+++ b/src/new.py\n@@ -0,0 +1 @@\n+x\n")
    rd = make_run("r", [
        {"instance_id": "over", "steps": [step(1, tool="write_file",
                                               args={"filepath": "/workspace/src/a.py"})],
         "patch": diff("src/a.py")},
        {"instance_id": "new", "steps": [step(1, tool="write_file",
                                              args={"filepath": "src/new.py"})],
         "patch": new_file},
        {"instance_id": "tmp", "steps": [step(1, tool="write_file",
                                              args={"filepath": "/tmp/repro.py"})],
         "patch": diff("src/a.py")},
    ])
    tasks = _tasks_jsonl(tmp_path, {k: diff("src/a.py") for k in ("over", "new", "tmp")})
    dbp = tmp_path / "t.sqlite"
    ingest.ingest_run(dbp, rd, "R", tasks_path=tasks)
    got = {r[0]: (r[1], r[2]) for r in tdb.connect(dbp).execute(
        "SELECT instance_id, destructive_write, failure_class FROM tasks")}
    assert got["over"] == (1, "destructive_write")
    assert got["new"] == (0, "wrong_file")
    assert got["tmp"] == (0, "right_file_unresolved")


def test_migration_adds_column_to_old_store(tmp_path):
    p = tmp_path / "old.sqlite"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE tasks (run_id TEXT, instance_id TEXT, PRIMARY KEY (run_id, instance_id))")
    con.commit(); con.close()
    cols = {r[1] for r in tdb.connect(p).execute("PRAGMA table_info(tasks)")}
    assert "destructive_write" in cols


def test_env_broken_pydantic_core_mismatch():
    log = ("E   SystemError: The installed pydantic-core version (2.50.4) is incompatible with "
           "the current pydantic version, which requires 2.46.4.")
    assert ingest.ENV_BROKEN.search(log)
    assert not ingest.ENV_BROKEN.search("E   AssertionError: assert 1 == 2\n1 failed, 7 passed")


def test_agent_saw_env_broken(make_run, tmp_path):
    bad = {"status": "ok", "stdout": "E   SystemError: The installed pydantic-core version (2.50.4) "
           "is incompatible with the current pydantic version, which requires 2.46.4."}
    rd = make_run("r", [
        {"instance_id": "a", "steps": [step(1, tool="run_command", args={"command": "pytest"}, obs=bad)],
         "patch": diff("src/a.py"), "test_log": bad["stdout"]},
        {"instance_id": "b", "steps": [step(1, tool="run_command", args={"command": "pytest"})],
         "patch": diff("src/a.py"), "test_log": "1 failed"},
    ])
    dbp = tmp_path / "t.sqlite"
    ingest.ingest_run(dbp, rd, "R")
    got = {r[0]: tuple(r[1:]) for r in tdb.connect(dbp).execute(
        "SELECT instance_id, agent_saw_env_broken, test_env_broken, failure_class FROM tasks")}
    assert got["a"] == (1, 1, "test_env_broken")
    assert got["b"] == (0, 0, "unresolved_unclassified")


def test_accumulator_keeps_reasoning_content_field_name():
    acc = llm_proxy.Accumulator(t0=0.0)
    acc.feed({"choices": [{"delta": {"reasoning_content": "think"}}]}, 0.1)
    acc.feed({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}, 0.2)
    msg = acc.response()["choices"][0]["message"]
    assert msg["reasoning_content"] == "think" and "reasoning" not in msg
