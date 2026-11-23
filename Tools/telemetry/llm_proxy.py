"""Thin timing proxy between the harness and the local OpenAI-compatible model server.

Why: the harness (ADK LiteLlm) sends non-streaming chat requests, so time-to-first-token
(TTFT) is invisible to it. This proxy forwards each chat request upstream with
`stream: true`, timestamps the first streamed token, reassembles the chunks into the
ordinary non-streaming response the client asked for, and writes one row per call to
SQLite (`llm_calls`). If the client itself asked to stream, chunks are relayed as-is.

Kept light on purpose: no tokenizing and no prompt storage during the run, one SQLite
insert per call, stdlib only. Everything heavier happens in `ingest.py` after the run.

Thinking-budget enforcement: when started with `--thinking-budget-field drop`
(vllm-metal), the budget is removed from the upstream request (the server would
reject it with HTTP 400) and enforced here instead. The proxy streams the reasoning,
counts streamed reasoning deltas (vLLM streams one chunk per generated token, so the
chunk count is the token estimate), stops at the budget, and resumes with a second
upstream request that presents the truncated reasoning as a completed
`<|channel>thought ... <channel|>` channel with thinking switched off, so the model
produces the action (content / tool calls) conditioned on exactly the budget-limited
reasoning. That is the same observable behaviour as vLLM's
ThinkingTokenBudgetLogitsProcessor, which forces the reasoning-end token and lets
generation continue. The telemetry row records `budget_enforced`,
`reasoning_chunks_at_cut` and `phase2_status` for the gate.

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
        self.reasoning_closed = False   # set when the thinking budget is hit
        self.reasoning_dropped_chars = 0
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
            kept_r = None
            if r:
                if self.reasoning_closed:
                    # Thinking already cut at the budget (phase 2 must not add
                    # more); count it so a bad resume is visible in telemetry.
                    self.reasoning_dropped_chars += len(r)
                else:
                    kept_r = r
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
            if (kept_r or c or tcs) and self.ttft is None:
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
    field="drop" removes it from the request and the handler enforces it in-stream instead
    (two-phase resume: stop at the budget, present the truncated reasoning as a completed
    channel with thinking off). Any other field name copies a positive budget into that
    top-level field, leaving a field the client set alone.
    """
    if not field:
        return body
    if field == "drop":
        # vllm-metal rejects thinking_token_budget with HTTP 400; remove it here.
        # The budget is then enforced by the proxy itself (see build_resume_body),
        # not by the server.
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


def build_resume_body(up: dict, acc: Accumulator) -> dict:
    """Second upstream request after the thinking budget is hit.

    Presents the truncated reasoning as a completed thinking channel, with thinking
    switched off, so the model produces the action (content / tool calls) conditioned
    on exactly the budget-limited reasoning. The reasoning channel is what the model
    itself emits (`<|channel>thought\\n...<channel|>`), and with `enable_thinking`
    off the template issues no new think trigger, so the model goes straight to the
    action. Total output for the turn stays capped at the original max_tokens: the
    resume may only spend what the reasoning did not.
    """
    reasoning = "".join(acc.reasoning)
    channel = "<|channel>thought\n" + reasoning + "<channel|>"
    body = dict(up)
    body["messages"] = list(up.get("messages") or []) + [
        {"role": "assistant", "content": channel}
    ]
    kwargs = dict(up.get("chat_template_kwargs") or {})
    kwargs["enable_thinking"] = False
    body["chat_template_kwargs"] = kwargs
    for key in ("max_tokens", "max_completion_tokens"):
        if isinstance(up.get(key), (int, float)) and up[key]:
            body[key] = max(1, int(up[key]) - acc.reasoning_chunks)
    body.pop("thinking_token_budget", None)
    if isinstance(body.get("extra_body"), dict):
        body["extra_body"] = {k: v for k, v in body["extra_body"].items()
                              if k != "thinking_token_budget"}
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

        def _stream_into(self, resp, acc: Accumulator, client_stream: bool,
                         budget: int | None) -> bool:
            """Feed streamed chunks into acc, relaying them if the client streams.

            Returns True when the thinking budget was hit mid-reasoning: the caller
            should close this upstream connection and resume with build_resume_body().
            Only triggers while the model is still reasoning (no content or tool
            calls yet, no finish reason). The token count is the streamed reasoning
            delta count; vLLM streams one chunk per generated token.
            """
            for chunk, line in iter_sse(resp):
                acc.feed(chunk, time.monotonic())
                if client_stream:
                    self.wfile.write(line + b"\n\n")
                    self.wfile.flush()
                if (budget is not None and acc.reasoning_chunks >= budget
                        and not acc.content and not acc.tool_calls
                        and acc.finish_reason is None):
                    acc.reasoning_closed = True
                    return True
            return False

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
                   "req_bytes": len(raw), **request_fields(body),
                   "budget_enforced": 0, "reasoning_chunks_at_cut": None,
                   "phase2_status": None, "reasoning_dropped_chars": 0}
            client_stream = bool(body.get("stream"))
            up = fill_generation_defaults(enforce_thinking_budget(dict(body), budget_field),
                                          default_top_k)
            row["enforced_thinking_budget"] = up.get(budget_field) if budget_field else None
            # Proxy-side enforcement only when the budget was dropped from the
            # request (vllm-metal). Otherwise the server enforces it itself.
            req_budget = request_fields(body)["req_thinking_budget"]
            budget = (int(req_budget) if budget_field == "drop"
                      and isinstance(req_budget, (int, float)) and req_budget > 0 else None)
            up["stream"] = True
            up["stream_options"] = {"include_usage": True}
            acc = Accumulator(t0)
            responded = False
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
                    responded = True
                else:
                    if client_stream:
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Connection", "close")
                        self.end_headers()
                    hit = self._stream_into(r, acc, client_stream, budget)
                    conn.close()
                    if hit:
                        row["budget_enforced"] = 1
                        row["reasoning_chunks_at_cut"] = acc.reasoning_chunks
                        resume = build_resume_body(up, acc)
                        conn2 = http.client.HTTPConnection(*upstream, timeout=timeout)
                        conn2.request("POST", self.path, body=json.dumps(resume).encode(),
                                      headers={"Content-Type": "application/json"})
                        r2 = conn2.getresponse()
                        row["phase2_status"] = r2.status
                        if r2.status != 200:
                            data = r2.read()
                            row["error"] = ("resume: " + data[:400].decode(errors="replace"))
                            if not client_stream:
                                err = json.dumps({"error": {"message": row["error"]}}).encode()
                                self.send_response(502)
                                self.send_header("Content-Type", "application/json")
                                self.send_header("Content-Length", str(len(err)))
                                self.end_headers()
                                self.wfile.write(err)
                                responded = True
                        else:
                            self._stream_into(r2, acc, client_stream, None)
                        conn2.close()
                    if client_stream:
                        self.wfile.write(b"data: [DONE]\n\n")
                        self.wfile.flush()
                        self.close_connection = True
                        responded = True
                    elif not responded:
                        data = json.dumps(acc.response()).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        responded = True
            except Exception as exc:  # record, then surface as 502
                row["error"] = f"{type(exc).__name__}: {exc}"[:500]
                if not responded:
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
                    reasoning_dropped_chars=acc.reasoning_dropped_chars,
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
                    help="'drop' removes thinking_token_budget from the request and enforces it in the proxy (vllm-metal); any other name copies the budget into that field")
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
