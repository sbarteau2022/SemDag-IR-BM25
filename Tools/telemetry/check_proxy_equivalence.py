"""Live gate: the proxy's stream-reassembled response must equal the server's own
non-streaming response for the same greedy request (reasoning, content, tool calls,
finish reason, completion tokens). Run before trusting proxy telemetry on a new server.

Usage: check_proxy_equivalence.py [--upstream 127.0.0.1:8124] [--model PATH]
Exit 0 on match, 1 on mismatch.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db as tdb  # noqa: E402
import llm_proxy  # noqa: E402

TOOLS = [{"type": "function", "function": {
    "name": "read_file", "description": "Read a file from the repository.",
    "parameters": {"type": "object", "properties": {
        "filepath": {"type": "string"}, "start_line": {"type": "integer"},
        "end_line": {"type": "integer"}}, "required": ["filepath"]}}}]


def post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def norm(resp):
    msg = resp["choices"][0]["message"]
    return {
        "reasoning": msg.get("reasoning") or msg.get("reasoning_content"),
        "content": msg.get("content"),
        "tool_calls": [(t["function"]["name"], json.loads(t["function"]["arguments"]))
                       for t in msg.get("tool_calls") or []],
        "finish_reason": resp["choices"][0]["finish_reason"],
        "completion_tokens": (resp.get("usage") or {}).get("completion_tokens"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", default="127.0.0.1:8124")
    ap.add_argument("--model", default=str(Path.home() / "models/gemma-4-e4b-it-qat-w4a16-mlx"))
    a = ap.parse_args()
    dbp = Path(tempfile.mkdtemp()) / "eq.sqlite"
    httpd = llm_proxy.serve(0, a.upstream, str(dbp), "equivalence")
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    body = {"model": a.model, "temperature": 0.0, "max_tokens": 512, "tools": TOOLS,
            "messages": [{"role": "user", "content":
                          "Use read_file to open src/app/utils.py lines 1 to 40, then stop."}]}
    cases = [body, {**body, "tools": None, "messages": [
        {"role": "user", "content": "In one sentence, what does git diff HEAD show?"}]}]
    ok = True
    for i, b in enumerate(cases):
        b = {k: v for k, v in b.items() if v is not None}
        direct = norm(post(f"http://{a.upstream}/v1/chat/completions", b))
        proxied = norm(post(f"http://127.0.0.1:{port}/v1/chat/completions", b))
        same = direct == proxied
        ok &= same
        print(f"case {i}: {'MATCH' if same else 'MISMATCH'} "
              f"tools={direct['tool_calls']} finish={direct['finish_reason']} "
              f"completion_tokens={direct['completion_tokens']}")
        if not same:
            print(" direct :", json.dumps(direct)[:600])
            print(" proxied:", json.dumps(proxied)[:600])
    row = tdb.connect(dbp).execute(
        "SELECT ttft_s, total_s, decode_tok_per_s, reasoning_chunks, completion_tokens "
        "FROM llm_calls ORDER BY wall_start").fetchall()
    for r in row:
        print("proxy row:", dict(r))
    httpd.shutdown()
    sys.exit(0 if ok and len(row) == len(cases) else 1)


if __name__ == "__main__":
    main()
