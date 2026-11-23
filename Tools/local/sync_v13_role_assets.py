"""Keep the three packaged native engines byte-identical; entry roles stay separate."""
import argparse
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]/'AgenticSubmission/v13_orchestrator/skills'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    source=ROOT/'semdag/assets/engine';expected={f.name:f.read_bytes() for f in source.glob('*.py')}
    for role in ['editor_1','editor_2']:
        dest=ROOT/role/'semdag/assets/engine'
        if a.check:
            if expected!={f.name:f.read_bytes() for f in dest.glob('*.py')}:
                raise SystemExit(f'engine drift: {role}')
        else:
            dest.mkdir(parents=True,exist_ok=True)
            for f in dest.glob('*.py'):
                if f.name not in expected:f.unlink()
            for f in source.glob('*.py'):shutil.copy2(f,dest/f.name)
    print('native engines identical')

if __name__=='__main__':main()
