"""Fixed-source component lifecycle comparison; not a model or task-resolution score.

Baseline and candidate receive identical real v13 retriever source, patch, and checks.
Run seven alternating old/new repetitions after one warm-up per arm.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'reports/v13_stage1_2026-11-22/baseline/skills/semdag/scripts'
CANDIDATE = ROOT / 'AgenticSubmission/v13_orchestrator/skills/semdag/scripts'
CHECK = 'python -c \'import retriever; assert retriever.tokens("CamelCase") == ["camelcase", "camel", "case"]\''


def trial(arm):
    scripts = SOURCE if arm == 'old' else CANDIDATE
    sys.path.insert(0, str(scripts))
    with tempfile.TemporaryDirectory(prefix='v13-timing-') as d:
        base=Path(d);repo=base/'central';repo.mkdir()
        source=(SOURCE/'retriever.py').read_text();(repo/'retriever.py').write_text(source)
        os.environ['SEMDAG_CACHE']=str(base/'cache')
        for args in [['init','-q'],['config','user.email','local@example.invalid'],['config','user.name','component'],
                     ['add','.'],['commit','-qm','base'],['tag','_swegemma_baseline']]:
            subprocess.run(['git',*args],cwd=repo,check=True)
        import workspace_mgr as wm
        import fix_edit as fe
        import repo_eval as reval
        wm.WS_PREFIX=str(base/'ws_')
        import ast
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_documents')
        a,b=node.lineno,node.end_lineno
        replacement='\n'.join(source.splitlines()[a-1:b]).replace('return docs','return list(docs)')
        def check(path):
            result=subprocess.run(['/bin/bash','-o','pipefail','-c',CHECK],cwd=path,capture_output=True,
                                  env={**os.environ,'PATH':str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH'],
                                       'PYTHONPATH':str(path),'PYTHONDONTWRITEBYTECODE':'1'})
            assert result.returncode==0, result.stderr
        if arm == 'new':
            import edit_tx as tx
            tx.home=lambda:base/'state'
        started=time.perf_counter()
        if arm=='old':
            check(repo)
            wm.spawn('1','retriever.py',f'{a}-{b}',CHECK,repo=str(repo))
            slot=Path(wm._ws_dir('1'))
            assert fe.run('retriever.py',f'L{a}-{b}',None,repo=str(slot))['ok']
            assert fe.run('retriever.py',f'L{a}-{b}',replacement,repo=str(slot))['ok']
            check(slot)
            assert not wm.collect('1',str(repo))['empty']
            assert wm.apply_ws('1',str(repo))['ok']
            check(repo)
            assert reval.verify(reval.parse_args(['--verify','--repo',str(repo)]))['clean']
            calls=9
        else:
            # begin is the deterministic prepare primitive after localization. Both arms use fixed span/check.
            baseline=tx.run_check(CHECK,repo,{'deadline':time.monotonic()+60})
            h=tx.begin(str(repo),'1','retriever.py',a,b,CHECK,60,baseline=baseline)['handle']
            h=tx.edit(h,replacement,str(repo),'1')['handle']
            assert tx.finalize(h,str(repo),'1')['ok']
            calls=4
        duration=time.perf_counter()-started
        expected='\n'.join(source.splitlines()[:a-1]+replacement.splitlines()+source.splitlines()[b:])+'\n'
        assert (repo/'retriever.py').read_text()==expected
        return {'arm':arm,'seconds':duration,'control_calls':calls,'output_sha256':__import__('hashlib').sha256(expected.encode()).hexdigest()}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--arm',choices=['old','new']);ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    if args.arm:
        print(json.dumps(trial(args.arm)));return
    def run(arm):
        r=subprocess.run([sys.executable,__file__,'--arm',arm],capture_output=True,text=True,
                         env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},check=True)
        return json.loads(r.stdout.splitlines()[-1])
    run('old');run('new');rows=[]
    for i in range(7):
        for arm in (['old','new'] if i%2==0 else ['new','old']): rows.append(run(arm))
    med={arm:statistics.median(r['seconds'] for r in rows if r['arm']==arm) for arm in ['old','new']}
    ratio=med['new']/med['old'];same=len({r['output_sha256'] for r in rows})==1
    out={'kind':'real-source component benchmark, no model/task-resolution claim','rows':rows,'medians_seconds':med,
         'new_over_old':ratio,'calls_old':9,'calls_new':4,'same_output':same,
         'gate_passed':same and ratio<=1.10 and 9-4>=3}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(out,indent=2));print(json.dumps(out))

if __name__=='__main__':main()
