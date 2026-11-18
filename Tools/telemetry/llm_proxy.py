"""Thin timing proxy between the harness and the local OpenAI-compatible model server.

Why: the harness (ADK LiteLlm) sends non-streaming chat requests, so time-to-first-token
(TTFT) is invisible to it. This proxy forwards each chat request upstream with
`stream: true`, timestamps the first streamed token, reassembles the chunks into the
ordinary non-streaming response the client asked for, and writes one row per call to
SQLite (`llm_calls`). If the client itself asked to stream, chunks are relayed as-is.

Kept light on purpose: no tokenizing and no prompt storage during the run, one SQLite
insert per call, stdlib only. Everything heavier happens in `ingest.py` after the run.

Run (inside the no-network seatbelt):
  sandbox-exec -f Tools/seatbelt/no_network.sb .venv-harness/bin/python \
    Tools/telemetry/llm_proxy.py --listen 8125 --upstream 127.0.0.1:8124 \
    --db results/telemetry.sqlite --run-id run_11_v6_1

Measured fields (seconds are from the proxy's receipt of the request):
  ttft_s             first chunk carrying reasoning, content or a tool call
  t_first_reasoning_s / t_first_action_s   first reasoning chunk / first content-or-tool chunk
  reasoning_s        last reasoning chunk minus first reasoning chunk
  total_s            upstream stream finished
  reasoning_chunks   streamed reasoning chunks; mlx_lm emits about one per generated token
  decode_tok_per_s   completion_tokens / (total_s - ttft_s)
"""

from __future__ import annotations

import argparse
import http.client
import json
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db as tdb  # noqa: E402


class Accumulator:
    """Fold OpenAI chat-completion stream chunks into one non-streaming response."""

    def __init__(self, t0: float):
        self.t0 = t0
        self.reasoning: list[str] = []
        self.reasoning_key = "reasoning"   # echo the server's own field name back
        self.content: list[str] = []
        self.tool_calls: list[dict] = []
        self._tc_by_index: dict[int, dict] = {}
        self.finish_reason = None
        self.usage: dict = {}
        self.meta: dict = {}
        self.chunks = 0
        self.reasoning_chunks = 0
        self.ttft = None
        self.t_first_reasoning = None
        self.t_last_reasoning = None
        self.t_first_action = None

    def feed(self, chunk: dict, now: float) -> None:
        self.chunks += 1
        for k in ("id", "model", "created", "system_fingerprint"):
            if k in chunk and k not in self.meta:
                self.meta[k] = chunk[k]
        if chunk.get("usage"):
            self.usage = chunk["usage"]
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            r = delta.get("reasoning") or delta.get("reasoning_content")
            if delta.get("reasoning_content") and not delta.get("reasoning"):
                self.reasoning_key = "reasoning_content"
            c = delta.get("content")
            tcs = delta.get("tool_calls") or []
            dt = now - self.t0
            if r:
                self.reasoning.append(r)
                self.reasoning_chunks += 1
                if self.t_first_reasoning is None:
                    self.t_first_reasoning = dt
                self.t_last_reasoning = dt
            if c or tcs:
                if self.t_first_action is None:
                    self.t_first_action = dt
            if c:
                self.content.append(c)
            for tc in tcs:
                self._merge_tool_call(tc)
            if (r or c or tcs) and self.ttft is None:
                self.ttft = dt
            if choice.get("finish_reason"):
                self.finish_reason = choice["finish_reason"]

    def _merge_tool_call(self, tc: dict) -> None:
        """Merge one streamed tool-call delta.

        mlx_lm sends each call whole in one chunk. vLLM (and vllm-metal) send the
        id and name first, then `function.arguments` in fragments that share an `index`.
        Fragments with an index already seen are appended to that call; anything else
        starts a new call.
        """
        idx = tc.get("index")
        fn = tc.get("function") or {}
        cur = self._tc_by_index.get(idx) if idx is not None else None
        if cur is not None and tc.get("id") and cur.get("id") and tc["id"] != cur["id"]:
            cur = None          # same index reused for a new, whole call: keep both
        if cur is not None:
            cfn = cur.setdefault("function", {})
            if fn.get("name") and not cfn.get("name"):
                cfn["name"] = fn["name"]
            if fn.get("arguments"):
                cfn["arguments"] = cfn.get("arguments", "") + fn["arguments"]
            for k in ("id", "type"):
                if tc.get(k) and not cur.get(k):
                    cur[k] = tc[k]
            return
        call = {k: v for k, v in tc.items() if k not in ("index", "function")}
        call["function"] = {"name": fn.get("name"), "arguments": fn.get("arguments") or ""}
        call.setdefault("type", "function")
        self.tool_calls.append(call)
        if idx is not None:
            self._tc_by_index[idx] = call

    def response(self) -> dict:
        message: dict = {"role": "assistant", "content": "".join(self.content) or None}
        if self.reasoning:
            message[self.reasoning_key] = "".join(self.reasoning)
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        out = {
            "id": self.meta.get("id", f"chatcmpl-{uuid.uuid4().hex}"),
            "object": "chat.completion",
            "created": self.meta.get("created", int(time.time())),
            "model": self.meta.get("model"),
            "choices": [
                {"index": 0, "finish_reason": self.finish_reason or "stop", "message": message}
            ],
        }
        if self.meta.get("system_fingerprint"):
            out["system_fingerprint"] = self.meta["system_fingerprint"]
        if self.usage:
            out["usage"] = self.usage
        return out


def iter_sse(resp):
    """Yield parsed JSON chunks from a text/event-stream response until [DONE]."""
    while True:
        line = resp.readline()
        if not line:
            return
        line = line.strip()
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if data == b"[DONE]":
            return
        try:
            yield json.loads(data), line
        except ValueError:
            continue


def request_fields(body: dict) -> dict:
    extra = body.get("extra_body") or {}
    budget = body.get("thinking_token_budget", extra.get("thinking_token_budget"))
    return {
        "req_messages": len(body.get("messages") or []),
        "req_tools": len(body.get("tools") or []),
        "req_max_tokens": body.get("max_completion_tokens") or body.get("max_tokens"),
        "req_thinking_budget": budget,
        "req_temperature": body.get("temperature"),
        "client_stream": int(bool(body.get("stream"))),
    }


def enforce_thinking_budget(body: dict, field: str | None) -> dict:
    """Adapt the request's thinking budget to what the local server accepts.

    ADK sends the budget as `thinking_token_budget` (top level, or under `extra_body`), which
    vLLM's logits processor enforces on the scorer. vllm-metal rejects it with HTTP 400, so
    field="drop" removes it (the budget is then NOT enforced locally). Any other field name
    copies a positive budget into that top-level field, leaving a field the client set alone.
    """
    if not field:
        return body
    if field == "drop":
        # vllm-metal rejects thinking_token_budget with HTTP 400; remove it (budget NOT enforced).
        body = dict(body)
        body.pop("thinking_token_budget", None)
        if isinstance(body.get("extra_body"), dict):
            body["extra_body"] = {k: v for k, v in body["extra_body"].items()
                                  if k != "thinking_token_budget"}
        return body
    budget = request_fields(body)["req_thinking_budget"]
    if isinstance(budget, (int, float)) and budget > 0 and field not in body:
        body = dict(body)
        body[field] = int(budget)
    return body


def fill_generation_defaults(body: dict, top_k: int | None) -> dict:
    """vLLM's default `--generation-config auto` fills unset sampling fields from the checkpoint's
    generation_config.json (temperature 1.0, top_k 64, top_p 0.95). ADK never sends top_k, so on
    the scorer every call samples with top_k 64. Mirror that locally when a request has no top_k."""
    if top_k and "top_k" not in body:
        body = dict(body)
        body["top_k"] = int(top_k)
    return body


def make_handler(upstream: tuple[str, int], con, run_id: str, timeout: float,
                 budget_field: str | None = None, default_top_k: int | None = None):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a):  # keep stderr quiet
            pass

        def _passthrough(self, method: str, body: bytes | None):
            conn = http.client.HTTPConnection(*upstream, timeout=timeout)
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
            conn.request(method, self.path, body=body, headers=headers)
            r = conn.getresponse()
            data = r.read()
            self.send_response(r.status)
            self.send_header("Content-Type", r.getheader("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            conn.close()

        def do_GET(self):
            self._passthrough("GET", None)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if not self.path.rstrip("/").endswith("chat/completions"):
                return self._passthrough("POST", raw)
            try:
                body = json.loads(raw)
            except ValueError:
                return self._passthrough("POST", raw)

            wall = time.time()
            t0 = time.monotonic()
            row = {"run_id": run_id, "call_id": uuid.uuid4().hex, "wall_start": wall,
                   "req_bytes": len(raw), **request_fields(body)}
            client_stream = bool(body.get("stream"))
            up = fill_generation_defaults(enforce_thinking_budget(dict(body), budget_field),
                                          default_top_k)
            row["enforced_thinking_budget"] = up.get(budget_field) if budget_field else None
            up["stream"] = True
            up["stream_options"] = {"include_usage": True}
            acc = Accumulator(t0)
            try:
                conn = http.client.HTTPConnection(*upstream, timeout=timeout)
                conn.request("POST", self.path, body=json.dumps(up).encode(),
                             headers={"Content-Type": "application/json"})
                r = conn.getresponse()
                row["upstream_status"] = r.status
                if r.status != 200:
                    data = r.read()
                    row["error"] = data[:500].decode(errors="replace")
                    self.send_response(r.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    if client_stream:
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Connection", "close")
                        self.end_headers()
                    for chunk, line in iter_sse(r):
                        acc.feed(chunk, time.monotonic())
                        if client_stream:
                            self.wfile.write(line + b"\n\n")
                            self.wfile.flush()
                    if client_stream:
                        self.wfile.write(b"data: [DONE]\n\n")
                        self.wfile.flush()
                        self.close_connection = True
                    else:
                        data = json.dumps(acc.response()).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                conn.close()
            except Exception as exc:  # record, then surface as 502
                row["error"] = f"{type(exc).__name__}: {exc}"[:500]
                try:
                    data = json.dumps({"error": {"message": row["error"]}}).encode()
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except Exception:
                    pass
            finally:
                total = time.monotonic() - t0
                usage = acc.usage or {}
                comp = usage.get("completion_tokens")
                row.update(
                    ttft_s=acc.ttft,
                    t_first_reasoning_s=acc.t_first_reasoning,
                    t_first_action_s=acc.t_first_action,
                    reasoning_s=(acc.t_last_reasoning - acc.t_first_reasoning)
                    if acc.t_first_reasoning is not None else None,
                    total_s=total,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=comp,
                    cached_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                    stream_chunks=acc.chunks,
                    reasoning_chunks=acc.reasoning_chunks,
                    reasoning_chars=sum(map(len, acc.reasoning)),
                    content_chars=sum(map(len, acc.content)),
                    n_tool_calls=len(acc.tool_calls),
                    tool_names=",".join((t.get("function") or {}).get("name", "?")
                                        for t in acc.tool_calls),
                    finish_reason=acc.finish_reason,
                    decode_tok_per_s=(comp / (total - acc.ttft))
                    if comp and acc.ttft is not None and total > acc.ttft else None,
                )
                try:
                    tdb.insert(con, "llm_calls", row)
                except Exception as exc:  # telemetry must never break the run
                    print(f"llm_proxy: db write failed: {exc}", file=sys.stderr)

    return Handler


def serve(listen: int, upstream: str, db_path: str, run_id: str, timeout: float = 900.0,
          budget_field: str | None = None, default_top_k: int | None = None):
    host, port = upstream.rsplit(":", 1)
    con = tdb.connect(db_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", listen),
                                make_handler((host, int(port)), con, run_id, timeout,
                                             budget_field, default_top_k))
    httpd.daemon_threads = True
    return httpd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", type=int, default=8125)
    ap.add_argument("--upstream", default="127.0.0.1:8124")
    ap.add_argument("--db", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--thinking-budget-field", default=None,
                    help="'drop' removes thinking_token_budget (vllm-metal); any other name copies the budget into that field")
    ap.add_argument("--default-top-k", type=int, default=None,
                    help="fill top_k when a request omits it (scorer: 64 from generation_config)")
    a = ap.parse_args()
    httpd = serve(a.listen, a.upstream, a.db, a.run_id, a.timeout, a.thinking_budget_field,
                  a.default_top_k)
    print(f"llm_proxy: 127.0.0.1:{a.listen} -> {a.upstream} run_id={a.run_id} db={a.db} "
          f"thinking_budget_field={a.thinking_budget_field}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
