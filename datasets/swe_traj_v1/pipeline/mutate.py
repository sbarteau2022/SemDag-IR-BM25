"""AST-guided, line-local bug injection (SWE-smith style, no LLM).

Each mutation is a dict:
  file, op, func (qualname), func_name, func_start, func_end,
  start, end            (1-based inclusive line span replaced)
  orig_lines, new_lines (lists of str, no newline)
  bad, good             (short code fragments for reasoning text)
"""
import ast
import random

CMP_SWAP = {ast.Lt: (ast.LtE, "<", "<="), ast.LtE: (ast.Lt, "<=", "<"),
            ast.Gt: (ast.GtE, ">", ">="), ast.GtE: (ast.Gt, ">=", ">"),
            ast.Eq: (ast.NotEq, "==", "!="), ast.NotEq: (ast.Eq, "!=", "=="),
            ast.Is: (ast.IsNot, "is", "is not"), ast.IsNot: (ast.Is, "is not", "is"),
            ast.In: (ast.NotIn, "in", "not in"), ast.NotIn: (ast.In, "not in", "in")}
METHOD_SWAP = {"startswith": "endswith", "endswith": "startswith", "lstrip": "rstrip",
               "rstrip": "lstrip", "upper": "lower", "lower": "upper", "keys": "values",
               "appendleft": "append", "popleft": "pop", "extend": "append",
               "remove": "discard", "isdigit": "isalpha", "isalpha": "isdigit"}
NAME_SWAP = {"min": "max", "max": "min", "any": "all", "all": "any",
             "isinstance": None}

OP_FAMILY = {"cmp_swap": "comparison", "boolop_swap": "logic", "drop_not": "logic",
             "off_by_one": "arithmetic", "const_bool": "constant", "index_swap": "indexing",
             "method_swap": "api_misuse", "builtin_swap": "api_misuse", "arg_swap": "call_args",
             "augassign_swap": "arithmetic", "drop_guard": "missing_check",
             "return_none": "wrong_return", "slice_shift": "indexing"}


def _seg(src_line_bytes, node):
    return src_line_bytes[node.col_offset:node.end_col_offset].decode("utf-8")


class _Collector(ast.NodeVisitor):
    def __init__(self, lines):
        self.lines = lines
        self.stack = []
        self.out = []

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node):
        self.stack.append(node.name)
        qual = ".".join(self.stack)
        if node.end_lineno - node.lineno >= 2:
            fstart = min([d.lineno for d in node.decorator_list] + [node.lineno])
            info = (qual, node.name, fstart, node.end_lineno)
            for stmt in node.body:
                self._scan_stmt_tree(stmt, info)
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    # ------------------------------------------------------------------
    def _scan_stmt_tree(self, stmt, info):
        for node in ast.walk(stmt):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) and node is not stmt:
                continue
            if isinstance(node, ast.If):
                self._guard(node, info)
            if not hasattr(node, "lineno") or node.lineno != getattr(node, "end_lineno", -1):
                continue
            self._expr(node, info)

    def _emit(self, op, node, new_seg, info, bad=None, good=None):
        ln = node.lineno
        line = self.lines[ln - 1]
        b = line.encode("utf-8")
        old_seg = _seg(b, node)
        new_line = (b[:node.col_offset].decode("utf-8") + new_seg + b[node.end_col_offset:].decode("utf-8"))
        if new_line == line:
            return
        self.out.append({"op": op, "func": info[0], "func_name": info[1], "func_start": info[2],
                         "func_end": info[3], "start": ln, "end": ln, "orig_lines": [line],
                         "new_lines": [new_line], "bad": new_seg, "good": old_seg})

    def _expr(self, node, info):
        b = self.lines[node.lineno - 1].encode("utf-8")
        seg = lambda n: _seg(b, n)  # noqa: E731
        try:
            if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in CMP_SWAP:
                l, r = node.left, node.comparators[0]
                if l.lineno == r.end_lineno == node.lineno:
                    _, a, z = CMP_SWAP[type(node.ops[0])]
                    self._emit("cmp_swap", node, f"{seg(l)} {z} {seg(r)}", info)
            elif isinstance(node, ast.BoolOp) and len(node.values) == 2:
                other = "or" if isinstance(node.op, ast.And) else "and"
                a, c = node.values
                self._emit("boolop_swap", node, f"{seg(a)} {other} {seg(c)}", info)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                inner = seg(node.operand)
                if isinstance(node.operand, (ast.BoolOp, ast.Compare)):
                    inner = f"({inner})" if not inner.startswith("(") else inner
                self._emit("drop_not", node, inner, info)
            elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)) and \
                    isinstance(node.right, ast.Constant) and node.right.value == 1 and \
                    not isinstance(node.left, ast.Constant):
                self._emit("off_by_one", node, seg(node.left), info)
            elif isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and \
                    isinstance(node.value.value, bool):
                self._emit("const_bool", node, f"return {not node.value.value}", info)
            elif isinstance(node, ast.Return) and node.value is not None and \
                    isinstance(node.value, (ast.Name, ast.Attribute, ast.BinOp, ast.Call)) :
                if random.random() < 0.15:
                    self._emit("return_none", node, "return None", info)
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and \
                    node.slice.value in (0, -1) and not isinstance(node.slice.value, bool):
                v = -1 if node.slice.value == 0 else 0
                self._emit("index_swap", node, f"{seg(node.value)}[{v}]", info)
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
                sl = node.slice
                if sl.step is None and isinstance(sl.lower, ast.Constant) and sl.lower.value == 1 and sl.upper is None:
                    self._emit("slice_shift", node, f"{seg(node.value)}[2:]", info)
                elif sl.step is None and sl.lower is None and isinstance(sl.upper, ast.UnaryOp) and \
                        isinstance(sl.upper.operand, ast.Constant) and sl.upper.operand.value == 1:
                    self._emit("slice_shift", node, f"{seg(node.value)}[:]", info)
            elif isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Attribute) and f.attr in METHOD_SWAP and f.end_lineno == node.lineno:
                    new = seg(node).replace("." + f.attr + "(", "." + METHOD_SWAP[f.attr] + "(", 1)
                    self._emit("method_swap", node, new, info)
                elif isinstance(f, ast.Name) and f.id in ("min", "max", "any", "all") and len(node.args) >= 1:
                    s = seg(node)
                    self._emit("builtin_swap", node, NAME_SWAP[f.id] + s[len(f.id):], info)
                elif len(node.args) == 2 and not node.keywords and all(isinstance(a, ast.Name) for a in node.args) \
                        and node.args[0].id != node.args[1].id and isinstance(f, (ast.Name, ast.Attribute)):
                    fs = seg(f)
                    self._emit("arg_swap", node, f"{fs}({node.args[1].id}, {node.args[0].id})", info)
            elif isinstance(node, ast.AugAssign) and isinstance(node.op, (ast.Add, ast.Sub)):
                op = "-=" if isinstance(node.op, ast.Add) else "+="
                self._emit("augassign_swap", node, f"{seg(node.target)} {op} {seg(node.value)}", info)
        except Exception:
            return

    def _guard(self, node, info):
        """Delete an `if cond: return/raise/continue` guard (<= 3 lines, no else)."""
        if node.orelse or len(node.body) != 1:
            return
        if not isinstance(node.body[0], (ast.Return, ast.Raise, ast.Continue, ast.Break)):
            return
        s, e = node.lineno, node.end_lineno
        if e - s > 2:
            return
        orig = self.lines[s - 1:e]
        cond = ast.get_source_segment("\n".join(self.lines), node.test) if False else None
        b = self.lines[s - 1].encode("utf-8")
        try:
            cond = _seg(b, node.test) if node.test.end_lineno == s else None
        except Exception:
            cond = None
        if cond is None:
            return
        self.out.append({"op": "drop_guard", "func": info[0], "func_name": info[1],
                         "func_start": info[2], "func_end": info[3], "start": s, "end": e,
                         "orig_lines": orig, "new_lines": [], "bad": "", "good": "\n".join(l.strip() for l in orig),
                         "guard_cond": cond})


def candidates(path, rel, seed=0):
    random.seed(hash((rel, seed)) & 0xFFFF)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines = text.split("\n")
    c = _Collector(lines)
    c.visit(tree)
    out = []
    for m in c.out:
        # skip docstring/log-only/pragma lines and lines in type-checking blocks
        if any("pragma" in l or "TYPE_CHECKING" in l for l in m["orig_lines"]):
            continue
        m["file"] = rel
        m["family"] = OP_FAMILY[m["op"]]
        out.append(m)
    return out


def apply(ws_file, m, revert=False):
    with open(ws_file, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    if not revert:
        assert lines[m["start"] - 1:m["end"]] == m["orig_lines"], "stale mutation"
        lines[m["start"] - 1:m["end"]] = m["new_lines"]
    else:
        n = len(m["new_lines"])
        lines[m["start"] - 1:m["start"] - 1 + n] = m["orig_lines"]
    text = "\n".join(lines)
    ast.parse(text)
    with open(ws_file, "w", encoding="utf-8") as fh:
        fh.write(text)
