"""Exact E4B prefill capture on the local MLX research copy.

The probe records repeated residual ablations. It emits measurements only.
Criticality and pruning stay one concordance label, and this run does not
assign either one: logit KL is not coding behavior.

Frozen before the first forward. Do not edit the constants after seeing a run.
"""

from __future__ import annotations

import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ledger import (
    chain_hash,
    canonical_dumps,
    event_schema,
    load_jsonl,
    seal,
    sha256_bytes,
    sha256_file,
    sha256_text,
    validate,
)

ROOT = Path(__file__).resolve().parent
MODEL_PATH = Path.home() / "models" / "gemma-4-e4b-it-qat-w4a16-mlx"

EFFECT_MARGIN_NATS = 0.05
PARITY_FLOOR = 0.999
ABLATION_MODE = "residual_identity_keep_kv"
ABLATION_SELECTOR = "live_layer_type_full_attention"
REPEATS = (0, 1)
TASK_ID = "probe_synthetic_pair"
SPLIT = "synthetic_local"
TOKENIZATION = "encode_add_special_tokens_false_no_chat_template"
COPY_CLASS = "mlx_research_conversion_not_cuda_qat"
PROMPTS = (
    (
        "dataflow",
        "Read base and offset. result = base + offset\nWhich name carries the sum?",
    ),
    (
        "lexical_decoy",
        "Read base and offset. result = result + result\nWhich word is repeated?",
    ),
)


def protocol_document() -> dict:
    return {
        "prompts": [{"condition_id": cid, "text": text} for cid, text in PROMPTS],
        "ablation_mode": ABLATION_MODE,
        "ablation_selector": ABLATION_SELECTOR,
        "effect_margin_nats": EFFECT_MARGIN_NATS,
        "parity_floor": PARITY_FLOOR,
        "repeats": list(REPEATS),
        "task_id": TASK_ID,
        "split": SPLIT,
        "tokenization": TOKENIZATION,
        "copy_class": COPY_CLASS,
        "claim_policy": "measurement_only",
    }


def protocol_digest() -> str:
    return sha256_text(canonical_dumps(protocol_document()))


def residual_identity_keep_kv(layer_index, ablate_index, residual, hidden, kv, offset):
    """Run the layer, then put the input residual back and keep its KV."""
    if ablate_index == layer_index:
        return residual, kv, offset
    return hidden, kv, offset


def _finite(value):
    if value is None:
        return None
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def kl_nats(clean, other):
    clean = np.asarray(clean, dtype=np.float64)
    other = np.asarray(other, dtype=np.float64)
    if clean.shape != other.shape or clean.ndim != 1 or clean.size == 0:
        return None
    def lse(values):
        peak = np.max(values)
        return float(peak + np.log(np.exp(values - peak).sum()))
    log_p = clean - lse(clean)
    log_q = other - lse(other)
    return _finite(float(np.sum(np.exp(log_p) * (log_p - log_q))))


def cosine(left, right):
    left = np.asarray(left, dtype=np.float64).reshape(-1)
    right = np.asarray(right, dtype=np.float64).reshape(-1)
    if left.shape != right.shape or left.size == 0:
        return None
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom == 0.0:
        return None
    return _finite(float(np.dot(left, right) / denom))


def concordance_value(left, right, margin):
    if left is None or right is None:
        return -1.0
    if (left >= margin) != (right >= margin):
        return -1.0
    return 1.0 if left >= margin else 0.0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _artifact(obj) -> bytes:
    return canonical_dumps(obj).encode("utf-8")


class LedgerWriter:
    def __init__(self, base: dict):
        self.base = base
        self.events: list[dict] = []
        self.artifacts: dict[str, bytes] = {}

    def add(self, artifact: bytes, **fields) -> dict:
        digest = sha256_bytes(artifact)
        self.artifacts[digest] = artifact
        raw = dict(self.base)
        raw.update(fields)
        raw["sequence"] = len(self.events) + 1
        raw["time_utc"] = fields.get("time_utc") or _now()
        raw["artifact_sha256"] = digest
        raw["parent_event_ids"] = [] if not self.events else [self.events[-1]["event_id"]]
        raw.setdefault("evidence_ids", [])
        raw.setdefault("node_ids", [f"task:{TASK_ID}"])
        sealed = seal(raw)
        self.events.append(sealed)
        return sealed

    def finish(self, **fields) -> dict:
        digest = chain_hash(self.events)
        raw = dict(self.base)
        raw.update(fields)
        raw["sequence"] = len(self.events) + 1
        raw["time_utc"] = _now()
        raw["artifact_sha256"] = digest
        raw["metric_name"] = "end_receipt"
        raw["edge_type"] = "declares"
        raw["metric_value"] = len(self.events)
        raw["parent_event_ids"] = [] if not self.events else [self.events[-1]["event_id"]]
        raw.setdefault("evidence_ids", [])
        raw.setdefault("node_ids", [f"task:{TASK_ID}"])
        raw.setdefault("claim_class", "none")
        raw.setdefault("status", "observed")
        raw.setdefault("condition_id", "protocol")
        raw.setdefault("capture_site", "run")
        raw.setdefault("repeat_index", 0)
        raw.setdefault("ablation_mode", "none")
        raw.setdefault("comparator_id", "event_chain")
        raw.setdefault("token_span_class", "none")
        raw.setdefault("prompt_sha256", sha256_text(""))
        sealed = seal(raw)
        self.events.append(sealed)
        return sealed


def _base(run_id: str, model_sha: str, tokenizer_sha: str) -> dict:
    return {
        "schema_version": "0.1.0",
        "run_id": run_id,
        "model_sha256": model_sha,
        "tokenizer_sha256": tokenizer_sha,
        "data_split_digest": protocol_digest(),
        "task_id": TASK_ID,
        "seed": 0,
        "effect_margin": EFFECT_MARGIN_NATS,
        "status": "observed",
        "claim_class": "measurement",
        "token_span_class": "last_token",
        "comparator_id": "none",
        "ablation_mode": "none",
        "prompt_sha256": sha256_text(""),
        "condition_id": "protocol",
        "capture_site": "run",
        "repeat_index": 0,
    }


def assemble_ledger(run_id, model_sha, tokenizer_sha, measurements) -> tuple[list[dict], dict[str, bytes], dict]:
    """Turn captured arrays into a measurement ledger. Assigns no basin label."""
    writer = LedgerWriter(_base(run_id, model_sha, tokenizer_sha))
    manifest = {
        "run_id": run_id,
        "data_split_digest": protocol_digest(),
        "required_conditions": [cid for cid, _ in PROMPTS],
        "ablation_mode": ABLATION_MODE,
        "ablation_selector": ABLATION_SELECTOR,
        "effect_margin_nats": EFFECT_MARGIN_NATS,
        "parity_floor": PARITY_FLOOR,
        "task_id": TASK_ID,
        "split": SPLIT,
        "tokenization": TOKENIZATION,
        "copy_class": COPY_CLASS,
        "claim_policy": "measurement_only",
        "prompt_sha256": {cid: sha256_text(text) for cid, text in PROMPTS},
    }
    writer.add(
        _artifact(manifest),
        edge_type="declares",
        metric_name="manifest",
        metric_value=1,
        claim_class="none",
        token_span_class="none",
        comparator_id="preregistered_protocol",
    )
    writer.add(
        measurements["runtime_bytes"],
        edge_type="declares",
        metric_name="runtime_identity",
        metric_value=1,
        claim_class="none",
        token_span_class="none",
        comparator_id="checkpoint_files",
    )
    layers = measurements["layers"]
    has_kv_mismatches = sum(1 for row in layers if row["has_kv"] != row["expected_has_kv"])
    type_mismatches = sum(1 for row in layers if row["layer_type"] != row["config_layer_type"])
    if measurements.get("layer_count_mismatch"):
        type_mismatches += 1
    writer.add(
        _artifact({"has_kv_mismatch_count": has_kv_mismatches, "layers": layers}),
        edge_type="contradicts" if has_kv_mismatches else "supports",
        metric_name="has_kv_mismatch_count",
        metric_value=has_kv_mismatches,
        comparator_id="config_arithmetic_split",
        token_span_class="none",
    )
    writer.add(
        _artifact({"layer_type_mismatch_count": type_mismatches}),
        edge_type="contradicts" if type_mismatches else "supports",
        metric_name="layer_type_mismatch_count",
        metric_value=type_mismatches,
        comparator_id="config_layer_types",
        token_span_class="none",
    )

    prompt_sha = {cid: sha256_text(text) for cid, text in PROMPTS}
    cosines = []
    for condition_id, _text in PROMPTS:
        reference = measurements["cleans"][(condition_id, 0)]["hidden"]
        for repeat in REPEATS:
            hidden = measurements["cleans"][(condition_id, repeat)]["hidden"]
            value = None if reference is None or hidden is None else cosine(reference, hidden)
            cosines.append(value)
            payload = {"cosine": value}
            if hidden is not None:
                raw = np.ascontiguousarray(hidden, dtype=np.float32).tobytes()
                payload["vector_sha256"] = sha256_bytes(raw)
                payload["dim"] = int(np.asarray(hidden).reshape(-1).size)
                writer.artifacts[payload["vector_sha256"]] = raw
            writer.add(
                _artifact(payload),
                edge_type="supports",
                status="inferred",
                metric_name="last_token_hidden_cosine",
                metric_value=value,
                condition_id=condition_id,
                prompt_sha256=prompt_sha[condition_id],
                capture_site=measurements["parity_site"],
                repeat_index=repeat,
                comparator_id=f"{condition_id}:clean:0",
            )

    kl_ids: dict[tuple, list[str]] = {}
    for layer in measurements["ablation_layers"]:
        site = f"layers.{layer}.layer_out"
        for condition_id, _text in PROMPTS:
            ids = []
            values = []
            clean = {
                repeat: measurements["cleans"][(condition_id, repeat)]["logits"]
                for repeat in REPEATS
            }
            for repeat in REPEATS:
                other = measurements["ablations"][(layer, condition_id, repeat)]
                value = kl_nats(clean[repeat], other["logits"])
                values.append(value)
                sealed = writer.add(
                    _artifact(
                        {
                            "kl_nats": value,
                            "top1_clean": int(clean[repeat].argmax()) if clean[repeat] is not None else None,
                            "top1_ablated": int(other["logits"].argmax()) if other["logits"] is not None else None,
                            "layer": layer,
                            "repeat": repeat,
                            "condition_id": condition_id,
                        }
                    ),
                    edge_type="changes",
                    metric_name="last_token_logit_kl",
                    metric_value=value,
                    condition_id=condition_id,
                    prompt_sha256=prompt_sha[condition_id],
                    capture_site=site,
                    repeat_index=repeat,
                    ablation_mode=ABLATION_MODE,
                    comparator_id=f"{condition_id}:clean:{repeat}",
                    node_ids=[f"task:{TASK_ID}", f"site:{site}"],
                )
                ids.append(sealed["event_id"])
            side = concordance_value(values[0], values[1], EFFECT_MARGIN_NATS)
            writer.add(
                _artifact({"concordance_side": side, "kl": values, "margin": EFFECT_MARGIN_NATS}),
                edge_type="supports" if side >= 0 else "contradicts",
                status="inferred",
                metric_name="concordance_side",
                metric_value=side,
                condition_id=condition_id,
                prompt_sha256=prompt_sha[condition_id],
                capture_site=site,
                ablation_mode=ABLATION_MODE,
                comparator_id="repeat_0_vs_1",
                evidence_ids=ids,
                node_ids=[f"task:{TASK_ID}", f"site:{site}"],
            )
            kl_ids[(layer, condition_id)] = ids

    for condition_id, _text in PROMPTS:
        clean = measurements["cleans"][(condition_id, 0)]["logits"]
        restored = measurements["restorations"][condition_id]["logits"]
        value = kl_nats(clean, restored)
        writer.add(
            _artifact({"restoration_logit_kl": value, "scope": "network_returned_to_first_clean"}),
            edge_type="restores",
            metric_name="restoration_logit_kl",
            metric_value=value,
            condition_id=condition_id,
            prompt_sha256=prompt_sha[condition_id],
            capture_site="run",
            comparator_id=f"{condition_id}:clean:0",
            token_span_class="last_token",
        )

    finite = [value for value in cosines if value is not None]
    parity_ok = bool(finite) and len(finite) == len(cosines) and min(finite) >= PARITY_FLOOR
    writer.add(
        _artifact({"parity_floor": PARITY_FLOOR, "cosines": cosines, "ok": parity_ok}),
        edge_type="supports" if parity_ok else "contradicts",
        status="inferred",
        metric_name="deterministic_parity",
        metric_value=1.0 if parity_ok else 0.0,
        comparator_id="clean_repeat_cosine",
        token_span_class="last_token",
        capture_site=measurements["parity_site"],
    )
    writer.finish(claim_class="none")
    catalog = {
        "sites": measurements["sites"],
        "layers": layers,
        "model_copy": COPY_CLASS,
        "ablation_layers": list(measurements["ablation_layers"]),
        "parity_site": measurements["parity_site"],
    }
    return writer.events, writer.artifacts, catalog


def summary_from_ledger(events: list[dict]) -> dict:
    wanted = {
        "last_token_logit_kl",
        "concordance_side",
        "restoration_logit_kl",
        "deterministic_parity",
        "last_token_hidden_cosine",
        "has_kv_mismatch_count",
        "layer_type_mismatch_count",
    }
    return {
        "copy_class": COPY_CLASS,
        "claim_policy": "measurement_only",
        "critical_claims": sum(event["claim_class"] == "critical" for event in events),
        "unnecessary_claims": sum(event["claim_class"] == "unnecessary" for event in events),
        "rows": [
            {
                "sequence": event["sequence"],
                "condition_id": event["condition_id"],
                "capture_site": event["capture_site"],
                "repeat_index": event["repeat_index"],
                "metric_name": event["metric_name"],
                "metric_value": event["metric_value"],
                "ablation_mode": event["ablation_mode"],
                "status": event["status"],
            }
            for event in events
            if event["metric_name"] in wanted
        ],
    }


class CaptureState:
    def __init__(self):
        self.active = False
        self.ablate = None
        self.final_index = None
        self.shapes: dict[str, list[int]] = {}
        self.hidden = None

    def save(self, site: str, tensor) -> None:
        import mlx.core as mx

        if tensor is None or getattr(tensor, "ndim", 0) < 2:
            return
        last = tensor[0, -1].astype(mx.float32)
        mx.eval(last)
        vec = np.array(last)
        shape = [int(dim) for dim in vec.shape]
        self.shapes.setdefault(site, shape)
        if self.final_index is not None and site == f"layers.{self.final_index}.layer_out":
            self.hidden = np.ascontiguousarray(vec, dtype=np.float32)


def install_hooks(layers, state: CaptureState):
    import mlx_lm.models.gemma4_text as gemma

    for layer in layers:
        layer.mlp._capture_layer_idx = layer.layer_idx
    orig_layer = gemma.DecoderLayer.__call__
    orig_attn = gemma.Attention.__call__
    orig_mlp = gemma.MLP.__call__

    def layer_call(self, x, mask=None, cache=None, per_layer_input=None, shared_kv=None, offset=None):
        if state.active:
            state.save(f"layers.{self.layer_idx}.residual_in", x)
        hidden, kv, off = orig_layer(
            self, x, mask, cache, per_layer_input, shared_kv, offset
        )
        if state.active:
            state.save(f"layers.{self.layer_idx}.layer_out", hidden)
            hidden, kv, off = residual_identity_keep_kv(
                self.layer_idx, state.ablate, x, hidden, kv, off
            )
        return hidden, kv, off

    def attn_call(self, x, mask=None, cache=None, shared_kv=None, offset=None):
        output = orig_attn(self, x, mask, cache, shared_kv=shared_kv, offset=offset)
        if state.active and isinstance(output, tuple) and output:
            state.save(f"layers.{self.layer_idx}.attn_out", output[0])
        return output

    def mlp_call(self, x):
        output = orig_mlp(self, x)
        index = getattr(self, "_capture_layer_idx", None)
        if state.active and index is not None:
            state.save(f"layers.{index}.mlp_out", output)
        return output

    gemma.DecoderLayer.__call__ = layer_call
    gemma.Attention.__call__ = attn_call
    gemma.MLP.__call__ = mlp_call

    def uninstall() -> None:
        gemma.DecoderLayer.__call__ = orig_layer
        gemma.Attention.__call__ = orig_attn
        gemma.MLP.__call__ = orig_mlp

    return uninstall


def _clear_cache() -> None:
    import mlx.core as mx

    metal = getattr(mx, "metal", None)
    if metal is not None and hasattr(metal, "clear_cache"):
        metal.clear_cache()


def _encode(tokenizer, text: str) -> list[int]:
    encoded = tokenizer.encode(text, add_special_tokens=False)
    return [int(token) for token in encoded]


def _prefill(model, token_ids, state: CaptureState):
    import mlx.core as mx

    state.hidden = None
    state.active = True
    try:
        logits = model(mx.array([token_ids]))
        last = logits[0, -1].astype(mx.float32)
        mx.eval(last)
        return np.array(last), None if state.hidden is None else np.array(state.hidden)
    finally:
        state.active = False
        state.ablate = None
        _clear_cache()


def _checkpoint_identity(model_path: Path) -> tuple[str, str, dict]:
    weights = sorted(model_path.glob("*.safetensors"))
    config = model_path / "config.json"
    if not config.is_file() or not weights:
        raise FileNotFoundError(f"checkpoint incomplete at {model_path}")
    weight_parts = [{"name": path.name, "sha256": sha256_file(path)} for path in weights]
    weight_parts.append({"name": "config.json", "sha256": sha256_file(config)})
    model_sha = sha256_text(canonical_dumps({"files": weight_parts}))
    tokenizer_names = [
        "tokenizer.json",
        "tokenizer.model",
        "tokenizer_config.json",
        "special_tokens_map.json",
    ]
    tokenizer_parts = []
    for name in tokenizer_names:
        path = model_path / name
        if path.is_file():
            tokenizer_parts.append({"name": name, "sha256": sha256_file(path)})
    if not tokenizer_parts:
        raise FileNotFoundError(f"tokenizer files missing at {model_path}")
    tokenizer_sha = sha256_text(canonical_dumps({"files": tokenizer_parts}))
    return model_sha, tokenizer_sha, {"weights": weight_parts, "tokenizer": tokenizer_parts}


def _code_revision() -> dict:
    files = []
    for name in ("ledger.py", "capture_probe.py", "export_obsidian.py", "validate_ledger.py"):
        path = ROOT / name
        files.append({"name": name, "sha256": sha256_file(path)})
    return {"files": files, "revision": sha256_text(canonical_dumps({"files": files}))}


def run_capture(model_path: Path) -> dict:
    import mlx.core as mx
    from mlx_lm import load

    print(f"protocol_digest {protocol_digest()}", flush=True)
    print(f"loading {model_path}", flush=True)
    model, tokenizer = load(str(model_path))
    model.eval()
    layers = list(model.layers)
    args = model.language_model.args
    live_count = len(layers)
    config_count = int(args.num_hidden_layers)
    shared = int(args.num_kv_shared_layers)
    config_types = list(args.layer_types)
    rows = []
    for index, layer in enumerate(layers):
        rows.append(
            {
                "index": index,
                "layer_type": str(layer.layer_type),
                "has_kv": bool(layer.self_attn.has_kv),
                "expected_has_kv": index < (live_count - shared),
                "config_layer_type": str(config_types[index]) if index < len(config_types) else "missing",
                "enable_moe": bool(getattr(layer, "enable_moe", False)),
            }
        )
    ablation_layers = [row["index"] for row in rows if row["layer_type"] == "full_attention"]
    state = CaptureState()
    state.final_index = live_count - 1
    uninstall = install_hooks(layers, state)
    encoded = {cid: _encode(tokenizer, text) for cid, text in PROMPTS}
    if any(len(ids) == 0 for ids in encoded.values()):
        uninstall()
        raise RuntimeError("tokenizer returned an empty id list")
    cleans = {}
    ablations = {}
    restorations = {}
    try:
        for condition_id, _text in PROMPTS:
            for repeat in REPEATS:
                print(f"clean {condition_id} repeat {repeat}", flush=True)
                logits, hidden = _prefill(model, encoded[condition_id], state)
                cleans[(condition_id, repeat)] = {"logits": logits, "hidden": hidden}
        sites = sorted(state.shapes)
        for layer in ablation_layers:
            for condition_id, _text in PROMPTS:
                for repeat in REPEATS:
                    print(f"ablate layer {layer} {condition_id} repeat {repeat}", flush=True)
                    state.ablate = layer
                    logits, _hidden = _prefill(model, encoded[condition_id], state)
                    ablations[(layer, condition_id, repeat)] = {"logits": logits}
        for condition_id, _text in PROMPTS:
            print(f"restore {condition_id}", flush=True)
            logits, _hidden = _prefill(model, encoded[condition_id], state)
            restorations[condition_id] = {"logits": logits}
    finally:
        uninstall()
        mx.eval(mx.zeros((1,)))
        _clear_cache()
    return {
        "layers": rows,
        "layer_count_mismatch": live_count != config_count,
        "ablation_layers": ablation_layers,
        "sites": sites,
        "parity_site": f"layers.{live_count - 1}.layer_out",
        "cleans": cleans,
        "ablations": ablations,
        "restorations": restorations,
        "token_sha256": {cid: sha256_text(canonical_dumps(ids)) for cid, ids in encoded.items()},
        "live_count": live_count,
        "config_count": config_count,
        "shared": shared,
    }


def write_run(out: Path, events, artifacts, catalog) -> None:
    from export_obsidian import export_vault

    out.mkdir(parents=True, exist_ok=False)
    artifact_dir = out / "artifacts"
    artifact_dir.mkdir()
    for digest, blob in artifacts.items():
        (artifact_dir / digest).write_bytes(blob)
    with (out / "ledger.jsonl").open("w") as handle:
        for event in events:
            handle.write(canonical_dumps(event) + "\n")
    (out / "catalog.json").write_text(canonical_dumps(catalog) + "\n")
    schema = event_schema(catalog["sites"])
    (out / "event.schema.json").write_text(canonical_dumps(schema) + "\n")
    errors = validate(events, catalog, artifacts)
    (out / "validate_errors.json").write_text(canonical_dumps({"errors": errors}) + "\n")
    summary = summary_from_ledger(events)
    summary["validator_errors"] = errors
    summary["protocol_digest"] = protocol_digest()
    (out / "summary.json").write_text(canonical_dumps(summary) + "\n")
    if not errors:
        export_vault(events, catalog, artifacts, out / "vault")
    return errors


def main() -> int:
    run_id = "e4b-mlx-capture-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "out" / run_id
    print(f"run_id {run_id}", flush=True)
    print(f"effect_margin_nats {EFFECT_MARGIN_NATS} parity_floor {PARITY_FLOOR}", flush=True)
    try:
        model_sha, tokenizer_sha, identity = _checkpoint_identity(MODEL_PATH)
        code = _code_revision()
        captured = run_capture(MODEL_PATH)
        import importlib.metadata

        runtime = {
            "copy_class": COPY_CLASS,
            "model_path": str(MODEL_PATH),
            "model_sha256": model_sha,
            "tokenizer_sha256": tokenizer_sha,
            "identity": identity,
            "code": code,
            "python": sys.version,
            "platform": platform.platform(),
            "mlx": importlib.metadata.version("mlx"),
            "live_layers": captured["live_count"],
            "config_layers": captured["config_count"],
            "num_kv_shared_layers": captured["shared"],
            "ablation_layers": captured["ablation_layers"],
            "token_sha256": captured["token_sha256"],
            "server_policy": "do_not_signal_existing_mlx_server",
            "note": "MLX research conversion. Not a CUDA QAT competition-base measurement.",
        }
        captured["runtime_bytes"] = _artifact(runtime)
        events, artifacts, catalog = assemble_ledger(run_id, model_sha, tokenizer_sha, captured)
        errors = write_run(out, events, artifacts, catalog)
    except Exception:
        failed = ROOT / "out" / (run_id + ".error")
        failed.parent.mkdir(parents=True, exist_ok=True)
        failed.write_text(traceback.format_exc())
        print(traceback.format_exc(), flush=True)
        print(f"FAILED partial record {failed}", flush=True)
        return 1
    print(f"wrote {out}", flush=True)
    if errors:
        print("FAILED validation", flush=True)
        for error in errors:
            print(error, flush=True)
        return 1
    summary = summary_from_ledger(load_jsonl(out / "ledger.jsonl"))
    print(
        f"DONE critical={summary['critical_claims']} unnecessary={summary['unnecessary_claims']} "
        f"events={len(load_jsonl(out / 'ledger.jsonl'))}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
