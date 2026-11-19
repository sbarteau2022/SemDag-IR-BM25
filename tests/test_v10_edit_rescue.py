"""v10_edit_rescue: edit-path repairs and flow-in-locate (synthetic repos, no competition data)."""
import importlib
import json
import os
import subprocess
import sys
import textwrap

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUB = os.path.join(ROOT, "AgenticSubmission", "v10_edit_rescue")
SCRIPTS = os.path.join(SUB, "skills", "semdag", "scripts")
NAMES = ("wsroot", "cache", "snapshot", "semdag_ir_ast", "retriever", "vulnwalk", "impact", "flow",
         "repo_eval", "fix_edit")

MOD = textwrap.dedent('''\
    class Frame:
        def __init__(self, filename, lineno, name):
            self.filename, self.lineno, self.name = filename, lineno, name


    def extract(stack):
        frames = []
        for summary in stack:
            frame = Frame(
                filename=summary[0],
                lineno=summary[1],
                name=summary[2],
            )
            frames.append(frame)
        return frames


    def split(text, cut):
        pos = 0
        width = 0
        while pos < len(text):
            width += 1
            if width > cut:
                return text[:pos] + " ", text[pos:]
            pos += 1
        return text, ""
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


@pytest.fixture()
def repo(tmp_path):
    """A git repo with the harness baseline tag, like the agent's /workspace."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text(MOD)
    (tmp_path / "pkg" / "__init__.py").write_text("")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "base"],
                ["git", "tag", "_swegemma_baseline"]):
        subprocess.run(cmd, cwd=tmp_path, check=True, env=env)
    return tmp_path


def _read(repo):
    return (repo / "pkg" / "mod.py").read_text()


# ---------------------------------------------------------------- fix_edit
def test_one_line_anchor_shows_and_replaces_the_whole_call(mods, repo):
    fe = mods["fix_edit"]
    # run_24 rich_3486: the model guessed `frame = Frame(frame_summary)`; the real call spans 5 lines
    out = fe.run("pkg/mod.py", "        frame = Frame(summary)", "        frame = Frame(summary, x=1)", repo=str(repo))
    assert out["ok"] is False and _read(repo) == MOD
    cand = out["candidates"][0]
    assert cand["lines"] == "9-13" and "name=summary[2]," in cand["text"] and cand["text"].rstrip().endswith(")")
    # new text 4 spaces too deep (as at rich_3486 step 26): moved left to the block's indentation
    new = ("            frame = Frame(\n                filename=summary[0],\n                lineno=summary[1],\n"
           "                name=summary[2],\n                location=None,\n            )")
    res = fe.run("pkg/mod.py", cand["ref"], new, repo=str(repo))
    assert res["ok"] is True and res["replaced_lines"] == "9-13", res
    compile(_read(repo), "mod.py", "exec")
    assert "\n            location=None,\n        )\n" in _read(repo)


def test_reference_refuses_a_replacement_that_breaks_syntax(mods, repo):
    fe = mods["fix_edit"]
    out = fe.run("pkg/mod.py", "        frame = Frame(summary)", "x", repo=str(repo))
    res = fe.run("pkg/mod.py", out["candidates"][0]["ref"], "            frame = Frame(summary,", repo=str(repo))
    assert res["ok"] is False and "parse" in res["error"] and _read(repo) == MOD


def test_old_string_from_before_an_own_edit_is_reported_stale(mods, repo):
    fe = mods["fix_edit"]
    old = '                return text[:pos] + " ", text[pos:]'
    first = fe.run("pkg/mod.py", old, "                return text[:pos], text[pos:]", repo=str(repo))
    assert first["ok"] is True
    # run_24 rich_3506: the same pre-edit old_string sent again after the edit succeeded
    again = fe.run("pkg/mod.py", old, '                return text[:pos], " " + text[pos:]', repo=str(repo))
    assert again["ok"] is False and again["stale"] is True and "BEFORE an earlier edit" in again["reason"]
    assert "return text[:pos], text[pos:]" in again["candidates"][0]["text"]
    assert again["candidates"][0].get("already_edited") is True


def test_text_from_an_intermediate_edit_is_flagged_through_the_edited_block(mods, repo):
    fe = mods["fix_edit"]
    assert fe.run("pkg/mod.py", '                return text[:pos] + " ", text[pos:]',
                  '                return text[:pos] + "", text[pos:]', repo=str(repo))["ok"]
    assert fe.run("pkg/mod.py", '                return text[:pos] + "", text[pos:]',
                  '                return text[:pos], text[pos:]', repo=str(repo))["ok"]
    # third edit quotes the second state, which is neither the baseline nor the current text
    out = fe.run("pkg/mod.py", '                return text[:pos] + "", text[pos:]',
                 '                return text[:pos], " " + text[pos:]', repo=str(repo))
    assert out["ok"] is False and out["stale"] is True and "earlier edit of yours" in out["reason"]


def test_whitespace_only_difference_still_applies(mods, repo):
    fe = mods["fix_edit"]
    res = fe.run("pkg/mod.py", "pos = 0\nwidth = 0", "pos = 0\nwidth = -1", repo=str(repo))
    assert res["ok"] is True and res["strategy"].startswith("whitespace")
    assert "    width = -1" in _read(repo)


def test_complete_statement_stops_at_closed_brackets(mods):
    fe = mods["fix_edit"]
    lines = MOD.split("\n")
    assert fe.complete_statement(lines, 8, 9) == 13          # `frame = Frame(` .. `)`
    assert fe.complete_statement(lines, 14, 15) == 15        # already complete
    assert fe._open_brackets('x = f("(", [1,') == 2          # bracket inside a string is ignored


# ---------------------------------------------------------------- locate carries flow
def test_locate_includes_flow_for_top_sites_within_budget(mods, repo):
    re_ = mods["repo_eval"]
    opt = re_.parse_args(["split returns the wrong text when width passes cut in the while loop of split"])
    opt["repo"], opt["container"] = str(repo), "v10flow"
    out = re_.locate(opt)
    assert out["mode"] == "locate" and out["top_edit_sites"][0]["qualname"] == "split"
    flows = {f["site"]: f for f in out["flow"]}
    assert "pkg/mod.py::split" in flows
    loop = flows["pkg/mod.py::split"]["loops"][0]
    assert loop["kind"] == "while" and {"pos", "width"} <= set(loop["carried"])
    assert len(json.dumps(out["flow"], separators=(",", ":"))) <= re_.FLOW_IN_LOCATE
    assert len(re_._dumps(out)) <= re_.LOCATE_BUDGET + re_.FLOW_IN_LOCATE + 10 < 5000


def test_trim_flow_respects_the_budget(mods):
    re_ = mods["repo_eval"]
    big = [{"site": f"S{i}", "loops": [{"at": f"{j}-{j + 9}", "kind": "for", "carried": ["a", "b", "c"],
                                         "calls": ["f", "g", "h"]} for j in range(6)],
            "callers": [f"pkg/m.py:{k} caller_{k}" for k in range(3)]} for i in range(2)]
    for budget in (1300, 400, 120, 10):
        out = re_.trim_flow(json.loads(json.dumps(big)), budget)
        assert len(re_._dumps(out)) <= budget or out == []


# ---------------------------------------------------------------- wiring
def test_editor_sub_agent_has_the_skill_and_a_fixed_reply_shape():
    cfg = yaml.safe_load(open(os.path.join(SUB, "sub_agents", "code_editor.yaml")).read().replace("!include", ""))
    assert cfg["skills"] == ["skills/semdag"]
    assert "edit_file" not in cfg["tools"]        # edits go through fix_edit by line range
    editor = open(os.path.join(SUB, "prompts", "editor.md")).read()
    assert "EDIT_OK" in editor and "EDIT_FAILED" in editor and "fix_edit.py" in editor
    assert "EOF" not in editor


def test_system_prompt_routes_failed_edits_to_fix_edit():
    system = open(os.path.join(SUB, "prompts", "system.md")).read()
    assert "your very next call is `run_skill_script`" in system and "Never resend a failed `edit_file`" in system
    assert "never from a read made before that edit" in system
    assert "Viewer -> Editor" not in system and "last resort" in system
    for principle in ("Think first", "Simplicity", "Surgical", "Goal-driven"):
        assert principle in system


def test_v10_validates_as_a_submission():
    adk = pytest.importorskip("adk_submission")
    from pathlib import Path
    from swegemma.config import build_submission_limits
    adk.validate_directory(Path(SUB), limits=build_submission_limits()[0])


def test_doubled_backslashes_in_old_string_are_collapsed(mods, tmp_path):
    # run_25 httpx_3672: the source says b"\r\n"; the model's old_string said b"\\r\\n"
    fe = mods["fix_edit"]
    (tmp_path / "p.py").write_text('def f(parser):\n    return parser.read_until(b"\\r\\n", max_size=4)\n')
    old = '    return parser.read_until(b"\\\\r\\\\n", max_size=4)'
    new = '    return parser.read_until(b"\\\\r\\\\n", max_size=8)'
    res = fe.run("p.py", old, new, repo=str(tmp_path))
    assert res["ok"] is True and res["strategy"] == "exact+cleaned", res
    assert (tmp_path / "p.py").read_text().endswith('read_until(b"\\r\\n", max_size=8)\n')


def test_read_file_json_tail_pasted_into_old_string_is_stripped(mods, tmp_path):
    # run_25 httpx_3672: old_string's last line ended with the read_file result's own metadata
    fe = mods["fix_edit"]
    (tmp_path / "p.py").write_text("def f():\n    x = 1\n    return 'done'\n")
    old = "    x = 1\n    return 'done'\", \"start_line\": 1, \"end_line\": 3, \"is_truncated\": false"
    res = fe.run("p.py", old, "    x = 2\n    return 'done'", repo=str(tmp_path))
    assert res["ok"] is True and res["strategy"] == "exact+cleaned", res
    assert (tmp_path / "p.py").read_text() == "def f():\n    x = 2\n    return 'done'\n"
