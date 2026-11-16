"""Synthetic/algorithmic families: dep-DAG compile+solve, import-graph compile, Python->IR compile. Answers by code."""

import ast
import collections
import json
import textwrap

from common import *
from g_graph import fmt, kahn, sccs

WORDS = [
    "auth",
    "cache",
    "config",
    "db",
    "events",
    "http",
    "io",
    "log",
    "models",
    "router",
    "schema",
    "session",
    "store",
    "tasks",
    "utils",
    "views",
    "worker",
    "queue",
    "parser",
    "render",
    "codec",
    "clock",
    "retry",
    "pool",
    "hooks",
    "admin",
    "audit",
    "search",
    "mail",
    "ledger",
]


def rand_dag(rng, n, p):
    names = rng.sample(WORDS, n)
    order = names[:]
    rng.shuffle(order)
    deps = {m: [] for m in names}
    for i, m in enumerate(order):
        for j in range(i):
            if rng.random() < p:
                deps[m].append(order[j])  # m depends on earlier ones
    return {m: sorted(v) for m, v in deps.items()}


def inject_cycle(rng, deps):
    ms = sorted(deps)
    a, b = rng.sample(ms, 2)
    if b not in deps[a]:
        deps[a] = sorted(deps[a] + [b])
    if a not in deps[b]:
        deps[b] = sorted(deps[b] + [a])
    return deps


def render_spec(rng, deps):
    k = rng.choice(["make", "arrows", "imports"])
    if k == "make":
        return (
            "make",
            "\n".join(f"{m}: {' '.join(d)}".rstrip() for m, d in sorted(deps.items())),
            "Makefile-style rules (`target: prerequisites`)",
        )
    if k == "arrows":
        ls = [f"{m} -> {d}" for m, ds in sorted(deps.items()) for d in ds] or [
            "(no dependencies)"
        ]
        return (
            "arrows",
            "\n".join(ls) + "\nmodules: " + ", ".join(sorted(deps)),
            "dependency lines where `a -> b` means a depends on b",
        )
    files = []
    for m, ds in sorted(deps.items()):
        body = "".join(
            (f"import {d}\n" if i % 2 == 0 else f"from {d} import run as run_{d}\n")
            for i, d in enumerate(ds)
        )
        files.append(f"# {m}.py\n{body}def run():\n    return '{m}'\n")
    return (
        "imports",
        "\n".join(files),
        "Python modules (only imports between these modules matter)",
    )


def parse_spec(kind, text):  # generator-side parse used for the gate
    """Inverse of render_spec: spec text -> {module: [prereqs]}.
    Returns None when the text does not parse cleanly (the gate rejects the row)."""
    if kind == "make":
        deps = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                return None
            m, _, rest = line.partition(":")
            deps[m.strip()] = rest.split()
        return deps or None
    if kind == "arrows":
        mods, edges = [], {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("modules:"):
                mods = [
                    x.strip() for x in line[len("modules:") :].split(",") if x.strip()
                ]
                continue
            if line == "(no dependencies)":
                continue  # empty edge set, only the modules line follows
            if "->" not in line:
                return None
            a, _, b = line.partition("->")
            edges.setdefault(a.strip(), []).append(b.strip())
        out = {m: [] for m in mods}
        for m, ds in edges.items():
            out.setdefault(m, []).extend(ds)
        return {m: sorted(set(v)) for m, v in out.items()} or None
    if kind == "imports":
        deps, cur = {}, None
        for line in text.splitlines():
            if line.startswith("# ") and line.endswith(".py"):
                cur = line[2:-3]
                deps.setdefault(cur, [])
                continue
            if cur is None:
                continue
            s = line.strip()
            if s.startswith("import ") and " as " not in s:
                name = s.split()[1]
                if "." not in name:
                    deps[cur].append(name)
            elif s.startswith("from ") and " import " in s:
                name = s.split()[1]
                if "." not in name:
                    deps[cur].append(name)
        return {m: sorted(set(v)) for m, v in deps.items()} or None
    return None


def build_order(deps):
    out = {m: set() for m in deps}  # edge dep -> dependent
    for m, ds in deps.items():
        for d in ds:
            out[d].add(m)
    return kahn(sorted(deps), out)


def longest(deps):
    order, _ = build_order(deps)
    best = {}
    for m in order:
        best[m] = max(
            ([best[d] for d in deps[m]] or [[]]),
            key=lambda p: (len(p), [-ord(c) for c in "".join(p)]),
        )
    return None


def critical(deps):
    order, _ = build_order(deps)
    depth, prev = {}, {}
    for m in order:
        depth[m] = 1 + max([depth[d] for d in deps[m]] or [0])
    top = max(depth.values())
    # enumerate all maximal chains, choose alphabetically earliest by node sequence
    chains = []

    def back(m, tail):
        if depth[m] == 1:
            chains.append([m] + tail)
            return
        for d in deps[m]:
            if depth[d] == depth[m] - 1:
                back(d, [m] + tail)

    for m in sorted(deps):
        if depth[m] == top:
            back(m, [])
    return min(chains), depth


def waves(deps):
    _, depth = critical(deps)
    w = collections.defaultdict(list)
    for m, d in depth.items():
        w[str(d - 1)].append(m)
    return {k: sorted(v) for k, v in sorted(w.items(), key=lambda kv: int(kv[0]))}


TASKS = ["order", "critical", "waves", "cycle", "compile"]


def dag_rows(split_counts):
    rows = []
    for split, n in split_counts.items():
        for i in range(n):
            rng = rng_for("synth", split, i)
            q = TASKS[i % len(TASKS)]
            size = rng.randint(5, 11)
            deps = rand_dag(rng, size, rng.choice([0.2, 0.3, 0.4]))
            cyc = q == "cycle" and rng.random() < 0.6
            if cyc:
                deps = inject_cycle(rng, deps)
            kind, spec, desc = render_spec(rng, deps)
            mods = sorted(deps)
            out_edges = {m: set() for m in deps}
            for m, ds in deps.items():
                for d in ds:
                    out_edges[d].add(m)
            comps = [c for c in sccs(mods, out_edges) if len(c) > 1]
            if comps and q != "cycle":
                continue
            if q == "order":
                val, tr = build_order(deps)
                ask = "Give a valid build order (prerequisites before dependents; alphabetical tie-break among ready modules)."
                think = (
                    "Dependencies: "
                    + "; ".join(
                        f"{m} needs {', '.join(d) if d else 'nothing'}"
                        for m, d in sorted(deps.items())
                    )
                    + ". "
                    + " ".join(
                        f"Build {n}; ready next: {', '.join(r) if r else 'none'}."
                        for n, r in tr
                    )
                )
            elif q == "critical":
                val, depth = critical(deps)
                ask = "Find the longest dependency chain (most modules, prerequisite first). Break ties by the alphabetically earliest chain."
                think = (
                    "Depth = 1 + deepest prerequisite: "
                    + ", ".join(f"{m}={depth[m]}" for m in mods)
                    + f". Deepest is {max(depth.values())}; the alphabetically earliest chain of that length is {' -> '.join(val)}."
                )
            elif q == "waves":
                val = waves(deps)
                ask = "Group modules into parallel build waves: wave 0 has no prerequisites, wave k needs only earlier waves and at least one in wave k-1."
                think = (
                    "Wave = depth - 1 where depth = 1 + deepest prerequisite. Result by wave: "
                    + "; ".join(f"{k}: {', '.join(v)}" for k, v in val.items())
                    + "."
                )
            elif q == "cycle":
                val = {"build_possible": not comps, "cycles": comps}
                ask = 'Can these modules be built at all? Return {"build_possible": bool, "cycles": [sorted groups of 2+ modules that depend on each other]}.'
                think = (
                    (
                        "Mutually dependent: "
                        + "; ".join(", ".join(c) for c in comps)
                        + ". A build order cannot exist while a cycle remains."
                    )
                    if comps
                    else "Repeatedly removing modules with no unbuilt prerequisites clears every module, so there is no cycle."
                )
            else:
                val = {m: deps[m] for m in mods}
                ask = "Compile the spec into a JSON object mapping each module to its sorted list of direct prerequisites (modules it depends on)."
                think = (
                    "Reading the "
                    + desc
                    + ": "
                    + "; ".join(
                        f"{m} -> {', '.join(d) if d else '-'}"
                        for m, d in sorted(deps.items())
                    )
                    + "."
                )
            user = f"Dependency spec ({desc}):\n```\n{spec}\n```\n\n{ask}\nEnd with a line `ANSWER: <json>`."
            rows.append(
                {
                    "family": "dag",
                    "subtype": f"synth_{q}",
                    "split": split,
                    "source": {"task": "synthetic", "kind": kind},
                    "thinking": True,
                    "tools": None,
                    "messages": [
                        {"role": "user", "content": user},
                        {
                            "role": "assistant",
                            "reasoning_content": think,
                            "content": "ANSWER: " + fmt(val),
                        },
                    ],
                    "verifier": {
                        "kind": "synth_dag",
                        "q": q,
                        "spec_kind": kind,
                        "spec": spec,
                        "answer": val,
                    },
                }
            )
    return rows


# ---------- Python -> IR compile ----------
def dotted(n):
    parts = []
    while isinstance(n, ast.Attribute):
        parts.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        parts.append(n.id)
        return ".".join(reversed(parts))
    return None


def ir_of(fn):
    a = fn.args
    params = [x.arg for x in a.posonlyargs + a.args]
    if a.vararg:
        params.append("*" + a.vararg.arg)
    params += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        params.append("**" + a.kwarg.arg)
    calls, raises, ret, br = [], [], 0, 0
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            d = dotted(n.func)
            if d:
                calls.append((n.lineno, n.col_offset, d))
        elif isinstance(n, ast.Raise) and n.exc is not None:
            e = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
            d = dotted(e)
            if d:
                raises.append(d)
        elif isinstance(n, ast.Return):
            ret += 1
        elif isinstance(
            n, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.Try)
        ):
            br += 1
    return {
        "name": fn.name,
        "params": params,
        "calls": sorted({c[2] for c in calls}),
        "raises": sorted(set(raises)),
        "returns": ret,
        "branches": br,
    }, [c[2] for c in sorted(calls)]


IR_ASK = (
    "Compile this function into a JSON summary with keys: name; params (argument names in order, `*args`/`**kwargs` keep their stars); "
    "calls (sorted unique callee names as written, e.g. `self.run`, `len`; only plain name or attribute chains, including nested functions and lambdas); "
    "raises (sorted unique exception names used with `raise`); returns (number of `return` statements); "
    "branches (count of if/elif, conditional expressions, for, while and try statements)."
)


def functions_from_sources(srcs, path_filter=lambda p: True, lo=4, hi=40):
    out = []
    for p in sorted(srcs):
        if is_test_path(p) or not path_filter(p):
            continue
        try:
            tree = ast.parse(srcs[p])
        except SyntaxError:
            continue
        lines = srcs[p].splitlines()
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                L = n.end_lineno - n.lineno + 1
                if lo <= L <= hi:
                    txt = textwrap.dedent("\n".join(lines[n.lineno - 1 : n.end_lineno]))
                    out.append((p, n.name, n.lineno, txt))
    return out


def ir_rows(tasks, smap, per_task=12):
    rows, seen = [], set()
    for t in tasks:
        try:
            srcs = load_src(t["instance_id"])
        except FileNotFoundError:
            continue
        fns = functions_from_sources(
            srcs, lambda p: "docs_src" not in p and not p.startswith("scripts/")
        )
        fns.sort(key=lambda f: sha(f"ir|{t['instance_id']}|{f[0]}|{f[2]}"))
        k = 0
        for p, name, ln, txt in fns:
            h = sha(txt)
            if h in seen:
                continue
            try:
                fn = ast.parse(txt).body[0]
            except SyntaxError:
                continue
            seen.add(h)
            ir, order = ir_of(fn)
            split = (
                "train"
                if int(sha("fn|" + h, 8), 16) % 10 < 8
                else ("dev" if int(sha("fn|" + h, 8), 16) % 10 == 8 else "test")
            )
            think = (
                f"Signature: {ir['name']}({', '.join(ir['params'])}). Calls in source order: {', '.join(order) if order else 'none'}. "
                f"Raises: {', '.join(ir['raises']) if ir['raises'] else 'none'}. {ir['returns']} return statement(s) and {ir['branches']} branching construct(s)."
            )
            user = (
                f"```python\n{txt}\n```\n\n{IR_ASK}\nEnd with a line `ANSWER: <json>`."
            )
            rows.append(
                {
                    "family": "dag",
                    "subtype": "py_to_ir",
                    "split": split,
                    "source": {
                        "task": t["instance_id"],
                        "repo": t["repo"],
                        "path": p,
                        "line": ln,
                    },
                    "thinking": True,
                    "tools": None,
                    "messages": [
                        {"role": "user", "content": user},
                        {
                            "role": "assistant",
                            "reasoning_content": think,
                            "content": "ANSWER: " + fmt(ir),
                        },
                    ],
                    "verifier": {"kind": "ir", "source": txt, "answer": ir},
                }
            )
            k += 1
            if k >= per_task:
                break
    return rows
