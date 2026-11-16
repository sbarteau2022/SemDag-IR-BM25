"""Phase 4b: the repo_eval --verify gate, measured without a model call.

For each public task: extract the full snapshot, commit it, run repo_eval once
(the frozen baseline, exactly the coder's first command), then for each
candidate patch apply it, run `repo_eval.py t . --verify` (no --test: syntax
and change detection only), record the verdict, and reset the tree.

Candidates: the gold `patch` (all 129 tasks; a correct gate must say clean),
and the Phase 2 E4B one-turn diffs (Rich, arms O and C, copies skipped).
`test_patch` and `hints_text` are never read.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = Path(os.environ.get("P4_DATA", ROOT / "DataSets/public/data"))
# Default: the repaired production gate. Set P4_SEMDAG=<phase4_semdag/legacy_semdag> for the as-shipped gate.
REPO_EVAL = Path(os.environ.get("P4_SEMDAG", ROOT / "AgenticSubmission/v4_semdag/skills/semdag/scripts")) / "repo_eval.py"
COMPL = Path(os.environ.get("P4_COMPLETIONS", HERE.parent / "phase2/out/completions"))
OUT = Path(os.environ.get("P4_OUT", HERE / "out"))
os.environ.setdefault("P4_SCRATCH", tempfile.gettempdir())


def sh(cmd, cwd, env=None, inp=None, timeout=300):
    p = subprocess.run(cmd, cwd=cwd, env=env, input=inp, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def run_task(task):
    iid = task["instance_id"]
    tmp = tempfile.mkdtemp(prefix=f"p4v_{iid}_", dir=os.environ["P4_SCRATCH"])
    repo = os.path.join(tmp, "repo"); os.makedirs(repo)
    env = dict(os.environ, SEMDAG_CACHE=os.path.join(tmp, "_cache"), PYTHONDONTWRITEBYTECODE="1")
    git = ["git", "-c", "user.name=p4", "-c", "user.email=p4@example.invalid"]
    row = {"instance_id": iid, "repo": task["repo"], "candidates": []}
    try:
        sh(["tar", "-xzf", str(DATA / "snapshots" / f"{iid}.tgz"), "-C", repo], tmp)
        if not os.path.isdir(os.path.join(repo, ".git")):
            sh(git + ["init", "-q"], repo)
        sh(git + ["add", "-A"], repo); sh(git + ["commit", "-qm", "p4base", "--allow-empty"], repo)
        rc, out, err = sh([sys.executable, str(REPO_EVAL), "t", ".",
                           "--problem", task["problem_statement"]], repo, env)
        try:
            base = json.loads(out)
            row["baseline"] = {"parity_ok": base["parity_ok"], "top_edit_sites": len(base["top_edit_sites"])}
        except Exception:
            row["baseline"] = {"error": (err or out)[-300:]}

        cands = [("gold", task["patch"])]
        for arm in ("O", "C"):
            fp = COMPL / f"{iid}_{arm}.json"
            if fp.exists():
                d = json.loads(fp.read_text())
                if d.get("copied_from_identical_prompt") or d.get("no_diff") or not d.get("diff"):
                    row["candidates"].append({"name": f"e4b_{arm}", "skipped":
                        "copy" if d.get("copied_from_identical_prompt") else "no_diff"})
                    continue
                cands.append((f"e4b_{arm}", d["diff"]))
        for name, diff in cands:
            if not diff.endswith("\n"):
                diff += "\n"
            c = {"name": name}
            rc, _, err = sh(["git", "apply", "--whitespace=nowarn", "-"], repo, inp=diff)
            c["applied"] = "git" if rc == 0 else None
            if rc != 0:
                rc2, _, _ = sh(["patch", "-p1", "--fuzz=3", "--no-backup-if-mismatch", "-s", "-f"], repo, inp=diff)
                if rc2 == 0:
                    c["applied"] = "patch_fuzz"
                else:
                    c["apply_error"] = err.strip().splitlines()[:2]
            if c["applied"]:
                rc, out, err = sh([sys.executable, str(REPO_EVAL), "t", ".", "--verify"], repo, env)
                try:
                    v = json.loads(out)
                    c.update({"clean": v["clean"], "changed": len(v["changed"]), "added": len(v["added"]),
                              "syntax_errors": v["syntax_errors"]})
                except Exception:
                    c["verify_error"] = (err or out)[-300:]
            row["candidates"].append(c)
            sh(["git", "reset", "--hard", "-q"], repo); sh(["git", "clean", "-fdq"], repo)
        return row
    except Exception as ex:
        row["error"] = repr(ex)
        return row
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in open(DATA / "tasks.jsonl")]
    for t in tasks:
        t.pop("hints_text", None); t.pop("test_patch", None)
    if len(sys.argv) > 1:
        tasks = [t for t in tasks if t["instance_id"] in sys.argv[1:]]
    with Pool(int(os.environ.get("P4_PROCS", "4"))) as pool:
        rows = pool.map(run_task, tasks, chunksize=1)
    with open(OUT / "verify_per_task.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    s = {"tasks": len(rows), "errors": [r["instance_id"] for r in rows if "error" in r],
         "baseline_parity_ok": sum(1 for r in rows if r.get("baseline", {}).get("parity_ok")),
         "baseline_with_edit_sites": sum(1 for r in rows if r.get("baseline", {}).get("top_edit_sites"))}
    for name in ("gold", "e4b_O", "e4b_C"):
        cs = [c for r in rows for c in r["candidates"] if c["name"] == name]
        ap = [c for c in cs if c.get("applied")]
        s[name] = {"n": len(cs), "skipped": sum(1 for c in cs if c.get("skipped")),
                   "applied": len(ap), "applied_by_fuzz": sum(1 for c in ap if c["applied"] == "patch_fuzz"),
                   "clean": sum(1 for c in ap if c.get("clean")),
                   "syntax_rejected": sum(1 for c in ap if c.get("syntax_errors")),
                   "verify_error": sum(1 for c in ap if "verify_error" in c)}
    json.dump(s, open(OUT / "verify_summary.json", "w"), indent=1, sort_keys=True)
    print(json.dumps(s, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
