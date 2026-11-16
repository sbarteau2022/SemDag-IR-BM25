"""Project a validated observer ledger into an Obsidian vault.

Layout and link proximity are not evidence. The vault is regenerated from
the ledger. Notes carry prompt hashes, never prompt text.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from ledger import canonical_dumps, load_jsonl, sha256_bytes, validate

ALLOW = (
    "event_id",
    "sequence",
    "edge_type",
    "status",
    "claim_class",
    "capture_site",
    "metric_name",
    "metric_value",
    "condition_id",
    "repeat_index",
    "ablation_mode",
    "prompt_sha256",
    "effect_margin",
    "run_id",
    "event_hash",
)


def _note(event: dict) -> str:
    claims_line = "Layout is not evidence. This note is a projection of one ledger event."
    links = []
    if event["capture_site"] not in {"run", "none"}:
        links.append(f"[[{event['capture_site']}]]")
    for evidence in event["evidence_ids"]:
        links.append(f"[[{evidence}]]")
    body = [f"{key}: {event[key]}" for key in ALLOW]
    return "\n".join(
        [
            "---",
            f"id: {event['event_id']}",
            "kind: event",
            f"status: {event['status']}",
            f"run_id: {event['run_id']}",
            f"digest: {event['event_hash']}",
            "---",
            "",
            f"# {event['event_id']}",
            "",
            claims_line,
            "",
            *body,
            "",
            *links,
            "",
        ]
    )


def export_vault(events, catalog, artifacts, vault: Path) -> Path:
    errors = validate(events, catalog, artifacts)
    if errors:
        raise ValueError("\n".join(errors))
    staging = vault.with_name(vault.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "events").mkdir(parents=True)
    (staging / "sites").mkdir()
    critical = sum(event["claim_class"] == "critical" for event in events)
    unnecessary = sum(event["claim_class"] == "unnecessary" for event in events)
    lines = [
        "---",
        "kind: index",
        f"run_id: {events[0]['run_id']}",
        "---",
        "",
        "# Observer projection",
        "",
        "Layout and link proximity are not evidence. The hashed ledger is the record.",
        "A zero claim count means the label was not admitted. It does not mean a quiet site is unnecessary.",
        "",
        f"critical claims admitted: {critical}",
        f"unnecessary claims admitted: {unnecessary}",
        "",
        "## Sequence",
        "",
    ]
    for event in events:
        (staging / "events" / f"{event['event_id']}.md").write_text(_note(event))
        lines.append(
            f"- {event['sequence']}. [[{event['event_id']}]] {event['edge_type']} "
            f"{event['metric_name']} {event['metric_value']}"
        )
    for site in catalog.get("sites") or []:
        (staging / "sites" / f"{site}.md").write_text(
            "\n".join(
                [
                    "---",
                    f"id: {site}",
                    "kind: site",
                    "status: proposed",
                    "---",
                    "",
                    f"# {site}",
                    "",
                    "Layout is not evidence. A site note does not make the site critical or unnecessary.",
                    "",
                ]
            )
        )
        lines.append(f"- site [[{site}]]")
    (staging / "index.md").write_text("\n".join(lines) + "\n")
    previous = vault.with_name(vault.name + ".previous")
    if previous.exists():
        shutil.rmtree(previous)
    if vault.exists():
        vault.rename(previous)
    staging.rename(vault)
    if previous.exists():
        shutil.rmtree(previous)
    return vault


def _load_artifacts(path: Path) -> dict[str, bytes]:
    artifacts = {}
    for item in path.iterdir():
        if item.is_file():
            blob = item.read_bytes()
            artifacts[sha256_bytes(blob)] = blob
    return artifacts


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: export_obsidian.py ledger.jsonl catalog.json artifacts_dir vault_dir")
        return 2
    events = load_jsonl(Path(sys.argv[1]))
    catalog = __import__("json").loads(Path(sys.argv[2]).read_text())
    try:
        export_vault(events, catalog, _load_artifacts(Path(sys.argv[3])), Path(sys.argv[4]))
    except ValueError as exc:
        print(str(exc))
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
