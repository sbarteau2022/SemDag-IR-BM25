"""Sandboxed executor. stdin JSON {src, fname, calls:[argsrepr...], trace:bool}. Run with python -I. Output JSON list."""
import ast, builtins, json, signal, sys
ALLOWED = ["re", "math", "string", "itertools", "functools", "collections", "operator", "textwrap", "json", "typing", "dataclasses", "enum", "decimal", "fractions", "unicodedata", "urllib", "codecs", "binascii", "base64", "hashlib", "datetime", "types", "copy"]

class Strip(ast.NodeTransformer):
    def visit_arg(self, n): n.annotation = None; return n
    def visit_FunctionDef(self, n):
        self.generic_visit(n); n.returns = None; n.decorator_list = []; return n
    def visit_AnnAssign(self, n):
        self.generic_visit(n)
        return ast.Assign(targets=[n.target], value=n.value, lineno=n.lineno) if n.value is not None else ast.Pass()

def main():
    spec = json.load(sys.stdin)
    tree = Strip().visit(ast.parse(spec["src"])); ast.fix_missing_locations(tree)
    ns = {"__builtins__": {k: getattr(builtins, k) for k in dir(builtins) if k not in ("open", "exec", "eval", "compile", "input", "__import__", "breakpoint", "exit", "quit", "help")}}
    import importlib
    for m in ALLOWED:
        ns[m] = importlib.import_module(m)
    ns["__builtins__"]["__import__"] = __import__
    exec(compile(tree, "<fn>", "exec"), ns)
    f = ns[spec["fname"]]
    code_lines = spec["src"].splitlines()
    out = []
    def handler(*a): raise TimeoutError("timeout")
    signal.signal(signal.SIGALRM, handler)
    for argsrepr in spec["calls"]:
        steps, top = [], []
        def tracer(frame, ev, arg):
            if frame.f_code.co_filename != "<fn>": return None
            if not top: top.append(frame)
            if frame is not top[0]: return None
            if ev == "line" and len(steps) < 80:
                steps.append((frame.f_lineno, {k: repr(v)[:60] for k, v in frame.f_locals.items()}))
            return tracer
        try:
            args = ast.literal_eval(argsrepr)
            signal.alarm(2)
            if spec.get("trace"): sys.settrace(tracer)
            try: v = f(*args)
            finally:
                sys.settrace(None); signal.alarm(0)
            rec = {"ok": repr(v)[:400]}
        except BaseException as e:
            rec = {"exc": type(e).__name__}
        if spec.get("trace"):
            rec["steps"] = [(ln, cur) for ln, cur in steps[:60]]; rec["nsteps"] = len(steps)
        out.append(rec)
    print(json.dumps(out))
main()
