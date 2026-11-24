"""Actual ADK compilation and subprocess execution; component fixtures, no model calls."""
import asyncio
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / 'AgenticSubmission/v13_orchestrator'


def get_status() -> str:
    return 'component status'


def submit_patch() -> str:
    return 'component submit'


def build_compiled(base,source='def value():\n    return 1\n'):
    from adk_submission import compile_submission, ModelRegistry, ToolRegistry
    from google.adk.models.lite_llm import LiteLlm
    from swegemma.sandbox import AdkSandboxCodeExecutor
    from swegemma.sandbox.subprocess import SubprocessManager
    from swegemma.harness.container_setup import setup_git_exclude
    base=base
    physical=base/'physical';physical.mkdir()
    alias=base/'alias';alias.symlink_to(physical,target_is_directory=True)
    manager=SubprocessManager(base_dir=alias)
    manager.initialize({'sample.py':source})
    for command in ['git init -q','git config user.email component@example.invalid',
                    'git config user.name component','git add sample.py','git commit -qm base',
                    'git tag _swegemma_baseline']:
        assert manager.run_command(command).exit_code==0
    sid=next(iter(manager.sandboxes));setup_git_exclude(manager,sid)
    executor=AdkSandboxCodeExecutor(sandbox=manager,timeout_seconds=30)
    models=ModelRegistry();models.register('gemma-4-e4b-it-qat-w4a16-ct',LiteLlm(
        model='openai/gemma-4-e4b-it-qat-w4a16-mlx',api_base='http://127.0.0.1:8124/v1',api_key='EMPTY'))
    tools=ToolRegistry();tools.register('get_status',get_status);tools.register('submit_patch',submit_patch)
    agent=compile_submission(SUB,tools,models,code_executor=executor)
    roles={'root':agent}
    roles.update({t.name:t.agent for t in agent.tools if hasattr(t,'agent')})
    return manager,roles


@pytest.fixture(scope='module')
def compiled(tmp_path_factory):
    manager,roles=build_compiled(tmp_path_factory.mktemp('role-sdk'))
    yield manager,roles
    manager.cleanup_all()

def toolset(agent):
    from google.adk.tools.skill_toolset import SkillToolset
    return next(t for t in agent.tools if isinstance(t,SkillToolset))


def invoke(roles,role,args,file_path='scripts/run.py',skill='semdag',raw=None):
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.sessions import Session,InMemorySessionService
    from google.adk.tools.tool_context import ToolContext
    agent=roles[role]
    context=InvocationContext(invocation_id='component-'+role,agent=agent,
        session=Session(id='component',app_name='component',user_id='component',state={}),
        session_service=InMemorySessionService())
    async def run():
        tools=await toolset(agent).get_tools()
        script=next(t for t in tools if t.name=='run_skill_script')
        return await script.run_async(args=raw if raw is not None else {
            'skill_name':skill,'file_path':file_path,'args':args},tool_context=ToolContext(context))
    return asyncio.run(run())


def payload(out):
    for value in [out.get('stdout',''),out.get('stderr','')]:
        lines=value.split("\n")
        for index,line in enumerate(lines):
            if not line.startswith('{'):
                continue
            try:
                header=json.loads(line)
            except ValueError:
                continue
            if isinstance(header,dict) and 'ok' in header:
                if header.get('source_format')=='numbered-python-v1':
                    assert lines[index+1]=='---BEGIN V13 SOURCE---'
                    end=lines.index('---END V13 SOURCE---',index+2)
                    header['text']='\n'.join(lines[index+2:end])
                return header
    raise AssertionError(out)


def test_compiled_roles_have_no_shell_or_raw_edit_tools(compiled):
    _,roles=compiled
    for role,agent in roles.items():
        names={getattr(t,'name',getattr(t,'__name__','')) for t in agent.tools}
        expanded=names | {t.name for t in asyncio.run(toolset(agent).get_tools())}
        assert not expanded & {'run_command','edit_file','write_file','read_file'}
        assert 'get_status' in names
        assert ('submit_patch' in names)==(role=='root')
        skills=toolset(agent)._skills
        assert set(skills)=={'semdag'}
        assert set(skills['semdag'].resources.list_scripts())==({'run.py','finalize.py'} if role=='root' else {'run.py'})
    entries=[toolset(a)._skills['semdag'].resources.get_script('run.py').src for a in roles.values()]
    assert len(set(entries))==3


@pytest.mark.parametrize('role,args',[
    ('root',['--edit','unknown','--text','x=1']),('root',['--view','unknown','--lines','1-2']),
    ('editor_1',['--prepare','issue','--remaining','30']),('editor_1',['--finalize','unknown']),
    ('editor_2',['--prepare','issue','--remaining','30']),('editor_2',['--finalize','unknown']),
    ('editor_1',['--status','--slot','2']),('editor_2',['--status','--slot','1']),
    ('editor_1',['--role','root','--prepare','issue','--remaining','30']),
    ('root',['--repo','/tmp','--status']),('root',['--slot','../1','--status']),
])
def test_native_role_denials_through_sdk(compiled,role,args):
    manager,roles=compiled
    before=manager.read_file('sample.py')
    result=payload(invoke(roles,role,args))
    assert not result['ok']
    assert ('PermissionError' in result['error'] or 'invalid native action' in result['error'])
    encoded=payload(invoke(roles,role,[json.dumps(args)]))
    assert not encoded['ok']
    assert manager.read_file('sample.py')==before


@pytest.mark.parametrize('path',[
    'scripts/edit_tx.py','scripts/fix_edit.py','scripts/workspace_mgr.py',
    'assets/engine/edit_tx.py','scripts/../assets/engine/edit_tx.py','../assets/engine/edit_tx.py',
    'scripts/../../semdag/scripts/run.py','/tmp/run.py',
])
def test_helper_asset_and_traversal_execution_denied(compiled,path):
    manager,roles=compiled;before=manager.read_file('sample.py')
    for role in roles:
        out=invoke(roles,role,['--status'],file_path=path)
        assert out.get('error_code')=='SCRIPT_NOT_FOUND',out
    assert manager.read_file('sample.py')==before


def test_official_missing_keys_remain_errors(compiled):
    _,roles=compiled
    assert invoke(roles,'root',[],raw={'args':['--status']})['error_code']=='INVALID_ARGUMENTS'
    assert invoke(roles,'root',['--status'],skill='dask')['error_code']=='SKILL_NOT_FOUND'


def test_native_serialized_json_arguments_and_outer_errors(compiled):
    _,roles=compiled
    out=payload(invoke(roles,'editor_1',[json.dumps(['--status'])]))
    assert out['state']=='unprepared' and not out['ok']
    assert 'EDIT_FAILED' in out['next']
    assert not payload(invoke(roles,'root',['[{}]']))['ok']
    assert not payload(invoke(roles,'root',['[invalid']))['ok']
    assert invoke(roles,'root',['--status'],skill='"semdag"')['error_code']=='SKILL_NOT_FOUND'


def test_root_unprepared_status_requests_prepare_not_editor_failure(compiled):
    _,roles=compiled
    out=payload(invoke(roles,'root',['--status']))
    assert not out['ok'] and out['state']=='unprepared'
    assert 'Prepare this slot' in out['next'] and 'EDIT_FAILED' not in out['next']


def test_actual_compiled_prepare_editor_edit_finalize(compiled):
    manager,roles=compiled
    prepared=payload(invoke(roles,'root',{'prepare':'sample.value returns 1 but must return 2','remaining':60,'slot':'1'}))
    assert prepared['ok'],prepared
    own=payload(invoke(roles,'editor_1',['--status']))
    assert own['ok'] and own['handle']==prepared['handle'],own
    # A sibling cannot replay a valid handle, even by omitting the slot flag.
    other=payload(invoke(roles,'editor_2',['--edit',own['handle'],'--text','def value():\n    return 9']))
    assert not other['ok'] and 'cross-slot' in other['error']
    edited=payload(invoke(roles,'editor_1',['--edit',own['handle'],'--text','def value():\n    return 2']))
    assert edited['ok'],edited
    assert manager.read_file('sample.py').endswith('return 1\n')
    status=payload(invoke(roles,'root',['--status']))
    assert status['state']=='edited' and not status['candidate_applied_to_central'] and status['next_execution']['file_path']=='scripts/finalize.py'
    applied=payload(invoke(roles,'root',[],raw=status['next_execution']))
    assert applied['ok'] and applied['state']=='applied',applied
    assert applied['outside_check']['exit_code']==applied['central_check']['exit_code']==0
    assert applied['next_tool']=='submit_patch' and applied['next_tool_arguments']=={} and applied['candidate_applied_to_central']
    assert manager.read_file('sample.py')=='def value():\n    return 2\n'


def test_compiled_editor_two_uses_its_own_alternative(compiled):
    manager,roles=compiled
    manager.write_file('sample.py','def value():\n    """shared retrieval signal"""\n    return 1\n\ndef other():\n    """shared retrieval signal"""\n    return 3\n')
    for command in ['git add sample.py','git commit -qm alternate-base','git tag -f _swegemma_baseline']:
        assert manager.run_command(command).exit_code==0
    prepared=payload(invoke(roles,'root',['--prepare','shared retrieval signal','--remaining','60','--slot','2']))
    assert prepared['ok'] and prepared['anchor']=='bm25',prepared
    own=payload(invoke(roles,'editor_2',['--status']))
    assert own['ok'] and own['slot']=='2',own
    edited=payload(invoke(roles,'editor_2',['--edit',own['handle'],'--text','def other():\n    """shared retrieval signal"""\n    return 4']))
    assert edited['ok'],edited
    applied=payload(invoke(roles,'root',['--finalize',edited['handle'],'--slot','2']))
    assert applied['ok'],applied
    assert 'return 4' in manager.read_file('sample.py')


def positional(roles,role,values):
    return invoke(roles,role,[],raw={'skill_name':'semdag','file_path':'scripts/run.py','positional_args':values})


@pytest.mark.parametrize('role,values',[
    ('root',['edit','unknown','x=1']),('root',['view','unknown','1-2']),
    ('editor_1',['prepare','issue','60','1']),('editor_2',['finalize','unknown','2']),
    ('editor_1',['status','2']),('editor_2',['status','1']),
    ('root',['prepare','issue','60']),('root',['prepare','issue','nan','1']),
    ('root',['prepare','issue','60','../1']),('root',['status','1','extra']),
])
def test_typed_positional_denials(compiled,role,values):
    manager,roles=compiled;before=manager.read_file('sample.py')
    out=payload(positional(roles,role,values));assert not out['ok'],out
    assert manager.read_file('sample.py')==before


def test_declared_positional_schema_and_no_mixed_array_arguments(compiled):
    _,roles=compiled
    tools=asyncio.run(toolset(roles['root']).get_tools())
    tool=next(t for t in tools if t.name=='run_skill_script')
    schema=tool._get_declaration().parameters_json_schema['properties']
    assert schema['positional_args']['type']=='array'
    assert schema['positional_args']['items']['type']=='string'
    out=invoke(roles,'root',[],raw={'skill_name':'semdag','file_path':'scripts/run.py','args':['--status'],'positional_args':['status']})
    assert out['error_code']=='INVALID_ARGUMENTS'


@pytest.mark.parametrize('role,values',[
    ('root',['edit_lines','unknown','pass']),('root',['view','1','2']),
    ('root',['view,1,2']),('editor_1',['edit_lines','unknown']),
    ('editor_1',['edit,unknown,return 2']),('editor_1',['edit_lines,unknown,return 2']),
    ('editor_1',['view','1','999999']),
])
def test_native_contextual_forms_fail_safely(compiled,role,values):
    manager,roles=compiled;before=manager.read_file('sample.py')
    out=payload(positional(roles,role,values));assert not out['ok'],out
    assert manager.read_file('sample.py')==before


def test_native_errors_have_sdk_error_status_and_stderr(compiled):
    _,roles=compiled
    out=positional(roles,'root',['edit_lines','unknown','pass'])
    assert out['status']=='error' and not out['stdout']
    assert 'PermissionError' in out['stderr'] and not payload(out)['ok']


def test_actual_sdk_positional_lifecycle(compiled):
    manager,roles=compiled
    manager.write_file('sample.py','def value():\n    return "quoted"\n')
    for command in ['git add sample.py','git commit -qm positional-base','git tag -f _swegemma_baseline']:
        assert manager.run_command(command).exit_code==0
    prepared=payload(positional(roles,'root',['prepare','sample.value returns 10 but must return 11','1']))
    assert prepared['ok'] and 'baseline' in prepared['budget_source'],prepared
    raw=positional(roles,'editor_1',['view,2,2']);own=payload(raw);assert own['ok'],own
    assert own['source_format']=='numbered-python-v1'
    assert '2:     return "quoted"' in raw['stdout']
    assert r'\"quoted\"' not in raw['stdout']
    assert r'\n' not in raw['stdout'].split('---BEGIN V13 SOURCE---',1)[1]
    assert own['edit_prefix']==['edit_lines',own['handle']]
    edited=payload(positional(roles,'editor_1',own['edit_prefix']+['    result = 11','    return result']))
    assert edited['ok'],edited
    applied=payload(positional(roles,'root',['finalize',edited['handle'],'1']))
    assert applied['ok'] and applied['state']=='applied',applied
    assert manager.read_file('sample.py')=='def value():\n    result = 11\n    return result\n'


def test_actual_sdk_context_read_never_grants_an_outside_write_lease(tmp_path):
    source='def value():\n    return 1\n\ndef helper_items():\n    return 3\n'
    manager,roles=build_compiled(tmp_path,source)
    try:
        ready=payload(positional(roles,'root',['prepare','helper_items','1']))
        assert ready['ok'],ready
        context=payload(positional(roles,'editor_1',['view','1','2']))
        assert context['ok'] and context['read_only']
        assert 'return 1' in context['text']
        assert 'handle' not in context and 'edit_prefix' not in context
        before=manager.read_file('sample.py')
        denied=payload(positional(roles,'editor_1',['edit',ready['handle'],'1-2','def value():\n    return 9']))
        assert not denied['ok'] and 'issued view' in denied['error']
        assert manager.read_file('sample.py')==before
        # An explicit handle + numeric context range is equally read-only.
        context=payload(positional(roles,'editor_1',['view',ready['handle'],'1','2']))
        assert context['ok'] and context['read_only'] and 'handle' not in context
    finally:
        manager.cleanup_all()


def test_fixed_finalizer_is_root_only_and_requires_exact_handle(compiled):
    manager,roles=compiled;before=manager.read_file('sample.py')
    for role in ['editor_1','editor_2']:
        assert positional_finalizer(roles,role,['unknown'])['error_code']=='SCRIPT_NOT_FOUND'
    for values in [[],['unknown'],['unknown','1'],['--role','editor']]:
        out=payload(positional_finalizer(roles,'root',values));assert not out['ok']
    # Generic dispatch still does not infer an omitted operation.
    assert not payload(positional(roles,'root',['unknown-handle-only']))['ok']
    assert manager.read_file('sample.py')==before


def positional_finalizer(roles,role,values):
    return invoke(roles,role,[],raw={'skill_name':'semdag','file_path':'scripts/finalize.py','positional_args':values})


@pytest.mark.parametrize('slot',['1','2'])
def test_failed_candidate_state_does_not_offer_another_finalize(tmp_path,slot):
    source='def first_items():\n    """shared retrieval signal"""\n    return 1\n\ndef second_items():\n    """shared retrieval signal"""\n    return 3\n'
    manager,roles=build_compiled(tmp_path,source)
    try:
        manager.write_file('tests/test_sample.py','from sample import first_items,second_items\ndef test_first_items():\n    assert first_items()==2\ndef test_second_items():\n    assert second_items()==4\n')
        for command in ['git add .','git commit -qm failing-test-base','git tag -f _swegemma_baseline']:
            assert manager.run_command(command).exit_code==0
        ready=payload(positional(roles,'root',['prepare','shared retrieval signal',slot]));assert ready['ok'],ready
        assert ready['state']=='prepared' and ready['next_actor']=='editor_'+slot
        assert ready['root_can_edit'] is False and ready['candidate_applied_to_central'] is False
        assert 'next_execution' not in ready and 'next_tool' not in ready
        unchanged=payload(positional(roles,'root',['status',slot]))
        assert unchanged['next_actor']==ready['next_actor'] and unchanged['root_can_edit'] is False
        name='first_items' if slot=='1' else 'second_items'
        edit=payload(positional(roles,'editor_'+slot,['edit_lines',ready['handle'],f'def {name}():','    """shared retrieval signal"""','    return 99']))
        assert edit['ok'],edit
        status=payload(positional(roles,'root',['status',slot]));assert 'next_execution' in status
        failed=payload(invoke(roles,'root',[],raw=status['next_execution']));assert not failed['ok'],failed
        assert 'outside verification' in failed['error']
        status=payload(positional(roles,'root',['status',slot]))
        assert status['verification_failed'] and status['next_actor']=='editor_'+slot
        assert 'next_execution' not in status
        assert manager.read_file('sample.py')==source
    finally:
        manager.cleanup_all()


def test_role_engines_are_identical_and_only_entries_differ():
    root=SUB/'skills/semdag/assets/engine'
    for folder in ['editor_1/semdag','editor_2/semdag']:
        other=SUB/'skills'/folder/'assets/engine'
        assert {p.name:p.read_bytes() for p in root.glob('*.py')}=={p.name:p.read_bytes() for p in other.glob('*.py')}
