"""task_ir: type the problem, not only the repository (v11).

Three deterministic steps, no model, standard library only:

  problem_ir(issue)          the issue as typed facts: identifiers, traceback frames, literals, paths
  anchor(ir, snap, pir, bm)  join those facts to the code IR by exact containment, in a fixed order:
                               1. a traceback frame whose line lies inside a library function
                               2. a literal (quoted string, exception message) found in exactly one
                                  library function
                               3. a mention of a function's qualname (dotted, or a distinctive bare name)
                               4. otherwise BM25 rank 1 (the v6 ranking), marked as a guess
  locus(ir, snap, site, pir) on the anchor only: intersect the issue's identifiers with the loop-carried
                             names and targets of the anchor's loops. A hit gives a line span (the loop
                             plus the statements that initialise the intersected names) and the loop's
                             condition. No hit means no locus: nothing about flow is shown.

Ties are broken by a canonical key (BM25 score, then file, then line), never by input order.
"""
import ast
import re

import retriever

FRAME = re.compile(r'File "([^"\n]+?)", line (\d+), in ([A-Za-z_<][\w<>.]*)')
PATH = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.py)\b")
INLINE_LOCATION = re.compile(r"(?<![\w/.-])(/?(?:[\w.-]+/)*[\w.-]+\.py)\s*(?::\s*|\s+line\s+)(\d+)\b")
AMBIGUOUS_LINES = re.compile(r"(/?(?:[\w.-]+/)*[\w.-]+\.py)\s+lines\s+\d+\s*,\s*\d+")
DOTTED = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b")
IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
QUOTED = re.compile(r"""(?<![A-Za-z0-9_])(?:"([^"\n]{4,160})"|'([^'\n]{4,160})')""")
EXC_MSG = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:Error|Exception|Warning)):\s*([^\n]{4,160})")
CODE_SPAN = re.compile(r"`([^`\n]{1,120})`")
MIN_LITERAL = 6            # shorter literals are too common to be an anchor
MAX_LITERALS = 12
LOCUS_PAD = 15             # lines of context read around the locus


def _distinctive(name):
    """A bare identifier that can name one function: snake_case with an underscore, or
    lowerCamel/PascalCase with an inner capital, at least 5 characters."""
    return len(name) >= 5 and ("_" in name.strip("_") or re.search(r"[a-z][A-Z]", name) is not None)


def problem_ir(issue):
    text = issue or ""
    frames = [{"path": p, "line": int(n), "qual": q} for p, n, q in FRAME.findall(text)]
    locations = [{"path": p, "line": int(n)} for p,n in INLINE_LOCATION.findall(text)]
    paths = sorted({p for p in PATH.findall(text) if not p.startswith(".")})
    literals = []
    for m in QUOTED.finditer(text):
        lit = (m.group(1) or m.group(2)).strip()
        if len(lit) >= MIN_LITERAL and not re.fullmatch(r"[\w.]+", lit):
            literals.append(lit)
    for exc, msg in EXC_MSG.findall(text):
        msg = msg.strip().strip("'\"")
        if len(msg) >= MIN_LITERAL:
            literals.append(msg)
    seen, lits = set(), []
    for lit in literals:
        if lit not in seen:
            seen.add(lit)
            lits.append(lit)
    dotted = sorted(set(DOTTED.findall(text)) - {p[:-3].replace("/", ".") for p in paths})
    code = [c.strip() for c in CODE_SPAN.findall(text)]
    idents = sorted(set(IDENT.findall(text)))
    return {"idents": idents, "locations": locations, "dotted": dotted, "code_spans": code, "frames": frames,
            "literals": lits[:MAX_LITERALS], "paths": paths}


# ---------------------------------------------------------------- joins
def _functions(ir):
    return [n for n in ir["nodes"] if n["kind"] in ("function", "method") and n.get("end_line")
            and retriever.is_candidate_path(n["file"]) and not n.get("overload")]


def _library_files(ir):
    return sorted({n["file"] for n in ir["nodes"] if n["kind"] == "file"
                   and retriever.is_candidate_path(n["file"])})


def _match_file(path, files):
    """Repository file for a path from a traceback or the text. The path's trailing components
    must equal the whole repository path, or the repository path without a leading src/ or lib/
    (an installed package prints site-packages/pkg/mod.py for src/pkg/mod.py). Longest match wins."""
    parts_p = [x for x in path.replace("\\", "/").split("/") if x not in ("", ".")]
    best, best_k = None, 0
    for f in files:
        parts_f = f.split("/")
        k = 0
        while k < min(len(parts_p), len(parts_f)) and parts_p[-1 - k] == parts_f[-1 - k]:
            k += 1
        need = len(parts_f) - (1 if len(parts_f) > 1 and parts_f[0] in ("src", "lib") else 0)
        if k >= need and k > best_k:
            best, best_k = f, k
    return best


def _innermost(funcs, rel, line):
    hits = [n for n in funcs if n["file"] == rel and n.get("start_line", n["line"]) <= line <= n["end_line"]]
    return min(hits, key=lambda n: (n["end_line"] - n.get("start_line", n["line"]), n["line"])) if hits else None


def _key(n, bm):
    return (-bm.get(n["id"], 0.0), n["file"], n["line"])


def anchor(ir, snap, pir, bm_scores):
    """(node, how, evidence) for the first join that hits, else (None, None, None).
    bm_scores: node id -> BM25 score, used only to order tied candidates."""
    funcs = _functions(ir)
    files = _library_files(ir)

    # 1. traceback frames, innermost (last printed) first
    for fr in reversed(pir["frames"]):
        rel = _match_file(fr["path"], files)
        if rel:
            n = _innermost(funcs, rel, fr["line"])
            if n:
                return n, "traceback", f'{rel}:{fr["line"]} in {fr["qual"]}'

    locations = {(p["path"],p["line"]) for p in pir.get("locations",[])}
    if len(locations) == 1:
        path,line = next(iter(locations))
        rel = _match_file(path,files)
        n = _innermost(funcs,rel,line) if rel else None
        if n:
            return n,"location",f"{rel}:{line}"

    # 2. a literal that occurs in exactly one library function
    for lit in pir["literals"]:
        holders = []
        for n in funcs:
            body = _body(snap, n)
            if body is not None and lit in body:
                holders.append(n)
                if len(holders) > 1:
                    break
        if len(holders) == 1:
            return holders[0], "literal", lit[:60]

    # 3. a qualname mention: dotted names first, then distinctive bare names
    by_qual, by_name = {}, {}
    for n in funcs:
        by_qual.setdefault(n.get("qualname", n["name"]), []).append(n)
        by_name.setdefault(n["name"], []).append(n)
    for d in sorted(pir["dotted"], key=lambda x: (-x.count("."), x)):
        parts = d.split(".")
        # Module-qualified globals and class methods are joined to their actual file.
        for cut in reversed(range(1,len(parts))):
            rel = _match_file("/".join(parts[:cut])+".py",files)
            q = ".".join(parts[cut:])
            cands = [n for n in by_qual.get(q,[]) if n["file"]==rel] if rel else []
            if cands:
                return min(cands,key=lambda n:_key(n,bm_scores)),"qualname",d
        for cut in range(len(parts)):  # pkg.mod.Class.method -> Class.method -> method
            q = ".".join(parts[cut:])
            cands = by_qual.get(q) if "." in q else None
            if cands:
                return min(cands, key=lambda n: _key(n, bm_scores)), "qualname", d
    mentioned = set(pir["idents"]) | {c for c in pir["code_spans"] if IDENT.fullmatch(c)}
    bare = sorted(x for x in mentioned if _distinctive(x) and x in by_name)
    if bare:
        cands = [n for x in bare for n in by_name[x]]
        best = min(cands, key=lambda n: _key(n, bm_scores))
        return best, "qualname", best["name"]
    return None, None, None


def _body(snap, n):
    content = snap["files"].get(n["file"], {}).get("content")
    if content is None:
        return None
    lines = content.splitlines()
    return "\n".join(lines[n.get("start_line", n["line"]) - 1:n["end_line"]])


# ---------------------------------------------------------------- locus
def _bare(loc):
    """`self.pos` -> pos, `buf[]` -> buf: the identifier an issue would use for a location."""
    return loc.rstrip("[]").split(".")[-1]


def _pre_loop_inits(snap, fn, loop, names):
    """Earliest line among the last assignments, inside fn and before the loop, to each of the
    names: a loop-carried value is its initial value plus its update, so both are the locus."""
    content = snap["files"].get(fn["file"], {}).get("content")
    if content is None:
        return None
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None
    last = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        if not (fn.get("start_line", fn["line"]) <= node.lineno < loop["line"]):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in targets:
            for sub in ast.walk(t):
                nm = sub.id if isinstance(sub, ast.Name) else sub.attr if isinstance(sub, ast.Attribute) else None
                if nm in names:
                    last[nm] = max(last.get(nm, 0), node.lineno)
    return min(last.values()) if last else None


def locus(ir, snap, site, pir):
    """Loop locus of the anchor, or None. The intersection uses exact identifiers only."""
    explicit = {i for span in pir.get("code_spans",[]) + pir.get("dotted",[]) for i in IDENT.findall(span)}
    words = {i for i in pir["idents"] if len(i)>1 or i in explicit}
    loops = [n for n in ir["nodes"] if n["kind"] == "loop" and n.get("owner") == site["id"]]
    best = None
    for lp in loops:
        names = list(lp.get("carried", [])) + list(lp.get("targets", []))
        hit = sorted({_bare(c) for c in names if _bare(c) in words})
        if not hit:
            continue
        key = (-len(hit), lp.get("end_line", lp["line"]) - lp["line"], lp["line"])
        if best is None or key < best[0]:
            best = (key, lp, hit)
    if best is None:
        return None
    _, lp, hit = best
    init = _pre_loop_inits(snap, site, lp, set(hit))
    start = min(init, lp["line"]) if init else lp["line"]
    carried = [c for c in lp.get("carried", []) if _bare(c) in hit] or hit
    guards = [e for e in lp.get("exit_conds", []) if e.get("cond")]
    return {"file": site["file"], "start": start, "end": lp.get("end_line", lp["line"]),
            "loop_line": lp["line"], "kind": lp["loop_kind"], "carried": carried,
            "test": lp.get("test"), "exit_guards": [f'{e["kind"]}@{e["line"]} if {e["cond"]}' for e in guards[:2]]}


def terminal_raise(snap, site):
    """Line of a `raise` that is the last statement of the function body, else None."""
    content = snap["files"].get(site["file"], {}).get("content")
    if content is None:
        return None
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno == site["line"]:
            last = node.body[-1] if node.body else None
            return last.lineno if isinstance(last, ast.Raise) else None
    return None
