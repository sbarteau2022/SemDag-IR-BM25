"""Live E4B editor capability on actual retriever source; never a SWE score.

The driver prepares a slot and invokes root finalization after model editing.
Actual compiled editor instructions/tools are unchanged. All model/tool events
remain local. Run under Seatbelt with the official subprocess backend.
"""
from __future__ import annotations
import argparse
import asyncio
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
SUB=ROOT/'AgenticSubmission/v13_orchestrator'
sys.path.insert(0,str(SUB/'skills/semdag/assets/engine'))
import edit_tx as tx

CASES={
 'none':('tokens', 'Update retriever.tokens so None is treated as empty input and returns an empty list. Preserve all existing tokenization behavior for strings. Make a small exact fragment edit; do not replace the function or unrelated code.',
         'import retriever as r; assert r.tokens(None)==[]; assert r.tokens("")==[]; assert r.tokens("CamelCase")==["camelcase","camel","case"]; assert r.tokens("snake_case")==["snake_case","snake","case"]'),
 'windows':('is_test_path','Update retriever.is_test_path to recognize Windows backslash directory separators as well as POSIX slash separators. Preserve ordinary-path and existing test-filename behavior. Make a small exact fragment edit; do not replace the function or unrelated code.',
            'import retriever as r; assert r.is_test_path(r"pkg\\tests\\helper.py"); assert r.is_test_path(r"pkg\\testing\\helper.py"); assert r.is_test_path("pkg/tests/helper.py"); assert r.is_test_path("test_value.py"); assert not r.is_test_path(r"pkg\\library.py"); assert not r.is_test_path("pkg/library.py")'),
}

def native(result):
    for key in ['stdout','stderr']:
        for line in result.get(key,'').split('\n'):
            if not line.startswith('{'):continue
            try:out=json.loads(line)
            except ValueError:continue
            if isinstance(out,dict) and 'ok' in out:return out
    raise ValueError('native result missing metadata header: '+str(result)[:300])

async def run_case(name,outdir):
    from adk_submission import compile_submission,ModelRegistry
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.runners import Runner
    from google.adk.apps.app import App
    from google.adk.agents.run_config import RunConfig
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools.skill_toolset import SkillToolset
    from google.adk.tools.tool_context import ToolContext
    from google.genai import types
    from swegemma.context import SwegemmaContext
    from swegemma.sandbox import AdkSandboxCodeExecutor
    from swegemma.sandbox.subprocess import SubprocessManager
    from swegemma.harness.container_setup import setup_git_exclude
    from swegemma.harness.agent_runner import _wrap_skill_toolset_tools,ToolErrorPlugin
    from adk_eval_core.plugins import ModelRetryPlugin
    from google.adk.apps._configs import EventsCompactionConfig
    from google.adk.agents.context_cache_config import ContextCacheConfig
    import shlex
    outdir.mkdir(parents=True,exist_ok=True)
    symbol,intent,assertions=CASES[name]
    source=(SUB/'skills/semdag/assets/engine/retriever.py').read_text()
    manager=SubprocessManager(timeout_seconds=300);manager.initialize({'retriever.py':source})
    receipt={'case':name,'scope':'live component editor, host preparation/finalization; not autonomous root or SWE score',
             'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'intent':intent,'model':'gemma-4-e4b-it-qat-w4a16-ct',
             'budget':{'seconds':240,'tools':40,'turns':60,'output':16384,'thinking':4096},'passed':False}
    events=[];started=time.monotonic()
    try:
        for command in ['git init -q','git config user.email component@example.invalid','git config user.name component','git add retriever.py','git commit -qm base','git tag _swegemma_baseline']:
            result=manager.run_command(command)
            if result.exit_code:raise RuntimeError(result.stderr)
        sid=next(iter(manager.sandboxes));setup_git_exclude(manager,sid)
        repo=os.path.realpath(manager.work_dir)
        context=SwegemmaContext(docker_manager=manager,container_id=sid,problem_statement=intent,
            repo='component/retriever',max_tool_calls=40,max_time_minutes=4,max_exec_seconds=300)
        tools=context.create_tools()
        executor=AdkSandboxCodeExecutor(sandbox=context.sandbox,timeout_seconds=300,
            start_time=context.task_start_time,max_time_minutes=4,budget_check_fn=context.check_budget)
        models=ModelRegistry();models.register('gemma-4-e4b-it-qat-w4a16-ct',LiteLlm(
            model='openai/gemma-4-e4b-it-qat-w4a16-mlx',api_base='http://127.0.0.1:8125/v1',api_key='EMPTY'))
        root=compile_submission(SUB,tools,models,code_executor=executor)
        _wrap_skill_toolset_tools(root)
        editor=next(t.agent for t in root.tools if getattr(t,'name','')=='editor_1')
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==symbol)
        check='python -c '+shlex.quote(assertions)
        baseline=tx.run_check(check,repo,{'deadline':time.monotonic()+60});receipt['baseline']=baseline
        if baseline['exit_code']==0:raise ValueError('component request already satisfied; invalid capability gate')
        program=('import sys,json;sys.path.insert(0,'+repr(str(SUB/'skills/semdag/assets/engine'))+');import edit_tx;print(json.dumps(edit_tx.begin('
                 +','.join(repr(v) for v in [repo,'1','retriever.py',node.lineno,node.end_lineno,check,240])
                 +',issue='+repr(intent)+',baseline='+repr(baseline)+')))')
        preparation=manager.run_command('python -c '+shlex.quote(program))
        if preparation.exit_code:raise RuntimeError(preparation.stderr)
        ready=json.loads(preparation.stdout)
        receipt['prepared']=ready['ok']
        sessions=InMemorySessionService();session=await sessions.create_session(app_name='v13_editor_capability',user_id='component')
        app=App(name='v13_editor_capability',root_agent=editor,plugins=[ModelRetryPlugin(),ToolErrorPlugin()],
          events_compaction_config=EventsCompactionConfig(compaction_interval=15,overlap_size=2,token_threshold=14336,event_retention_size=5),
          context_cache_config=ContextCacheConfig(min_tokens=2048,ttl_seconds=1800,cache_intervals=10))
        runner=Runner(app=app,session_service=sessions)
        async def call_native(agent,arguments):
            skill=next(t for t in agent.tools if isinstance(t,SkillToolset))
            tool=next(t for t in await skill.get_tools() if t.name=='run_skill_script')
            ctx=InvocationContext(invocation_id='host-verifier',agent=agent,session=session,session_service=sessions)
            result=await tool.run_async(args=arguments,tool_context=ToolContext(ctx))
            return native(result)
        context.start_agent_session();executor.start_time=context.agent_start_time
        model_start=time.monotonic()
        async with asyncio.timeout(240):
            message=types.Content(role='user',parts=[types.Part(text=intent+'\nSlot 1 is prepared. Read native status for source/handle and return EDIT_READY after editing.')])
            async for event in runner.run_async(user_id='component',session_id=session.id,new_message=message,run_config=RunConfig(max_llm_calls=60)):
                context.handle_adk_event(event,agent_name=editor.name)
                events.append(event.model_dump(mode='json',exclude_none=True))
                content=getattr(event,'content',None)
                for part in getattr(content,'parts',[]) or []:
                    call=getattr(part,'function_call',None)
                    if call:print(name,'tool',call.name,flush=True)
            receipt['editor_seconds']=time.monotonic()-model_start
            state=await call_native(root,{'skill_name':'semdag','file_path':'scripts/run.py','positional_args':['status','1']})
            receipt['state_after_editor']=state.get('state')
            if state.get('state')!='edited' or not state.get('next_execution'):
                raise ValueError('E4B did not produce an edited candidate')
            result=await call_native(root,state['next_execution']);receipt['finalization']=result
            if not result.get('ok') or result.get('state')!='applied':raise ValueError('root native verification did not apply candidate')
            patch=manager.run_command('git diff HEAD -- retriever.py');(outdir/'model.patch').write_text(patch.stdout)
            final=manager.read_file('retriever.py');new_node=next(n for n in ast.parse(final).body if isinstance(n,ast.FunctionDef) and n.name==symbol)
            old_lines=source.splitlines(True);new_lines=final.splitlines(True)
            unchanged=(old_lines[:node.lineno-1]==new_lines[:new_node.lineno-1] and old_lines[node.end_lineno:]==new_lines[new_node.end_lineno:])
            receipt['surrounding_source_unchanged']=unchanged
            receipt['independent_central_check']=tx.run_check(check,repo,{'deadline':time.monotonic()+30})
            receipt['patch_bytes']=len(patch.stdout.encode())
            receipt['passed']=bool(unchanged and patch.stdout and receipt['independent_central_check']['exit_code']==0)
    except Exception as exc:
        receipt['error']=type(exc).__name__+': '+str(exc)[:1800]
    finally:
        receipt['duration_seconds']=time.monotonic()-started
        receipt['events']=len(events)
        (outdir/'events.json').write_text(json.dumps(events,indent=2))
        (outdir/'receipt.json').write_text(json.dumps(receipt,indent=2))
        manager.cleanup_all()
    print(name,json.dumps({k:receipt.get(k) for k in ['passed','editor_seconds','duration_seconds','patch_bytes','error']}),flush=True)
    return receipt

async def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--case',choices=list(CASES));args=ap.parse_args()
    rows=[]
    for name in ([args.case] if args.case else CASES):rows.append(await run_case(name,args.out/name))
    args.out.mkdir(parents=True,exist_ok=True);(args.out/'summary.json').write_text(json.dumps(rows,indent=2))
    return 0 if all(r['passed'] for r in rows) else 1

if __name__=='__main__':raise SystemExit(asyncio.run(main()))
