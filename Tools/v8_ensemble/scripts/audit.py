"""audit: deterministic sign-off for the brigade loop. One compact JSON verdict on stdout.

args: []                          audit the current change
      ["--repro", "<shell cmd>"]  also run the plan's repro command (must exit 0 to be green)
      ["<shell cmd>"]             same, without the flag

Checks, in order (no model reasoning; never raises):
  1. patch     - what the harness patch will contain (repo_eval verify): empty? scratch files?
  2. breakage  - syntax errors, undefined names, removed-but-still-used, signature breaks
  3. tests     - the nearest test files, run once, time-boxed. Counts are checked, not just the
                 exit code: 0 collected tests is "unverified", never green. A red is classified
                 as an assertion failure or a collection/import error.
  4. repro     - the plan's repro command, if given
  5. strikes   - two-strike rule. Each audit records a signature of the diff. Re-submitting a
                 diff that was already judged red is an "identical retry". After the second red
                 verdict the loop must stop: submit the best unbroken diff.

decision: "submit"      everything green
          "submit_best" second red verdict, but the diff is non-empty and unbroken
          "revise"      fix the listed reasons with a materially different approach
"""
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wsroot  # noqa: E402
os.environ["SEMDAG_CACHE"] = wsroot.cache_root()
import cache  # noqa: E402
import impact  # noqa: E402
import meta  # noqa: E402
import repo_eval  # noqa: E402

BUDGET = 2600
TEST_TIMEOUT = 90
REPRO_TIMEOUT = 30
MAX_TEST_FILES = 3
MAX_STRIKES = 2
# The harness excludes these from the patch (.git/info/exclude), so they never count.
HARNESS_IGNORED = re.compile(r"(^|/)__pycache__/|\.pyc$|(^|/)\.pytest_cache/|\.egg-info(/|$)|"
                             r"^(build|dist)/|(^|/)\.coverage$")
SCRATCH = re.compile(r"(^|/)(tmp|scratch)/|(^|/)(repro|scratch|debug|tmp)[^/]*\.py$|\.(log|txt|out)$")


def _dumps(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def parse(argv):
    import ensemble  # local import: undo nested / quoted args (run_21)
    args = ensemble.normalize(argv)
    wt = None
    for flag in ("--wt", "--dir"):
        if flag in args:
            i = args.index(flag)
            val = args[i + 1] if i + 1 < len(args) else ""
            m = re.search(r"(\d+)\s*$", val)
            wt = int(m.group(1)) if m else None
            del args[i:i + 2]
    repro = None
    if "--repro" in args:
        i = args.index("--repro")
        repro = args[i + 1] if i + 1 < len(args) else None
    elif len(args) == 1 and args[0].strip() and not args[0].startswith("--"):
        repro = args[0]
    return {"repro": (repro or "").strip() or None, "wt": wt}


def rewrite_paths(cmd, repo):
    """The subprocess backend rewrites /workspace and /tmp only inside run_command strings, so a
    command copied from the plan must be mapped the same way before this script runs it."""
    if os.path.isdir(wsroot.LITERAL) and os.path.abspath(repo) == wsroot.LITERAL:
        return cmd
    cmd = cmd.replace(wsroot.LITERAL, repo)
    sandbox_tmp = os.path.join(os.path.dirname(repo), "tmp")
    if os.path.isdir(sandbox_tmp):
        cmd = re.sub(r"(?<![\w.])/tmp/", sandbox_tmp + "/", cmd)
    return cmd


def run_repro(cmd, repo, wt=False, main_root=None):
    # Paths in the command are written against the main workspace (/workspace/.git/wt_k, /tmp),
    # so they are mapped with the main root, never with the worktree directory.
    try:
        p = subprocess.run(["bash", "-c", rewrite_paths(cmd, main_root or repo)], cwd=repo,
                           capture_output=True,
                           text=True, timeout=REPRO_TIMEOUT, env=meta.run_env(repo if wt else None))
        out = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
        return {"cmd": cmd[:200], "rc": p.returncode, "green": p.returncode == 0,
                "tail": "\n".join(out[-6:])[-500:]}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd[:200], "rc": None, "green": False, "tail": "timeout"}
    except OSError as ex:
        return {"cmd": cmd[:200], "rc": None, "green": False, "tail": str(ex)[:200]}


def diff_signature(repo):
    ref = impact.baseline_ref(repo) or "HEAD"
    try:
        p = subprocess.run(["git", "diff", "--no-color", ref], cwd=repo, capture_output=True,
                           text=True, timeout=30)
        text = p.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        text = ""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def test_files(cid, verify_out):
    files = []
    try:
        files += cache.read(cid, "meta.json").get("tests_near_sites") or []
    except (OSError, ValueError):
        pass
    for t in verify_out.get("tests_to_run") or []:
        f = t.get("file") if isinstance(t, dict) else t
        if f:
            files.append(f)
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out[:MAX_TEST_FILES]


def audit(argv):
    opt = parse(argv)
    ropt = repo_eval.parse_args(["--verify"])
    main_cid, main_root = ropt["container"], ropt["repo"]
    if opt["wt"]:
        # A solver worktree: same checks, run inside <workspace>/.git/wt_<k>, own cache namespace.
        wt_dir = os.path.join(ropt["repo"], ".git", f"wt_{opt['wt']}")
        if not os.path.isdir(wt_dir):
            return {"mode": "audit", "decision": "revise",
                    "reasons": [f"worktree .git/wt_{opt['wt']} does not exist: call fork.py first"]}
        ropt = repo_eval.parse_args(["--verify", "--repo", wt_dir,
                                     "--container", f"{main_cid}_wt{opt['wt']}"])
    repo, cid = ropt["repo"], ropt["container"]
    v = repo_eval.verify(ropt)
    reasons, gaps = [], []
    if v.get("error"):
        reasons.append(f"verify failed: {v['error']}")
    patch = v.get("patch") or {}
    files = [f for f in patch.get("files") or [] if not HARNESS_IGNORED.search(f)]
    new_files = [f for f in patch.get("new_files") or [] if not HARNESS_IGNORED.search(f)]
    scratch = [f for f in new_files if SCRATCH.search(f)]
    if not files:
        reasons.append("patch is empty: no source file was changed")
    if scratch:
        reasons.append("scratch files inside the repository would enter the patch: "
                       + ", ".join(scratch[:4]) + " (create repro files in /tmp via run_command)")
    breaks = {k: v.get(k) for k in ("syntax_errors", "undefined_names", "removed_still_used",
                                    "signature_breaks") if v.get(k)}
    for k, items in breaks.items():
        reasons.append(f"{k}: " + _dumps(items)[:220])

    tests = None
    tfiles = test_files(main_cid, v)
    if meta.readiness()["pytest"] and tfiles:
        tests = meta.run_pytest(repo, tfiles, TEST_TIMEOUT)
        rr = tests["red_reason"]
        if tests.get("env_broken") or rr in ("collection_error", "pytest_unavailable"):
            gaps.append(f"tests unverifiable here ({tests.get('env_broken') or rr})")
        elif rr == "no_tests_collected":
            gaps.append("0 tests collected: the test run proves nothing")
        elif rr:
            reasons.append(f"tests red ({rr}, {tests['failed']} failed, {tests['errors']} errors)")
    else:
        gaps.append("no runnable tests near the change")

    repro = run_repro(opt["repro"], repo, bool(opt["wt"]), main_root) if opt["repro"] else None
    if repro and not repro["green"]:
        reasons.append(f"repro still fails (rc={repro['rc']})")
    if not repro:
        gaps.append("no repro command was given")

    # Tests that were already red before any edit, and are no worse now, do not block a change
    # whose repro is green: report them as a gap instead.
    if tests is not None and tests["red_reason"] in ("assertion", "test_failure") \
            and repro and repro["green"]:
        try:
            base = cache.read(main_cid, "meta.json").get("baseline_tests") or {}
        except (OSError, ValueError):
            base = {}
        if base.get("red_reason") in ("assertion", "test_failure") \
                and tests["failed"] <= base.get("failed", 0):
            reasons = [r for r in reasons if not r.startswith("tests red")]
            gaps.append(f"{tests['failed']} test failure(s) were already red before the edit")

    verified = (tests is not None and tests["red_reason"] is None) or bool(repro and repro["green"])
    if not reasons and not verified:
        reasons.append("nothing verified the change: give a repro command or runnable tests")
    green = not reasons

    sig = diff_signature(repo)
    try:
        strikes = cache.read(cid, "strikes.json")
    except (OSError, ValueError):
        strikes = []
    identical = any(s["sig"] == sig and not s["green"] for s in strikes)
    strikes.append({"sig": sig, "green": green, "reasons": reasons[:3]})
    try:
        cache.write(cid, "strikes.json", strikes)
    except OSError:
        pass
    reds = sum(1 for s in strikes if not s["green"])
    unbroken = bool(files) and not breaks and not scratch

    if green:
        decision = "submit"
    elif reds >= MAX_STRIKES and unbroken:
        decision = "submit_best"
    else:
        decision = "revise"
    if identical:
        reasons.insert(0, "identical retry: this exact diff was already judged red; change approach")

    out = {"mode": "audit", "wt": opt["wt"], "decision": decision, "green": green, "strike": reds,
           "reasons": reasons, "gaps": gaps, "patch_files": files[:6]}
    if tests is not None:
        out["tests"] = {k: tests[k] for k in ("cmd", "collected", "passed", "failed", "errors",
                                              "red_reason", "tail")}
    if repro:
        out["repro"] = repro
    out["next"] = {"submit": "Call submit_patch now.",
                   "submit_best": "Strike limit reached: call submit_patch now with this diff.",
                   "revise": "Do not submit. Report the reasons; the planner must change approach."
                   }[decision]
    try:
        cache.write(cid, "audit.json", dict(out, repro_cmd=opt["repro"]))
    except OSError:
        pass
    return out


def _trim(out):
    while len(_dumps(out)) > BUDGET:
        t = out.get("tests") or {}
        if len(t.get("tail", "")) > 200:
            t["tail"] = t["tail"][-200:]
        elif out.get("repro") and len(out["repro"].get("tail", "")) > 150:
            out["repro"]["tail"] = out["repro"]["tail"][-150:]
        elif len(out["reasons"]) > 3:
            out["reasons"] = out["reasons"][:3]
        else:
            break
    return out


def main(argv=None):
    try:
        out = _trim(audit(sys.argv[1:] if argv is None else argv))
    except Exception as ex:  # never hand the model a traceback
        out = {"mode": "audit", "decision": "revise", "error": f"{type(ex).__name__}: {ex}"[:300]}
    print(_dumps(out))
    return out


if __name__ == "__main__":
    main()
