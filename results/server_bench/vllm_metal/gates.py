"""vllm-metal parity gates + throughput smoke. Direct to 127.0.0.1:8124 (no proxy)."""
import concurrent.futures as cf
import json
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8124/v1/chat/completions"
MODEL = "gemma-4-e4b-it-qat-w4a16-mlx"
OUT = {}


def post(body, timeout=600):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400], time.time() - t0


def msg(text):
    return [{"role": "user", "content": text}]


# G2: thinking budget as the harness sends it
s, r, _ = post({"model": MODEL, "messages": msg("What is 17*23? Think first."), "max_tokens": 600,
                "temperature": 0, "chat_template_kwargs": {"enable_thinking": True},
                "thinking_token_budget": 64})
OUT["G2_thinking_budget"] = {"status": s, "body": r if s != 200 else
                             {"reasoning_chars": len((r["choices"][0]["message"].get("reasoning") or ""))}}

# G4: tool call + reasoning extraction
tools = [{"type": "function", "function": {"name": "read_file", "description": "Read a file",
          "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}},
                         "required": ["filepath"]}}}]
s, r, _ = post({"model": MODEL, "messages": msg("Open src/app.py with the read_file tool."),
                "tools": tools, "max_tokens": 800, "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": True}})
m = r["choices"][0]["message"] if s == 200 else {}
OUT["G4_tools_reasoning"] = {"status": s, "tool_calls": [(c["function"]["name"], c["function"]["arguments"])
                             for c in (m.get("tool_calls") or [])],
                             "reasoning_chars": len(m.get("reasoning") or m.get("reasoning_content") or ""),
                             "finish": r["choices"][0]["finish_reason"] if s == 200 else r}

# G3: penalty reach - a forced repetition loop, penalty off vs on
loop_prompt = "Write the word 'banana' separated by spaces, 300 times, and nothing else."
res = {}
for fp in (0.0, 0.5):
    s, r, _ = post({"model": MODEL, "messages": msg(loop_prompt), "max_tokens": 700, "temperature": 0,
                    "frequency_penalty": fp, "chat_template_kwargs": {"enable_thinking": False}})
    txt = r["choices"][0]["message"]["content"] if s == 200 else str(r)
    res[str(fp)] = {"status": s, "banana_count": txt.lower().count("banana"),
                    "tokens": r["usage"]["completion_tokens"] if s == 200 else None}
OUT["G3_frequency_penalty"] = res

# Throughput: 1 stream, then 4 concurrent; 512 tokens, thinking off, fixed length via ignore_eos
def gen(_):
    s, r, dt = post({"model": MODEL, "messages": msg("Write a long story about a lighthouse keeper."),
                     "max_tokens": 512, "temperature": 0.2, "top_p": 0.95, "ignore_eos": True,
                     "chat_template_kwargs": {"enable_thinking": False}})
    return (r["usage"]["completion_tokens"] if s == 200 else 0), dt, s

for n in (1, 4):
    t0 = time.time()
    with cf.ThreadPoolExecutor(n) as ex:
        rows = list(ex.map(gen, range(n)))
    wall = time.time() - t0
    toks = sum(r[0] for r in rows)
    OUT[f"throughput_{n}"] = {"statuses": [r[2] for r in rows], "tokens": toks,
                              "wall_s": round(wall, 1), "agg_tok_s": round(toks / wall, 1),
                              "per_req_tok_s": [round(r[0] / r[1], 1) for r in rows]}
print(json.dumps(OUT, indent=1))
json.dump(OUT, open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/vllm_metal/gates.json", "w"), indent=1)
