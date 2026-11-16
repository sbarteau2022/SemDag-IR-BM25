#!/usr/bin/env python3
"""Independent gates for the Phase 3 role-silo probe. Run by the validator, not by a parcel's author.

  python3 validate.py p0|p1|p2|p3|p4|p5 [--out DIR]
  python3 validate.py selftest          # synthetic data; exercises p4 and p5 code paths

Exit code 0 only if every check of the gate passes. Needs numpy only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROLES = ["LOC", "ANA", "IMP", "VER"]
CHANCE = {"LOC": 1 / 8, "ANA": 0.5, "VER": 0.5}
BANDS = {"early": list(range(6, 12)), "middle": list(range(18, 24)), "late": list(range(30, 36))}
RAND_SEEDS = [0, 1, 2, 3, 4]
N_BOOT, BOOT_SEED, CHAR_CAP = 4000, 0, 5000


class Gate:
    def __init__(self, name: str):
        self.name, self.fails, self.notes = name, [], []

    def check(self, ok: bool, msg: str) -> None:
        print(("  ok   " if ok else "  FAIL ") + msg)
        if not ok:
            self.fails.append(msg)

    def note(self, msg: str) -> None:
        print("  note " + msg)
        self.notes.append(msg)

    def done(self, out: Path) -> int:
        status = "pass" if not self.fails else "fail"
        print(f"[{self.name}] {status.upper()} ({len(self.fails)} failed)")
        if out.exists():
            with (out / "validator_receipts.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"gate": self.name, "status": status, "fails": self.fails, "notes": self.notes}) + "\n")
        return 0 if not self.fails else 1


def jl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def conditions() -> list[str]:
    return ["base"] + [f"role:{r}" for r in ROLES] + [f"tmpl:{r}" for r in ROLES] + [f"rand:{s}" for s in RAND_SEEDS]


# ---------------------------------------------------------------- P1
def p1(out: Path) -> int:
    g = Gate("P1")
    rows, skips, man = jl(out / "prompts.jsonl"), jl(out / "skips.jsonl"), json.loads((out / "split.json").read_text())
    tasks = {t["instance_id"]: t for t in jl(ROOT / "DataSets/public/data/tasks.jsonl")}
    split = man["split"]
    g.check(man["prompts_sha256"] == sha_file(out / "prompts.jsonl"), "prompts.jsonl digest matches split.json")
    g.check(man["tasks_sha256"] == sha_file(ROOT / "DataSets/public/data/tasks.jsonl"), "tasks.jsonl digest matches")
    g.check(man["builder_sha256"] == sha_file(HERE / "build_dataset.py"), "builder digest matches (dataset built by the current builder)")
    g.check(set(split) == set(tasks), "every task has a split")
    by = Counter(split.values())
    g.check(by == Counter(fit=47, dev=20, heldout=62), f"split sizes fit/dev/heldout = 47/20/62 (got {dict(by)})")
    repos = defaultdict(set)
    for i, s in split.items():
        repos["heldout" if s == "heldout" else "fitdev"].add(tasks[i]["repo"])
    g.check(not (repos["heldout"] & repos["fitdev"]), "held-out repositories are disjoint from fit/dev repositories")
    ids = [r["prompt_id"] for r in rows]
    g.check(len(ids) == len(set(ids)), "prompt ids unique")
    g.check(all(r["split"] == split[r["instance_id"]] for r in rows), "row split equals manifest split")
    g.check(all((r["template"], r["kind"]) in {("T1", "task"), ("T1", "tmpl")} for r in rows if r["split"] == "fit"), "fit rows are T1 only")
    g.check(all((r["template"], r["kind"]) == ("T2", "task") for r in rows if r["split"] != "fit"), "dev and held-out rows are T2 task prompts only")
    fit_task = {r["item_id"] for r in rows if r["split"] == "fit" and r["kind"] == "task"}
    fit_tmpl = {r["item_id"] for r in rows if r["kind"] == "tmpl"}
    g.check(fit_task == fit_tmpl, "every fit item has exactly one template-only twin")
    g.check(max(r["n_chars"] for r in rows) <= CHAR_CAP, f"all prompts within {CHAR_CAP} chars (max {max(r['n_chars'] for r in rows)})")
    for role in ("ANA", "VER"):
        for sp in ("fit", "dev", "heldout"):
            c = Counter(r["gold"] for r in rows if r["role"] == role and r["split"] == sp and r["kind"] == "task")
            g.check(c[" Yes"] == c[" No"] and c[" Yes"] > 0, f"{role}/{sp} balanced Yes/No ({c[' Yes']}/{c[' No']})")
    c = Counter(r["gold"] for r in rows if r["role"] == "LOC" and r["kind"] == "task")
    n = sum(c.values())
    chi2 = sum((c[" " + L] - n / 8) ** 2 / (n / 8) for L in "ABCDEFGH")
    g.check(chi2 < 18.48, f"LOC gold letter spread consistent with uniform (chi2={chi2:.2f}, df=7, 1% critical 18.48)")
    g.check(all(r["gold"] in r["candidates"] for r in rows if r["candidates"]), "gold is one of the candidates")
    # leakage: long test_patch / hints lines must not appear unless also in the issue or the gold patch
    leaks = 0
    for r in rows:
        t = tasks[r["instance_id"]]
        allowed = t["problem_statement"] + "\n" + t["patch"]
        if r.get("neg_source"):
            allowed += tasks[r["neg_source"]]["patch"]
        for src in (t.get("test_patch") or "", t.get("hints_text") or ""):
            for line in src.split("\n"):
                s = line.lstrip("+- ").strip()
                if len(s) >= 40 and s in r["user_text"] and s not in allowed:
                    leaks += 1
    g.check(leaks == 0, f"no test_patch or hints_text line (>=40 chars) appears in any prompt ({leaks} found)")
    g.check(all(tasks[r["neg_source"]]["repo"] == r["repo"] and r["neg_source"] != r["instance_id"] for r in rows if r.get("neg_source")), "VER negatives come from another task in the same repo")
    have = {(r["instance_id"], r["role"]) for r in rows} | {(s["instance_id"], s["role"]) for s in skips}
    g.check(have == {(i, ro) for i in tasks for ro in ROLES}, "every task x role is either probed or listed in skips.jsonl")
    echo = sum(1 for r in rows if r["role"] == "IMP" and r["kind"] == "task" and r["gold"].strip() in r["user_text"])
    g.note(f"IMP items whose gold line text already occurs in the prompt: {echo} of {sum(1 for r in rows if r['role']=='IMP' and r['kind']=='task')} (report in the paper)")
    g.note("held-out usable items: " + ", ".join(f"{ro}={sum(1 for r in rows if r['split']=='heldout' and r['role']==ro)}" for ro in ROLES))
    return g.done(out)


# ---------------------------------------------------------------- score files
def check_scores(g: Gate, rows: list[dict], prompts: dict[str, dict], want_ids: set[str], want_conds: list[str], label: str) -> None:
    cells = Counter((r["prompt_id"], r["condition"]) for r in rows)
    g.check(all(v == 1 for v in cells.values()), f"{label}: no duplicate (prompt, condition) cells")
    missing = [(p, c) for p in want_ids for c in want_conds if (p, c) not in cells]
    g.check(not missing, f"{label}: every expected cell present ({len(missing)} missing of {len(want_ids) * len(want_conds)})")
    extra = {r["prompt_id"] for r in rows} - want_ids
    g.check(not extra, f"{label}: no prompt outside the expected split ({len(extra)} extra)")
    bad = 0
    for r in rows:
        p = prompts.get(r["prompt_id"])
        if p is None or not isinstance(r["score"], (int, float)) or not math.isfinite(r["score"]):
            bad += 1
            continue
        if p["candidates"]:
            lp = r.get("cand_logprobs")
            if not lp or len(lp) != len(p["candidates"]):
                bad += 1
                continue
            a = np.asarray(lp, dtype=np.float64)
            want = a[p["candidates"].index(p["gold"])] - (a.max() + math.log(np.exp(a - a.max()).sum()))
            if abs(want - r["score"]) > 1e-5:
                bad += 1
    g.check(bad == 0, f"{label}: scores finite and equal to the normalised gold log-prob recomputed from cand_logprobs ({bad} bad rows)")
    abl = [r for r in rows if r["condition"] != "base"]
    g.check(all(isinstance(r.get("removed_energy"), (int, float)) and 0 <= r["removed_energy"] <= 1 for r in abl), f"{label}: removed_energy logged in [0,1] for every ablated row")


def load_prompts(out: Path) -> dict[str, dict]:
    return {r["prompt_id"]: r for r in jl(out / "prompts.jsonl")}


def p0(out: Path) -> int:
    g = Gate("P0")
    d = json.loads((out / "p0_probe.json").read_text())
    g.check(d.get("n_layers") == 42 and d.get("d_model") == 2560, f"42 blocks, width 2560 (got {d.get('n_layers')}, {d.get('d_model')})")
    g.check(d.get("noop_max_abs_logit_diff", 1) <= 1e-4, "no-op hook leaves logits unchanged (<=1e-4)")
    g.check(d.get("rerun_max_abs_logit_diff", 1) <= 1e-6, "two identical runs give identical logits (<=1e-6)")
    g.check(d.get("ablation_max_abs_logit_diff", 0) > 1e-3, "a real ablation changes logits (>1e-3)")
    g.check(d.get("thinking_disabled") is True, "thinking disabled in the chat template")
    tok = d.get("candidate_token_ids", {})
    need = [" " + c for c in "ABCDEFGH"] + [" Yes", " No"]
    g.check(all(isinstance(tok.get(c), int) for c in need) and len({tok.get(c) for c in need}) == len(need), "each candidate string is one distinct token after the 'Answer:' prefix")
    g.check(bool(d.get("model_sha256")) and bool(d.get("tokenizer_sha256")), "model and tokenizer digests recorded")
    return g.done(out)


def p2(out: Path) -> int:
    g = Gate("P2")
    prompts = load_prompts(out)
    rows = jl(out / "base_scores.jsonl")
    check_scores(g, rows, prompts, set(prompts), ["base"], "base_scores")
    for name, sel in (("acts_fit.npy", lambda p: p["split"] == "fit"), ("acts_dev.npy", lambda p: p["split"] == "dev")):
        a = np.load(out / name, mmap_mode="r")
        idx = json.loads((out / name.replace(".npy", "_ids.json")).read_text())
        want = {i for i, p in prompts.items() if sel(p)}
        g.check(a.shape == (len(idx), 42, 2560) and set(idx) == want, f"{name}: shape [n,42,2560] and ids equal the split ({a.shape}, {len(idx)} ids)")
        g.check(bool(np.isfinite(a[: min(50, len(idx))]).all()), f"{name}: finite (first rows sampled)")
    return g.done(out)


def p3(out: Path) -> int:
    g = Gate("P3")
    prompts = load_prompts(out)
    z = np.load(out / "subspaces.npz")
    g.check(z["mu"].shape == (42, 2560), "mu has shape [42,2560]")
    names = [f"role_{r}" for r in ROLES] + [f"tmpl_{r}" for r in ROLES] + [f"rand_{s}" for s in RAND_SEEDS]
    worst = 0.0
    for nme in names:
        if nme not in z:
            g.check(False, f"subspace {nme} present")
            continue
        u = z[nme]  # [42, 2560, k]
        ok = u.shape[:2] == (42, 2560)
        g.check(ok, f"{nme} has shape [42,2560,k] (got {u.shape})")
        if ok:
            for layer in sorted(set(sum(BANDS.values(), []))):
                worst = max(worst, float(np.abs(u[layer].T.astype(np.float64) @ u[layer] - np.eye(u.shape[2])).max()))
    g.check(worst <= 1e-5, f"all subspaces orthonormal at band layers (worst deviation {worst:.2e})")
    fit_ids = set(json.loads((out / "fit_ids.json").read_text()))
    g.check(fit_ids <= {i for i, p in prompts.items() if p["split"] == "fit"}, "subspaces fitted on fit-split prompts only")
    bc = json.loads((out / "band_choice.json").read_text())
    g.check(bc.get("band") in BANDS and bc.get("k") == 4, f"primary band is a pre-registered candidate at k=4 (got {bc.get('band')}, k={bc.get('k')})")
    dev_ids = {i for i, p in prompts.items() if p["split"] == "dev"}
    rows = jl(out / "dev_scores.jsonl")
    for band in BANDS:
        check_scores(g, [r for r in rows if r["band"] == band or r["condition"] == "base"], prompts, dev_ids, ["base"] + [f"role:{r}" for r in ROLES], f"dev_scores[{band}]")
    si = {b: stats([r for r in rows if r["band"] == b or r["condition"] == "base"], prompts, use_rand=False, boot=0)["SI"] for b in BANDS}
    g.check(max(si, key=si.get) == bc.get("band"), f"chosen band has the largest dev silo index (recomputed: { {k: round(v, 4) for k, v in si.items()} })")
    g.check(not (out / "heldout_scores.jsonl").exists() or (out / "heldout_scores.jsonl").stat().st_mtime >= (out / "band_choice.json").stat().st_mtime, "band was chosen before held-out scores were written")
    return g.done(out)


def p4(out: Path) -> int:
    g = Gate("P4")
    prompts = load_prompts(out)
    rows = jl(out / "heldout_scores.jsonl")
    band = json.loads((out / "band_choice.json").read_text())["band"]
    prim = [r for r in rows if r["condition"] == "base" or (r["band"] == band and r["k"] == 4)]
    check_scores(g, prim, prompts, {i for i, p in prompts.items() if p["split"] == "heldout"}, conditions(), "heldout_scores[primary]")
    g.check(len({r.get("run_id") for r in prim}) == 1, "primary cells come from a single run_id")
    return g.done(out)


# ---------------------------------------------------------------- statistics
def stats(rows: list[dict], prompts: dict[str, dict], use_rand: bool = True, boot: int = N_BOOT) -> dict:
    """Silo index and matrix from per-prompt scores. Bootstrap resamples tasks."""
    score = defaultdict(dict)
    for r in rows:
        score[r["condition"]][r["prompt_id"]] = r["score"]
    base = score["base"]
    pids = sorted(p for p in base if all(p in score[c] for c in score))
    tasks = sorted({prompts[p]["instance_id"] for p in pids})
    t_ix = {t: i for i, t in enumerate(tasks)}
    conds = [c for c in conditions() if c != "base" and c in score]
    T, R, C = len(tasks), len(ROLES), len(conds)
    dsum, cnt, acc = np.zeros((T, R, C)), np.zeros((T, R)), np.zeros((T, R))
    sd = {}
    for ri, role in enumerate(ROLES):
        ps = [p for p in pids if prompts[p]["role"] == role]
        sd[role] = float(np.std([base[p] for p in ps], ddof=1)) if len(ps) > 1 else float("nan")
        for p in ps:
            ti = t_ix[prompts[p]["instance_id"]]
            cnt[ti, ri] += 1
            acc[ti, ri] += float(base[p] > math.log(CHANCE[role])) if role in CHANCE else 0.0
            for ci, c in enumerate(conds):
                dsum[ti, ri, ci] += base[p] - score[c][p]
    sdv = np.array([sd[r] for r in ROLES])

    def derive(w: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n = np.maximum(w @ cnt, 1e-12)
        D = (np.tensordot(w, dsum, axes=1) / n[:, None]) / sdv[:, None]  # [target role, condition]
        rand = D[:, [i for i, c in enumerate(conds) if c.startswith("rand:")]].mean(axis=1) if use_rand and any(c.startswith("rand:") for c in conds) else np.zeros(R)
        N = np.stack([D[:, conds.index(f"role:{r}")] for r in ROLES], axis=1) - rand[:, None]  # N[s, r] = N(s <- r)
        M = np.stack([D[:, conds.index(f"tmpl:{r}")] for r in ROLES], axis=1) - rand[:, None] if f"tmpl:{ROLES[0]}" in conds else np.full((R, R), np.nan)
        return N, M, (w @ acc) / n

    def silo(N: np.ndarray, keep: list[int]) -> float:
        if len(keep) < 2:
            return float("nan")
        sub = N[np.ix_(keep, keep)]
        return float(np.trace(sub) / len(keep) - (sub.sum() - np.trace(sub)) / (len(keep) * (len(keep) - 1)))

    w1 = np.ones(T)
    N, M, a = derive(w1)
    rng = np.random.default_rng(BOOT_SEED)
    W = rng.multinomial(T, np.ones(T) / T, size=boot).astype(float) if boot else np.zeros((0, T))
    boots = [derive(w) for w in W]
    keep = []
    chance = {}
    for ri, role in enumerate(ROLES):
        if role not in CHANCE:
            keep.append(ri)
            continue
        lo = float(np.quantile([b[2][ri] for b in boots], 0.025)) if boots else float(a[ri])
        chance[role] = {"p_gold_above_chance_rate": float(a[ri]), "ci_low": lo}
        if lo > 0.5:  # majority of items put more than chance mass on the gold answer
            keep.append(ri)
    si = silo(N, keep)
    bs = np.array([silo(b[0], keep) for b in boots]) if boots else np.array([])
    diag_role = float(np.mean([N[i, i] for i in keep])) if keep else float("nan")
    diag_tmpl = float(np.mean([M[i, i] for i in keep])) if keep else float("nan")
    return {
        "n_tasks": T, "n_prompts": len(pids), "roles": ROLES, "included_roles": [ROLES[i] for i in keep],
        "base_sd": sd, "chance": chance, "N_target_by_source": N.tolist(), "TMPL_target_by_source": M.tolist(),
        "SI": si, "SI_ci95": [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))] if len(bs) else None,
        "diag_role_mean": diag_role, "diag_tmpl_mean": diag_tmpl,
        "tmpl_fraction_of_role_diag": (diag_tmpl / diag_role) if diag_role not in (0.0,) and math.isfinite(diag_role) else None,
    }


def verdict(s: dict) -> str:
    ci, frac = s["SI_ci95"], s["tmpl_fraction_of_role_diag"]
    if ci is None or not (ci[0] > 0 or ci[1] < 0) or s["SI"] <= 0:
        return "no separable role subspaces detected at rank 4 in this band"
    if frac is None or frac >= 0.5:
        return "lexical, not operational"
    return "siloed"


def p5(out: Path) -> int:
    g = Gate("P5")
    prompts = load_prompts(out)
    band = json.loads((out / "band_choice.json").read_text())["band"]
    rows = [r for r in jl(out / "heldout_scores.jsonl") if r["condition"] == "base" or (r["band"] == band and r["k"] == 4)]
    mine = stats(rows, prompts)
    mine["verdict"] = verdict(mine)
    (out / "stats_validator.json").write_text(json.dumps(mine, indent=1) + "\n")
    print(json.dumps({k: mine[k] for k in ("SI", "SI_ci95", "included_roles", "diag_role_mean", "diag_tmpl_mean", "verdict")}, indent=1))
    theirs = json.loads((out / "stats.json").read_text()) if (out / "stats.json").exists() else None
    g.check(theirs is not None, "stats.json from the P5 parcel exists")
    if theirs:
        g.check(abs(theirs["SI"] - mine["SI"]) <= 1e-9, "SI matches independent recomputation")
        g.check(np.allclose(theirs["N_target_by_source"], mine["N_target_by_source"], atol=1e-9), "4x4 matrix matches")
        g.check(np.allclose(theirs["SI_ci95"], mine["SI_ci95"], atol=1e-9), "bootstrap interval matches (same seed and resample scheme)")
        g.check(theirs.get("verdict") == mine["verdict"], f"verdict matches the pre-registered rule ({mine['verdict']})")
    return g.done(out)


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    import tempfile
    rng = np.random.default_rng(1)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        prompts = [r for r in jl(HERE / "out" / "prompts.jsonl") if r["split"] == "heldout"]
        (out / "prompts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in prompts))
        (out / "band_choice.json").write_text(json.dumps({"band": "middle", "k": 4}))
        results = {}
        for mode in ("siloed", "null"):
            rows = []
            for p in prompts:
                for c in conditions():
                    hit = mode == "siloed" and c == f"role:{p['role']}"
                    drop = (1.5 if hit else 0.1 if c != "base" else 0.0) + (rng.normal(0, 0.05) if c != "base" else 0.0)
                    if p["candidates"]:
                        lp = rng.normal(-3, 0.3, len(p["candidates"]))
                        lp[p["candidates"].index(p["gold"])] = 2.0 - drop
                        sc = float(lp[p["candidates"].index(p["gold"])] - (lp.max() + math.log(np.exp(lp - lp.max()).sum())))
                        lp = lp.tolist()
                    else:
                        lp, sc = None, float(-1.0 - rng.random() * 0.5 - drop)
                    rows.append({"prompt_id": p["prompt_id"], "condition": c, "band": None if c == "base" else "middle", "k": None if c == "base" else 4,
                                 "score": sc, "cand_logprobs": lp, "removed_energy": None if c == "base" else 0.01, "run_id": "selftest"})
            (out / "heldout_scores.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            rc = p4(out)
            s = stats(rows, {p["prompt_id"]: p for p in prompts})
            results[mode] = (rc, s["SI"], s["SI_ci95"], verdict(s))
            print(mode, results[mode])
        ok = results["siloed"][0] == 0 and results["siloed"][3] == "siloed" and results["null"][3].startswith("no separable")
        print("SELFTEST", "PASS" if ok else "FAIL")
        return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("gate", choices=["p0", "p1", "p2", "p3", "p4", "p5", "selftest"])
    ap.add_argument("--out", default=str(HERE / "out"))
    a = ap.parse_args()
    sys.exit(selftest() if a.gate == "selftest" else {"p0": p0, "p1": p1, "p2": p2, "p3": p3, "p4": p4, "p5": p5}[a.gate](Path(a.out)))
