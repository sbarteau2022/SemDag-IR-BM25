#!/usr/bin/env python3
"""Offline validator for the proposed brigade design bundle."""

from __future__ import annotations

import copy
import hashlib
import json
import posixpath
import re
import sys
from pathlib import Path

import jsonschema
import yaml


ALLOWED_TOOLS = {
    "run_command",
    "read_file",
    "edit_file",
    "write_file",
    "get_status",
    "submit_patch",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
}

EXAMPLE_SCHEMAS = {
    "evidence-section.example.json": "evidence-section.schema.json",
    "relational-snapshot.example.json": "relational-snapshot.schema.json",
    "decision-packet.example.json": "decision-packet.schema.json",
    "judge-receipt.example.json": "judge-receipt.schema.json",
}

RUNBOOKS = {
    "C1": "C1-graph-seeds.md",
    "C2": "C2-graph-relations.md",
    "C3": "C3-structural-ir.md",
    "C4": "C4-risk-compliance.md",
    "C5": "C5-edge-coherence.md",
    "C6": "C6-api-contract.md",
    "C7": "C7-relational-snapshot.md",
    "C8": "C8-verification.md",
    "S": "S-synthesis.md",
    "I": "I-implementation.md",
    "F": "F-finalization.md",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict:
    def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, item in pairs:
            require(key not in result, f"{path}: duplicate JSON key {key!r}")
            result[key] = item
        return result

    def reject_constant(value: str) -> None:
        raise AssertionError(f"{path}: non-finite JSON number {value}")

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_pairs,
        parse_constant=reject_constant,
    )
    require(isinstance(value, dict), f"{path}: expected object")
    return value


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def envelope_digest(value: dict, field: str) -> str:
    body = {key: item for key, item in value.items() if key != field}
    encoded = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return digest_bytes(encoded)


def check_digest(value: dict, field: str) -> None:
    require(value[field] == envelope_digest(value, field), f"{field}: digest mismatch")


def safe_path(value: str) -> bool:
    return bool(value) and not value.startswith("/") and "\\" not in value and "\x00" not in value and all(
        part not in ("", ".", "..") for part in value.split("/")
    ) and posixpath.normpath(value) == value


def protected_path(value: str) -> bool:
    parts = value.split("/")
    name = parts[-1]
    return name in {"pytest.ini", "conftest.py"} or name.startswith("test_") or "tests" in parts


def validate_snapshot(snapshot: dict) -> set[str]:
    check_digest(snapshot, "snapshot_sha256")
    refs: set[str] = set()
    file_refs: set[str] = set()
    for row in snapshot["files"]:
        require(row["ref"] not in refs, f"duplicate snapshot ref: {row['ref']}")
        require(safe_path(row["path"]), f"unsafe snapshot path: {row['path']}")
        require(row["end_line"] >= row["start_line"], f"reversed excerpt: {row['ref']}")
        require(
            len(row["exact_source"].splitlines(keepends=True)) == row["end_line"] - row["start_line"] + 1,
            f"line range/excerpt mismatch: {row['ref']}",
        )
        require(
            digest_bytes(row["exact_source"].encode("utf-8")) == row["source_sha256"],
            f"source excerpt digest mismatch: {row['ref']}",
        )
        refs.add(row["ref"])
        file_refs.add(row["ref"])
    for edge in snapshot["relations"]:
        require(edge["ref"] not in refs, f"duplicate snapshot ref: {edge['ref']}")
        for key in ("from_ref", "to_ref"):
            require(edge[key] in file_refs, f"relation endpoint absent: {edge['ref']} {key}")
        require(set(edge["evidence_refs"]) <= file_refs, f"relation evidence absent: {edge['ref']}")
        refs.add(edge["ref"])
    return refs


def validate_evidence(evidence: dict, snapshot: dict, refs: set[str]) -> None:
    check_digest(evidence, "content_sha256")
    require(evidence["task_id"] == snapshot["task_id"], "evidence task mismatch")
    if evidence["compartment"] in {3, 4, 5, 6, 8}:
        require(
            evidence["input_digests"].get(snapshot["snapshot_id"]) == snapshot["snapshot_sha256"],
            "derived evidence lacks exact snapshot input digest",
        )
        require(snapshot["snapshot_id"] in evidence.get("inputs", []), "snapshot absent from declared inputs")
    claim_ids: set[str] = set()
    for claim in evidence["claims"]:
        require(claim["id"] not in claim_ids, f"duplicate evidence claim: {claim['id']}")
        claim_ids.add(claim["id"])
        require(claim["id"].startswith(f"C{evidence['compartment']}:"), "claim/compartment mismatch")
        require(set(claim["snapshot_refs"]) <= refs, f"claim cites absent snapshot ref: {claim['id']}")
        if claim["label"] == "INFERRED":
            require(bool(claim.get("evidence_boundary", "").strip()), "empty inference boundary")
    if evidence["compartment"] == 5:
        relation_refs = {row["ref"] for row in snapshot["relations"]}
        require(all(row["relation_ref"] in relation_refs for row in evidence["payload"]["relations"]), "payload relation absent")


def validate_decision(decision: dict, snapshot: dict, refs: set[str]) -> None:
    check_digest(decision, "packet_sha256")
    require(decision["task_id"] == snapshot["task_id"], "decision task mismatch")
    require(decision["snapshot_id"] == snapshot["snapshot_id"], "decision snapshot id mismatch")
    require(decision["snapshot_sha256"] == snapshot["snapshot_sha256"], "decision snapshot digest mismatch")
    target = decision["target"]
    require(target["snapshot_ref"] in refs, "target snapshot ref absent")
    target_row = next((row for row in snapshot["files"] if row["ref"] == target["snapshot_ref"]), None)
    require(target_row is not None, "target reference must be a file excerpt")
    require(target["path"] == target_row["path"], "target path disagrees with snapshot")
    require(target["symbol"] == target_row["symbol"], "target symbol disagrees with snapshot")
    require(all(safe_path(p) for p in decision["edit_contract"]["allowed_files"]), "unsafe allowed file")
    require(target["path"] in decision["edit_contract"]["allowed_files"], "target not in allowed files")
    require(
        all(not protected_path(p) for p in decision["edit_contract"]["allowed_files"]),
        "protected file in edit contract",
    )
    ids: set[str] = set()
    for claim in decision["outline_claims"]:
        require(claim["id"] not in ids, f"duplicate outline claim: {claim['id']}")
        require(set(claim["snapshot_refs"]) <= refs, f"outline cites absent snapshot ref: {claim['id']}")
        if decision["verdict"] == "implement" and claim.get("critical", True):
            require(claim["verdict"] == "supported", f"critical claim not supported: {claim['id']}")
        ids.add(claim["id"])
    if decision["verdict"] == "implement":
        require(any(row.get("critical", True) for row in decision["outline_claims"]), "implement has no critical claim")


def validate_receipt(receipt: dict) -> None:
    check_digest(receipt, "receipt_sha256")
    if receipt["judge_type"] == "command" and receipt["passed"]:
        require(receipt.get("command") and receipt.get("exit_code") == 0, "passing command lacks zero exit")
    if "stdout_text" in receipt:
        require(digest_bytes(receipt["stdout_text"].encode("utf-8")) == receipt.get("stdout_sha256"), "stdout digest mismatch")
    if "stderr_text" in receipt:
        require(digest_bytes(receipt["stderr_text"].encode("utf-8")) == receipt.get("stderr_sha256"), "stderr digest mismatch")


def validate_controller_ledger(ledger: dict) -> None:
    check_digest(ledger, "ledger_sha256")
    sequences = [event["sequence"] for event in ledger["events"]]
    require(sequences == list(range(1, len(sequences) + 1)), "controller sequence gap or reorder")
    times = [event["monotonic_ms"] for event in ledger["events"]]
    require(times == sorted(times), "controller monotonic time regression")
    calls = [event["tool_calls_total"] for event in ledger["events"]]
    require(calls == sorted(calls), "controller tool-call counter regression")
    for event in ledger["events"]:
        if "supersedes_sequence" in event:
            require(event["supersedes_sequence"] < event["sequence"], "controller correction points forward")
        if event["event"] == "commit":
            require(event["artifact_sha256"] is not None, "committed artifact lacks hash")


def validate_host_export(manifest: dict, ledger: dict) -> None:
    check_digest(manifest, "manifest_sha256")
    require(manifest["task_id"] == ledger["task_id"], "host export task mismatch")
    require(manifest["run_id"] == ledger["run_id"], "host export run mismatch")
    require(manifest["base_commit"] == ledger["base_commit"], "host export base mismatch")
    require(manifest["ledger_sha256"] == ledger["ledger_sha256"], "host export ledger mismatch")
    paths = [row["path"] for row in manifest["artifacts"]]
    require(len(paths) == len(set(paths)), "duplicate host artifact path")
    require(all(safe_path(path) for path in paths), "unsafe host artifact path")
    kinds = {row["kind"] for row in manifest["artifacts"]}
    require({"snapshot", "decision", "judge", "patch", "controller"} <= kinds, "host export missing proof artifact")
    patch_rows = [row for row in manifest["artifacts"] if row["kind"] == "patch"]
    require(len(patch_rows) == 1 and patch_rows[0]["sha256"] == manifest["patch_sha256"], "host patch mismatch")


def validate_implementation_result(result: dict, decision: dict, snapshot: dict) -> None:
    check_digest(result, "result_sha256")
    require(result["task_id"] == snapshot["task_id"] == decision["task_id"], "implementation task mismatch")
    require(result["packet_sha256"] == decision["packet_sha256"], "implementation packet mismatch")
    require(result["snapshot_sha256"] == snapshot["snapshot_sha256"], "implementation snapshot mismatch")
    require(result["base_commit"] == snapshot["base_commit"], "implementation base mismatch")
    paths = [row["path"] for row in result["changed_files"]]
    require(len(paths) == len(set(paths)), "duplicate implementation path")
    require(all(safe_path(path) and not protected_path(path) for path in paths), "unsafe implementation path")
    require(set(paths) <= set(decision["edit_contract"]["allowed_files"]), "implementation path outside contract")
    if result["status"] == "applied":
        require(decision["verdict"] == "implement", "source applied without implement verdict")
        require(all(row["preimage_sha256"] != row["postimage_sha256"] for row in result["changed_files"]), "unchanged file claimed as edit")


def validate_command_receipt(receipt: dict, result: dict) -> None:
    check_digest(receipt, "receipt_sha256")
    require(receipt["task_id"] == result["task_id"], "command task mismatch")
    require(receipt["patch_sha256"] == result["patch_sha256"], "command patch mismatch")
    for key in ("stdout_artifact", "stderr_artifact"):
        require(receipt[key] is None or safe_path(receipt[key]), f"unsafe {key}")
    if receipt["status"] == "passed":
        require(receipt["exit_code"] == 0, "passing command has nonzero exit")
    if receipt["status"] == "skipped":
        require(receipt["exit_code"] is None, "skipped command has exit code")


def validate_examples(root: Path) -> None:
    checker = jsonschema.FormatChecker()
    for example_name, schema_name in sorted(EXAMPLE_SCHEMAS.items()):
        example = load_json(root / "examples" / example_name)
        schema = load_json(root / "schemas" / schema_name)
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(example, schema, format_checker=checker)

    snapshot = load_json(root / "examples" / "relational-snapshot.example.json")
    refs = validate_snapshot(snapshot)
    evidence = load_json(root / "examples" / "evidence-section.example.json")
    decision = load_json(root / "examples" / "decision-packet.example.json")
    receipt = load_json(root / "examples" / "judge-receipt.example.json")
    validate_evidence(evidence, snapshot, refs)
    validate_decision(decision, snapshot, refs)
    validate_receipt(receipt)
    require(receipt["task_id"] == snapshot["task_id"], "receipt task mismatch")


def validate_export_contracts(root: Path) -> None:
    schema = load_json(root / "schemas" / "controller-ledger.schema.json")
    export_schema = load_json(root / "schemas" / "host-export.schema.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator.check_schema(export_schema)
    zero = "0" * 64
    ledger = {
        "schema_version": "0.1.0", "task_id": "example_task", "run_id": "RUN_0001",
        "base_commit": "a" * 40, "model": "gemma-4-e4b-it-qat-w4a16-ct",
        "profile_sha256": zero, "started_at": "2026-11-11T00:00:00Z", "status": "completed",
        "events": [
            {"sequence": 1, "lane": "C7", "event": "start", "status": "partial", "monotonic_ms": 0, "tool_calls_total": 0, "artifact_sha256": None},
            {"sequence": 2, "lane": "C7", "event": "commit", "status": "complete", "monotonic_ms": 25, "tool_calls_total": 1, "artifact_sha256": "1" * 64},
        ], "ledger_sha256": zero,
    }
    ledger["ledger_sha256"] = envelope_digest(ledger, "ledger_sha256")
    jsonschema.validate(ledger, schema, format_checker=jsonschema.FormatChecker())
    validate_controller_ledger(ledger)
    required = ["snapshot", "decision", "judge", "patch", "controller"]
    manifest = {
        "schema_version": "0.1.0", "task_id": ledger["task_id"], "run_id": ledger["run_id"],
        "base_commit": ledger["base_commit"], "patch_sha256": "2" * 64,
        "ledger_sha256": ledger["ledger_sha256"], "captured_at": "2026-11-11T00:01:00Z",
        "artifacts": [
            {"kind": kind, "path": f"{kind}.json", "sha256": "2" * 64 if kind == "patch" else "3" * 64, "size_bytes": 1}
            for kind in required
        ], "manifest_sha256": zero,
    }
    manifest["manifest_sha256"] = envelope_digest(manifest, "manifest_sha256")
    jsonschema.validate(manifest, export_schema, format_checker=jsonschema.FormatChecker())
    validate_host_export(manifest, ledger)
    bad = copy.deepcopy(ledger)
    bad["events"][1]["sequence"] = 3
    bad["ledger_sha256"] = envelope_digest(bad, "ledger_sha256")
    try:
        validate_controller_ledger(bad)
    except AssertionError:
        pass
    else:
        raise AssertionError("controller sequence gap was admitted")
    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["artifacts"][0]["path"] = "../escape.json"
    bad_manifest["manifest_sha256"] = envelope_digest(bad_manifest, "manifest_sha256")
    try:
        validate_host_export(bad_manifest, ledger)
    except AssertionError:
        pass
    else:
        raise AssertionError("host export traversal was admitted")


def validate_edit_and_command_contracts(root: Path) -> None:
    checker = jsonschema.FormatChecker()
    edit_schema = load_json(root / "schemas" / "implementation-result.schema.json")
    command_schema = load_json(root / "schemas" / "command-receipt.schema.json")
    jsonschema.Draft202012Validator.check_schema(edit_schema)
    jsonschema.Draft202012Validator.check_schema(command_schema)
    snapshot = load_json(root / "examples" / "relational-snapshot.example.json")
    decision = load_json(root / "examples" / "decision-packet.example.json")
    result = {
        "schema_version": "0.1.0", "task_id": snapshot["task_id"],
        "packet_sha256": decision["packet_sha256"], "snapshot_sha256": snapshot["snapshot_sha256"],
        "base_commit": snapshot["base_commit"], "status": "applied",
        "changed_files": [{"path": "pkg/module.py", "preimage_sha256": "1" * 64, "postimage_sha256": "2" * 64}],
        "patch_sha256": "3" * 64, "result_sha256": "0" * 64,
    }
    result["result_sha256"] = envelope_digest(result, "result_sha256")
    jsonschema.validate(result, edit_schema, format_checker=checker)
    validate_implementation_result(result, decision, snapshot)
    receipt = {
        "schema_version": "0.1.0", "task_id": snapshot["task_id"], "patch_sha256": result["patch_sha256"],
        "command_id": "CMD:TARGET", "command": "python -m pytest tests/test_module.py -q",
        "started_at": "2026-11-11T00:00:00Z", "duration_ms": 100,
        "exit_code": 0, "status": "passed", "stdout_sha256": "4" * 64,
        "stderr_sha256": "5" * 64, "stdout_artifact": "outputs/target.stdout",
        "stderr_artifact": "outputs/target.stderr", "receipt_sha256": "0" * 64,
    }
    receipt["receipt_sha256"] = envelope_digest(receipt, "receipt_sha256")
    jsonschema.validate(receipt, command_schema, format_checker=checker)
    validate_command_receipt(receipt, result)
    bad = copy.deepcopy(result)
    bad["changed_files"][0]["path"] = "tests/test_module.py"
    bad["result_sha256"] = envelope_digest(bad, "result_sha256")
    try:
        validate_implementation_result(bad, decision, snapshot)
    except AssertionError:
        pass
    else:
        raise AssertionError("protected implementation path admitted")
    bad_receipt = copy.deepcopy(receipt)
    bad_receipt["patch_sha256"] = "6" * 64
    bad_receipt["receipt_sha256"] = envelope_digest(bad_receipt, "receipt_sha256")
    try:
        validate_command_receipt(bad_receipt, result)
    except AssertionError:
        pass
    else:
        raise AssertionError("command receipt for different patch admitted")


def validate_hostile_schema_cases(root: Path) -> None:
    schema = load_json(root / "schemas" / "evidence-section.schema.json")
    valid = load_json(root / "examples" / "evidence-section.example.json")
    attacks = []
    bad = copy.deepcopy(valid)
    bad["compartment"] = 9
    attacks.append(("invalid compartment", bad))
    bad = copy.deepcopy(valid)
    bad["content_sha256"] = "ABC"
    attacks.append(("invalid digest", bad))
    bad = copy.deepcopy(valid)
    bad["claims"][1].pop("evidence_boundary")
    attacks.append(("unbounded inference", bad))
    for name, attack in attacks:
        try:
            jsonschema.validate(attack, schema)
        except jsonschema.ValidationError:
            continue
        raise AssertionError(f"hostile case was admitted: {name}")

    snap_schema = load_json(root / "schemas" / "relational-snapshot.schema.json")
    bad_snap = load_json(root / "examples" / "relational-snapshot.example.json")
    bad_snap["files"][0]["path"] = "../escape.py"
    try:
        jsonschema.validate(bad_snap, snap_schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise AssertionError("hostile case was admitted: path traversal")

    snapshot = load_json(root / "examples" / "relational-snapshot.example.json")
    refs = validate_snapshot(snapshot)
    evidence = load_json(root / "examples" / "evidence-section.example.json")
    decision = load_json(root / "examples" / "decision-packet.example.json")

    def reject(name: str, fn: object) -> None:
        try:
            fn()
        except (AssertionError, StopIteration):
            return
        raise AssertionError(f"hostile semantic case was admitted: {name}")

    bad = copy.deepcopy(evidence)
    bad["input_digests"] = {}
    bad["content_sha256"] = envelope_digest(bad, "content_sha256")
    reject("missing snapshot dependency", lambda: validate_evidence(bad, snapshot, refs))
    bad = copy.deepcopy(evidence)
    bad["claims"].append(copy.deepcopy(bad["claims"][0]))
    bad["content_sha256"] = envelope_digest(bad, "content_sha256")
    reject("duplicate claim", lambda: validate_evidence(bad, snapshot, refs))
    bad = copy.deepcopy(evidence)
    bad["payload"]["relations"][0]["relation_ref"] = "S7:F1"
    bad["content_sha256"] = envelope_digest(bad, "content_sha256")
    reject("file masquerades as relation", lambda: validate_evidence(bad, snapshot, refs))
    bad = copy.deepcopy(decision)
    bad["target"]["snapshot_ref"] = "S7:E1"
    bad["packet_sha256"] = envelope_digest(bad, "packet_sha256")
    reject("edge masquerades as target", lambda: validate_decision(bad, snapshot, refs))
    bad = copy.deepcopy(decision)
    bad["edit_contract"]["allowed_files"].append("tests/test_module.py")
    bad["packet_sha256"] = envelope_digest(bad, "packet_sha256")
    reject("protected edit file", lambda: validate_decision(bad, snapshot, refs))


def validate_lanes(root: Path) -> set[str]:
    cfg = yaml.safe_load((root / "contracts" / "lanes.yaml").read_text())
    lanes = cfg["lanes"]
    ids = [lane["id"] for lane in lanes]
    require(len(ids) == len(set(ids)), "duplicate lane id")
    known = set(ids)
    for lane in lanes:
        require(set(lane.get("depends_on", [])) <= known, f"{lane['id']}: unknown dependency")
        if lane.get("parallel_group"):
            require(lane["mode"] == "read_only", f"{lane['id']}: parallel writer forbidden")
        for output in lane.get("writes", []):
            require(".." not in output and not output.startswith("/"), f"{lane['id']}: unsafe write path")

    visiting: set[str] = set()
    visited: set[str] = set()
    deps = {lane["id"]: lane.get("depends_on", []) for lane in lanes}

    def visit(lane_id: str) -> None:
        require(lane_id not in visiting, f"dependency cycle at {lane_id}")
        if lane_id in visited:
            return
        visiting.add(lane_id)
        for dep in deps[lane_id]:
            visit(dep)
        visiting.remove(lane_id)
        visited.add(lane_id)

    for lane_id in ids:
        visit(lane_id)

    time_total = sum(lane["time_weight_percent"] for lane in lanes)
    time_total += cfg["controller_time_weight_percent"]
    require(time_total == 100, f"time weights total {time_total}, expected 100")
    calls = sum(lane["max_tool_calls_100_profile"] for lane in lanes)
    require(calls <= 100, f"tool ceilings total {calls}, expected <=100")
    writes = [item for lane in lanes for item in lane.get("writes", []) if item != "workspace-source"]
    require(len(writes) == len(set(writes)), "lane output collision")
    for lane_id, filename in RUNBOOKS.items():
        require(lane_id in known, f"runbook lane {lane_id} missing contract")
        require((root / "runbooks" / filename).is_file(), f"missing runbook {filename}")
    return known


def validate_agents(root: Path, lane_ids: set[str]) -> None:
    cfg = yaml.safe_load((root / "contracts" / "agents.yaml").read_text())
    agents = cfg["agents"]
    names = [agent["name"] for agent in agents]
    keys = [agent["output_key"] for agent in agents]
    require(len(names) == len(set(names)), "duplicate agent name")
    require(len(keys) == len(set(keys)), "duplicate output key")
    require({agent["lane"] for agent in agents} == lane_ids, "agent/lane coverage mismatch")
    required_model = cfg["required_model"]
    require(all(agent["model"] == required_model for agent in agents), "mixed model declaration")
    for agent in agents:
        unknown = set(agent.get("tools", [])) - ALLOWED_TOOLS
        require(not unknown, f"{agent['name']}: unknown tools {sorted(unknown)}")
    writers = [agent["name"] for agent in agents if agent["source_write"]]
    submitters = [agent["name"] for agent in agents if "submit_patch" in agent["tools"]]
    require(writers == [cfg["rules"]["sole_source_writer"]], f"wrong source writers: {writers}")
    require(submitters == [cfg["rules"]["sole_submitter"]], f"wrong submitters: {submitters}")
    implementer = next(agent for agent in agents if agent["name"] == writers[0])
    require("submit_patch" not in implementer["tools"], "implementer may not submit")


def validate_four_role_candidate(root: Path, lane_ids: set[str]) -> None:
    cfg = yaml.safe_load((root / "contracts" / "roles.yaml").read_text(encoding="utf-8"))
    roles = cfg["roles"]
    ids = [role["id"] for role in roles]
    require(len(ids) == len(set(ids)) == 4, "four-role candidate must have four unique roles")
    require(all(set(role["tools"]) <= ALLOWED_TOOLS for role in roles), "four-role tool violation")
    require([r["id"] for r in roles if r["source_write"]] == ["lead"], "four-role writer violation")
    require([r["id"] for r in roles if r["submit_patch"]] == ["lead"], "four-role submitter violation")
    require(all(("submit_patch" in r["tools"]) == r["submit_patch"] for r in roles), "submit flag/tool disagreement")
    require([r["id"] for r in roles if r["controller"]] == ["lead"], "four-role controller violation")
    require([r["id"] for r in roles if r["kind"] == "root"] == ["lead"], "four-role root violation")
    mapped = [lane for role in roles for lane in role["lanes"]]
    scripted = [row["lane"] for row in cfg["deterministic_producers"]]
    require(set(mapped + scripted) == lane_ids, "four-role lane coverage mismatch")
    require(len(mapped) == len(set(mapped)), "multiple role owners for one lane")
    require(set(scripted) == {"C7", "S", "F"}, "unexpected deterministic lane ownership")
    require(all(row["host_role"] == "lead" for row in cfg["deterministic_producers"]), "script host must be lead")
    require(all(row["lane"] in {"S", "F"} or row["lane"] not in mapped for row in cfg["deterministic_producers"]), "conflicting producer")


def validate_docs(root: Path) -> None:
    required = [
        "README.md",
        "design.md",
        "brigade-workflow.md",
        "Governing_law.md",
        "RESEARCH.md",
        "PRESSURE_TEST.md",
        "AUDIT.md",
        "packet-contract.yaml",
    ]
    for name in required:
        path = root / name
        require(path.is_file() and path.stat().st_size > 0, f"missing or empty {name}")
    law = (root / "Governing_law.md").read_text(encoding="utf-8")
    for phrase in ("C1 → C2 → C7", "Hash agreement proves identity only", "Exactly one S lane", "submit_patch"):
        require(phrase in law, f"governing law missing phrase: {phrase}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_contracts.py <brigade-root>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    checks = [
        ("documents", lambda: validate_docs(root)),
        ("examples-and-schemas", lambda: validate_examples(root)),
        ("controller-and-export-contracts", lambda: validate_export_contracts(root)),
        ("edit-and-command-contracts", lambda: validate_edit_and_command_contracts(root)),
        ("hostile-schema-cases", lambda: validate_hostile_schema_cases(root)),
    ]
    lane_ids: set[str] = set()

    def lanes_check() -> None:
        nonlocal lane_ids
        lane_ids = validate_lanes(root)

    checks.append(("lane-contract", lanes_check))
    checks.append(("agent-contract", lambda: validate_agents(root, lane_ids)))
    checks.append(("four-role-candidate", lambda: validate_four_role_candidate(root, lane_ids)))
    for name, check in checks:
        check()
        print(f"PASS {name}")
    print("PASS brigade-design-contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
