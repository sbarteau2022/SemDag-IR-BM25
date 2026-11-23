"""Find the repository under test, in either harness backend.

The harness has two sandbox backends. With docker the repository is at /workspace. With the
subprocess backend (the one the official Kaggle notebook uses) it is at
<tmp>/swegemma_sandbox_<id>/workspace, and the harness only rewrites the text "/workspace" inside
command strings: a path written inside a script is not rewritten, and /workspace does not exist.
In both backends the harness starts a skill script from a wrapper file it writes into the
repository root, <root>/.adk_exec_<hex>.py, and then changes directory to a temporary folder. So
the wrapper's own location is the one reliable anchor.
"""
import os
import sys
import tempfile
import re

LITERAL = "/workspace"


def _wrapper_dir():
    frame = sys._getframe()
    found = None
    while frame is not None:
        name = frame.f_code.co_filename
        base = os.path.basename(name)
        if base.startswith(".adk_exec_") and base.endswith(".py"):
            found = os.path.dirname(os.path.abspath(name))
        frame = frame.f_back
    return found


def workspace_root(explicit=None):
    """Directory of the repository under test. `explicit` is honoured unless it is the literal
    /workspace, which means "the workspace" and is resolved like the default."""
    if explicit and explicit.rstrip("/") != LITERAL:
        if explicit.startswith("/tmp/ws_"):
            if not re.fullmatch(r"/tmp/ws_[A-Za-z0-9_-]{1,64}", explicit):
                raise ValueError("invalid sandbox slot path")
            explicit = os.path.join(tempfile.gettempdir(), os.path.basename(explicit))
        if not os.path.isdir(explicit):
            raise ValueError("explicit workspace does not exist")
        return os.path.abspath(explicit)
    env = os.environ.get("SEMDAG_REPO")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    wrapper = _wrapper_dir()
    if wrapper and os.path.isdir(wrapper):
        return wrapper
    for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep):
        if entry and os.path.isdir(os.path.join(entry, ".git")):
            return os.path.abspath(entry)
    if os.path.isdir(LITERAL):
        return LITERAL
    return os.getcwd()


def cache_root():
    """Cache directory outside the repository. TMPDIR is per-sandbox in the subprocess backend
    and /tmp in docker, so the cache never enters the patch and never mixes two tasks."""
    return os.environ.get("SEMDAG_CACHE") or os.path.join(tempfile.gettempdir(), "semdag-cache")
