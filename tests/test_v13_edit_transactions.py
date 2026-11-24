"""Adversarial component fixtures; these do not establish real-task resolution."""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'AgenticSubmission/v13_orchestrator/skills/semdag/assets/engine'
NAMES = ['edit_tx', 'workspace_mgr', 'fix_edit', 'wsroot', 'impact', 'cache', 'snapshot',
         'semdag_ir_ast', 'retriever', 'vulnwalk', 'flow', 'task_ir', 'repo_eval']

@pytest.fixture
def modules(tmp_path, monkeypatch):
    saved = {n: sys.modules.pop(n) for n in NAMES if n in sys.modules}
    monkeypatch.syspath_prepend(str(SCRIPTS))
    monkeypatch.setenv('SEMDAG_CACHE', str(tmp_path / 'cache'))
    tx, wm = importlib.import_module('edit_tx'), importlib.import_module('workspace_mgr')
    monkeypatch.setattr(tx, 'home', lambda: tmp_path / 'state')
    monkeypatch.setattr(wm, 'WS_PREFIX', str(tmp_path / 'ws_'))
    yield tx, wm
    for n in NAMES:
        sys.modules.pop(n, None)
    sys.modules.update(saved)

@pytest.fixture
def repo(tmp_path):
    root = tmp_path / 'central'
    root.mkdir()
    (root / 'sample.py').write_text('def value():\n    return 1\n')
    for args in [['init','-q'], ['config','user.email','test@example.invalid'],
                 ['config','user.name','test'], ['add','.'], ['commit','-qm','base'],
                 ['tag','_swegemma_baseline']]:
        subprocess.run(['git',*args],cwd=root,check=True)
    return root


def begin(tx, repo, **kwargs):
    return tx.begin(str(repo), kwargs.pop('slot','1'), 'sample.py', 2, 2,
                    kwargs.pop('check', 'python -c "import sample; assert sample.value() == 2"'),
                    kwargs.pop('remaining', 30), **kwargs)


def test_success_single_use_outside_check_and_legacy_apply(modules, repo):
    tx, wm = modules
    initial = begin(tx,repo)
    edit = tx.edit(initial['handle'],'    return 2',str(repo),'1')
    assert (repo/'sample.py').read_text().endswith('return 1\n')
    with pytest.raises(ValueError,match='stale'):
        tx.edit(initial['handle'],'    return 3',str(repo),'1')
    applied = wm.apply_ws('1',str(repo))
    assert applied['ok'] and applied['clean']
    assert applied['outside_check']['exit_code'] == applied['central_check']['exit_code'] == 0
    assert (repo/'sample.py').read_text().endswith('return 2\n')
    with pytest.raises(ValueError):
        tx.finalize(edit['handle'],str(repo),'1')

@pytest.mark.parametrize('failure',['central','slot','cross_slot','cross_task','unknown','syntax','import','scope','range_write'])
def test_refused_edits_preserve_bytes(modules,repo,tmp_path,failure):
    tx,wm=modules
    handle=begin(tx,repo)['handle']
    slot=Path(wm._ws_dir('1'))
    if failure=='central': (repo/'sample.py').write_text('def value():\n    return 9\n')
    if failure=='slot': (slot/'sample.py').write_text('def value():\n    return 9\n')
    before=(repo/'sample.py').read_bytes(),(slot/'sample.py').read_bytes()
    with pytest.raises((ValueError,FileNotFoundError)):
        if failure=='scope': tx.narrow(handle,1,2,str(repo),'1')
        elif failure=='cross_slot': tx.edit(handle,'    return 2',str(repo),'2')
        elif failure=='cross_task':
            other=tmp_path/'other';other.mkdir();tx.edit(handle,'    return 2',str(other),'1')
        elif failure=='unknown':tx.edit('unknown','    return 2',str(repo),'1')
        elif failure=='syntax':tx.edit(handle,'    return (',str(repo),'1')
        elif failure=='import':tx.edit(handle,'    import no_such_v13_module_123',str(repo),'1')
        elif failure=='range_write':tx.legacy('sample.py','L2-2','    return 2',str(slot))
        else:tx.edit(handle,'    return 2',str(repo),'1')
    assert before==((repo/'sample.py').read_bytes(),(slot/'sample.py').read_bytes())


def test_stale_legacy_read_and_off_span_replayed(modules,repo):
    tx,wm=modules
    begin(tx,repo)
    fe=importlib.import_module('fix_edit');slot=Path(wm._ws_dir('1'))
    read=fe.run('sample.py','L2-2',None,repo=str(slot));assert read['handle']
    (slot/'sample.py').write_text('\ndef value():\n    return 1\n')
    with pytest.raises(ValueError):fe.run('sample.py','L2-2',None,repo=str(slot))
    with pytest.raises(ValueError):fe.run('sample.py','L1-1','pass',repo=str(slot))
    assert (repo/'sample.py').read_text()=='def value():\n    return 1\n'

@pytest.mark.parametrize('kind',['protected','unassigned','deleted','external_slot'])
def test_finalize_refuses_tampered_candidate(modules,repo,kind):
    tx,wm=modules;h=begin(tx,repo)['handle'];h=tx.edit(h,'    return 2',str(repo),'1')['handle']
    slot=Path(wm._ws_dir('1'))
    if kind=='protected':(slot/'conftest.py').write_text('raise RuntimeError')
    elif kind=='unassigned':(slot/'other.py').write_text('x=1')
    elif kind=='deleted':(slot/'sample.py').unlink()
    else:(slot/'sample.py').write_text('def value():\n    return 3\n')
    before=(repo/'sample.py').read_bytes()
    with pytest.raises((ValueError,FileNotFoundError)):tx.finalize(h,str(repo),'1')
    assert (repo/'sample.py').read_bytes()==before


def test_failed_check_and_pipefail_never_apply(modules,repo):
    tx,wm=modules;h=begin(tx,repo,check='python -c "raise AssertionError" | tail -1')['handle']
    h=tx.edit(h,'    return 2',str(repo),'1')['handle']
    before=(repo/'sample.py').read_bytes();out=tx.finalize(h,str(repo),'1')
    assert not out['ok'] and out['check']['exit_code']!=0
    assert (repo/'sample.py').read_bytes()==before


def test_timeout_never_applies(modules,repo):
    tx,wm=modules;h=begin(tx,repo,check='python -c "import time; time.sleep(2)"',remaining=0.2)['handle']
    h=tx.edit(h,'    return 2',str(repo),'1')['handle'];before=(repo/'sample.py').read_bytes()
    with pytest.raises((TimeoutError,subprocess.TimeoutExpired)):tx.finalize(h,str(repo),'1')
    assert (repo/'sample.py').read_bytes()==before

@pytest.mark.parametrize('interfere',[False,True])
def test_central_failure_rolls_back_only_own_bytes(modules,repo,monkeypatch,interfere):
    tx,wm=modules;h=begin(tx,repo)['handle'];h=tx.edit(h,'    return 2',str(repo),'1')['handle']
    real=tx.run_check
    def check(cmd,root,s):
        if Path(root)==repo:
            if interfere:(repo/'sample.py').write_text('def value():\n    return 99\n')
            return {'exit_code':1,'output':'failure','seconds':0}
        return real(cmd,root,s)
    monkeypatch.setattr(tx,'run_check',check)
    with pytest.raises(ValueError):tx.finalize(h,str(repo),'1')
    assert (repo/'sample.py').read_text().endswith('return 99\n' if interfere else 'return 1\n')

@pytest.mark.parametrize('eol,final,bom',[('\n',True,False),('\r\n',True,False),('\n',False,False),('\n',True,True)])
def test_modes_unicode_and_newlines(modules,repo,eol,final,bom):
    tx,wm=modules
    raw=('def value():\n    return 1'+ ('\n' if final else '')).replace('\n',eol).encode('utf-8-sig' if bom else 'utf-8')
    (repo/'sample.py').write_bytes(raw);os.chmod(repo/'sample.py',0o750)
    h=begin(tx,repo)['handle'];result=tx.edit(h,'    return 2  # π',str(repo),'1')
    data=(Path(wm._ws_dir('1'))/'sample.py').read_bytes()
    assert data==raw.replace(b'return 1', 'return 2  # π'.encode())
    assert (Path(wm._ws_dir('1'))/'sample.py').stat().st_mode&0o777==0o750
    assert result['handle']!=h


def test_encoding_range_deadline_and_reset(modules,repo):
    tx,wm=modules
    with pytest.raises(ValueError):tx.begin(str(repo),'1','sample.py',1,99,'true',30)
    with pytest.raises(ValueError):begin(tx,repo,remaining=241)
    (repo/'sample.py').write_bytes(b'# coding: latin-1\nx="\xe9"\n')
    with pytest.raises(ValueError):begin(tx,repo)
    (repo/'sample.py').write_text('def value():\n    return 1\n')
    h=begin(tx,repo)['handle'];wm.reset('1')
    with pytest.raises(ValueError):tx.edit(h,'    return 2',str(repo),'1')
    assert begin(tx,repo)['ok']


def test_can_repair_preexisting_syntax_error(modules,repo):
    tx,wm=modules
    (repo/'sample.py').write_text('def value():\n    return (\n')
    h=begin(tx,repo)['handle']
    assert tx.edit(h,'    return 2',str(repo),'1')['ok']


def test_protected_assignment_and_truncated_view_refused(modules,repo):
    tx,wm=modules
    (repo/'conftest.py').write_text('x=1\n')
    with pytest.raises(ValueError):tx.begin(str(repo),'1','conftest.py',1,1,'true',30)
    (repo/'sample.py').write_text('#' + 'x'*6100 + '\ndef value():\n    return 1\n')
    h=tx.begin(str(repo),'1','sample.py',1,3,'true',30)['handle']
    with pytest.raises(ValueError,match='truncated'):tx.edit(h,'x=2',str(repo),'1')


def test_empty_deletion_can_finalize(modules,repo):
    tx,wm=modules
    (repo/'sample.py').write_text('def value():\n    return 1\n# removable\n')
    for args in [['add','.'],['commit','-qm','comment baseline'],['tag','-f','_swegemma_baseline']]:
        subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
    h=tx.begin(str(repo),'1','sample.py',3,3,'python -c "import sample; assert sample.value()==1"',30)['handle']
    h=tx.edit(h,'',str(repo),'1')['handle']
    with pytest.raises(ValueError):tx.edit(h,'# replay',str(repo),'1')
    assert tx.finalize(h,str(repo),'1')['ok']

@pytest.mark.parametrize('loss',['missing','old_checkpoint'])
def test_crash_lost_metadata_fails_closed(modules,repo,loss):
    tx,wm=modules
    h=begin(tx,repo)['handle'];path,state=tx.load_handle(h,str(repo),'1');checkpoint=path.read_bytes()
    current=tx.edit(h,'    return 2',str(repo),'1')['handle']
    if loss=='missing':path.unlink()
    else:path.write_bytes(checkpoint)
    before=(repo/'sample.py').read_bytes()
    with pytest.raises((ValueError,FileNotFoundError)):
        if loss=='missing':tx.finalize(current,str(repo),'1')
        else:tx.edit(h,'    return 3',str(repo),'1')
    assert (repo/'sample.py').read_bytes()==before
    fe=importlib.import_module('fix_edit')
    with pytest.raises(ValueError):fe.run('sample.py','L2-2','    return 3',repo=wm._ws_dir('1'))


def test_fused_prepare_through_real_localizer_and_finalize(modules,repo):
    tx,wm=modules
    prepared=tx.prepare('sample.value returns 1 but must return 2',30,str(repo),'1')
    assert prepared['ok'] and prepared['baseline']['exit_code']==0
    assert 'return 1' in prepared['text']
    h=tx.edit(prepared['handle'],'def value():\n    return 2',str(repo),'1')['handle']
    assert tx.finalize(h,str(repo),'1')['ok']
    assert (repo/'sample.py').read_text()=='def value():\n    return 2\n'

@pytest.mark.parametrize('replacement',['return 2','break','continue','yield 1','nonlocal missing'])
def test_compile_context_errors_refused_before_slot_write(modules,repo,replacement):
    tx,wm=modules
    h=tx.begin(str(repo),'1','sample.py',1,2,'true',30)['handle']
    before=(repo/'sample.py').read_bytes(),(Path(wm._ws_dir('1'))/'sample.py').read_bytes()
    with pytest.raises(ValueError,match='cannot compile'):tx.edit(h,replacement,str(repo),'1')
    assert before==((repo/'sample.py').read_bytes(),(Path(wm._ws_dir('1'))/'sample.py').read_bytes())


def test_unmodified_reassignment_revokes_old_handles_and_metadata(modules,repo):
    tx,wm=modules
    (repo/'other.py').write_text('def other():\n    return 3\n')
    first=begin(tx,repo);path,state=tx.load_handle(first['handle'],str(repo),'1');old=path.read_bytes()
    second=tx.begin(str(repo),'1','other.py',1,2,'true',30)
    assert second['file']=='other.py' and second['handle']!=first['handle']
    with pytest.raises(ValueError):tx.edit(first['handle'],'    return 9',str(repo),'1')
    current=path.read_bytes();path.write_bytes(old)
    with pytest.raises(ValueError,match='generation'):tx.edit(first['handle'],'    return 9',str(repo),'1')
    path.write_bytes(current)
    third=tx.edit(second['handle'],'def other():\n    return 4',str(repo),'1')
    before=(Path(wm._ws_dir('1'))/'other.py').read_bytes()
    with pytest.raises(ValueError,match='pending changes'):begin(tx,repo)
    assert (Path(wm._ws_dir('1'))/'other.py').read_bytes()==before
    assert tx.load_handle(third['handle'],str(repo),'1')[1]['state']=='edited'


def test_read_view_checkpoint_cannot_revoke_newer_generation(modules,repo):
    tx,wm=modules;h=tx.begin(str(repo),'1','sample.py',1,2,'true',30)['handle']
    path,state=tx.load_handle(h,str(repo),'1');old=path.read_bytes()
    tx.narrow(h,2,2,str(repo),'1');path.write_bytes(old)
    with pytest.raises(ValueError,match='generation'):tx.edit(h,'def value():\n    return 2',str(repo),'1')
    assert (repo/'sample.py').read_text().endswith('return 1\n')


def test_bm25_keeps_function_and_trusted_anchor_keeps_locus(modules,repo):
    tx,wm=modules
    content='def first_items():\n    """shared item"""\n    values = [item for item in range(2)]\n    return values\n'
    (repo/'sample.py').write_text(content)
    guessed=tx.prepare('shared item',30,str(repo),'1')
    p,s=tx.load_handle(guessed['handle'],str(repo),'1');cache=importlib.import_module('cache')
    guessed_ir=cache.read(s['container'],'task_ir.json')
    assert guessed_ir['anchor']['how']=='bm25'
    assert guessed_ir['locus'] is None and s['allowed']==[1,4]
    exact=tx.prepare('sample.first_items item',30,str(repo),'1')
    p,s=tx.load_handle(exact['handle'],str(repo),'1');exact_ir=cache.read(s['container'],'task_ir.json')
    assert exact_ir['anchor']['how']=='qualname' and exact_ir['locus'] is not None
    assert s['allowed']==[3,3]


def test_slot_specific_cache_metadata_and_other_cache_poisoning(modules,repo):
    tx,wm=modules
    content='def first():\n    """shared item"""\n    values = [item for item in range(2)]\n    return values\n'
    (repo/'sample.py').write_text(content)
    (repo/'zeta.py').write_text(content.replace('first','second'))
    for args in [['add','.'],['commit','-qm','two sites'],['tag','-f','_swegemma_baseline']]:
        subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
    one=tx.prepare('shared item',30,str(repo),'1');two=tx.prepare('shared item',30,str(repo),'2')
    _,s1=tx.load_handle(one['handle'],str(repo),'1');_,s2=tx.load_handle(two['handle'],str(repo),'2')
    assert s1['container']!=s2['container'] and s1['file']!=s2['file']
    cache=importlib.import_module('cache')
    for state in [s1,s2]:
        ir=cache.read(state['container'],'task_ir.json')
        assert ir['edit']['file']==state['file'] and state['file'] in state['check']
        assert ir['locus'] is None
    poison={'edit':{'file':s1['file'],'start':999,'end':1000},'locus':{'kind':'for','file':s1['file'],'start':999,'end':1000,'carried':['item']}}
    cache.write('task','task_ir.json',poison);cache.write(s2['container'],'task_ir.json',poison)
    target=(Path(s1['workspace'])/s1['file']).read_text()
    replacement=target.replace('range(2)','range(3)')
    h=tx.edit(one['handle'],replacement,str(repo),'1')['handle']
    assert tx.finalize(h,str(repo),'1')['ok']
    assert 'range(3)' in (repo/s1['file']).read_text()


def test_baseline_clock_is_conservative_and_expired_future_missing_fail(modules,repo,monkeypatch,tmp_path):
    tx,wm=modules
    stamp=int(subprocess.run(['git','show','-s','--format=%ct','refs/tags/_swegemma_baseline'],cwd=repo,capture_output=True,text=True,check=True).stdout)
    monkeypatch.setattr(tx.time,'time',lambda:stamp+10.25)
    assert tx.task_remaining(repo)==pytest.approx(229.75)
    monkeypatch.setattr(tx.time,'time',lambda:stamp+240)
    with pytest.raises(TimeoutError):tx.task_remaining(repo)
    monkeypatch.setattr(tx.time,'time',lambda:stamp-1)
    with pytest.raises(ValueError,match='future'):tx.task_remaining(repo)
    empty=tmp_path/'no-clock';empty.mkdir()
    with pytest.raises(tx.BudgetAnchorUnavailable):tx.task_remaining(empty)


def test_unicode_separators_are_not_python_source_line_boundaries(modules,repo):
    tx,wm=modules
    original='def value():\n    return "a\u2028b\u2029c"\n'
    (repo/'sample.py').write_text(original)
    h=tx.begin(str(repo),'1','sample.py',2,2,'true',30)['handle']
    view=tx.view_result(tx.load_handle(h,str(repo),'1')[1])
    assert view['text']=='2:     return "a\u2028b\u2029c"'
    out=tx.edit(h,'    return "x\u2028y\u2029z"',str(repo),'1')
    assert out['ok']
    assert (Path(wm._ws_dir('1'))/'sample.py').read_text()=='def value():\n    return "x\u2028y\u2029z"\n'
    assert tx.finalize(out['handle'],str(repo),'1')['ok']


def test_explicit_location_and_module_global_disambiguate(modules,repo):
    tx,wm=modules
    (repo/'other.py').write_text('def value():\n    return 9\n')
    for args in [['add','.'],['commit','-qm','two modules'],['tag','-f','_swegemma_baseline']]:
        subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
    ready=tx.prepare('other.py:2 wrong return',30,str(repo),'1')
    _,state=tx.load_handle(ready['handle'],str(repo),'1')
    assert ready['anchor']=='location' and state['file']=='other.py'
    ready=tx.prepare('sample.value wrong return',30,str(repo),'1')
    _,state=tx.load_handle(ready['handle'],str(repo),'1')
    assert ready['anchor']=='qualname' and state['file']=='sample.py'


def test_ambiguous_location_list_fails_without_preparation(modules,repo):
    tx,wm=modules
    with pytest.raises(ValueError,match='ambiguous'):
        tx.prepare('sample.py lines 1, 2 fail',30,str(repo),'1')
    assert not tx.state_path(str(repo),'1').exists()


def test_single_letter_prose_does_not_force_a_loop_locus(modules,repo):
    tx,wm=modules
    (repo/'sample.py').write_text('def merge_items():\n    a = []\n    for item in range(2):\n        a.append(item)\n    return a\n')
    ready=tx.prepare('merge_items has a failure',30,str(repo),'1')
    _,state=tx.load_handle(ready['handle'],str(repo),'1');cache=importlib.import_module('cache')
    assert cache.read(state['container'],'task_ir.json')['locus'] is None
    ready=tx.prepare('merge_items has a failure in `a`',30,str(repo),'1')
    _,state=tx.load_handle(ready['handle'],str(repo),'1')
    assert cache.read(state['container'],'task_ir.json')['locus'] is not None


def test_verification_baseline_is_operation_local_and_worktree_stays_fresh(modules, repo, monkeypatch):
    impact=importlib.import_module('impact');reval=importlib.import_module('repo_eval')
    calls=[];real_git=impact._git
    def observe(path,*args,**kwargs):
        calls.append(args)
        return real_git(path,*args,**kwargs)
    monkeypatch.setattr(impact,'_git',observe)
    opt=reval.parse_args(['--verify','--container','native_git_reads','--repo',str(repo)])
    (repo/'sample.py').write_text('def value():\n    return 2\n')
    first=reval.verify(opt)
    assert first['clean'] and first['base']=='_swegemma_baseline'
    assert sum(c[0]=='rev-parse' for c in calls)==1
    assert sum(c[0]=='show' for c in calls)==1
    (repo/'sample.py').write_text('def value():\n    return missing_native_name\n')
    second=reval.verify(opt)
    assert not second['clean'] and second['blocked'] and second['undefined_names']
    # A later verification observes a moved baseline as well as the current tree.
    (repo/'sample.py').write_text('def value():\n    return 2\n')
    for args in [['add','sample.py'],['commit','-qm','new-base'],['tag','-f','_swegemma_baseline']]:
        subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
    third=reval.verify(opt)
    assert third['patch']['empty'] and third['blocked'] and not third['clean']


def test_old_side_reads_use_immutable_commit_when_tag_moves(modules,repo,tmp_path):
    impact=importlib.import_module('impact');reval=importlib.import_module('repo_eval')
    baseline=impact.resolve_baseline(str(repo))
    (repo/'sample.py').write_text('def value():\n    return 2\n')
    for args in [['add','.'],['commit','-qm','later'],['tag','-f','_swegemma_baseline']]:
        subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
    assert baseline.old_content('sample.py').endswith('return 1\n')
    fixed=impact.analyze(str(repo),baseline=baseline)
    assert not fixed['patch']['empty'] and fixed['changed_defs']
    assert reval.old_hunks(str(repo),'sample.py',baseline=baseline)==[(2,2)]
    assert impact.analyze(str(repo))['patch']['empty']
    with pytest.raises(ValueError,match='another repository'):
        impact.analyze(str(tmp_path),baseline=baseline)


def test_shared_git_reads_preserve_destructive_and_protected_gates(modules,repo):
    reval=importlib.import_module('repo_eval')
    original='def value():\n'+''.join(f'    item_{i} = {i}\n' for i in range(60))+'    return 1\n'
    (repo/'sample.py').write_text(original)
    for args in [['add','.'],['commit','-qm','long-base'],['tag','-f','_swegemma_baseline']]:
        subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
    (repo/'sample.py').write_text('def value():\n    return 2\n')
    (repo/'test_untracked.py').write_text('raise RuntimeError("protected")\n')
    result=reval.verify(reval.parse_args(['--verify','--container','destructive_git_reads','--repo',str(repo)]))
    assert not result['clean'] and result['blocked'] and 'deletes' in result['next']
    assert result['patch']['files']==['sample.py']
    assert 'test_untracked.py' in result['patch']['stripped']


def test_missing_git_baseline_retains_snapshot_fallback(modules,tmp_path):
    impact=importlib.import_module('impact');cache=importlib.import_module('cache')
    path=tmp_path/'plain';path.mkdir();source=path/'sample.py';source.write_text('def value():\n    return 1\n')
    base={'sample.py':{'sha256':cache.sha256_file(source),'content':source.read_text()}}
    source.write_text('def value():\n    return 2\n')
    result=impact.analyze(str(path),base_files=base)
    assert result['base']=='snapshot' and result['clean'] and result['patch']['files']==['sample.py']


@pytest.mark.parametrize('eol,bom',[(b'\n',b''),(b'\r\n',b''),(b'\n',b'\xef\xbb\xbf')])
def test_exact_fragment_preserves_header_docstring_and_surrounding_bytes(modules,repo,eol,bom):
    tx,wm=modules
    text='def value():\n    """literal \\n, "quotes", λ\u2028content"""\n    result = 1\n    return result\n\ndef untouched():\n    return 9'
    data=bom+text.encode().replace(b'\n',eol);(repo/'sample.py').write_bytes(data)
    h=tx.begin(str(repo),'1','sample.py',1,4,'python -c "import sample; assert sample.value()==2"',60)['handle']
    out=tx.replace_text(h,'result = 1','result = 2',str(repo),'1')
    assert out['ok'] and out['edit_operation']=='exact_fragment'
    assert Path(wm._ws_dir('1'),'sample.py').read_bytes()==data.replace(b'result = 1',b'result = 2',1)
    assert (repo/'sample.py').read_bytes()==data
    result=tx.finalize(out['handle'],str(repo),'1');assert result['ok'],result
    assert (repo/'sample.py').read_bytes()==data.replace(b'result = 1',b'result = 2',1)


@pytest.mark.parametrize('case',['missing','ambiguous','overlap','outside','stale','cross_slot','syntax','empty','long','too_many_lines'])
def test_exact_fragment_failures_do_not_mutate_source_or_lease(modules,repo,case):
    tx,wm=modules
    source='def value():\n    text = "aaa"\n    result = 1 + 1\n    return result\n\ndef other():\n    return 7\n'
    (repo/'sample.py').write_text(source)
    h=tx.begin(str(repo),'1','sample.py',1,4,'python -c "import sample"',60)['handle']
    old,new='result = 1 + 1','result = 2'
    if case=='missing':old='not present'
    if case=='ambiguous':old='1'
    if case=='overlap':old='aa'
    if case=='outside':old='return 7'
    if case=='stale':tx.narrow(h,3,3,str(repo),'1')
    if case=='syntax':new='result = ('
    if case=='empty':old=''
    if case=='long':old='x'*2049
    if case=='too_many_lines':old='x\n'*17
    slot=Path(wm._ws_dir('1'));before=(slot/'sample.py').read_bytes();manifest=tx.state_path(str(repo),'1').read_bytes()
    with pytest.raises((ValueError,FileNotFoundError)):
        tx.replace_text(h,old,new,str(repo),'2' if case=='cross_slot' else '1')
    assert (slot/'sample.py').read_bytes()==before and (repo/'sample.py').read_text()==source
    assert tx.state_path(str(repo),'1').read_bytes()==manifest


def test_exact_fragment_intervening_view_is_not_silently_rebased(modules,repo,monkeypatch):
    tx,_=modules;h=begin(tx,repo)['handle'];real_edit=tx.edit
    def intervene(handle,replacement,*args):
        tx.narrow(handle,2,2,str(repo),'1')
        return real_edit(handle,replacement,*args)
    monkeypatch.setattr(tx,'edit',intervene)
    with pytest.raises(ValueError,match='stale'):
        tx.replace_text(h,'return 1','return 2',str(repo),'1')
    assert (repo/'sample.py').read_text()=='def value():\n    return 1\n'


def test_exact_fragment_explicit_deletion_preserves_remaining_lines(modules,repo):
    tx,wm=modules
    source='def value():\n    unused = 1\n    return 2\n';(repo/'sample.py').write_text(source)
    h=tx.begin(str(repo),'1','sample.py',1,3,'python -c "import sample; assert sample.value()==2"',60)['handle']
    out=tx.replace_text(h,'    unused = 1\n','',str(repo),'1')
    assert out['ok'] and Path(wm._ws_dir('1'),'sample.py').read_text()=='def value():\n    return 2\n'


def test_real_retriever_header_loss_replay_and_exact_fragment_counterpart(modules,repo):
    import ast
    tx,wm=modules
    original=(SCRIPTS/'retriever.py').read_text();(repo/'sample.py').unlink();(repo/'retriever.py').write_text(original)
    for args in [['add','-A'],['commit','-qm','real-retriever'],['tag','-f','_swegemma_baseline']]:
        subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
    node=next(n for n in ast.parse(original).body if isinstance(n,ast.FunctionDef) and n.name=='_documents')
    check='python -c "import retriever; assert callable(retriever._documents); assert retriever.tokens(\'CamelCase\')==[\'camelcase\',\'camel\',\'case\']"'
    bad=tx.begin(str(repo),'1','retriever.py',node.lineno,node.end_lineno,check,60)
    body_only=tx.edit(bad['handle'],'    return list(docs)',str(repo),'1')
    assert body_only['ok']  # Reproduces the old compiled-but-missing-definition failure.
    failed=tx.finalize(body_only['handle'],str(repo),'1')
    assert not failed['ok'] and 'outside verification' in failed['error']
    assert (repo/'retriever.py').read_text()==original
    good=tx.begin(str(repo),'2','retriever.py',node.lineno,node.end_lineno,check,60)
    changed=tx.replace_text(good['handle'],'return docs','return list(docs)',str(repo),'2')
    expected=original.replace('return docs','return list(docs)',1)
    assert Path(wm._ws_dir('2'),'retriever.py').read_text()==expected
    assert tx.finalize(changed['handle'],str(repo),'2')['ok']
    assert (repo/'retriever.py').read_text()==expected


def test_ast_analysis_accepts_only_one_leading_encoding_marker(modules):
    impact=importlib.import_module('impact')
    assert impact._parse('\ufeffx=1','bom.py')[1] is None
    assert impact._parse('\ufeff\ufeffx=1','double.py')[1] is not None
    assert impact._parse('x=1\n\ufeffy=2','embedded.py')[1] is not None
