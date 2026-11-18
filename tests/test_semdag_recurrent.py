"""Unit tests for the v9 recurrent typed SemDAG IR (synthetic repo, no competition data)."""
import importlib
import os
import sys
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "AgenticSubmission", "v9_recurrent", "skills", "semdag", "scripts")

FILES = {
    "src/pkg/__init__.py": "from .core import Walker, run\n",
    "src/pkg/core.py": textwrap.dedent('''
        from typing import overload
        from .util import helper

        class Base:
            def visit(self, n):
                return self.generic(n)
            def generic(self, n):
                for c in n.children:
                    self.visit(c)

        class Walker(Base):
            def __init__(self):
                self.total = 0
            def generic(self, n):
                return super().generic(n)

        @overload
        def run(x: int) -> int: ...
        @overload
        def run(x: str) -> str: ...
        def run(x):
            acc = 0
            i = 0
            while i < x:
                acc += helper(i)
                i += 1
            w = Walker()
            return [helper(v) for v in range(acc)]

        def fact(n):
            return 1 if n <= 1 else n * fact(n - 1)

        def ping(n):
            return pong(n - 1) if n else 0

        def pong(n):
            return ping(n - 1) if n else 1

        def shadow(helper):
            return helper(1)

        def use_walker(tree):
            w = Walker()
            return w.visit(tree)
    '''),
    "src/pkg/util.py": "def helper(i):\n    return i * 2\n",
    "tests/test_core.py": "import pkg\nfrom pkg.core import fact\n\ndef test_fact():\n    assert fact(3) == 6\n    pkg.run(2)\n",
}


NAMES = ("wsroot", "cache", "snapshot", "semdag_ir_ast", "retriever", "vulnwalk", "impact", "flow",
         "repo_eval")


@pytest.fixture(scope="module")
def mods(tmp_path_factory):
    """Import the v9 scripts under their plain names without clashing with other versions'
    scripts of the same names (v6/v7 tests import their own `repo_eval`, `cache`, ...)."""
    saved = {n: sys.modules.pop(n) for n in NAMES if n in sys.modules}
    old_cache = os.environ.get("SEMDAG_CACHE")
    os.environ["SEMDAG_CACHE"] = str(tmp_path_factory.mktemp("cache"))
    sys.path.insert(0, SCRIPTS)
    try:
        yield {n: importlib.import_module(n) for n in NAMES}
    finally:
        sys.path.remove(SCRIPTS)
        for n in NAMES:
            sys.modules.pop(n, None)
        sys.modules.update(saved)
        if old_cache is None:
            os.environ.pop("SEMDAG_CACHE", None)
        else:
            os.environ["SEMDAG_CACHE"] = old_cache


@pytest.fixture(scope="module")
def ir(mods, tmp_path_factory):
    repo = tmp_path_factory.mktemp("repo")
    for rel, text in FILES.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    mods["cache"].init_container("t", str(repo))
    mods["snapshot"].snapshot("t", str(repo))
    return mods["semdag_ir_ast"].build("t")


def _edges(ir, rel):
    return {(e["src"].split("::")[-1].split("#")[0] if "::" in e["src"] else e["src"],
             e["dst"].split("::")[-1].split("#")[0] if "::" in e["dst"] else e["dst"])
            for e in ir["edges"] if e["rel"] == rel}


def _node(ir, kind, qualname):
    return next(n for n in ir["nodes"] if n["kind"] == kind and n.get("qualname") == qualname)


def test_src_layout_imports_resolve_to_files(ir):
    imports = _edges(ir, "imports")
    assert ("file:tests/test_core.py", "file:src/pkg/__init__.py") in imports
    assert ("file:tests/test_core.py", "file:src/pkg/core.py") in imports
    assert not any(n["kind"] == "module" and n["name"].startswith("pkg") for n in ir["nodes"])


def test_reexport_and_overload(ir):
    calls = _edges(ir, "calls")
    assert ("test_fact", "run") in calls             # pkg.run -> __init__ re-export -> core.run
    run = [n for n in ir["nodes"] if n.get("qualname") == "run"]
    assert sum(1 for n in run if n.get("overload")) == 2
    target = next(e["dst"] for e in ir["edges"] if e["rel"] == "calls" and "test_fact" in e["src"] and "run" in e["dst"])
    assert not next(n for n in ir["nodes"] if n["id"] == target).get("overload")


def test_loops_are_typed_nodes_with_back_edges(ir):
    loops = [n for n in ir["nodes"] if n["kind"] == "loop" and n["owner"].endswith(("run#fn@24", "run#fn@" + str(_node(ir, "function", "run")["line"]))) ]
    kinds = sorted(n["loop_kind"] for n in ir["nodes"] if n["kind"] == "loop" and "::run#loop" in n["id"])
    assert kinds == ["listcomp", "while"]
    wl = next(n for n in ir["nodes"] if n["kind"] == "loop" and n["loop_kind"] == "while")
    assert wl["carried"] == ["acc", "i"]
    assert (wl["id"], wl["id"], "loop_back") in {(e["src"], e["dst"], e["rel"]) for e in ir["edges"]}
    assert any(e["rel"] == "loop_calls" and e["src"] == wl["id"] and e["dst"].endswith("helper#fn@1") for e in ir["edges"])


def test_recursion_kept_and_condensed(ir):
    assert _node(ir, "function", "fact")["recursive"]
    assert ("fact", "fact") in _edges(ir, "recurses")
    ping, pong = _node(ir, "function", "ping"), _node(ir, "function", "pong")
    assert ping["scc"] == pong["scc"] and ping["topo_rank"] == pong["topo_rank"]
    rec = next(n for n in ir["nodes"] if n["id"] == ping["scc"])
    assert rec["kind"] == "recursion" and rec["size"] == 2
    assert ir["counts"]["condensed_acyclic"]
    # Base.visit -> self.generic resolves through the MRO; Walker.generic -> super().generic
    calls = _edges(ir, "calls")
    assert ("Base.visit", "Base.generic") in calls and ("Walker.generic", "Base.generic") in calls


def test_inheritance_instantiation_and_shadowing(ir):
    assert ("Walker", "Base") in _edges(ir, "inherits")
    assert ("run", "Walker") in _edges(ir, "instantiates")
    assert ("run", "Walker.__init__") in _edges(ir, "calls")
    assert not any(s == "shadow" for s, _ in _edges(ir, "calls"))   # parameter shadows helper


def test_every_forward_edge_has_its_inverse(ir, mods):
    keys = {(e["src"], e["dst"], e["rel"]) for e in ir["edges"]}
    b = mods["semdag_ir_ast"]
    for s, d, r in list(keys):
        if r in b.INVERSE:
            assert (d, s, b.INVERSE[r]) in keys


# ---------------------------------------------------------------- tooling on the graph
def test_flow_describes_loops_recursion_and_callers(ir, mods):
    flow = mods["flow"]
    d = flow.describe(ir, "run")
    assert d["node"].endswith(" run") and [l["kind"] for l in d["loops"]] == ["while", "listcomp"]
    assert d["loops"][0]["carried"] == ["acc", "i"] and d["loops"][0]["calls"] == ["helper"]
    assert d["test_callers"] == 1
    f = flow.describe(ir, "ping")
    assert f["recursion"]["cycle_size"] == 2 and "pong" in f["recursion"]["with"][0]
    assert flow.describe(ir, "nope")["error"]


def test_local_instance_resolution(ir):
    calls = _edges(ir, "calls")
    assert ("use_walker", "Base.visit") in calls


def test_verify_recurrence_notes(ir, mods):
    repo_eval = mods["repo_eval"]
    notes = repo_eval.recurrence_notes(ir, ["src/pkg/core.py::fact", "src/pkg/core.py::run", "x.py::new (new)"])
    assert any("fact is recursive" in n for n in notes)
    assert any("run has 2 loop(s) carrying acc, i" in n for n in notes)


@pytest.mark.parametrize("argv", [["--flow", "Walker.generic"], ["--flow Walker.generic"],
                                  ['["--flow", "Walker.generic"]'], ["flow", "Walker.generic"]])
def test_flow_argument_shapes(argv, mods):
    opt = mods["repo_eval"].parse_args(argv)
    assert opt["mode"] == "flow" and opt["ref"] == "Walker.generic"
