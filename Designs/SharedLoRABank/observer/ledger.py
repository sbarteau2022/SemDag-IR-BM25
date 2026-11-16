"""Append-only observer ledger. The hash is the identity of an event.

Criticality and pruning are two labels of one concordance chain. The
validator admits neither label unless the twin evidence is present.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA_VERSION = "0.1.0"
EDGE_TYPES = {
    "declares",
    "elicits",
    "located_at",
    "candidate_for",
    "recurs_in",
    "tested_by",
    "changes",
    "restores",
    "retains",
    "routes_to",
    "supports",
    "contradicts",
}
STATUSES = {"proposed", "observed", "inferred", "refuted"}
CLAIM_CLASSES = {"none", "measurement", "selectivity", "critical", "unnecessary"}
FORBIDDEN_MARKERS = ("held-out", "held_out", "hidden_test", "test_patch", "hints_text", "gold_patch")

REQUIRED = [
    "schema_version",
    "event_id",
    "event_hash",
    "run_id",
    "sequence",
    "time_utc",
    "node_ids",
    "edge_type",
    "status",
    "claim_class",
    "model_sha256",
    "tokenizer_sha256",
    "data_split_digest",
    "task_id",
    "prompt_sha256",
    "condition_id",
    "seed",
    "capture_site",
    "token_span_class",
    "metric_name",
    "metric_value",
    "comparator_id",
    "artifact_sha256",
    "parent_event_ids",
    "evidence_ids",
    "repeat_index",
    "effect_margin",
    "ablation_mode",
]


def canonical_dumps(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def event_body(event: dict) -> dict:
    return {key: event[key] for key in REQUIRED if key not in {"event_id", "event_hash"}}


def seal(event: dict) -> dict:
    missing = [key for key in REQUIRED if key not in event and key not in {"event_id", "event_hash"}]
    if missing:
        raise ValueError(f"event missing {missing}")
    body = event_body(event)
    digest = sha256_text(canonical_dumps(body))
    sealed = dict(event)
    sealed["event_hash"] = digest
    sealed["event_id"] = digest[:32]
    return sealed


def chain_hash(events: list[dict]) -> str:
    payload = "\n".join(event["event_hash"] for event in events) + "\n"
    return sha256_text(payload)


def _as_map(events: list[dict]) -> dict[str, dict]:
    return {event["event_id"]: event for event in events}


def _parents_ok(event: dict, by_id: dict[str, dict], errors: list[str]) -> None:
    for parent in event["parent_event_ids"]:
        if parent not in by_id:
            errors.append(f"{event['event_id']} parent missing {parent}")
            continue
        if by_id[parent]["sequence"] >= event["sequence"]:
            errors.append(f"{event['event_id']} parent {parent} is not earlier")


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _effect_pair(event: dict, by_id: dict[str, dict]) -> tuple[dict, dict] | None:
    changes = []
    for evidence_id in event["evidence_ids"]:
        item = by_id.get(evidence_id)
        if item is None:
            return None
        if (
            item["edge_type"] == "changes"
            and item["capture_site"] == event["capture_site"]
            and item["metric_name"] == "behavior_change"
        ):
            changes.append(item)
    if len(changes) != 2:
        return None
    if changes[0]["condition_id"] != changes[1]["condition_id"]:
        return None
    if changes[0]["repeat_index"] == changes[1]["repeat_index"]:
        return None
    return changes[0], changes[1]


def _same_side(left: dict, right: dict) -> bool:
    margin = left["effect_margin"]
    if margin is None or right["effect_margin"] != margin or not _number(margin):
        return False
    if not _number(left["metric_value"]) or not _number(right["metric_value"]):
        return False
    return (left["metric_value"] >= margin) == (right["metric_value"] >= margin)


def validate(events: list[dict], catalog: dict, artifacts: dict[str, bytes]) -> list[str]:
    errors: list[str] = []
    if not events:
        return ["ledger is empty"]
    by_id: dict[str, dict] = {}
    sites = set(catalog.get("sites") or [])
    seen_sequence: dict[str, int] = {}
    for event in events:
        missing = [key for key in REQUIRED if key not in event]
        if missing:
            errors.append(f"missing fields {missing}")
            continue
        body = event_body(event)
        digest = sha256_text(canonical_dumps(body))
        if event["event_hash"] != digest or event["event_id"] != digest[:32]:
            errors.append(f"hash mismatch at sequence {event['sequence']}")
        if event["event_id"] in by_id:
            errors.append(f"duplicate event_id {event['event_id']}")
        by_id[event["event_id"]] = event
        if event["schema_version"] != SCHEMA_VERSION:
            errors.append(f"{event['event_id']} schema_version")
        if event["edge_type"] not in EDGE_TYPES or event["status"] not in STATUSES:
            errors.append(f"{event['event_id']} bad edge or status")
        if event["claim_class"] not in CLAIM_CLASSES:
            errors.append(f"{event['event_id']} bad claim_class")
        if event["capture_site"] not in sites and event["capture_site"] not in {"run", "none"}:
            errors.append(f"{event['event_id']} unknown capture_site {event['capture_site']}")
        blob = json.dumps(event, ensure_ascii=False).lower()
        if any(marker in blob for marker in FORBIDDEN_MARKERS):
            errors.append(f"{event['event_id']} carries a held-out marker")
        run = event["run_id"]
        previous = seen_sequence.get(run, 0)
        if event["sequence"] != previous + 1:
            errors.append(f"{event['event_id']} sequence gap")
        seen_sequence[run] = event["sequence"]
        _parents_ok(event, by_id, errors)
        if event["edge_type"] == "routes_to" and event["status"] == "observed":
            errors.append(f"{event['event_id']} routes_to cannot be observed")
        if event["claim_class"] == "selectivity" and event["status"] == "observed":
            errors.append(f"{event['event_id']} selectivity cannot be observed")
        if event["edge_type"] == "elicits" and event["status"] == "observed":
            errors.append(f"{event['event_id']} association is not an observed cause")
        if event["metric_name"] != "end_receipt":
            blob = artifacts.get(event["artifact_sha256"])
            if blob is None:
                errors.append(f"{event['event_id']} artifact missing")
            elif sha256_bytes(blob) != event["artifact_sha256"]:
                errors.append(f"{event['event_id']} artifact hash mismatch")
        if event["claim_class"] in {"critical", "unnecessary"}:
            pair = _effect_pair(event, by_id)
            if pair is None or not _same_side(*pair):
                errors.append(f"{event['event_id']} concordance pair missing")
            elif event["claim_class"] == "critical":
                if pair[0]["metric_value"] < pair[0]["effect_margin"]:
                    errors.append(f"{event['event_id']} critical requires a repeated effect")
                restores = [
                    by_id[item]
                    for item in event["evidence_ids"]
                    if item in by_id
                    and by_id[item]["edge_type"] == "restores"
                    and by_id[item]["metric_name"] == "behavior_restored"
                    and _number(by_id[item]["metric_value"])
                    and by_id[item]["metric_value"] >= 0
                ]
                if len(restores) != 1:
                    errors.append(f"{event['event_id']} critical requires restoration")
            else:
                if pair[0]["metric_value"] >= pair[0]["effect_margin"]:
                    errors.append(f"{event['event_id']} unnecessary requires a repeated null")
                retains = [
                    by_id[item]
                    for item in event["evidence_ids"]
                    if item in by_id and by_id[item]["edge_type"] == "retains"
                ]
                if len(retains) != 1 or retains[0]["metric_name"] != "coding_accuracy_delta":
                    errors.append(f"{event['event_id']} unnecessary requires coding retention")
                elif not _number(retains[0]["metric_value"]) or retains[0]["metric_value"] < 0:
                    errors.append(f"{event['event_id']} retention failed")

    if errors:
        return errors
    head = events[0]
    if head["edge_type"] != "declares" or head["metric_name"] != "manifest":
        errors.append("first event must declare the manifest")
    tail = events[-1]
    if tail["edge_type"] != "declares" or tail["metric_name"] != "end_receipt":
        errors.append("complete ledger requires an end receipt")
    else:
        expected = chain_hash(events[:-1])
        if tail["artifact_sha256"] != expected:
            errors.append("end receipt does not bind the event chain")
    manifest_bytes = artifacts.get(head["artifact_sha256"]) if events else None
    if manifest_bytes is None:
        errors.append("manifest artifact missing")
    elif sha256_bytes(manifest_bytes) != head["artifact_sha256"]:
        errors.append("manifest artifact hash mismatch")
    else:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        required = manifest.get("required_conditions") or []
        present = {event["condition_id"] for event in events}
        for condition in required:
            if condition not in present:
                errors.append(f"omitted condition {condition}")
    return errors


METRIC_NAMES = [
    "manifest",
    "end_receipt",
    "runtime_identity",
    "has_kv_mismatch_count",
    "layer_type_mismatch_count",
    "last_token_hidden_cosine",
    "deterministic_parity",
    "last_token_logit_kl",
    "concordance_side",
    "restoration_logit_kl",
    "behavior_change",
    "behavior_restored",
    "coding_accuracy_delta",
]


def event_schema(sites: list[str]) -> dict:
    """Schema for one ledger event. Site names come from a capture catalog."""
    capture_sites = sorted(set(sites) | {"run", "none"})
    string = {"type": "string"}
    string_list = {"type": "array", "items": {"type": "string"}}
    number_or_null = {"type": ["number", "null"]}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "observer-event-0.1.0",
        "title": "ObserverEvent",
        "type": "object",
        "additionalProperties": False,
        "required": list(REQUIRED),
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "event_id": string,
            "event_hash": string,
            "run_id": string,
            "sequence": {"type": "integer", "minimum": 1},
            "time_utc": string,
            "node_ids": string_list,
            "edge_type": {"enum": sorted(EDGE_TYPES)},
            "status": {"enum": sorted(STATUSES)},
            "claim_class": {"enum": sorted(CLAIM_CLASSES)},
            "model_sha256": string,
            "tokenizer_sha256": string,
            "data_split_digest": string,
            "task_id": string,
            "prompt_sha256": string,
            "condition_id": string,
            "seed": {"type": ["integer", "null"]},
            "capture_site": {"enum": capture_sites},
            "token_span_class": string,
            "metric_name": {"enum": METRIC_NAMES},
            "metric_value": number_or_null,
            "comparator_id": string,
            "artifact_sha256": string,
            "parent_event_ids": string_list,
            "evidence_ids": string_list,
            "repeat_index": {"type": "integer"},
            "effect_margin": number_or_null,
            "ablation_mode": string,
        },
    }


def load_jsonl(path: Path) -> list[dict]:
    events = []
    with path.open() as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    return events
