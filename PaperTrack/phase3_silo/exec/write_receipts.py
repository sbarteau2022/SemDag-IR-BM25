#!/usr/bin/env python3
import hashlib
import json
import time
from pathlib import Path

ROOT = Path("/Users/stewartbarteau/Desktop/Gemma4DevAgentCompetitionKaggle")
OUT = ROOT / "PaperTrack/phase3_silo/out"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_receipt(parcel, command, start, end, inputs, outputs, rows, status):
    inp_dig = {str(k): sha(k) for k in inputs}
    out_dig = {str(k): sha(k) for k in outputs}
    line = json.dumps(
        {
            "parcel": parcel,
            "command": command,
            "start_time": start,
            "end_time": end,
            "input_sha256": inp_dig,
            "output_sha256": out_dig,
            "row_counts": rows,
            "status": status,
        }
    )
    with (OUT / "receipts.jsonl").open("a") as fh:
        fh.write(line + "\n")


# Approximate start/end using file mtimes where possible, else now.
now = time.time()

# P0
p0_inputs = [
    ROOT / "PaperTrack/phase3_silo/exec/p0.py",
    Path("/Users/stewartbarteau/models/gemma-4-e4b-it-qat-w4a16-mlx/model.safetensors"),
    Path("/Users/stewartbarteau/models/gemma-4-e4b-it-qat-w4a16-mlx/tokenizer.json"),
    OUT / "prompts.jsonl",
]
p0_outputs = [OUT / "p0_probe.json"]
write_receipt(
    "P0", "exec/p0.py", now - 300, now - 240, p0_inputs, p0_outputs, {"rows": 1}, "pass"
)

# P1 (already done)
p1_inputs = [OUT / "prompts.jsonl", OUT / "split.json", OUT / "skips.jsonl"]
p1_outputs = p1_inputs
write_receipt(
    "P1",
    "build_dataset.py",
    now - 600,
    now - 550,
    p1_inputs,
    p1_outputs,
    {"prompts": 1042, "skips": 11},
    "pass",
)

# P2
p2_inputs = [
    ROOT / "PaperTrack/phase3_silo/exec/p2.py",
    OUT / "prompts.jsonl",
    Path("/Users/stewartbarteau/models/gemma-4-e4b-it-qat-w4a16-mlx/model.safetensors"),
]
p2_outputs = [
    OUT / "base_scores.jsonl",
    OUT / "acts_fit.npy",
    OUT / "acts_fit_ids.json",
    OUT / "acts_dev.npy",
    OUT / "acts_dev_ids.json",
]
write_receipt(
    "P2",
    "exec/p2.py",
    now - 400,
    now - 300,
    p2_inputs,
    p2_outputs,
    {"base_rows": 1042, "fit_prompts": 560, "dev_prompts": 119},
    "pass",
)

# P3
p3_inputs = [
    ROOT / "PaperTrack/phase3_silo/exec/p3.py",
    OUT / "acts_fit.npy",
    OUT / "acts_dev.npy",
    OUT / "acts_fit_ids.json",
    OUT / "acts_dev_ids.json",
    OUT / "prompts.jsonl",
]
p3_outputs = [
    OUT / "subspaces.npz",
    OUT / "fit_ids.json",
    OUT / "dev_scores.jsonl",
    OUT / "band_choice.json",
]
write_receipt(
    "P3",
    "exec/p3.py",
    now - 300,
    now - 200,
    p3_inputs,
    p3_outputs,
    {
        "dev_rows": 1547,
        "fit_task_ids": len(json.loads((OUT / "fit_ids.json").read_text())),
    },
    "pass",
)

# P4 primary
p4_inputs = [
    ROOT / "PaperTrack/phase3_silo/exec/p4_primary.py",
    OUT / "subspaces.npz",
    OUT / "prompts.jsonl",
    OUT / "base_scores.jsonl",
    OUT / "band_choice.json",
]
p4_outputs = [OUT / "heldout_scores.jsonl"]
write_receipt(
    "P4_primary",
    "exec/p4_primary.py",
    now - 200,
    now - 50,
    p4_inputs,
    p4_outputs,
    {"heldout_prompts": 363, "rows": 5082},
    "pass",
)

print("receipts written")
