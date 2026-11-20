"""fix_edit: the only edit path of v11 (edit_file and write_file are not in the agent's tools).

Primary use: args [filepath, "L120-126", new_text] replaces exactly those lines; the line span
comes from repo_eval locate, so the model never retypes an anchor. [filepath, "L120-126"] prints
the lines numbered. The old_string forms below remain for the rare edit outside the span.

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
import difflib
import io
import hashlib
import json
import os
import re
import sys
import tokenize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wsroot  # noqa: E402
os.environ["SEMDAG_CACHE"] = wsroot.cache_root()
import cache, impact  # noqa: E402

CONTAINER = "task"
REFS_FILE = "edit_refs.json"
MIN_RATIO = 0.5            # below this a block is not offered as a candidate
MAX_CANDIDATES = 2
MAX_BLOCK_LINES = 30
SHOW_BUDGET = 4600         # characters of numbered text printed per call (stdout cap is 5,000)
SHOW_LINES = 90            # lines a range view prints (repo_eval READ_MAX)
DIFF_BUDGET = 1200
USAGE = ('args: ["FILE L10-14"] shows lines 10 to 14; ["FILE L10-14\\n<new lines>"] replaces them; '
         '[filepath, old_string, new_string] to edit; [filepath, "@1", new_string] to replace a block '
         'this script showed; [filepath, "L10-14", new_string] to replace lines 10 to 14.')
FILE_KEYS = {"file", "filepath", "file_path", "path", "filename"}
OLD_KEYS = {"old", "old_string", "old_str", "old_text", "search", "target", "ref", "lines"}
NEW_KEYS = {"new", "new_string", "new_str", "new_text", "replace", "replacement", "content"}


# ---------------------------------------------------------------- arguments
def parse_args(argv):
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
        if key in FILE_KEYS | OLD_KEYS | NEW_KEYS and i + 1 < len(args):
            slot = "file" if key in FILE_KEYS else "old" if key in OLD_KEYS else "new"
            named[slot] = args[i + 1]
            i += 2
            continue
        bare.append(args[i])
        i += 1
    for slot in ("file", "old", "new"):
        if slot not in named and bare:
            named[slot] = bare.pop(0)
    f, o, n = named.get("file"), named.get("old"), named.get("new")
    if f is not None and o is None:
        packed = _unpack(f)   # v11: the whole call packed into one string
        if packed:
            f, o, n = packed
    if o is not None and RANGE_BARE.fullmatch(_unquote(o)):
        o = "L" + _unquote(o).strip()   # "87-89" or "\"87-89\"" means a line range
    if n is not None:
        n = _clean_new(n)
    return f, o, n


# v11 (run_26): E4B packs the call into one string or drops the "L" of a range. The shapes seen:
#   "src/pkg/mod.py L72-121"                       read a range
#   "src/pkg/mod.py L87-89\n<new lines>"            replace (the documented one-string form)
#   "src/pkg/mod.py, 87-89, \"<new text>\""        replace, comma-separated, text quoted
#   "fix rich/segment.py 155-160 \"<new text>\""   replace, with a leading verb
PACKED = re.compile(r"""\A\s*(?:fix\s+|edit\s+|read\s+)?["']?(?P<file>[\w./-]+\.\w+)["']?[\s,:]+["']?[Ll]?(?:ines?)?\s*"""
                    r"""(?P<a>\d+)\s*(?:[-:,]\s*(?P<b>\d+))?["']?(?P<rest>.*)\Z""", re.S)
RANGE_BARE = re.compile(r"\s*\d+\s*[-:]\s*\d+\s*")


def _unquote(text):
    t = text.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    return t


ESCAPED_NL = re.compile(r"\\n(?=[ \t]|\\n|$)")


def _decode_newlines(text):
    """A text with no real newline but with escaped ones ("\\n" followed by indentation, another
    "\\n" or the end) was escaped once too often in transport; a "\\n" inside a string literal
    on the same line is left alone."""
    if "\n" in text or "\\n" not in text:
        return text
    return ESCAPED_NL.sub("\n", text)


def _unpack(text):
    if "\n" not in text:
        head = re.match(r"(\s*\S+[\s,]+[Ll]?\d+(?:\s*[-:,]\s*\d+)?)\\n", text)
        if head:   # the header's own separator was escaped: decode it and the body's
            text = head.group(1) + "\n" + _decode_newlines(text[head.end():])
    m = PACKED.match(text)
    if not m:
        return None
    rng = f"L{m.group('a')}" + (f"-{m.group('b')}" if m.group("b") else "")
    rest = m.group("rest")
    if rest.startswith("\n"):
        rest = rest[1:]
    else:
        rest = re.sub(r"\A[ \t]*,?[ \t]*", "", rest)
        if rest.startswith("\n"):
            rest = rest[1:]
    return m.group("file"), rng, (rest if rest.strip() else None)


def _clean_new(text):
    """Quotes around the whole text, escaped quotes inside it, and a shell-style backslash at
    the end of every line but the last are transport artifacts, not code. A quoted text counts
    as wrapped only when its inside starts with indentation or spans lines: a real Python line
    puts its indentation outside any quotes."""
    t = _decode_newlines(text)
    stripped = t.strip()
    if (len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "\"'"
            and (stripped[1:2].isspace() or "\n" in stripped)):
        t = stripped[1:-1].replace("\\" + stripped[0], stripped[0])
    lines = t.split("\n")
    body = [i for i, l in enumerate(lines) if l.strip()]
    if len(body) > 1 and all(lines[i].rstrip().endswith("\\") for i in body[:-1]):
        for i in body[:-1]:
            lines[i] = lines[i].rstrip()[:-1].rstrip()
        t = "\n".join(lines)
    return t


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


def _open_brackets(text):
    """Bracket depth at the end of text, ignoring brackets inside strings and comments."""
    depth = 0
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.OP and tok.string in "([{":
                depth += 1
            elif tok.type == tokenize.OP and tok.string in ")]}":
                depth -= 1
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass  # unfinished statement: depth so far is what we want
    return depth


def complete_statement(lines, a, b, limit=MAX_BLOCK_LINES):
    """Grow lines[a:b] until its brackets close, so a one-line match such as `x = f(` shows
    (and its reference replaces) the whole call rather than its first line."""
    while b < len(lines) and b - a < limit and _open_brackets("\n".join(l.strip() for l in lines[a:b])) > 0:
        b += 1
    return b


def baseline_text(repo, rel):
    """The file as it was before this session's edits (harness baseline commit), or None."""
    try:
        ref = impact.baseline_ref(repo)
        base = impact.old_content(repo, ref, rel) if ref else None
    except Exception:  # noqa: BLE001 - git trouble must never block the rescue
        base = None
    return base.replace("\r\n", "\n") if base else None


def _stripped_in(block_lines, text):
    want = "\n".join(l.strip() for l in _strip_blank_edges(block_lines))
    return bool(want) and want in "\n".join(l.strip() for l in _split(text))


def stale_note(base, old):
    """When old_string is in the baseline version of the file but not in the file now, an earlier
    edit in this session already replaced it. Say so: the model is editing from an old read."""
    if not base:
        return None
    if old in base or _stripped_in(_split(old), base):
        return ("old_string is the text from BEFORE an earlier edit of this file. The file has changed "
                "since you read it. Use the current lines below, not your earlier read.")
    return None


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
    """Move new_text so its first line starts at the indentation of the block it replaces:
    right when it starts shallower, left when every line has the extra indentation to lose."""
    lines = _split(new_text)
    first = next((l for l in lines if l.strip()), None)
    if first is None:
        return new_text, 0
    shift = target_indent - _indent(first)
    if shift > 0:
        pad = " " * shift
        return "\n".join((pad + l) if l.strip() else l for l in lines), shift
    if shift < 0 and all(l[:-shift].strip() == "" for l in lines if l.strip()):
        return "\n".join(l[-shift:] if l.strip() else l for l in lines), shift
    return new_text, 0


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


READ_META_TAIL = re.compile(r'",\s*"(?:start_line|end_line|total_lines|is_truncated|filepath|status)"\s*:.*\Z', re.S)


def _strip_meta(text):
    return READ_META_TAIL.sub("", text)


def _collapse(text):
    return text.replace("\\\\", "\\")


def _cleanings(old):
    """Fixes for text copied out of a tool result, cheapest first; only those that change old."""
    out = []
    if READ_META_TAIL.search(old):
        out.append(_strip_meta)
    if "\\\\" in old:
        out.append(_collapse)
        if out[0] is _strip_meta:
            out.append(lambda t: _collapse(_strip_meta(t)))
    return out


def _parses(text):
    try:
        ast.parse(text)
        return True, None
    except SyntaxError as ex:
        return False, {"line": ex.lineno, "msg": str(ex.msg)}
    except (ValueError, RecursionError) as ex:
        return False, {"line": None, "msg": str(ex)}


def commit(absolute, rel, old_content, build, strategy, eol):
    """build(new_text) -> full new content. Writes only if the syntax guard passes."""
    was_ok = (not rel.endswith(".py")) or _parses(old_content)[0]
    last_err, chosen, note = None, None, None
    for candidate, tag in build:
        ok, err = (True, None) if not rel.endswith(".py") or not was_ok else _parses(candidate)
        if ok:
            chosen, note = candidate, tag
            break
        last_err = err
    if chosen is None:
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
            shown = lines[a - 1:min(b, a - 1 + SHOW_LINES)]
            while len(shown) > 1 and len(_numbered(shown, a)) > SHOW_BUDGET:
                shown.pop()  # whole lines only, so the reported range is the range shown
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
        elif "parse" in res.get("error", ""):
            # show what the range really holds: a miscounted range is the usual cause (run_27)
            lo, hi = max(1, a - 2), min(len(lines), b + 2)
            res["lines_you_replaced"] = _numbered(lines[a - 1:b], a)[:1200]
            res["context"] = f"{lo}-{hi}"
            res["hint"] = (f"Nothing was written. Lines {a}-{b} hold the text in lines_you_replaced. "
                           f"Pick the range whose lines your new text replaces, then call again.")
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

    # ---- copy artifacts (run_25 httpx_3672): the model doubled every backslash of an escape
    # sequence and/or pasted the tail of the read_file JSON (", "start_line": 325, ...) onto the last
    # line. When a cleaned old_string matches exactly once, apply new_string cleaned the same way.
    if not spans:
        for clean in _cleanings(old):
            hits = exact_spans(content, clean(old))
            if len(hits) == 1:
                s, e = hits[0]
                return commit(absolute, rel, content, [(content[:s] + clean(new) + content[e:], "cleaned")],
                              "exact", eol)

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
    base = baseline_text(repo, rel)
    refs, shown, budget = {}, [], SHOW_BUDGET
    for k, (ratio, a, b) in enumerate(candidates, 1):
        b = complete_statement(lines, a, min(b, a + MAX_BLOCK_LINES))
        text = _numbered(lines[a:b], a + 1)
        if len(text) > budget and shown:
            break
        budget -= len(text)
        refs[str(k)] = {"start": a + 1, "end": b, "sha": _sha(lines[a:b])}
        cand = {"ref": f"@{k}", "lines": f"{a + 1}-{b}", "similarity": round(ratio, 2), "text": text[:SHOW_BUDGET]}
        if base and not _stripped_in(lines[a:b], base):
            cand["already_edited"] = True   # this block holds an earlier edit of this session
        shown.append(cand)
    try:
        cache.write(CONTAINER, REFS_FILE, {"file": rel, "refs": refs})
    except OSError:
        pass
    out = {"ok": False, "applied": False, "file": rel, "reason": reason, "candidates": shown}
    stale = stale_note(base, old) if not spans else None
    if not stale and not spans and any(c.get("already_edited") for c in shown):
        stale = ("old_string is not in the file. The closest block already holds an earlier edit of yours, "
                 "so your copy of it is out of date. Use the current lines below.")
    if stale:
        out["stale"] = True
        out["reason"] = stale
    if refused and refused.get("syntax_error"):
        out["syntax_error"] = refused["syntax_error"]
    return {**out,
            "next": f'Nothing was written. To replace a block, call again with args ["{rel}", "{shown[0]["ref"]}", new_string]. '
                    "new_string must be the full replacement for the lines shown."}


def main(argv=None):
    try:
        filepath, old, new = parse_args(sys.argv[1:] if argv is None else argv)
        out = run(filepath, old, new)
    except Exception as ex:  # never hand the model a traceback
        out = {"ok": False, "error": f"{type(ex).__name__}: {ex}"[:300], "hint": USAGE}
    print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return out


if __name__ == "__main__":
    main()
