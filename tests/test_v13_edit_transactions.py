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
