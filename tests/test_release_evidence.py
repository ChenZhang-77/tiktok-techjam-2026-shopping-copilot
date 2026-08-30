from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from experiments.release_default_audit import score_sessions

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs/release_reports"


class ReleaseEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.reports = {name: json.loads((REPORTS / f"{name}_default.json").read_text())
                        for name in ("p0", "chen", "llm")}

    def test_synthetic_score_and_miss_penalty(self):
        result = score_sessions([
            {"hit": True, "first_hit_turn": 2, "reciprocal_rank": .5, "scenario_type": "buying"},
            {"hit": False, "first_hit_turn": None, "reciprocal_rank": 0, "scenario_type": "buying"},
        ])
        self.assertEqual(result["hit_rate_at_10"], .5)
        self.assertEqual(result["mrr"], .25)
        self.assertEqual(result["mttc"], 6.5)
        self.assertEqual(result["recommended_technical_score"], .415)
        self.assertEqual(score_sessions([])["recommended_technical_score"], 0)

    def test_report_and_runner_hashes(self):
        manifest = json.loads((REPORTS / "manifest.json").read_text())
        self.assertEqual(set(manifest), {"p0_default.json", "chen_default.json", "llm_default.json"})
        for name, expected in manifest.items():
            self.assertEqual(hashlib.sha256((REPORTS / name).read_bytes()).hexdigest(), expected)
        runner_sha = hashlib.sha256((ROOT / "experiments/release_default_audit.py").read_bytes()).hexdigest()
        for report in self.reports.values():
            self.assertEqual(report["provenance"]["runner_sha256"], runner_sha)

    def test_population_inputs_and_reliability(self):
        split = json.loads((ROOT / "docs/public_split_v1.json").read_text())
        folds = json.loads((ROOT / "docs/development_folds_v1.json").read_text())["folds"]
        expected = {item for members in folds.values() for item in members}
        self.assertEqual(len(expected), 160)
        for report in self.reports.values():
            self.assertEqual(len(report["sessions"]), 160)
            self.assertEqual({row["sample_id"] for row in report["sessions"]}, expected)
            self.assertEqual(report["provenance"]["input_sha256"], self.reports["chen"]["provenance"]["input_sha256"])
            self.assertEqual(report["provenance"]["dense_asset_sha256"], self.reports["chen"]["provenance"]["dense_asset_sha256"])
            self.assertEqual(report["provenance"]["external_llm_calls"], 0)
            for key in ("respond_exceptions", "invalid_response_payloads", "reported_fallbacks"):
                self.assertEqual(report["observed_run_counts"][key], 0)
            self.assertEqual(report["retrieval_diagnostics"]["route_failure_counts"], {})
            self.assertGreater(report["retrieval_diagnostics"]["executed_route_counts"]["dense"], 0)
        self.assertEqual(self.reports["chen"]["sessions"], self.reports["llm"]["sessions"])
        self.assertIsInstance(split, dict)

    def test_metrics_recompute_independently(self):
        folds = json.loads((ROOT / "docs/development_folds_v1.json").read_text())["folds"]
        for report in self.reports.values():
            groups = [(report, report["sessions"])]
            groups.extend((report["fixed_folds"][name],
                           [row for row in report["sessions"] if row["sample_id"] in members])
                          for name, members in folds.items())
            groups.extend((metrics, [row for row in report["sessions"] if row["scenario_type"] == name])
                          for name, metrics in report["scenario_metrics"].items())
            for metrics, rows in groups:
                hit_rate = sum(row["hit"] for row in rows) / len(rows)
                mrr = sum(row["reciprocal_rank"] for row in rows) / len(rows)
                mttc = sum(row["first_hit_turn"] if row["first_hit_turn"] is not None else 11 for row in rows) / len(rows)
                self.assertEqual(metrics["sample_count"], len(rows))
                self.assertAlmostEqual(metrics["hit_rate_at_10"], hit_rate, places=6)
                self.assertAlmostEqual(metrics["mrr"], mrr, places=6)
                self.assertAlmostEqual(metrics["mttc"], mttc, places=6)
                expected = .5 * hit_rate + .3 * mrr + .2 * (11 - mttc) / 10
                self.assertLess(abs(metrics["recommended_technical_score"] - expected), .0000011)

    def test_active_source_still_matches_measured_runtime(self):
        # Presence of the parity-only module identifies the llm source family.
        name = "llm" if (ROOT / "starter/core/question_policy.py").exists() else "chen"
        for relative, expected in self.reports[name]["provenance"]["source_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected, relative)


if __name__ == "__main__":
    unittest.main()
