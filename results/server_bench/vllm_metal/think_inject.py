import json, urllib.request
URL="http://127.0.0.1:8124/v1/chat/completions"; M="gemma-4-e4b-it-qat-w4a16-mlx"
tools=[{"type":"function","function":{"name":"read_file","parameters":{"type":"object","properties":{"filepath":{"type":"string"}},"required":["filepath"]}}}]
user="The bug is in src/calc.py: add() subtracts. Use read_file to open the file."
def call(sys_text, enable):
    b={"model":M,"temperature":0,"max_tokens":1500,"tools":tools,
       "messages":[{"role":"system","content":sys_text},{"role":"user","content":user}],
       "chat_template_kwargs":{"enable_thinking":enable}}
    r=json.loads(urllib.request.urlopen(urllib.request.Request(URL,json.dumps(b).encode(),{"Content-Type":"application/json"}),timeout=300).read())
    m=r["choices"][0]["message"]
    return {"reasoning_chars":len(m.get("reasoning") or m.get("reasoning_content") or ""),
            "content_head":(m.get("content") or "")[:80],
            "tool_calls":[c["function"]["name"] for c in m.get("tool_calls") or []],
            "finish":r["choices"][0]["finish_reason"],"completion_tokens":r["usage"]["completion_tokens"],
            "prompt_tokens":r["usage"]["prompt_tokens"]}
base="You are a careful coding agent."
for name,s,e in [("A thinking OFF (flag)",base,False),("B thinking ON (flag)",base,True),
                 ("C flag OFF + literal <|think|> in system",  "<|think|>"+base,False),
                 ("D flag ON + 'think briefly: <=3 sentences'", base+" Think briefly: at most 3 sentences of reasoning, then act.",True)]:
    print(name, json.dumps(call(s,e)))
# does the literal string become the special token?
tk=json.loads(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8124/tokenize",json.dumps({"model":M,"prompt":"<|think|>"}).encode(),{"Content-Type":"application/json"})).read())
print("tokenize('<|think|>') ->", tk.get("tokens"), tk.get("count"))
