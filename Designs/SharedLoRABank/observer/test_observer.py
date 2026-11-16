"""Adversarial checks for the concordance lock. No model and no basin claim."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture_probe
import export_obsidian
from ledger import REQUIRED, chain_hash, event_schema, seal, sha256_bytes, validate


SITE = "layers.1.layer_out"


def _defaults(**overrides):
    raw = {
        "schema_version": "0.1.0",
        "run_id": "run-test",
        "time_utc": "2026-11-11T00:00:00Z",
        "node_ids": ["task:probe_synthetic_pair"],
        "edge_type": "changes",
        "status": "observed",
        "claim_class": "measurement",
        "model_sha256": "m" * 64,
        "tokenizer_sha256": "t" * 64,
        "data_split_digest": "d" * 64,
        "task_id": "probe_synthetic_pair",
        "prompt_sha256": "p" * 64,
        "condition_id": "op_a",
        "seed": 0,
        "capture_site": SITE,
        "token_span_class": "last_token",
        "metric_name": "behavior_change",
        "metric_value": 1.0,
        "comparator_id": "none",
        "repeat_index": 0,
        "effect_margin": 0.05,
        "ablation_mode": "none",
        "evidence_ids": [],
        "parent_event_ids": [],
    }
    raw.update(overrides)
    return raw


class Spine:
    def __init__(self, required=("op_a",)):
        self.events = []
        self.artifacts = {}
        manifest = ('{"required_conditions":[' + ",".join(f'"{item}"' for item in required) + "]}")
        self.add(manifest.encode(), **_defaults(
            edge_type="declares",
            metric_name="manifest",
            metric_value=1,
            claim_class="none",
            condition_id="protocol",
            capture_site="run",
            token_span_class="none",
        ))

    def add(self, artifact: bytes, **fields):
        digest = sha256_bytes(artifact)
        self.artifacts[digest] = artifact
        fields = _defaults(**fields)
        fields["sequence"] = len(self.events) + 1
        fields["artifact_sha256"] = digest
        fields["parent_event_ids"] = [] if not self.events else [self.events[-1]["event_id"]]
        sealed = seal(fields)
        self.events.append(sealed)
        return sealed

    def finish(self):
        digest = chain_hash(self.events)
        fields = _defaults(
            edge_type="declares",
            metric_name="end_receipt",
            metric_value=len(self.events),
            claim_class="none",
            condition_id="protocol",
            capture_site="run",
            token_span_class="none",
            comparator_id="event_chain",
        )
        fields["sequence"] = len(self.events) + 1
        fields["artifact_sha256"] = digest
        fields["parent_event_ids"] = [self.events[-1]["event_id"]]
        self.events.append(seal(fields))
        return self

    def check(self, sites=(SITE,)):
        return validate(self.events, {"sites": list(sites)}, self.artifacts)


class ObserverTests(unittest.TestCase):
    def test_residual_rule_keeps_kv(self):
        kv = object()
        self.assertEqual(capture_probe.residual_identity_keep_kv(5, 5, "x", "h", kv, 7), ("x", kv, 7))
        self.assertIs(capture_probe.residual_identity_keep_kv(5, 5, "x", "h", kv, 7)[1], kv)
        self.assertEqual(capture_probe.residual_identity_keep_kv(5, 4, "x", "h", kv, 7), ("h", kv, 7))

    def test_protocol_digest_is_stable(self):
        self.assertEqual(capture_probe.protocol_digest(), capture_probe.protocol_digest())
        self.assertEqual(len(capture_probe.protocol_digest()), 64)

    def test_identical_logits_have_no_kl(self):
        logits = np.array([0.2, -0.4, 1.1])
        self.assertAlmostEqual(capture_probe.kl_nats(logits, logits), 0.0, places=6)

    def test_schema_required_matches_ledger(self):
        schema = event_schema([SITE])
        self.assertEqual(schema["required"], REQUIRED)
        self.assertIn(SITE, schema["properties"]["capture_site"]["enum"])
        self.assertIn("run", schema["properties"]["capture_site"]["enum"])
        self.assertFalse(schema["additionalProperties"])

    def test_legal_critical_and_unnecessary(self):
        critical = Spine()
        left = critical.add(b"c0", metric_value=1.0, repeat_index=0)
        right = critical.add(b"c1", metric_value=0.8, repeat_index=1)
        restored = critical.add(
            b"r",
            edge_type="restores",
            metric_name="behavior_restored",
            metric_value=1,
        )
        critical.add(
            b"claim-c",
            claim_class="critical",
            metric_name="behavior_change",
            metric_value=1,
            evidence_ids=[left["event_id"], right["event_id"], restored["event_id"]],
        )
        self.assertEqual(critical.finish().check(), [])

        quiet = Spine()
        left = quiet.add(b"n0", metric_value=0.01, repeat_index=0)
        right = quiet.add(b"n1", metric_value=0.02, repeat_index=1)
        retained = quiet.add(
            b"keep",
            edge_type="retains",
            metric_name="coding_accuracy_delta",
            metric_value=0.0,
        )
        quiet.add(
            b"claim-u",
            claim_class="unnecessary",
            metric_name="behavior_change",
            metric_value=0.01,
            evidence_ids=[left["event_id"], right["event_id"], retained["event_id"]],
        )
        self.assertEqual(quiet.finish().check(), [])

    def test_logit_kl_cannot_crown_critical(self):
        spine = Spine()
        left = spine.add(b"k0", metric_name="last_token_logit_kl", metric_value=1.2, repeat_index=0)
        right = spine.add(b"k1", metric_name="last_token_logit_kl", metric_value=1.1, repeat_index=1)
        restored = spine.add(b"r", edge_type="restores", metric_name="behavior_restored", metric_value=1)
        spine.add(
            b"nope",
            claim_class="critical",
            metric_name="last_token_logit_kl",
            metric_value=1.2,
            evidence_ids=[left["event_id"], right["event_id"], restored["event_id"]],
        )
        errors = spine.finish().check()
        self.assertTrue(any("concordance pair missing" in error for error in errors))

    def test_low_norm_cannot_prune(self):
        spine = Spine()
        left = spine.add(b"a0", metric_name="activation_norm", metric_value=0.001, repeat_index=0)
        right = spine.add(b"a1", metric_name="activation_norm", metric_value=0.002, repeat_index=1)
        retained = spine.add(b"keep", edge_type="retains", metric_name="coding_accuracy_delta", metric_value=1)
        spine.add(
            b"prune",
            claim_class="unnecessary",
            metric_name="activation_norm",
            metric_value=0.001,
            evidence_ids=[left["event_id"], right["event_id"], retained["event_id"]],
        )
        errors = spine.finish().check()
        self.assertTrue(any("concordance pair missing" in error for error in errors))

    def test_critical_without_restoration_or_agreement(self):
        missing = Spine()
        left = missing.add(b"c0", metric_value=1.0, repeat_index=0)
        right = missing.add(b"c1", metric_value=0.9, repeat_index=1)
        missing.add(
            b"claim",
            claim_class="critical",
            evidence_ids=[left["event_id"], right["event_id"]],
        )
        errors = missing.finish().check()
        self.assertTrue(any("restoration" in error for error in errors))

        split = Spine()
        left = split.add(b"c0", metric_value=1.0, repeat_index=0)
        right = split.add(b"c1", metric_value=0.0, repeat_index=1)
        restored = split.add(b"r", edge_type="restores", metric_name="behavior_restored", metric_value=1)
        split.add(
            b"claim",
            claim_class="critical",
            evidence_ids=[left["event_id"], right["event_id"], restored["event_id"]],
        )
        errors = split.finish().check()
        self.assertTrue(any("concordance pair missing" in error for error in errors))

    def test_unnecessary_retention_must_hold(self):
        dropped = Spine()
        left = dropped.add(b"n0", metric_value=0.01, repeat_index=0)
        right = dropped.add(b"n1", metric_value=0.01, repeat_index=1)
        dropped.add(b"claim", claim_class="unnecessary", evidence_ids=[left["event_id"], right["event_id"]])
        errors = dropped.finish().check()
        self.assertTrue(any("coding retention" in error for error in errors))

        failed = Spine()
        left = failed.add(b"n0", metric_value=0.01, repeat_index=0)
        right = failed.add(b"n1", metric_value=0.01, repeat_index=1)
        retained = failed.add(b"keep", edge_type="retains", metric_name="coding_accuracy_delta", metric_value=-0.2)
        failed.add(
            b"claim",
            claim_class="unnecessary",
            evidence_ids=[left["event_id"], right["event_id"], retained["event_id"]],
        )
        errors = failed.finish().check()
        self.assertTrue(any("retention failed" in error for error in errors))

    def test_hash_duplicate_heldout_and_false_promotion(self):
        spine = Spine().finish()
        broken = [dict(event) for event in spine.events]
        broken[1]["event_hash"] = "ab"
        errors = validate(broken, {"sites": [SITE]}, spine.artifacts)
        self.assertTrue(any("hash mismatch" in error for error in errors))

        duplicated = [dict(event) for event in spine.events]
        duplicated.insert(-1, dict(spine.events[1]))
        errors = validate(duplicated, {"sites": [SITE]}, spine.artifacts)
        self.assertTrue(any("duplicate event_id" in error for error in errors))

        leaked = Spine()
        leaked.add(b"leak", task_id="gold_patch")
        errors = leaked.finish().check()
        self.assertTrue(any("held-out marker" in error for error in errors))

        caused = Spine()
        caused.add(b"assoc", edge_type="elicits", status="observed", claim_class="none", metric_name="behavior_change")
        errors = caused.finish().check()
        self.assertTrue(any("not an observed cause" in error for error in errors))

        routed = Spine()
        routed.add(b"gate", edge_type="routes_to", status="observed", claim_class="none")
        errors = routed.finish().check()
        self.assertTrue(any("routes_to cannot be observed" in error for error in errors))

        selected = Spine()
        selected.add(b"sel", claim_class="selectivity", status="observed")
        errors = selected.finish().check()
        self.assertTrue(any("selectivity cannot be observed" in error for error in errors))

    def test_omitted_condition_and_chain(self):
        omitted = Spine(required=("op_a", "missing_cond")).finish()
        errors = omitted.check()
        self.assertTrue(any("omitted condition missing_cond" in error for error in errors))

        unbound = Spine()
        unbound.finish()
        unbound.events[-1] = seal(_defaults(
            sequence=unbound.events[-1]["sequence"],
            edge_type="declares",
            metric_name="end_receipt",
            metric_value=1,
            claim_class="none",
            condition_id="protocol",
            capture_site="run",
            token_span_class="none",
            artifact_sha256="0" * 64,
            parent_event_ids=[unbound.events[-2]["event_id"]],
        ))
        errors = validate(unbound.events, {"sites": [SITE]}, unbound.artifacts)
        self.assertTrue(any("does not bind" in error for error in errors))

    def test_probe_ledger_records_concordance_without_labels(self):
        hidden = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        clean = np.array([0.0, 0.0])
        ablated = np.array([5.0, 0.0])
        cleans = {}
        ablations = {}
        restorations = {}
        for condition_id, _text in capture_probe.PROMPTS:
            for repeat in capture_probe.REPEATS:
                cleans[(condition_id, repeat)] = {"logits": clean, "hidden": hidden}
                ablations[(3, condition_id, repeat)] = {"logits": ablated}
            restorations[condition_id] = {"logits": clean}
        measurements = {
            "runtime_bytes": b'{"runtime":"fixture"}',
            "layers": [
                {
                    "index": 3,
                    "layer_type": "full_attention",
                    "has_kv": True,
                    "expected_has_kv": True,
                    "config_layer_type": "full_attention",
                    "enable_moe": False,
                }
            ],
            "layer_count_mismatch": False,
            "ablation_layers": [3],
            "sites": ["layers.3.attn_out", "layers.3.layer_out", "layers.3.mlp_out", "layers.3.residual_in"],
            "parity_site": "layers.3.layer_out",
            "cleans": cleans,
            "ablations": ablations,
            "restorations": restorations,
        }
        events, artifacts, catalog = capture_probe.assemble_ledger("run-fixture", "m" * 64, "t" * 64, measurements)
        self.assertEqual(validate(events, catalog, artifacts), [])
        self.assertTrue(all(event["claim_class"] not in {"critical", "unnecessary"} for event in events))
        sides = [event for event in events if event["metric_name"] == "concordance_side"]
        self.assertEqual(len(sides), 2)
        self.assertTrue(all(event["metric_value"] == 1.0 for event in sides))
        parity = next(event for event in events if event["metric_name"] == "deterministic_parity")
        self.assertEqual(parity["metric_value"], 1.0)
        summary = capture_probe.summary_from_ledger(events)
        self.assertEqual(summary["critical_claims"], 0)
        self.assertEqual(summary["unnecessary_claims"], 0)
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            export_obsidian.export_vault(events, catalog, artifacts, vault)
            text = "\n".join(path.read_text() for path in vault.rglob("*.md"))
            for _cid, prompt in capture_probe.PROMPTS:
                self.assertNotIn(prompt, text)
            self.assertIn("Layout and link proximity are not evidence.", text)
            self.assertIn("critical claims admitted: 0", text)
            self.assertIn("unnecessary claims admitted: 0", text)
            broken = events[:-1]
            with self.assertRaises(ValueError):
                export_obsidian.export_vault(broken, catalog, artifacts, Path(tmp) / "refused")


if __name__ == "__main__":
    unittest.main()
