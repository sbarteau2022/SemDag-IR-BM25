"""workspace_mgr: deterministic /tmp/ws_<slot> isolation for v13_orchestrator subagents.

Subcommands:
  --spawn <slot> --file <F> --lines <A-B> [--check <CMD>] [--carried <NAMES>] [--issue <TEXT>]
      Creates /tmp/ws_<slot> from the central repository, writes /tmp/ws_<slot>/Agents.md
      with tool definitions, scope, numbered target lines, and the directive not to touch
      central code, and prints compact JSON.
  --collect <slot>
      Diffs non-test/non-config Python changes in /tmp/ws_<slot> against the central repo,
      writes /tmp/ws_<slot>.patch, and prints the diff summary.
  --apply <slot>
      Applies verified non-test file changes from /tmp/ws_<slot> to the central repository.
  --reset <slot>
      Removes /tmp/ws_<slot> and /tmp/ws_<slot>.patch.
"""
import argparse
import difflib
import json
import os
import shutil
import sys
import re
import tempfile
import shlex

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wsroot  # noqa: E402
import impact  # noqa: E402

WS_PREFIX = os.path.join(tempfile.gettempdir(), "ws_")
IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv*", ".adk_exec_*")


def _ws_dir(slot):
    safe = str(slot)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", safe):
        raise ValueError("invalid workspace slot")
    return f"{WS_PREFIX}{safe}"


def _numbered_slice(repo, rel, span):
    path = os.path.join(repo, rel)
    if not os.path.isfile(path):
        return f"(file {rel} not found)"
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    parts = span.lstrip("Ll").split("-")
    try:
        a = max(1, int(parts[0]))
        b = min(len(lines), int(parts[1]) if len(parts) > 1 else a)
    except ValueError:
        a, b = 1, min(len(lines), 60)
    width = len(str(b))
    return "\n".join(f"{i:>{width}}: {lines[i - 1]}" for i in range(a, b + 1))


def _safe_path(root, rel):
    if os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
        raise ValueError("path must stay inside workspace")
    target = os.path.join(root, rel)
    current = root
    for part in rel.split("/"):
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise ValueError("symlinks are not allowed in workspace paths")
    if os.path.commonpath([os.path.realpath(root), os.path.realpath(target)]) != os.path.realpath(root):
        raise ValueError("path escapes workspace")
    return target


def _independent_copy(src, dst):
    if os.path.islink(src):
        raise ValueError("symlinks are not allowed in workspace copies")
    return shutil.copy2(src, dst)


def spawn(slot, rel, span, check_cmd="", carried="", issue="", repo=None):
    repo = wsroot.workspace_root(repo)
    ws = _ws_dir(slot)
    if rel:
        _safe_path(repo, rel)
    if os.path.islink(ws):
        raise ValueError("workspace root cannot be a symlink")
    for source_root, dirs, files in os.walk(repo):
        ignored = IGNORE(source_root, dirs + files)
        dirs[:] = [d for d in dirs if d not in ignored]
        for name in dirs + [f for f in files if f not in ignored]:
            if os.path.islink(os.path.join(source_root, name)):
                raise ValueError("symlinks are not allowed in workspace copies")
    if os.path.exists(ws):
        shutil.rmtree(ws)
    shutil.copytree(repo, ws, ignore=IGNORE, copy_function=_independent_copy)
    numbered = _numbered_slice(repo, rel, span) if rel else "(locate target first)"
    agents_md = f"""# Subagent Assignment (Slot {slot})

## Workspace & Isolation Directive
- Your isolated workspace is `{ws}`.
- **NEVER** read, modify, or run commands inside the central repository (`/workspace` or `{repo}`).
- **NEVER** edit test files, `conftest.py`, `pytest.ini`, `pyproject.toml`, `tox.ini`, or `setup.cfg`.
- Do not communicate with other subagents. Report only back to the orchestrator.

## Available Tooling
1. **`run_skill_script`** (`skill_name: "semdag"`, `file_path: "scripts/fix_edit.py"`):
   - Read lines: `args: ["--repo", "{ws}", "{rel or 'FILE'}", "LA-B"]`
   - Edit lines: `args: ["--repo", "{ws}", "{rel or 'FILE'}", "LX-Y", "<new lines>"]`
   - Refuses syntax errors and unresolved/hallucinated imports automatically.
2. **`run_command`**:
   - Run targeted tests inside `{ws}`: `cd {ws} && {check_cmd or 'python -m pytest -q -x | tail -20'}`

## Scope & Target
- **Target file:** `{rel}`
- **Target span:** `L{span}`
- **Loop-carried state:** {carried or 'none specified'}
- **Issue summary:** {issue[:600] if issue else 'See orchestrator prompt.'}

### Numbered Target Lines (`{rel} L{span}`)
```python
{numbered}
```

## Return Format
End your response with one line:
- `PATCH_READY {ws}` if your edit is applied and the targeted check passed, or
- `PATCH_FAILED <short reason>` if blocked.
"""
    with open(os.path.join(ws, "Agents.md"), "w", encoding="utf-8") as fh:
        fh.write(agents_md)
    return {"ok": True, "slot": str(slot), "workspace": ws, "agents_md": os.path.join(ws, "Agents.md"),
            "file": rel, "lines": span}


def _changed_files(repo, ws):
    if os.path.islink(ws):
        raise ValueError("workspace root cannot be a symlink")
    changed = []
    for root, dirs, files in os.walk(ws):
        for name in dirs:
            if os.path.islink(os.path.join(root, name)):
                raise ValueError("workspace directory cannot be a symlink")
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".pytest_cache")]
        for fn in files:
            if fn in ("Agents.md",) or fn.endswith(".fixedit.tmp") or fn.startswith(".adk_exec_"):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, ws)
            _safe_path(ws, rel)
            _safe_path(repo, rel)
            if not fn.endswith(".py"):
                continue
            if impact.is_protected(rel):
                continue
            orig = os.path.join(repo, rel)
            new_text = open(full, encoding="utf-8", errors="replace").read()
            old_text = open(orig, encoding="utf-8", errors="replace").read() if os.path.isfile(orig) else ""
            if new_text != old_text:
                changed.append((rel, old_text, new_text))
    return sorted(changed, key=lambda x: x[0])


def collect(slot, repo=None):
    repo = wsroot.workspace_root(repo)
    ws = _ws_dir(slot)
    if not os.path.isdir(ws):
        return {"ok": False, "error": f"workspace {ws} not found"}
    changed = _changed_files(repo, ws)
    diffs = []
    for rel, old_t, new_t in changed:
        diffs.extend(difflib.unified_diff(
            old_t.splitlines(keepends=True), new_t.splitlines(keepends=True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}", n=3
        ))
    patch_text = "".join(diffs)
    patch_path = f"{ws}.patch"
    with open(patch_path, "w", encoding="utf-8") as fh:
        fh.write(patch_text)
    return {"ok": True, "slot": str(slot), "empty": not bool(changed),
            "files": [c[0] for c in changed], "patch_file": patch_path,
            "diff": patch_text[:2400]}


def apply_ws(slot, repo=None):
    repo = wsroot.workspace_root(repo)
    ws = _ws_dir(slot)
    if not os.path.isdir(ws):
        return {"ok": False, "error": f"workspace {ws} not found"}
    changed = _changed_files(repo, ws)
    if not changed:
        return {"ok": False, "error": f"no non-test changes in {ws}"}
    applied = []
    for rel, _old, new_t in changed:
        dst = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(new_t)
        applied.append(rel)
    return {"ok": True, "slot": str(slot), "applied_files": applied}


def reset(slot):
    ws = _ws_dir(slot)
    if os.path.exists(ws):
        shutil.rmtree(ws)
    if os.path.exists(f"{ws}.patch"):
        os.remove(f"{ws}.patch")
    return {"ok": True, "slot": str(slot), "reset": True}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--spawn", metavar="SLOT")
    ap.add_argument("--collect", metavar="SLOT")
    ap.add_argument("--apply", metavar="SLOT")
    ap.add_argument("--reset", metavar="SLOT")
    ap.add_argument("--file", default="")
    ap.add_argument("--lines", default="1-60")
    ap.add_argument("--check", default="")
    ap.add_argument("--carried", default="")
    ap.add_argument("--issue", default="")
    ap.add_argument("--repo", default=None)
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 1 and argv[0].startswith(("--spawn ", "--collect ", "--apply ", "--reset ")):
        try:
            argv = shlex.split(argv[0])
        except ValueError as exc:
            ap.error(f"invalid packed arguments: {exc}")
    args = ap.parse_args(argv)
    if args.spawn:
        out = spawn(args.spawn, args.file, args.lines, args.check, args.carried, args.issue, args.repo)
    elif args.collect:
        out = collect(args.collect, args.repo)
    elif args.apply:
        out = apply_ws(args.apply, args.repo)
    elif args.reset:
        out = reset(args.reset)
    else:
        out = {"ok": False, "error": "pass --spawn, --collect, --apply, or --reset"}
    print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return out


if __name__ == "__main__":
    main()
