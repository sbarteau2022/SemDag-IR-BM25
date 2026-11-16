"""Python families from real repo functions, labels from execution: fn_repair, spec_to_code, exec_trace."""
import ast, builtins, copy, re, symtable, textwrap, json
from common import *
import sandbox

ALLOWED_MODS = {"re","math","string","itertools","functools","collections","operator","textwrap","json","typing","dataclasses","enum","decimal","fractions","unicodedata","urllib","codecs","binascii","base64","hashlib","datetime","types","copy"}
BAN = {"open","exec","eval","compile","input","__import__","breakpoint","exit","quit","help","globals","locals","vars","setattr","delattr","print"}
OKGLOB = (set(dir(builtins)) - BAN) | ALLOWED_MODS
STRS = ["", "a", "Hello World", "  padded  ", "snake_case_name", "CamelCaseName", "a,b,,c", "x=1&y=2", "foo.bar.baz", "ÄÖü", "123", "tab\tsep", "UPPER lower", "line1\nline2", "https://example.com/a?b=c", "-", "a b  c", "x", "Content-Type", "utf-8", "[bold]hi[/bold]"]
INTS = [-3, -1, 0, 1, 2, 3, 4, 5, 8, 10, 100]
FLOATS = [0.0, 0.5, 1.5, -2.25, 3.0, 10.5]
BYTES = [b"", b"abc", b"a b", b"\xc3\xa4"]
STR_NAMES = {"text","string","name","s","value","line","path","word","char","msg","prefix","suffix","key","url","content","data","header","style","title","label","markup","code","encoding","method"}
INT_NAMES = {"n","i","j","count","index","size","width","length","num","offset","start","end","limit","depth","level","number","pos","position","height","step"}

class Unsupported(Exception): pass

def gen_val(rng, ann, name):
    a = (ann or "").replace(" ", "").replace("typing.", "")
    if a.startswith("Optional[") and a.endswith("]"):
        return None if rng.random() < 0.25 else gen_val(rng, a[9:-1], name)
    if "|None" in a or a.startswith("None|"):
        return None if rng.random() < 0.25 else gen_val(rng, a.replace("|None", "").replace("None|", ""), name)
    if a == "str": return rng.choice(STRS)
    if a == "int": return rng.choice(INTS)
    if a == "float": return rng.choice(FLOATS)
    if a == "bool": return rng.random() < 0.5
    if a == "bytes": return rng.choice(BYTES)
    m = re.match(r"(list|List|Sequence|Iterable|set|Set|tuple|Tuple)\[(.+?)(?:,\.\.\.)?\]$", a)
    if m:
        inner = m.group(2).split(",")[0]
        items = [gen_val(rng, inner, name) for _ in range(rng.randint(0, 4))]
        return set(items) if m.group(1) in ("set", "Set") and all(isinstance(x, (int, str)) for x in items) else (tuple(items) if m.group(1) in ("tuple", "Tuple") else items)
    m = re.match(r"(dict|Dict|Mapping)\[(.+?),(.+)\]$", a)
    if m:
        return {gen_val(rng, "str", name): gen_val(rng, m.group(3), name) for _ in range(rng.randint(0, 3))}
    if a == "":
        if name in STR_NAMES: return rng.choice(STRS)
        if name in INT_NAMES: return rng.choice(INTS)
        raise Unsupported(name)
    raise Unsupported(a)

def globals_used(src):
    tab = symtable.symtable(src, "<f>", "exec")
    out = set()
    def rec(t):
        for s in t.get_symbols():
            if (s.is_global() and (s.is_referenced() or s.is_assigned())): out.add(s.get_name())
        for c in t.get_children(): rec(c)
    rec(tab.get_children()[0])
    return out

BADNODES = (ast.Yield, ast.YieldFrom, ast.Await, ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom)

def fn_ok(fn):
    if fn.decorator_list or any(isinstance(n, BADNODES) for n in ast.walk(fn)): return False
    a = fn.args
    if a.vararg or a.kwarg or a.kwonlyargs: return False
    try:
        for d in a.defaults: ast.literal_eval(d)
    except Exception: return False
    return True

def resolve(node, defs, imp_names, acc, seen):
    if isinstance(node, ast.FunctionDef):
        try: need = globals_used(ast.unparse(node)) - {node.name}
        except Exception: return False
    else:
        need = {n.id for n in ast.walk(node.value) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    for name in sorted(need):
        if name in OKGLOB or name in imp_names or name in seen: continue
        d = defs.get(name)
        if d is None or d is node: return False
        seen.add(name)
        if isinstance(d, ast.FunctionDef) and not fn_ok(d): return False
        if not resolve(d, defs, imp_names, acc, seen): return False
        acc.append(d)
    return True

def find_pure(srcs, lo=3, hi=35):
    out = []
    for p in sorted(srcs):
        if is_test_path(p) or "docs_src" in p or p.startswith(("scripts/", "docs/", "benchmarks/", "examples/")): continue
        try: tree = ast.parse(srcs[p])
        except SyntaxError: continue
        defs, imports, imp_names = {}, [], set()
        for n in tree.body:
            if isinstance(n, ast.FunctionDef): defs[n.name] = n
            elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name): defs[n.targets[0].id] = n
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
                defs[n.target.id] = ast.Assign(targets=[n.target], value=n.value, lineno=n.lineno)
            elif isinstance(n, ast.Import) and all(x.name.split(".")[0] in ALLOWED_MODS for x in n.names):
                imports.append(n); imp_names |= {(x.asname or x.name).split(".")[0] for x in n.names}
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and (n.module or "").split(".")[0] in ALLOWED_MODS:
                imports.append(n); imp_names |= {x.asname or x.name for x in n.names}
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef) or fn.name.startswith("__") or not fn_ok(fn): continue
            if not (lo <= fn.end_lineno - fn.lineno + 1 <= hi): continue
            acc, seen = [], {fn.name}
            if not resolve(fn, defs, imp_names, acc, seen) or len(acc) > 6: continue
            ctx_nodes = sorted(acc, key=lambda d: d.lineno)
            body_src = "\n".join(ast.unparse(d) for d in ctx_nodes) + "\n" + ast.unparse(fn)
            used = {n.id for n in ast.walk(ast.parse(body_src)) if isinstance(n, ast.Name)} | {n.value.id for n in ast.walk(ast.parse(body_src)) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
            imps = [ast.unparse(i) for i in imports if used & ({(x.asname or x.name).split(".")[0] for x in i.names})]
            ctx = "\n".join(imps + [ast.unparse(d) for d in ctx_nodes])
            if ctx.count("\n") > 70: continue
            out.append((p, fn, ctx))
    return out

def sample_calls(fn, rng, n=40):
    a = fn.args; params = a.posonlyargs + a.args; nd = len(a.defaults); calls, seen = [], set()
    for _ in range(n * 3):
        try: vals = [gen_val(rng, ast.unparse(x.annotation) if x.annotation else "", x.arg) for x in params]
        except Unsupported: return None
        if nd and rng.random() < 0.3: vals = vals[:len(vals) - rng.randint(1, nd)]
        r = repr(tuple(vals)) if len(vals) != 1 else repr((vals[0],))
        if r not in seen: seen.add(r); calls.append(r)
        if len(calls) >= n: break
    return calls

def show_call(name, argsrepr):
    t = ast.literal_eval(argsrepr)
    return f"{name}({', '.join(repr(x) for x in t)})"

def res_str(r): return ("returns " + r["ok"]) if "ok" in r else ("raises " + r["exc"])

SWAP_CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}
SYM = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=", ast.In: "in", ast.NotIn: "not in", ast.Is: "is", ast.IsNot: "is not", ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.FloorDiv: "//", ast.And: "and", ast.Or: "or"}

class Mut(ast.NodeTransformer):
    def __init__(self, target): self.target, self.i, self.note = target, 0, None
    def hit(self):
        self.i += 1; return self.i - 1 == self.target
    def visit_Compare(self, n):
        self.generic_visit(n)
        if len(n.ops) == 1 and type(n.ops[0]) in SWAP_CMP and self.hit():
            self.note = ("compare", SYM[type(n.ops[0])], SYM[SWAP_CMP[type(n.ops[0])]]); n.ops = [SWAP_CMP[type(n.ops[0])]()]
        return n
    def visit_BinOp(self, n):
        self.generic_visit(n)
        mp = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult}
        if type(n.op) in mp and self.hit():
            self.note = ("binop", SYM[type(n.op)], SYM[mp[type(n.op)]]); n.op = mp[type(n.op)]()
        return n
    def visit_BoolOp(self, n):
        self.generic_visit(n)
        if self.hit():
            self.note = ("boolop", SYM[type(n.op)], SYM[ast.Or if isinstance(n.op, ast.And) else ast.And]); n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()
        return n
    def visit_Constant(self, n):
        if isinstance(n.value, int) and not isinstance(n.value, bool) and abs(n.value) < 50 and self.hit():
            self.note = ("const", str(n.value), str(n.value + 1 if n.value >= 0 else n.value - 1)); return ast.Constant(n.value + 1 if n.value >= 0 else n.value - 1)
        return n
    def visit_UnaryOp(self, n):
        self.generic_visit(n)
        if isinstance(n.op, ast.Not) and self.hit():
            self.note = ("not", "not x", "x"); return n.operand
        return n

def mutate(fn, target):
    t = copy.deepcopy(fn); m = Mut(target); t = m.visit(t); ast.fix_missing_locations(t)
    return (ast.unparse(t), m.note) if m.note else (None, None)

NOTE = {"compare": "The comparison uses `{b}` where `{a}` is required.", "binop": "The operator `{b}` should be `{a}`.",
        "boolop": "The boolean operator `{b}` should be `{a}`.", "const": "The constant `{b}` should be `{a}` (an off-by-one).",
        "not": "A negation (`not`) was dropped from the condition; it must be restored."}
def note_text(note):
    k, a, b = note  # a = original token, b = mutated token; for 'not' we restore
    if k == "not": return NOTE[k]
    return NOTE[k].format(a=a, b=b)

def fence(code): return "```python\n" + code + "\n```"
def trace_text(src, steps, res, off=0):
    lines = src.splitlines(); out = []
    for i, (ln, cur) in enumerate(steps):
        ln = ln - off
        nxt = steps[i + 1][1] if i + 1 < len(steps) else None
        ch = ", ".join(f"{k}={v}" for k, v in (nxt or {}).items() if cur.get(k) != v)
        code = lines[ln - 1].strip() if 0 < ln <= len(lines) else "?"
        out.append(f"L{ln} `{code}`" + (f" -> {ch}" if ch else ""))
    return " | ".join(out) + f" | result: {res_str(res)}."

def fsplit(h):
    v = int(sha("fn|" + h, 8), 16) % 10
    return "train" if v < 8 else ("dev" if v == 8 else "test")

def full(ctx, fn_src): return (ctx + "\n\n" if ctx else "") + fn_src
def ctx_block(ctx): return (f"Module-level definitions the function relies on:\n{fence(ctx)}\n\n" if ctx else "")

def process(fn, ctx, src, h, src_info):
    rows = []
    rng = rng_for("py", h)
    calls = sample_calls(fn, rng)
    if not calls: return rows
    base = sandbox.run(full(ctx, src), fn.name, calls, trace=False)
    if not base: return rows
    oks = [r for r in base if "ok" in r]
    if len(oks) < 8 or len({r["ok"] for r in oks}) < 3: return rows
    split = fsplit(h)
    cb = ctx_block(ctx)
    sites = list(range(8)); rng.shuffle(sites); made = 0
    for s_ in sites:
        msrc, note = mutate(fn, s_)
        if not msrc or msrc == src: continue
        mres = sandbox.run(full(ctx, msrc), fn.name, calls)
        if not mres: continue
        diff = [i for i, (x, y) in enumerate(zip(base, mres)) if x != y]
        if not diff: continue
        i = min(diff, key=lambda k: len(calls[k]))
        obs = show_call(fn.name, calls[i])
        fail = f"`{obs}` {res_str(mres[i])}, but it should {res_str(base[i]).replace('returns', 'return', 1).replace('raises', 'raise', 1)}."
        user = f"This Python function has a bug.\n\n{cb}{fence(msrc)}\n\nObserved failure: {fail}\n\nReturn the corrected function in a single ```python block."
        think = f"Evaluating the failing call by hand: the code {res_str(mres[i])}; the correct behaviour {res_str(base[i])}. " + note_text(note) + " Restoring that one token fixes the call."
        rows.append({"family": "pyedit", "subtype": "fn_repair", "split": split, "source": src_info, "thinking": True, "tools": None,
                     "messages": [{"role": "user", "content": user}, {"role": "assistant", "reasoning_content": think, "content": fence(src)}],
                     "verifier": {"kind": "fn_repair", "fname": fn.name, "context": ctx, "original": src, "mutant": msrc, "calls": calls, "expected": base, "shown": i}})
        made += 1
        if made >= 2: break
    doc = ast.get_docstring(fn)
    if doc and len(doc) > 15:
        ex = [i for i, r in enumerate(base) if "ok" in r]; rng.shuffle(ex); ex = sorted(ex[:3], key=lambda k: len(calls[k]))
        sig = src.split(":\n")[0] if ":\n" in src else src.splitlines()[0]
        exs = "\n".join(f"- `{show_call(fn.name, calls[i])}` returns `{base[i]['ok']}`" for i in ex)
        docblock = sig + ":\n    " + chr(34) * 3 + textwrap.indent(doc, "    ").lstrip() + "\n    " + chr(34) * 3
        user = f"Implement this Python function.\n\n{cb}Signature and docstring:\n\n{fence(docblock)}\n\nExamples:\n{exs}\n\nReturn the full function (signature, docstring and body) in a single ```python block."
        think = "Match every example before writing: " + "; ".join(f"{show_call(fn.name, calls[i])} -> {base[i]['ok']}" for i in ex) + ". Then implement the behaviour the docstring describes and check each example against the code."
        rows.append({"family": "pyedit", "subtype": "spec_to_code", "split": split, "source": src_info, "thinking": True, "tools": None,
                     "messages": [{"role": "user", "content": user}, {"role": "assistant", "reasoning_content": think, "content": fence(src)}],
                     "verifier": {"kind": "spec_to_code", "fname": fn.name, "context": ctx, "original": src, "calls": calls, "expected": base, "shown": ex}})
    tr = sandbox.run(full(ctx, src), fn.name, calls[:12], trace=True)
    if tr:
        good = [i for i, r in enumerate(tr) if 2 <= r.get("nsteps", 99) <= 24 and len(r.get("ok", r.get("exc", ""))) < 160 and len(calls[i]) < 110]
        for i in good[:2]:
            r = tr[i]; ans = r["ok"] if "ok" in r else "raises " + r["exc"]
            user = f"{cb}{fence(src)}\n\nWhat happens when you evaluate `{show_call(fn.name, calls[i])}`? Trace it, then give the returned value as a Python repr, or `raises <ExceptionName>` if it raises.\nEnd with a line `ANSWER: <value>`."
            rows.append({"family": "exec", "subtype": "exec_trace", "split": split, "source": src_info, "thinking": True, "tools": None,
                         "messages": [{"role": "user", "content": user}, {"role": "assistant", "reasoning_content": trace_text(src, [tuple(s_) for s_ in r["steps"]], r, (ctx.count(chr(10)) + 2) if ctx else 0), "content": "ANSWER: " + ans}],
                         "verifier": {"kind": "exec_trace", "fname": fn.name, "context": ctx, "original": src, "call": calls[i], "answer": ans}})
    return rows

def make_rows(tasks, max_fn=900):
    rows, seen, taken = [], set(), 0
    for t in tasks:
        try: srcs = load_src(t["instance_id"])
        except FileNotFoundError: continue
        for p, fn, ctx in find_pure(srcs):
            if taken >= max_fn: break
            src = ast.unparse(fn); h = sha(ctx + "||" + src)
            if h in seen: continue
            seen.add(h)
            r = process(fn, ctx, src, h, {"task": t["instance_id"], "repo": t["repo"], "path": p, "function": fn.name})
            if r: taken += 1; rows += r
    return rows
