"""Hash-bound managed edits and deterministic prepare/finalize skill actions.

These guards cover this module and managed legacy helpers, not arbitrary shell writes.
State and verification copies stay in the sandbox's temporary directory.
"""
import argparse
import ast
import importlib.util
import sys
import contextlib
import difflib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import signal
import stat
import subprocess
import tempfile
import time
import tokenize
import uuid

import wsroot


def digest(data):
    return hashlib.sha256(data).hexdigest()


def home():
    return Path(tempfile.gettempdir()) / 'v13-edit-tx'


def state_path(repo, slot):
    import workspace_mgr as wm
    wm._ws_dir(slot)  # Validate before constructing paths.
    return home() / digest(os.fsencode(os.path.realpath(repo)))[:20] / (str(slot) + '.json')


def save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.state-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(state, f, sort_keys=True)
            f.flush()
        # Ephemeral metadata is atomically replaced. Crash-lost metadata fails closed
        # against source hashes; only actual source writes require durable fsync.
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextlib.contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix('.lock'), 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def managed(repo):
    root = os.path.realpath(repo)
    for p in home().glob('*/*.json'):
        s = json.loads(p.read_text())
        if s['workspace'] == root:
            return p, s
    if (Path(root) / '.v13-managed').exists():
        raise ValueError('managed slot metadata missing; prepare a fresh slot')
    return None


def load_handle(handle, repo=None, slot=None):
    m = re.fullmatch(r'([a-f0-9]{20})\.([A-Za-z0-9_-]{1,64})\.([a-f0-9]{32})', handle)
    if not m:
        raise ValueError('unknown edit handle')
    p = home() / m[1] / (m[2] + '.json')
    s = json.loads(p.read_text())
    if s['handle'] != handle:
        raise ValueError('stale or already-used handle')
    if slot is not None and str(slot) != s['slot']:
        raise ValueError('cross-slot handle')
    actual = os.path.realpath(wsroot.workspace_root(repo))
    if actual not in (s['repo'], s['workspace']):
        raise ValueError('cross-task handle')
    return p, s


def check_deadline(s):
    left = s['deadline'] - time.monotonic()
    if left <= 0:
        raise TimeoutError('transaction deadline exhausted')
    return left


def file_at(root, rel):
    import workspace_mgr as wm
    return Path(wm._safe_path(root, rel))


def decode(data):
    enc = tokenize.detect_encoding(io.BytesIO(data).readline)[0]
    if enc not in ('utf-8', 'utf-8-sig'):
        raise ValueError('unsupported source encoding; unchanged')
    raw = data.decode(enc)
    if '\r' in raw.replace('\r\n', ''):
        raise ValueError('unsupported bare CR newline; unchanged')
    if '\r\n' in raw and '\n' in raw.replace('\r\n', ''):
        raise ValueError('mixed newlines; unchanged')
    return raw.replace('\r\n', '\n'), enc, '\r\n' if '\r\n' in raw else '\n'


def tree(root):
    import workspace_mgr as wm
    out = {}
    for current, dirs, names in os.walk(root):
        ignored = wm.IGNORE(current, dirs + names)
        dirs[:] = [d for d in dirs if d not in ignored]
        for n in dirs + [n for n in names if n not in ignored]:
            if os.path.islink(os.path.join(current, n)):
                raise ValueError('symlink in managed workspace')
        for n in names:
            if n in ignored or n in ('Agents.md', '.v13-managed'):
                continue
            p = Path(current) / n
            out[str(p.relative_to(root))] = digest(p.read_bytes())
    return out


def check_versions(s):
    check_deadline(s)
    central = file_at(s['repo'], s['file'])
    target = file_at(s['workspace'], s['file'])
    if digest(central.read_bytes()) != s['base_hash']:
        raise ValueError('central source changed since preparation')
    if digest(target.read_bytes()) != s['slot_hash']:
        raise ValueError('slot source changed since last issued view')
    return central, target


def issue_handle(p, s, span=None):
    if span:
        s['view'] = span
    s['generation'] += 1
    s['handle'] = f'{p.parent.name}.{s["slot"]}.{uuid.uuid4().hex}'
    save(p, s)
    return view_result(s)


def view_result(s):
    data = file_at(s['workspace'], s['file']).read_bytes()
    text, _enc, _eol = decode(data)
    a, b = s['view']
    shown = '\n'.join(f'{i}: {line}' for i, line in enumerate(text.splitlines()[a-1:b], a))
    return {'ok': True, 'slot': s['slot'], 'handle': s['handle'], 'generation': s['generation'],
            'file': s['file'], 'lines': f'{a}-{b}', 'text': shown[:6000],
            'text_truncated': len(shown) > 6000, 'baseline': s.get('baseline'),
            'remaining_seconds': round(max(0, s['deadline'] - time.monotonic()), 2)}


def run_check(command, root, s):
    left = check_deadline(s)
    started = time.monotonic()
    # pipefail preserves pytest failure even when a legacy check pipes through tail.
    with tempfile.TemporaryFile() as output:
        proc = subprocess.Popen(['/bin/bash', '-o', 'pipefail', '-c', command], cwd=root,
                                stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
                                env={**os.environ, 'PYTHONPATH': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
                                     'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '/usr/bin:/bin')})
        try:
            code = proc.wait(timeout=min(300, left))
        except BaseException:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            raise
        output.seek(0, os.SEEK_END)
        length = output.tell()
        output.seek(max(0, length - 3000))
        text = output.read().decode('utf-8', errors='replace')
    return {'exit_code': code, 'seconds': time.monotonic() - started, 'output': text,
            'output_truncated': length > 3000}


def begin(repo, slot, rel, a, b, check, remaining, issue='', baseline=None):
    import impact
    import workspace_mgr as wm
    repo = os.path.realpath(wsroot.workspace_root(repo))
    if not 0 < remaining <= 240:
        raise ValueError('remaining must be between 0 and 240 seconds from get_status')
    path = file_at(repo, rel)
    if impact.is_protected(rel) or not rel.endswith('.py'):
        raise ValueError('only assigned, unprotected Python source is editable')
    source = path.read_bytes()
    text, _enc, _eol = decode(source)
    if not 1 <= a <= b <= len(text.splitlines()):
        raise ValueError('assignment range outside source')
    if not check.strip():
        raise ValueError('verification command required')
    p = state_path(repo, slot)
    with locked(p):
        if p.exists() and json.loads(p.read_text())['state'] not in ('applied', 'failed'):
            raise ValueError('slot already has an active transaction')
        deadline = time.monotonic() + remaining
        original_tree = tree(repo)
        result = wm._spawn_copy(slot, rel, f'{a}-{b}', check, issue=issue, repo=repo)
        s = {'repo': repo, 'workspace': os.path.realpath(result['workspace']), 'slot': str(slot),
             'file': rel, 'allowed': [a, b], 'view': [a, b], 'base_hash': digest(source),
             'slot_hash': digest(source), 'base_tree': original_tree, 'generation': 0,
             'state': 'prepared', 'check': check, 'deadline': deadline, 'baseline': baseline}
        if tree(repo) != original_tree or tree(s['workspace']) != original_tree:
            raise ValueError('source changed during workspace creation')
        check_deadline(s)
        (Path(s['workspace']) / '.v13-managed').write_text('managed\n')
        out = issue_handle(p, s)
        # A managed assignment must not retain the legacy edit/check instructions.
        assignment = (f"# Managed editor assignment: slot {slot}\n\n"
                      f"Workspace: {s['workspace']}\nFile: {rel}\nSpan: {a}-{b}\n"
                      f"Handle: {s['handle']}\n\nIssue: {issue}\n\n"
                      f"Numbered view:\n{out['text']}\n\n"
                      "Use run_skill_script with skill_name semdag, file_path scripts/edit_tx.py, "
                      "and args [--edit, HANDLE, --slot, SLOT, --text, REPLACEMENT]. "
                      "All args are strings. Use --view HANDLE --slot SLOT --lines A-B to narrow a truncated view. "
                      "Return EDIT_READY with the new handle after edit success. "
                      "Outside tests and finalization belong to the orchestrator. "
                      "Never edit central source, other slots or tests/configs.\n")
        (Path(s['workspace']) / 'Agents.md').write_text(assignment)
        return out


def prepare(issue, remaining, repo=None, slot='1'):
    import cache
    import repo_eval
    if not 0 < remaining <= 240:
        raise ValueError('remaining must be between 0 and 240')
    started = time.monotonic()
    result = repo_eval.locate(repo_eval.parse_args(['--repo', wsroot.workspace_root(repo), issue]))
    if result.get('error') or not result.get('text', '').startswith('edit '):
        raise ValueError('localization did not produce an edit assignment: ' + str(result)[:300])
    assignment = cache.read('task', 'task_ir.json')
    check = assignment['check']
    s = {'deadline': started + remaining}
    baseline = run_check(check, wsroot.workspace_root(repo), s)
    ranked = cache.read('task', 'eval.json')['retrieval']['top']
    alternatives = ranked[1:3] if assignment['anchor']['how'] == 'bm25' else []
    rel, a, b = assignment['edit']['file'], assignment['edit']['start'], assignment['edit']['end']
    if str(slot) == '2':
        if not alternatives:
            raise ValueError('no distinct alternative assigned to slot 2')
        alt = alternatives[0]
        rel, a, b = alt['file'], alt['line'], alt['end_line']
    result = begin(repo, slot, rel, a, b, check, check_deadline(s), issue, baseline)
    result['alternatives'] = alternatives
    result['anchor'] = assignment['anchor']['how']
    return result


def narrow(handle, a, b, repo=None, slot=None):
    p, _ = load_handle(handle, repo, slot)
    with locked(p):
        _, s = load_handle(handle, repo, slot)
        check_versions(s)
        if not s['allowed'][0] <= a <= b <= s['allowed'][1]:
            raise ValueError('view outside assignment')
        return issue_handle(p, s, [a, b])


def edit(handle, replacement, repo=None, slot=None):
    import fix_edit
    p, _ = load_handle(handle, repo, slot)
    with locked(p):
        _, s = load_handle(handle, repo, slot)
        if s['state'] not in ('prepared', 'edited'):
            raise ValueError('transaction cannot edit in current state')
        _, target = check_versions(s)
        before = target.read_bytes()
        text, enc, eol = decode(before)
        a, b = s['view']
        if a > b:
            raise ValueError('deleted view has no further editable lines; finalize or prepare again')
        if view_result(s)['text_truncated']:
            raise ValueError('view is truncated; request a smaller --view before editing')
        lines = text.splitlines()
        block = replacement.replace('\r\n', '\n').splitlines()
        candidate = '\n'.join(lines[:a-1] + block + lines[b:]) + ('\n' if text.endswith('\n') else '')
        if candidate == text:
            raise ValueError('no change')
        try:
            new_tree = ast.parse(candidate)
        except (SyntaxError, ValueError, RecursionError) as exc:
            raise ValueError('replacement would break Python syntax') from exc
        try:
            old_tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            old_tree = ast.Module(body=[], type_ignores=[])
        errors = fix_edit._import_errors(s['workspace'], s['file'], old_tree, new_tree)
        old_imports = {a.name for node in ast.walk(old_tree) if isinstance(node, ast.Import) for a in node.names}
        for node in ast.walk(new_tree):
            if not isinstance(node, ast.Import):
                continue
            for alias in node.names:
                if alias.name in old_imports:
                    continue
                root_name = alias.name.split('.')[0]
                local = fix_edit._resolve_repo_module(s['workspace'], s['file'], alias.name, 0)
                try:
                    known = local or importlib.util.find_spec(root_name)
                except (ImportError, ValueError, AttributeError):
                    known = None
                if not known:
                    errors.append({'import': alias.name, 'msg': 'module not found'})
        if errors:
            raise ValueError('unresolved new import: ' + str(errors)[:400])
        data = candidate.replace('\n', eol).encode(enc)
        # Recheck immediately before replacement. Locks coordinate these helpers, not arbitrary shells.
        check_versions(s)
        atomic_source(target, data, stat.S_IMODE(target.stat().st_mode))
        delta = len(block) - (b-a+1)
        s['allowed'][1] += delta
        s['view'] = [a, a+len(block)-1] if block else [s['allowed'][0], s['allowed'][1]]
        s['slot_hash'], s['state'] = digest(data), 'edited'
        out = issue_handle(p, s)
        out['diff'] = ''.join(difflib.unified_diff(text.splitlines(True), candidate.splitlines(True),
                                                fromfile='a/'+s['file'], tofile='b/'+s['file']))[:1600]
        return out


def atomic_source(path, data, mode):
    fd, tmp = tempfile.mkstemp(prefix='.v13-edit-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def legacy(filepath, old, new, repo):
    item = managed(repo)
    if not item:
        raise ValueError('not a managed slot')
    p, s = item
    if filepath != s['file']:
        raise ValueError('file is outside assignment')
    m = re.fullmatch(r'L(\d+)(?:-(\d+))?', old or '', re.IGNORECASE)
    if not m:
        raise ValueError('managed edits require an issued handle or a numbered range')
    a, b = int(m[1]), int(m[2] or m[1])
    if new is None:
        return narrow(s['handle'], a, b, repo, s['slot'])
    raise ValueError('managed range writes require the edit handle returned by read; use edit_tx --edit')


def finalize(handle, repo=None, slot=None):
    import workspace_mgr as wm
    import repo_eval
    p, _ = load_handle(handle, repo, slot)
    with locked(p):
        _, s = load_handle(handle, repo, slot)
        if s['state'] != 'edited':
            raise ValueError('no edited candidate ready')
        central, target = check_versions(s)
        current_tree = tree(s['workspace'])
        changed = {k for k in set(current_tree) | set(s['base_tree'])
                   if current_tree.get(k) != s['base_tree'].get(k)}
        if changed != {s['file']}:
            raise ValueError('candidate changed files outside its assignment')
        candidate, before = target.read_bytes(), central.read_bytes()
        # External shell edits also must stay inside the original assignment.
        old_text, _, _ = decode(before)
        new_text, _, _ = decode(candidate)
        a, b = s['allowed'][0], s['allowed'][1]
        original_b = b - (len(new_text.splitlines()) - len(old_text.splitlines()))
        if (old_text.splitlines()[:a-1] != new_text.splitlines()[:a-1]
                or old_text.splitlines()[original_b:] != new_text.splitlines()[b:]):
            raise ValueError('candidate changes outside assigned span')
        with tempfile.TemporaryDirectory(prefix='v13-verify-') as verify:
            # Test current central tree with only this candidate overlaid, not editor-provided tests.
            import shutil
            shutil.copytree(s['repo'], verify, dirs_exist_ok=True, ignore=wm.IGNORE,
                            copy_function=wm._independent_copy)
            file_at(verify, s['file']).write_bytes(candidate)
            outside = run_check(s['check'], verify, s)
            if file_at(verify, s['file']).read_bytes() != candidate:
                raise ValueError('verification changed candidate source')
        if outside['exit_code'] != 0:
            return {'ok': False, 'error': 'outside verification failed', 'check': outside}
        check_versions(s)
        mode = stat.S_IMODE(central.stat().st_mode)
        atomic_source(central, candidate, mode)
        try:
            checked = run_check(s['check'], s['repo'], s)
            analysis = repo_eval.verify(repo_eval.parse_args(['--verify', '--repo', s['repo']]))
            if checked['exit_code'] or not analysis.get('clean'):
                raise ValueError('central verification failed: ' + str(checked)[:800] + str(analysis)[:800])
            check_deadline(s)
            if central.read_bytes() != candidate:
                raise ValueError('central source changed during verification')
        except BaseException:
            if central.read_bytes() == candidate:
                atomic_source(central, before, mode)
            raise
        s['state'] = 'applied'
        s['handle'] = ''
        s['outside_check'], s['central_check'], s['analysis'] = outside, checked, analysis
        save(p, s)
        return {'ok': True, 'state': 'applied', 'file': s['file'], 'outside_check': outside,
                'central_check': checked, 'clean': analysis['clean']}


def main(argv=None):
    ap = argparse.ArgumentParser()
    actions = ap.add_mutually_exclusive_group(required=True)
    actions.add_argument('--prepare', metavar='ISSUE')
    actions.add_argument('--edit', metavar='HANDLE')
    actions.add_argument('--view', metavar='HANDLE')
    actions.add_argument('--finalize', metavar='HANDLE')
    ap.add_argument('--remaining', type=float)
    ap.add_argument('--slot', default='1')
    ap.add_argument('--repo')
    ap.add_argument('--text')
    ap.add_argument('--lines')
    args = ap.parse_args(argv)
    try:
        if args.prepare is not None:
            if args.remaining is None or not 0 < args.remaining <= 240:
                raise ValueError('supply --remaining from get_status (0 < seconds <= 240)')
            out = prepare(args.prepare, args.remaining, args.repo, args.slot)
        elif args.edit:
            if args.text is None:
                raise ValueError('--text required')
            out = edit(args.edit, args.text, args.repo, args.slot)
        elif args.view:
            if not args.lines or not re.fullmatch(r'L?\d+-\d+', args.lines):
                raise ValueError('--lines A-B required')
            a,b = map(int, args.lines.lstrip('L').split('-'))
            out = narrow(args.view, a,b,args.repo,args.slot)
        else:
            out = finalize(args.finalize,args.repo,args.slot)
    except Exception as exc:
        out = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'[:1800]}
    print(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
    return out


if __name__ == '__main__':
    main()
