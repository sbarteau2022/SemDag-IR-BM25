"""BM25 over function source, stdlib only. Usage: locate.py "<issue text>" [top_n]"""
import ast
import math
import os
import re
import sys
from collections import Counter

ROOT = "/workspace"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
STOP = {"the", "and", "for", "that", "this", "with", "not", "but", "are", "was", "from", "have",
        "has", "when", "you", "can", "should", "would", "will", "use", "using", "def", "self",
        "return", "import", "none", "true", "false", "class", "if", "else", "in", "is", "of",
        "to", "it", "as", "on", "be", "or", "an", "at", "by", "we"}
SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", "site-packages", "build", "dist"}


def is_test(rel):
    parts = rel.split("/")
    name = parts[-1]
    return (any(p in ("tests", "test", "testing") for p in parts[:-1])
            or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py")


def toks(text):
    out = []
    for ident in IDENT.findall(text):
        low = ident.lower()
        if len(low) >= 2 and low not in STOP:
            out.append(low)
        parts = [p.lower() for chunk in ident.split("_") for p in CAMEL.findall(chunk)]
        if len(parts) > 1:
            out.extend(p for p in parts if len(p) >= 2 and p not in STOP)
    return out


def spans(src):
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, ast.ClassDef):
                walk(ch, prefix + [ch.name])
            elif isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([ch.lineno] + [d.lineno for d in ch.decorator_list])
                out.append((start, ch.end_lineno, ".".join(prefix + [ch.name])))
                walk(ch, prefix + [ch.name])
            else:
                walk(ch, prefix)
    walk(tree, [])
    return out


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("usage: locate.py \"<issue text>\" [top_n]")
        return
    query = Counter(toks(sys.argv[1]))
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8
    funcs = []
    for root, dirs, names in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for nm in sorted(names):
            if not nm.endswith(".py"):
                continue
            fp = os.path.join(root, nm)
            rel = os.path.relpath(fp, ROOT)
            if is_test(rel):
                continue
            try:
                src = open(fp, errors="replace").read()
            except OSError:
                continue
            lines = src.splitlines()
            for start, end, qual in spans(src):
                head = qual.replace(".", " ") + " " + rel.replace("/", " ").replace(".py", "")
                doc = Counter(toks("\n".join(lines[start - 1:end])) + toks(head) * 3)
                funcs.append((rel, start, end, qual, doc, sum(doc.values())))
    n = len(funcs)
    if not n:
        print("no functions found under /workspace")
        return
    df = Counter()
    for f in funcs:
        df.update(f[4].keys())
    avg = sum(f[5] for f in funcs) / n
    scores = [0.0] * n
    for term, qtf in query.items():
        d = df.get(term)
        if not d:
            continue
        w = math.log(1 + (n - d + 0.5) / (d + 0.5)) * min(qtf, 3)
        for i, f in enumerate(funcs):
            tf = f[4].get(term)
            if tf:
                scores[i] += w * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * f[5] / avg))
    order = sorted(range(n), key=lambda i: (-scores[i], funcs[i][0], funcs[i][1]))
    print("Most likely edit sites (path:start-end qualified.name):")
    for i in order[:top_n]:
        if scores[i] <= 0:
            break
        rel, start, end, qual = funcs[i][:4]
        print(f"{rel}:{start}-{end} {qual}")


main()
