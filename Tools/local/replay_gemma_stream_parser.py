"""Component replay with real tokenizer/parser and actual issue text; no model score."""
import argparse
import json
from pathlib import Path
import sys
import time


def native(value):
    if isinstance(value,str):
        if '<|"|>' in value:raise ValueError('fixture contains native delimiter')
        return '<|"|>'+value+'<|"|>'
    if isinstance(value,list):return '['+','.join(native(v) for v in value)+']'
    raise TypeError(type(value))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.parent.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'Tools/telemetry'));import llm_proxy
    from vllm.tokenizers.registry import get_tokenizer
    from vllm.tool_parsers.gemma4_engine_tool_parser import Gemma4EngineToolParser
    from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
    row=json.loads((root/'DataSets/v13_external_qualification/data/tasks.jsonl').read_text().splitlines()[0]);expected={'file_path':'scripts/run.py','positional_args':['prepare',row['problem_statement'],'220','1'],'skill_name':'semdag'}
    text='<|tool_call>call:run_skill_script{'+','.join(k+':'+native(v) for k,v in expected.items())+'}<tool_call|>'
    tokenizer=get_tokenizer(str(Path.home()/'models/gemma-4-e4b-it-qat-w4a16-mlx'))
    tokens=tokenizer.encode(text,add_special_tokens=False)
    tool=json.loads((args.out.parent/'sdk_tool.json').read_text());request=ChatCompletionRequest(model='gemma-4-e4b-it-qat-w4a16-mlx',messages=[{'role':'user','content':'component replay'}],tools=[tool],tool_choice='auto')
    full=Gemma4EngineToolParser(tokenizer,request.tools).extract_tool_calls(text,request)
    full_args=json.loads(full.tool_calls[0].function.arguments)
    rows=[]
    for chunk in [1,7,31]:
        parser=Gemma4EngineToolParser(tokenizer,request.tools);acc=llm_proxy.Accumulator(time.monotonic());previous='';old_ids=[]
        for end in range(chunk,len(tokens)+chunk,chunk):
            ids=tokens[:min(end,len(tokens))];current=tokenizer.decode(ids,skip_special_tokens=False)
            if not current.startswith(previous):raise ValueError('non-monotonic tokenizer prefix')
            delta=parser.extract_tool_calls_streaming(previous,current,current[len(previous):],old_ids,ids,ids[len(old_ids):],request)
            if delta is not None:acc.feed({'choices':[{'delta':delta.model_dump(exclude_none=True),'index':0}]},time.monotonic())
            previous,old_ids=current,ids
        final=parser.finish_streaming()
        if final is not None:acc.feed({'choices':[{'delta':final.model_dump(exclude_none=True),'index':0}]},time.monotonic())
        calls=acc.response()['choices'][0]['message'].get('tool_calls') or []
        got=json.loads(calls[0]['function']['arguments']) if len(calls)==1 else None
        rows.append({'token_chunk':chunk,'one_call':len(calls)==1,'arguments_match':got==expected,'fields':list(got or {})})
    result={'scope':'constructed valid native call with original external issue, real tokenizer and installed parser/accumulator; component replay not neural output','issue_characters':len(row['problem_statement']),'tokens':len(tokens),'nonstream_match':full_args==expected,'stream_replays':rows,'passed':full_args==expected and all(r['arguments_match'] for r in rows)}
    args.out.write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
