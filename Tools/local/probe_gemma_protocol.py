"""Read-only E4B protocol probe: native generation, installed parser, chat output.

No tool is executed and no malformed result is corrected. This is a transport
probe, not a SWE task score. Run in the vLLM Metal environment under Seatbelt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.request

MODEL='gemma-4-e4b-it-qat-w4a16-mlx'

def post(path,body):
    request=urllib.request.Request('http://127.0.0.1:8124'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    started=time.monotonic()
    with urllib.request.urlopen(request,timeout=180) as response:out=json.load(response)
    return out,time.monotonic()-started


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--case',choices=['json','native','typed']);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    tool=json.loads((args.out.parent/'sdk_tool.json').read_text())
    expected={'skill_name':'semdag','file_path':'scripts/run.py','args':['--status']}
    guidance={
      'json':'Call run_skill_script once to query native status. Exact JSON arguments: '+json.dumps(expected)+'. Do not execute anything else.',
      'typed':'Call run_skill_script once to query native status. Use skill_name semdag, file_path scripts/run.py, and positional_args as the one-element string array containing status. Native argument form: skill_name:<|"|>semdag<|"|>,file_path:<|"|>scripts/run.py<|"|>,positional_args:[<|"|>status<|"|>]. Do not execute anything else.',
      'native':'Call run_skill_script once to query native status. Use the Gemma4 native call syntax: call:run_skill_script{skill_name:<|"|>semdag<|"|>,file_path:<|"|>scripts/run.py<|"|>,args:[<|"|>--status<|"|>]} . The native string delimiter already quotes values; do not insert JSON double quotes into them. Do not execute anything else.',
    }
    from vllm.parser.gemma4 import _parse_gemma4_args
    receipts={}
    for label,system in guidance.items():
        if args.case and label != args.case:
            continue
        expected = ({'skill_name':'semdag','file_path':'scripts/run.py','positional_args':['status']} if label=='typed'
                    else {'skill_name':'semdag','file_path':'scripts/run.py','args':['--status']})
        messages=[{'role':'system','content':system},{'role':'user','content':'Query the native status using the provided tool.'}]
        tokenize={'model':MODEL,'messages':messages,'tools':[tool],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False},'return_token_strs':True}
        rendered,_=post('/tokenize',tokenize)
        (args.out/(label+'_tokenize.json')).write_text(json.dumps(rendered,indent=2))
        raw_body={'model':MODEL,'prompt':rendered['tokens'],'temperature':0,'top_p':0.95,'top_k':20,'max_tokens':16384,'skip_special_tokens':False,'stream':False}
        raw,raw_seconds=post('/v1/completions',raw_body)
        (args.out/(label+'_raw.json')).write_text(json.dumps(raw,indent=2))
        text=raw['choices'][0]['text']
        (args.out/(label+'_raw.txt')).write_text(text)
        match=re.search(r'<\|tool_call>call:([^\{]+)\{(.*?)\}(?:<tool_call\|>|<\|tool_response>)',text,re.S)
        parsed=_parse_gemma4_args(match[2]) if match else None
        chat_body={'model':MODEL,'messages':messages,'tools':[tool],'tool_choice':'auto','temperature':0,'top_p':0.95,'top_k':20,'max_tokens':16384,'chat_template_kwargs':{'enable_thinking':False},'stream':False}
        chat,chat_seconds=post('/v1/chat/completions',chat_body)
        (args.out/(label+'_chat.json')).write_text(json.dumps(chat,indent=2))
        calls=chat['choices'][0]['message'].get('tool_calls') or []
        chat_args=json.loads(calls[0]['function']['arguments']) if len(calls)==1 else None
        receipt={'native_tool_name':match[1] if match else None,'native_typed_arguments':parsed,'chat_arguments':chat_args,
                 'raw_matches_expected':bool(match and match[1]=='run_skill_script' and parsed==expected),
                 'chat_matches_expected':bool(len(calls)==1 and calls[0]['function']['name']=='run_skill_script' and chat_args==expected),
                 'raw_and_chat_args_equal':parsed==chat_args,'raw_seconds':raw_seconds,'chat_seconds':chat_seconds,
                 'prompt_tokens':len(rendered['tokens']),'raw_sha256':hashlib.sha256(text.encode()).hexdigest(),
                 'raw_usage':raw.get('usage'),'chat_usage':chat.get('usage'),'request':{'messages':messages,'tools':[tool]},
                 'scope':'greedy thinking-off fixed-call probe, not full-agent reproduction'}
        receipts[label]=receipt
        print(label,json.dumps({k:v for k,v in receipt.items() if k not in ['request','raw_usage','chat_usage']}),flush=True)
        (args.out/'summary.json').write_text(json.dumps(receipts,indent=2))

if __name__=='__main__':main()
