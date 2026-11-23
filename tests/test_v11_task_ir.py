"""v11_task_ir: problem IR, anchor join, loop locus, hardened code IR, blocking verify.
Synthetic repositories only; no competition data."""
import importlib
import os
import subprocess
import sys
import textwrap

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUB = os.path.join(ROOT, "AgenticSubmission", "v11_task_ir")
SCRIPTS = os.path.join(SUB, "skills", "semdag", "scripts")
NAMES = ("wsroot", "cache", "snapshot", "semdag_ir_ast", "retriever", "vulnwalk", "impact", "flow",
         "task_ir", "repo_eval", "fix_edit")

MOD = textwrap.dedent('''\
    import os


    class Frame:
        def __init__(self, filename, lineno, name):
            self.filename, self.lineno, self.name = filename, lineno, name


    def extract(stack):
        frames = []
        for summary in stack:
            frames.append(Frame(summary[0], summary[1], summary[2]))
        if not frames:
            raise ValueError("stack must not be empty here")
        return frames


    def split_cells(text, cut):
        pos = len(text) // 2
        width = 0
        while pos < len(text):
            width += 1
            if width > cut:
                return text[:pos], text[pos:]
            pos += 1
        raise AssertionError("never")


    def helper_path(name):
        import posixpath as path
        return path(name)


    def path(name):
        return name


    def caller(name):
        return path(name)
''')


@pytest.fixture(scope="module")
def mods(tmp_path_factory):
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


def _git_repo(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "base"],
                ["git", "tag", "_swegemma_baseline"]):
        subprocess.run(cmd, cwd=tmp_path, check=True, env=env)
    return tmp_path


@pytest.fixture()
def repo(tmp_path):
    test = "from pkg.mod import split_cells\n\n\ndef test_split_cells_basic():\n    assert split_cells('ab', 1)\n"
    return _git_repo(tmp_path, {"pkg/__init__.py": "", "pkg/mod.py": MOD, "tests/test_mod.py": test})


def _locate(mods, repo, issue, cid):
    re_ = mods["repo_eval"]
    opt = re_.parse_args([issue])
    opt["repo"], opt["container"] = str(repo), cid
    return re_.locate(opt)


def _ir(mods, repo, cid):
    mods["cache"].init_container(cid, str(repo))
    mods["snapshot"].snapshot(cid, str(repo))
    return mods["semdag_ir_ast"].build(cid)


# ---------------------------------------------------------------- problem IR
def test_problem_ir_types_frames_literals_paths_and_names(mods):
    issue = textwrap.dedent('''\
        Calling `Segment.split_cells` crashes:
        Traceback (most recent call last):
          File "/usr/lib/python3/site-packages/pkg/mod.py", line 22, in split_cells
        ValueError: stack must not be empty here
        See pkg/mod.py and the "never reach this" message.
    ''')
    pir = mods["task_ir"].problem_ir(issue)
    assert pir["frames"] == [{"path": "/usr/lib/python3/site-packages/pkg/mod.py", "line": 22, "qual": "split_cells"}]
    assert "stack must not be empty here" in pir["literals"] and "never reach this" in pir["literals"]
    assert "pkg/mod.py" in pir["paths"] and "Segment.split_cells" in pir["dotted"]
    assert "split_cells" in pir["idents"]


# ---------------------------------------------------------------- anchor join order
def test_traceback_frame_from_site_packages_anchors_the_innermost_function(mods, repo):
    out = _locate(mods, repo, 'Traceback:\n  File "/venv/lib/site-packages/pkg/mod.py", line 22, in split_cells\n'
                              'AssertionError: never', "t1")
    first = out["text"].splitlines()[0]
    assert first.startswith("edit pkg/mod.py:") and "split_cells" in first and "anchor: traceback" in first


def test_unique_literal_anchors_its_function(mods, repo):
    out = _locate(mods, repo, 'It fails with "stack must not be empty here" when given nothing.', "t2")
    assert "extract" in out["text"].splitlines()[0] and "anchor: literal" in out["text"]


def test_qualname_mention_anchors_and_bm25_is_the_marked_fallback(mods, repo):
    out = _locate(mods, repo, "Frame.__init__ ignores the line number", "t3")
    assert "Frame.__init__" in out["text"].splitlines()[0] and "anchor: qualname" in out["text"]
    out = _locate(mods, repo, "the name comes back wrong for some text", "t4")
    assert "anchor: bm25" in out["text"] and out["text"].splitlines()[-1].startswith("alt ")


# ---------------------------------------------------------------- locus and output
def test_locus_needs_an_issue_name_the_loop_carries_and_covers_its_init(mods, repo):
    out = _locate(mods, repo, "split_cells returns the wrong split: pos starts too far right", "t5")
    lines = out["text"].splitlines()
    loop = next(l for l in lines if l.startswith("loop "))
    assert "while" in loop and "pos" in loop and "test: pos < len(text)" in loop
    # the span starts at `pos = len(text) // 2` (line 19), before the loop (lines 21-25)
    assert lines[0].startswith("edit pkg/mod.py:19-25 split_cells")
    assert "the terminal raise at L" in out["text"]
    # no carried name in the issue: no locus, no flow at all
    plain = _locate(mods, repo, "split_cells returns the wrong split", "t6")
    assert not any(l.startswith("loop ") for l in plain["text"].splitlines())


def test_locate_prints_one_short_action_and_keeps_the_rest_for_eval(mods, repo):
    out = _locate(mods, repo, "split_cells returns the wrong split: pos starts too far right", "t7")
    text = out["text"]
    assert len(text) <= 600
    for gone in ("hubs", "walk_paths", "risk", "fan_in", "topo_rank"):
        assert gone not in text
    assert any(l.startswith("check python -m pytest tests/test_mod.py::test_split_cells_basic") for l in text.splitlines())
    ev = mods["cache"].read("t7", "eval.json")
    assert {"hubs", "walk_paths", "top_edit_sites"} <= set(ev) and "risk" in ev["top_edit_sites"][0]


# ---------------------------------------------------------------- hardened code IR
def test_carried_locations_cover_attributes_subscripts_and_conditional_stores(mods, tmp_path):
    src = textwrap.dedent('''\
        class Scanner:
            def run(self, items, flags):
                buf = [0]
                last = None
                while self.pos < len(items):
                    if flags:
                        last = items[self.pos]
                    use(last)
                    buf[0] = buf[0] + 1
                    self.pos += 1
                return buf


        def use(x):
            return x
    ''')
    repo = _git_repo(tmp_path, {"m.py": src})
    ir = _ir(mods, repo, "t8")
    loop = next(n for n in ir["nodes"] if n["kind"] == "loop")
    # v10's single pass missed all three: `last` is stored on one branch only, then read
    assert {"self.pos", "buf[]", "last"} <= set(loop["carried"])
    assert loop["test"] == "self.pos < len(items)"


def test_exit_conditions_are_recorded_as_text(mods, repo):
    ir = _ir(mods, repo, "t9")
    loop = next(n for n in ir["nodes"] if n["kind"] == "loop" and n["loop_kind"] == "while")
    assert {"kind": "return", "line": 24, "cond": "width > cut"} in loop["exit_conds"]


def test_function_level_import_is_scoped_and_shadows(mods, repo):
    ir = _ir(mods, repo, "t10")
    calls = {(e["src"].split("::")[1].split("#")[0], e["dst"].split("::")[1].split("#")[0])
             for e in ir["edges"] if e["rel"] == "calls"}
    assert ("caller", "path") in calls             # the module-level def still resolves elsewhere
    assert ("helper_path", "path") not in calls     # the local `import posixpath as path` shadows it


def test_annotated_local_is_typed(mods, tmp_path):
    src = textwrap.dedent('''\
        class Env:
            def parse(self):
                return 1


        def make():
            return Env()


        def go():
            env: Env = make()
            return env.parse()
    ''')
    ir = _ir(mods, _git_repo(tmp_path, {"m.py": src}), "t11")
    assert any(e["rel"] == "calls" and e["src"].startswith("m.py::go#") and "Env.parse" in e["dst"]
               for e in ir["edges"])


def test_method_lookup_follows_c3_not_breadth_first(mods, tmp_path):
    # D(B, C) with B(A): C3 order is D, B, A, C. Breadth-first would find C.m first.
    src = textwrap.dedent('''\
        class A:
            def m(self):
                return "A"


        class B(A):
            pass


        class C:
            def m(self):
                return "C"


        class D(B, C):
            def go(self):
                return self.m()
    ''')
    ir = _ir(mods, _git_repo(tmp_path, {"m.py": src}), "t12")
    dst = [e["dst"] for e in ir["edges"] if e["rel"] == "calls" and "D.go" in e["src"]]
    assert dst and dst[0].startswith("m.py::A.m#")


# ---------------------------------------------------------------- verify gate
def _run_verify(mods, repo, cid):
    re_ = mods["repo_eval"]
    opt = re_.parse_args(["--verify"])
    opt["repo"], opt["container"] = str(repo), cid
    return re_.verify(opt)


def test_verify_blocks_a_patch_that_misses_the_loop_locus(mods, repo):
    _locate(mods, repo, "split_cells returns the wrong split: pos starts too far right", "task")
    fe = mods["fix_edit"]
    # an edit to the terminal raise only, as in run_25 rich_3506
    text = (repo / "pkg" / "mod.py").read_text().splitlines()
    n = text.index('    raise AssertionError("never")') + 1
    assert fe.run("pkg/mod.py", f"L{n}-{n}", "    return text, ''", repo=str(repo))["ok"]
    out = _run_verify(mods, repo, "task")
    assert out["blocked"] is True and out["clean"] is False and out["next"].startswith("blocked: patch does not touch while")
    assert out["patch"]["empty"] is False
    # now fix inside the span: the gate opens
    assert fe.run("pkg/mod.py", "L19-19", "    pos = 0", repo=str(repo))["ok"]
    out = _run_verify(mods, repo, "task")
    assert not out.get("blocked") and not out["next"].startswith("blocked")


def test_verify_blocks_a_whole_file_rewrite(mods, tmp_path):
    body = "\n".join(f"def f{i}():\n    return {i}\n" for i in range(40))
    repo = _git_repo(tmp_path, {"big.py": body})
    (repo / "big.py").write_text("def f0():\n    return 0\n")
    cache = mods["cache"]
    cache.init_container("task", str(repo))
    cache.write("task", "task_ir.json", {"locus": None})
    out = _run_verify(mods, repo, "task")
    assert out["blocked"] is True and "deletes" in out["next"] and "git checkout -- big.py" in out["next"]


# ---------------------------------------------------------------- wiring
def test_agent_has_one_edit_path_and_no_sub_agent():
    cfg = yaml.safe_load(open(os.path.join(SUB, "agent.yaml")).read().replace("!include", ""))
    tools = cfg["tools"]
    assert "edit_file" not in tools and "write_file" not in tools
    assert not any(isinstance(t, dict) for t in tools)   # no agent_tool
    assert not os.path.exists(os.path.join(SUB, "sub_agents"))
    system = open(os.path.join(SUB, "prompts", "system.md")).read()
    assert 'Its first line is `FILE LX-Y`' in system and "blocked:" in system


def test_v11_validates_as_a_submission():
    adk = pytest.importorskip("adk_submission")
    from pathlib import Path
    from swegemma.config import build_submission_limits
    adk.validate_directory(Path(SUB), limits=build_submission_limits()[0])


# ---------------------------------------------------------------- fix_edit argument shapes (run_26)
@pytest.mark.parametrize("argv, want", [
    (["pkg/mod.py L19-25"], ("pkg/mod.py", "L19-25", None)),
    (["pkg/mod.py L19-19\n    pos = 0"], ("pkg/mod.py", "L19-19", "    pos = 0")),
    (['pkg/mod.py, 19-19, "    pos = \\"x\\""'], ("pkg/mod.py", "L19-19", '    pos = "x"')),
    (["pkg/mod.py", '"19-19"', "    pos = 0"], ("pkg/mod.py", "L19-19", "    pos = 0")),
    (['fix pkg/mod.py 23-24 "            if width > cut:\\\n                return text, \'\'\n"'],
     ("pkg/mod.py", "L23-24", "            if width > cut:\n                return text, ''\n")),
    (["pkg/mod.py", "L3", "    return 'x'"], ("pkg/mod.py", "L3", "    return 'x'")),
])
def test_fix_edit_accepts_the_shapes_e4b_sends(mods, argv, want):
    assert mods["fix_edit"].parse_args(argv) == want


def test_one_string_edit_applies_end_to_end(mods, repo):
    fe = mods["fix_edit"]
    out = fe.run(*fe.parse_args(["pkg/mod.py L19-19\n    pos = 0"]), repo=str(repo))
    assert out["ok"] is True and "\n    pos = 0\n" in (repo / "pkg" / "mod.py").read_text()


def test_prompt_example_is_synthetic():
    system = open(os.path.join(SUB, "prompts", "system.md")).read()
    for public in ("rich/", "requests/", "httpx/", "fastapi/", "segment", "cell_"):
        assert public not in system


def test_escaped_newlines_are_decoded_but_string_literals_kept(mods):
    fe = mods["fix_edit"]
    arg = "pkg/mod.py L19-20\\n    pos = 0\\n    width = 0"
    assert fe.parse_args([arg]) == ("pkg/mod.py", "L19-20", "    pos = 0\n    width = 0")
    assert fe.parse_args(['pkg/mod.py L3-3\\n    x = "a\\nb"']) == ("pkg/mod.py", "L3-3", '    x = "a\\nb"')


def test_refused_range_edit_shows_what_the_range_holds(mods, repo):
    fe = mods["fix_edit"]
    out = fe.run("pkg/mod.py", "L21-22", "                return 1,", repo=str(repo))
    assert out["ok"] is False and "while pos < len(text):" in out["lines_you_replaced"]
    assert "21:" in out["lines_you_replaced"] and (repo / "pkg" / "mod.py").read_text() == MOD


def test_no_read_file_and_read_line_is_the_exact_call(mods, repo):
    cfg = yaml.safe_load(open(os.path.join(SUB, "agent.yaml")).read().replace("!include", ""))
    assert "read_file" not in cfg["tools"]
    out = _locate(mods, repo, "split_cells returns the wrong split", "t13")
    assert any(l.startswith('read fix_edit.py ["pkg/mod.py L') for l in out["text"].splitlines())


def test_mutating_container_calls_are_tracked_as_loop_carried(mods, tmp_path):
    src = textwrap.dedent('''\
        def collect(items):
            out = []
            for item in items:
                out.append(item)
            return out
    ''')
    ir = _ir(mods, _git_repo(tmp_path, {"c.py": src}), "t14")
    loop = next(n for n in ir["nodes"] if n["kind"] == "loop")
    assert "out" in loop["carried"]


def test_graph_walk_recalls_zero_bm25_neighbor_and_uses_recurrent_edges(mods, tmp_path):
    src = textwrap.dedent('''\
        def entrypoint(items):
            for x in items:
                _internal_worker(x)


        def _internal_worker(val):
            return val + 1
    ''')
    repo_dir = _git_repo(tmp_path, {"w.py": src})
    ir = _ir(mods, repo_dir, "t15")
    snap = mods["cache"].read("t15", "snapshot.json")
    ranked = mods["retriever"].rank(ir, snap, "entrypoint fails on items", top_n=5, damping=0.15)
    names = [s["name"] for s in ranked["top"]]
    assert "entrypoint" in names and "_internal_worker" in names
    assert "loop_calls" in ranked["relations_used"]
    worker = next(s for s in ranked["top"] if s["name"] == "_internal_worker")
    assert worker["lexical_score"] == 0.0 and worker["structural_score"] > 0.0
    # d=0 must remain pure BM25 (only positive lexical hits)
    d0 = mods["retriever"].rank(ir, snap, "entrypoint fails on items", top_n=5, damping=0.0)
    assert [s["name"] for s in d0["top"]] == ["entrypoint"]
