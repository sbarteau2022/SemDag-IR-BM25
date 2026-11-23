"""fix_edit: recover from a failed edit_file call without guessing the text again.

`edit_file` needs old_string to match the file. When it does not, the harness only says
"old_string not found". This script turns that dead end into two deterministic steps:

  1. args [filepath, old_string, new_string]
     Applies the edit when old_string matches exactly once, or once after ignoring leading and
     trailing whitespace on every line. Otherwise it prints the closest real block(s) of the file,
     verbatim, with line numbers and a reference such as "@1". Nothing is written in that case.
  2. args [filepath, "@1", new_string]
     Replaces exactly the block that reference names. The model no longer has to reproduce the
     old text at all.

Also: args [filepath, "L120-126", new_string] replaces a line range, and [filepath, "L120-126"]
prints those lines with numbers.

Guards: the path must stay inside the repository; test and runner-config files are refused
(the harness strips them from the patch); a Python file that parsed before the edit must still
parse after it, otherwise nothing is written. Standard library only.
"""
import ast
import builtins
import difflib
import hashlib
import importlib.util
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wsroot  # noqa: E402
os.environ["SEMDAG_CACHE"] = wsroot.cache_root()
import cache, impact  # noqa: E402

CONTAINER = "task"
REFS_FILE = "edit_refs.json"
MIN_RATIO = 0.5            # below this a block is not offered as a candidate
MAX_CANDIDATES = 2
MAX_BLOCK_LINES = 30
SHOW_BUDGET = 2400         # characters of numbered text printed per call
DIFF_BUDGET = 1200
USAGE = ('args: [filepath, old_string, new_string] to edit; [filepath, "@1", new_string] to replace a block '
         'this script showed; [filepath, "L10-14", new_string] to replace lines 10 to 14.')
FILE_KEYS = {"file", "filepath", "file_path", "path", "filename"}
OLD_KEYS = {"old", "old_string", "old_str", "old_text", "search", "target", "ref", "lines"}
NEW_KEYS = {"new", "new_string", "new_str", "new_text", "replace", "replacement", "content"}
REPO_KEYS = {"repo", "repo_dir", "workspace"}


# ---------------------------------------------------------------- arguments
def parse_args(argv, return_repo=False):
    args = [str(a) for a in argv]
    if len(args) == 1 and args[0].lstrip().startswith("["):
        try:
            parsed = ast.literal_eval(args[0])
            if isinstance(parsed, (list, tuple)):
                args = [str(x) for x in parsed]
        except (ValueError, SyntaxError):
            pass
    named, bare, i = {}, [], 0
    while i < len(args):
        m = re.fullmatch(r"--?([A-Za-z_][A-Za-z0-9_-]*)", args[i])
        key = m.group(1).replace("-", "_").lower() if m else None
        if key in FILE_KEYS | OLD_KEYS | NEW_KEYS | REPO_KEYS and i + 1 < len(args):
            slot = ("file" if key in FILE_KEYS else "old" if key in OLD_KEYS
                    else "new" if key in NEW_KEYS else "repo")
            named[slot] = args[i + 1]
            i += 2
            continue
        bare.append(args[i])
        i += 1
    for slot in ("file", "old", "new"):
        if slot not in named and bare:
            named[slot] = bare.pop(0)
    return (named.get("file"), named.get("old"), named.get("new"), named.get("repo")) if return_repo else (named.get("file"), named.get("old"), named.get("new"))


def resolve(filepath, repo):
    """Return (absolute path, relative path) inside repo, or raise ValueError."""
    fp = filepath.strip()
    for prefix in (repo.rstrip("/") + "/", wsroot.LITERAL + "/"):
        if fp.startswith(prefix):
            fp = fp[len(prefix):]
            break
    while fp.startswith("./"):
        fp = fp[2:]
    absolute = os.path.realpath(os.path.join(repo, fp))
    root = os.path.realpath(repo)
    if not (absolute == root or absolute.startswith(root + os.sep)):
        raise ValueError("the path leaves the repository")
    return absolute, os.path.relpath(absolute, root)


# ---------------------------------------------------------------- text helpers
def _split(text):
    return text.split("\n")


def _indent(line):
    return len(line) - len(line.lstrip(" \t"))


def _strip_blank_edges(lines):
    a, b = 0, len(lines)
    while a < b and not lines[a].strip():
        a += 1
    while b > a and not lines[b - 1].strip():
        b -= 1
    return lines[a:b]


def _numbered(lines, start):
    width = len(str(start + len(lines)))
    return "\n".join(f"{start + i:>{width}}: {l}" for i, l in enumerate(lines))


def _sha(lines):
    return hashlib.sha256("\n".join(lines).encode("utf-8", "replace")).hexdigest()[:16]


def detab(text, file_lines):
    """Leading tabs become four spaces when the file itself is indented with spaces."""
    if "\t" not in text or any(l.startswith("\t") for l in file_lines):
        return text
    out = []
    for line in _split(text):
        body = line.lstrip(" \t")
        out.append(line[:len(line) - len(body)].replace("\t", "    ") + body)
    return "\n".join(out)


def reindent(new_text, target_indent):
    """Shift new_text right when it starts shallower than the block it replaces."""
    lines = _split(new_text)
    first = next((l for l in lines if l.strip()), None)
    if first is None:
        return new_text, 0
    shift = target_indent - _indent(first)
    if shift <= 0:
        return new_text, 0
    pad = " " * shift
    return "\n".join((pad + l) if l.strip() else l for l in lines), shift


# ---------------------------------------------------------------- matching
def exact_spans(content, old):
    """Line spans (start, end exclusive, char offsets) of every exact occurrence."""
    spans, at = [], content.find(old)
    while at != -1:
        spans.append((at, at + len(old)))
        at = content.find(old, at + 1)
    return spans


def whitespace_spans(lines, old_lines):
    """Start indexes where the block matches after stripping every line."""
    want = [l.strip() for l in _strip_blank_edges(old_lines)]
    if not want:
        return [], 0
    n, hits = len(want), []
    stripped = [l.strip() for l in lines]
    first = want[0]
    for i in range(0, len(lines) - n + 1):
        if stripped[i] == first and stripped[i:i + n] == want:
            hits.append(i)
    return hits, n


def nearest_blocks(lines, old_lines):
    """Closest windows of the file to old_lines: [(ratio, start, end exclusive)], best first."""
    want = [l.strip() for l in _strip_blank_edges(old_lines)]
    if not want:
        return []
    n = len(want)
    stripped = [l.strip() for l in lines]
    want_set = {w for w in want if w}
    # stage 1: windows with the most lines in common
    hits = [1 if s and s in want_set else 0 for s in stripped]
    starts = {}
    if any(hits):
        run = sum(hits[:n])
        for i in range(0, max(1, len(lines) - n + 1)):
            if i:
                run += (hits[i + n - 1] if i + n - 1 < len(hits) else 0) - hits[i - 1]
            if run:
                starts[i] = run
    # stage 2: anchor on the most distinctive lines when few lines are shared verbatim
    anchors = sorted(want_set, key=len, reverse=True)[:3]
    for off_line in anchors:
        offset = want.index(off_line)
        sm = difflib.SequenceMatcher(None, "", off_line, autojunk=False)
        best = []
        for j, s in enumerate(stripped):
            if not s or abs(len(s) - len(off_line)) > max(len(off_line), 8):
                continue
            sm.set_seq1(s)
            if sm.real_quick_ratio() < 0.6 or sm.quick_ratio() < 0.6:
                continue
            r = sm.ratio()
            if r >= 0.6:
                best.append((r, j))
        for r, j in sorted(best, reverse=True)[:4]:
            starts.setdefault(max(0, j - offset), 0)
    ranked = sorted(starts, key=lambda i: (-starts[i], i))[:12]
    target = "\n".join(want)
    out = []
    for i in ranked:
        best = None
        for a in (i - 1, i, i + 1):
            for length in (n - 1, n, n + 1):
                if a < 0 or length < 1 or a + length > len(lines):
                    continue
                r = difflib.SequenceMatcher(None, "\n".join(stripped[a:a + length]), target, autojunk=False).ratio()
                if best is None or r > best[0] + 1e-9:
                    best = (r, a, a + length)
        if best and best[0] >= MIN_RATIO:
            out.append(best)
    out.sort(key=lambda t: (-t[0], t[1]))
    picked = []
    for r, a, b in out:
        if all(b <= pa or a >= pb for _r, pa, pb in picked):
            picked.append((r, a, b))
        if len(picked) == MAX_CANDIDATES:
            break
    return picked


# ---------------------------------------------------------------- writing
def _variants(new_text):
    """The text as given, then with literal \\n and \\t unescaped when it holds no real newline."""
    yield new_text, None
    if "\n" not in new_text and ("\\n" in new_text or "\\t" in new_text):
        yield new_text.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"'), "unescaped"


def _parses(text):
    try:
        ast.parse(text)
        return True, None
    except SyntaxError as ex:
        return False, {"line": ex.lineno, "msg": str(ex.msg)}
    except (ValueError, RecursionError) as ex:
        return False, {"line": None, "msg": str(ex)}


def _module_exports(py_path):
    """Static top-level exports of a Python file, or None if dynamic (__getattr__ / import *)."""
    try:
        with open(py_path, encoding="utf-8", errors="replace") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError, ValueError, RecursionError):
        return None
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == "__getattr__":
                return None
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    return None
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def _resolve_repo_module(repo, rel, mod_name, level):
    """Return path to a repo-local .py file for (mod_name, level), or None."""
    if level > 0:
        parts = rel.replace("\\", "/").split("/")
        pkg = parts[:-1]
        if level - 1 > len(pkg):
            return None
        base = os.path.join(repo, *pkg[:len(pkg) - level + 1]) if pkg[:len(pkg) - level + 1] else repo
        rel_mod = mod_name.replace(".", "/") if mod_name else ""
        cands = [os.path.join(base, rel_mod + ".py"), os.path.join(base, rel_mod, "__init__.py")] if rel_mod else [os.path.join(base, "__init__.py")]
    else:
        rel_mod = mod_name.replace(".", "/")
        cands = []
        for root in (repo, os.path.join(repo, "src"), os.path.join(repo, "lib")):
            cands.append(os.path.join(root, rel_mod + ".py"))
            cands.append(os.path.join(root, rel_mod, "__init__.py"))
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def _collect_imports(text):
    """Collect imports from source or an already parsed tree without reparsing it."""
    try:
        tree = text if isinstance(text, ast.AST) else ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return []
    out = []

    def walk(stmts, in_try=False):
        for node in stmts:
            if isinstance(node, ast.Try) or (hasattr(ast, "TryStar") and isinstance(node, ast.TryStar)):
                walk(node.body, True)
                for h in node.handlers:
                    walk(h.body, True)
                walk(node.orelse, in_try)
                walk(node.finalbody, in_try)
                continue
            if in_try:
                continue
            if isinstance(node, ast.Import):
                for a in node.names:
                    out.append((node.lineno, a.name, 0, None))
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    out.append((node.lineno, node.module or "", node.level or 0, a.name))
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While,
                                      ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    body = getattr(child, "body", [])
                    if isinstance(child, ast.If) and isinstance(child.test, ast.Name) and child.test.id == "TYPE_CHECKING":
                        continue
                    walk(body, in_try)
                    walk(getattr(child, "orelse", []), in_try)

    walk(tree.body)
    return out


def _import_errors(repo, rel, old_content, new_content):
    """Check newly introduced imports against the repository, builtins, and importlib."""
    old_set = {(m, lvl, nm) for _ln, m, lvl, nm in _collect_imports(old_content)}
    errs = []
    for ln, mod, lvl, nm in _collect_imports(new_content):
        if (mod, lvl, nm) in old_set:
            continue
        if lvl > 0:
            target = _resolve_repo_module(repo, rel, mod, lvl)
            if not target:
                if not mod and nm and nm != "*":
                    sub = _resolve_repo_module(repo, rel, nm, lvl)
                    if sub:
                        continue
                errs.append({"line": ln, "import": f"{'.' * lvl}{mod}", "symbol": nm,
                             "msg": "relative module not found in repository"})
                continue
            if nm and nm != "*":
                exports = _module_exports(target)
                if exports is not None and nm not in exports and not _resolve_repo_module(repo, rel, f"{mod}.{nm}" if mod else nm, lvl):
                    errs.append({"line": ln, "import": f"{'.' * lvl}{mod}", "symbol": nm,
                                 "msg": f"'{nm}' not defined in {os.path.relpath(target, repo)}"})
            continue
        # Absolute import
        repo_target = _resolve_repo_module(repo, rel, mod, 0)
        if repo_target:
            if nm and nm != "*":
                exports = _module_exports(repo_target)
                if exports is not None and nm not in exports and not _resolve_repo_module(repo, rel, f"{mod}.{nm}", 0):
                    errs.append({"line": ln, "import": mod, "symbol": nm,
                                 "msg": f"'{nm}' not defined in {os.path.relpath(repo_target, repo)}"})
            continue
        if mod == "builtins":
            if nm and nm != "*" and not hasattr(builtins, nm):
                errs.append({"line": ln, "import": "builtins", "symbol": nm,
                             "msg": f"'{nm}' is not in Python builtins"})
            continue
        try:
            spec = importlib.util.find_spec(mod)
        except (ImportError, ValueError, AttributeError):
            spec = None
        if spec is None:
            errs.append({"line": ln, "import": mod, "symbol": nm,
                         "msg": f"module '{mod}' not found"})
        elif nm and nm != "*" and spec.origin and spec.origin.endswith(".py") and os.path.isfile(spec.origin):
            exports = _module_exports(spec.origin)
            if exports is not None and nm not in exports:
                sub_spec = None
                try:
                    sub_spec = importlib.util.find_spec(f"{mod}.{nm}")
                except (ImportError, ValueError, AttributeError):
                    pass
                if sub_spec is None:
                    errs.append({"line": ln, "import": mod, "symbol": nm,
                                 "msg": f"'{nm}' not found in module '{mod}'"})
    return errs


def commit(absolute, rel, old_content, build, strategy, eol):
    """build(new_text) -> full new content. Writes only if syntax and import guards pass."""
    was_ok = (not rel.endswith(".py")) or _parses(old_content)[0]
    repo = absolute[:-len(rel)].rstrip(os.sep) if rel and absolute.endswith(rel) else os.path.dirname(absolute)
    last_err, chosen, note, imp_err = None, None, None, None
    for candidate, tag in build:
        ok, err = (True, None) if not rel.endswith(".py") or not was_ok else _parses(candidate)
        if ok:
            if rel.endswith(".py") and was_ok:
                imp = _import_errors(repo, rel, old_content, candidate)
                if imp:
                    imp_err = imp
                    continue
            chosen, note = candidate, tag
            break
        last_err = err
    if chosen is None:
        if imp_err and last_err is None:
            return {"ok": False, "error": "refused: unresolved import or symbol",
                    "import_errors": imp_err,
                    "hint": "Nothing was written. Fix or remove the unknown import/symbol and call again."}
        return {"ok": False, "error": "refused: the file would no longer parse",
                "syntax_error": last_err, "hint": "Nothing was written. Fix new_string (indentation, brackets, "
                "quotes) and call again with the same reference."}
    if chosen == old_content:
        return {"ok": False, "error": "no change: the new text equals the old text"}
    data = chosen.replace("\n", eol) if eol != "\n" else chosen
    tmp = absolute + ".fixedit.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(data)
    os.replace(tmp, absolute)
    diff = "\n".join(difflib.unified_diff(old_content.split("\n"), chosen.split("\n"),
                                          f"a/{rel}", f"b/{rel}", lineterm="", n=2))
    out = {"ok": True, "file": rel, "strategy": strategy if not note else f"{strategy}+{note}",
           "diff": diff[:DIFF_BUDGET]}
    if len(diff) > DIFF_BUDGET:
        out["diff_truncated"] = True
    return out


def _replace_lines(lines, a, b, new_text):
    block = _split(new_text)
    return "\n".join(lines[:a] + block + lines[b:])


# ---------------------------------------------------------------- entry
def run(filepath, old, new, repo=None):
    repo = wsroot.workspace_root(repo)
    import edit_tx
    if edit_tx.managed(repo):
        return edit_tx.legacy(filepath, old, new, repo)
    if not filepath:
        return {"ok": False, "error": "no file path", "hint": USAGE}
    try:
        absolute, rel = resolve(filepath, repo)
    except ValueError as ex:
        return {"ok": False, "error": str(ex), "hint": "Use a path relative to the repository root."}
    if not os.path.isfile(absolute):
        return {"ok": False, "error": f"file not found: {rel}",
                "hint": "Check the path with run_command: git ls-files | grep <name>"}
    if impact.is_protected(rel):
        return {"ok": False, "error": f"{rel} is a test or runner-config file",
                "hint": "The harness removes such files from the patch. Fix the library source instead."}
    with open(absolute, encoding="utf-8", errors="replace", newline="") as fh:
        raw = fh.read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    content = raw.replace("\r\n", "\n")
    lines = _split(content)
    if old is None:
        return {"ok": False, "error": "no old_string, reference or line range", "hint": USAGE}

    # ---- line range: show or replace
    m = re.fullmatch(r"\s*[Ll](?:ines?)?\s*(\d+)\s*(?:[-:,]\s*(\d+))?\s*", old)
    if m:
        a = int(m.group(1))
        b = int(m.group(2) or a)
        if a < 1 or b < a or a > len(lines):
            return {"ok": False, "error": f"line range {a}-{b} is outside the file (1-{len(lines)})"}
        b = min(b, len(lines))
        if new is None:
            shown = lines[a - 1:min(b, a - 1 + 60)]
            return {"ok": True, "file": rel, "lines": f"{a}-{a - 1 + len(shown)}", "total_lines": len(lines),
                    "text": _numbered(shown, a)[:SHOW_BUDGET]}
        target_indent = next((_indent(l) for l in lines[a - 1:b] if l.strip()), 0)
        builds = []
        for text, tag in _variants(new):
            shifted, shift = reindent(detab(text, lines).rstrip("\n"), target_indent)
            builds.append((_replace_lines(lines, a - 1, b, shifted), tag))
        res = commit(absolute, rel, content, builds, "lines", eol)
        if res.get("ok"):
            res["replaced_lines"] = f"{a}-{b}"
        return res

    # ---- reference from an earlier call
    m = re.fullmatch(r"\s*@(\d+)\s*", old)
    if m:
        if new is None:
            return {"ok": False, "error": "no new_string", "hint": USAGE}
        try:
            refs = cache.read(CONTAINER, REFS_FILE)
        except (OSError, ValueError):
            refs = {}
        ref = (refs.get("refs") or {}).get(m.group(1))
        if not ref or refs.get("file") != rel:
            return {"ok": False, "error": f"reference @{m.group(1)} is not known for {rel}",
                    "hint": "Call with [filepath, old_string, new_string] first to get references."}
        a, b = ref["start"] - 1, ref["end"]
        if b > len(lines) or _sha(lines[a:b]) != ref["sha"]:
            return {"ok": False, "error": "the file changed since the reference was made",
                    "hint": "Call with [filepath, old_string, new_string] again to get fresh references."}
        target_indent = next((_indent(l) for l in lines[a:b] if l.strip()), 0)
        builds = []
        for text, tag in _variants(new):
            shifted, shift = reindent(detab(text, lines).rstrip("\n"), target_indent)
            builds.append((_replace_lines(lines, a, b, shifted), tag))
        res = commit(absolute, rel, content, builds, "reference", eol)
        if res.get("ok"):
            res["replaced_lines"] = f"{ref['start']}-{ref['end']}"
        return res

    if new is None:
        return {"ok": False, "error": "no new_string", "hint": USAGE}
    old = old.replace("\r\n", "\n")

    # ---- exact
    spans = exact_spans(content, old)
    if len(spans) == 1:
        s, e = spans[0]
        builds = [(content[:s] + text + content[e:], tag) for text, tag in _variants(new)]
        return commit(absolute, rel, content, builds, "exact", eol)

    old = detab(old, lines)
    new = detab(new, lines)
    old_lines = _split(old)
    candidates = []
    refused = None
    if len(spans) > 1:
        n = len(old_lines)
        for s, _e in spans[:6]:
            start = content.count("\n", 0, s)
            candidates.append((1.0, start, min(len(lines), start + n)))
        reason = f"old_string occurs {len(spans)} times; pick one occurrence by reference"
    else:
        hits, n = whitespace_spans(lines, old_lines)
        if len(hits) == 1:
            a = hits[0]
            core = _strip_blank_edges(old_lines)
            target_indent = _indent(lines[a])
            builds = []
            for text, tag in _variants(new):
                body = "\n".join(_strip_blank_edges(_split(text)))
                first_old = next((l for l in core if l.strip()), "")
                # keep the new text's own indentation relative to old_string, moved to the real block
                delta = target_indent - _indent(first_old)
                if delta > 0:
                    body = "\n".join((" " * delta + l) if l.strip() else l for l in _split(body))
                elif delta < 0 and all(_indent(l) >= -delta for l in _split(body) if l.strip()):
                    body = "\n".join(l[-delta:] if l.strip() else l for l in _split(body))
                builds.append((_replace_lines(lines, a, a + n, body), tag))
            res = commit(absolute, rel, content, builds, "whitespace", eol)
            if res.get("ok"):
                res["replaced_lines"] = f"{a + 1}-{a + n}"
                return res
            refused = res
            candidates = [(1.0, a, a + n)]
            reason = ("old_string matches this block apart from whitespace, but new_string would break the "
                      "file's syntax: " + str((res.get("syntax_error") or {}).get("msg", res.get("error"))))
        elif len(hits) > 1:
            candidates = [(1.0, a, a + n) for a in hits[:6]]
            reason = f"old_string matches {len(hits)} places apart from whitespace; pick one by reference"
        else:
            candidates = nearest_blocks(lines, old_lines)
            reason = "old_string is not in the file; these are the closest real blocks"

    if not candidates:
        return {"ok": False, "error": "old_string is not in the file and nothing similar was found",
                "hint": f'Read the lines first: args ["{rel}", "L<start>-<end>"]. Then replace them with '
                        f'["{rel}", "L<start>-<end>", new_string].', "total_lines": len(lines)}
    refs, shown, budget = {}, [], SHOW_BUDGET
    for k, (ratio, a, b) in enumerate(candidates, 1):
        b = min(b, a + MAX_BLOCK_LINES)
        text = _numbered(lines[a:b], a + 1)
        if len(text) > budget and shown:
            break
        budget -= len(text)
        refs[str(k)] = {"start": a + 1, "end": b, "sha": _sha(lines[a:b])}
        shown.append({"ref": f"@{k}", "lines": f"{a + 1}-{b}", "similarity": round(ratio, 2), "text": text[:SHOW_BUDGET]})
    try:
        cache.write(CONTAINER, REFS_FILE, {"file": rel, "refs": refs})
    except OSError:
        pass
    out = {"ok": False, "applied": False, "file": rel, "reason": reason, "candidates": shown}
    if refused and refused.get("syntax_error"):
        out["syntax_error"] = refused["syntax_error"]
    return {**out,
            "next": f'Nothing was written. To replace a block, call again with args ["{rel}", "{shown[0]["ref"]}", new_string]. '
                    "new_string must be the full replacement for the lines shown."}


def main(argv=None):
    try:
        filepath, old, new, repo = parse_args(sys.argv[1:] if argv is None else argv, return_repo=True)
        out = run(filepath, old, new, repo=repo)
    except Exception as ex:  # never hand the model a traceback
        out = {"ok": False, "error": f"{type(ex).__name__}: {ex}"[:300], "hint": USAGE}
    print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return out


if __name__ == "__main__":
    main()
