#!/usr/bin/env python3
"""Lossless repack of a compressed-tensors W4A16 (pack-quantized, symmetric, group 32)
checkpoint into MLX affine 4-bit format.

compressed-tensors symmetric int4 stores u = q + 8 (u in 0..15) packed 8 per int32,
little-end first, with dequant w = (u - 8) * scale.
MLX affine 4-bit stores u packed 8 per uint32, little-end first, with w = u * scale + bias.
So the packed words carry over unchanged; bias = -8 * scale (exact in bf16).

Usage: python convert_ct_to_mlx.py <src_dir> <dst_dir>
"""
import json
import shutil
import sys
from pathlib import Path

import mlx.core as mx

src = Path(sys.argv[1]).expanduser()
dst = Path(sys.argv[2]).expanduser()
dst.mkdir(parents=True, exist_ok=True)

cfg = json.loads((src / "config.json").read_text())
qc = cfg.get("quantization_config")
assert qc and qc.get("format") == "pack-quantized", "source is not pack-quantized"
w = qc["config_groups"]["group_0"]["weights"]
assert w["num_bits"] == 4 and w["symmetric"] and w["strategy"] == "group", w
GROUP = w["group_size"]
print(f"source: 4-bit symmetric group_size={GROUP}")

tensors = mx.load(str(src / "model.safetensors"))
out = {}
n_quant = 0
for name, arr in tensors.items():
    if name == "lm_head.weight" and cfg.get("tie_word_embeddings"):
        continue  # tied to embed_tokens; MLX model has no lm_head
    if name.endswith(".weight_shape"):
        continue
    if name.endswith(".weight_packed"):
        base = name[: -len(".weight_packed")]
        scale = tensors[base + ".weight_scale"]
        packed = arr.view(mx.uint32)
        # sanity: packed unsigned nibbles should centre near 8 for symmetric int4
        if n_quant == 0:
            nib = [(packed[:4] >> (4 * j)) & 0xF for j in range(8)]
            mean = mx.mean(mx.stack([n.astype(mx.float32) for n in nib])).item()
            print(f"first tensor {base}: mean nibble {mean:.2f} (expect ~8)")
            assert 6.5 < mean < 9.5, "unexpected nibble distribution; offset convention may differ"
        out[base + ".weight"] = packed
        out[base + ".scales"] = scale
        out[base + ".biases"] = (scale.astype(mx.float32) * -8.0).astype(scale.dtype)
        n_quant += 1
    elif name.endswith(".weight_scale"):
        continue
    else:
        out[name] = arr
print(f"repacked {n_quant} linear layers; total tensors {len(out)}")

mx.save_safetensors(str(dst / "model.safetensors"), out, metadata={"format": "mlx"})

cfg.pop("quantization_config")
cfg["quantization"] = {"group_size": GROUP, "bits": 4, "mode": "affine"}
(dst / "config.json").write_text(json.dumps(cfg, indent=2))
for f in ("generation_config.json", "tokenizer.json", "tokenizer_config.json",
          "chat_template.jinja", "processor_config.json"):
    if (src / f).exists():
        shutil.copy(src / f, dst / f)
print("done ->", dst)
