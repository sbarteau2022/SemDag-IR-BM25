"""Adversarial integration checks for the release repo_ir context command."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


BINARY = Path(__file__).resolve().parents[1] / "target/release/repo_ir"


class ContextContractTest(unittest.TestCase):
    def test_reachability_and_flag_scope(self):
        self.assertTrue(BINARY.is_file(), "build with cargo build --release first")
        with tempfile.TemporaryDirectory(prefix="repo-ir-context-") as directory:
            root = Path(directory)
            (root / "api.py").write_text(
                "def entry(payload):\n"
                "    return helper(payload)\n"
                "\n"
                "def request(payload):\n"
                "    return helper(payload)\n"
                "\n"
                "def helper(value):\n"
                "    assert value\n"
                "    return value\n"
                "\n"
                "def orphan():\n"
                "    assert False\n",
                encoding="utf-8",
            )
            run = subprocess.run(
                [str(BINARY), "context", str(root), "--out-dir", str(root / ".ir")],
                capture_output=True, text=True, check=True,
            )
            receipt = json.loads(run.stdout)
            self.assertTrue(receipt["ok"])
            report = json.loads((root / ".ir/context_prob.json").read_text())
            self.assertEqual(report["contextual_flag_count_key"]["vuln_flags"], 2)
            self.assertEqual(report["contextual_flag_count_key"]["reachable_vulns"], 1)
            self.assertEqual(len(report["sources"]), 1)
            self.assertTrue(report["sources"][0].endswith("::request"))
            self.assertTrue(all(row["kind"] == "vuln_flag" for row in report["vulnerable_flags"]))
            self.assertTrue(all(row["score_kind"] == "uncalibrated_heuristic" for row in report["vulnerable_flags"]))
            self.assertTrue(all(row["needed_closures"] == [] for row in report["vulnerable_flags"]))
            self.assertTrue(all(len(row["reachability_paths"]) <= 3 for row in report["vulnerable_flags"]))
            orphan = next(row for row in report["vulnerable_flags"] if row["function_node"].endswith("::orphan"))
            self.assertFalse(orphan["reachable_from_source"])
            self.assertEqual(orphan["contextual_score"], orphan["confidence"])

    def test_same_name_in_other_module_is_not_a_call_edge(self):
        self.assertTrue(BINARY.is_file(), "build with cargo build --release first")
        with tempfile.TemporaryDirectory(prefix="repo-ir-names-") as directory:
            root = Path(directory)
            (root / "entry.py").write_text(
                "def request(value):\n    return helper(value)\n\ndef helper(value):\n    assert value\n",
                encoding="utf-8",
            )
            (root / "other.py").write_text(
                "def helper(value):\n    assert value\n",
                encoding="utf-8",
            )
            subprocess.run(
                [str(BINARY), "context", str(root), "--out-dir", str(root / ".ir")],
                capture_output=True, text=True, check=True,
            )
            report = json.loads((root / ".ir/context_prob.json").read_text())
            by_file = {row["file"]: row for row in report["vulnerable_flags"]}
            self.assertTrue(by_file["entry.py"]["reachable_from_source"])
            self.assertFalse(by_file["other.py"]["reachable_from_source"])


if __name__ == "__main__":
    unittest.main()
