from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS = (
    "hit_rate_at_10",
    "mrr",
    "mttc",
    "efficiency",
    "recommended_technical_score",
)


class B9ConditionalDenseEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/b9_conditional_dense_evidence.json").read_text(
                encoding="utf-8"
            )
        )
        cls.baseline = json.loads(
            (ROOT / cls.record["baseline"]["report"]).read_text(encoding="utf-8")
        )
        cls.candidate = json.loads(
            (ROOT / cls.record["candidate"]["report"]).read_text(encoding="utf-8")
        )

    def test_hashes_and_clean_development_only_provenance(self) -> None:
        reports = [
            self.record["baseline"],
            self.record["candidate"],
            *self.record["fold_reports"].values(),
        ]
        for report in reports:
            path = ROOT / report.get("report", report.get("path"))
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                report["sha256"],
            )
        for report in [self.record["candidate"], *self.record["fold_reports"].values()]:
            payload = json.loads(
                (ROOT / report.get("report", report.get("path"))).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["code_provenance"]["commit"], "b620357")
            self.assertTrue(payload["code_provenance"]["worktree_clean"])
            self.assertEqual(payload["evaluation"]["split"], "development")
        self.assertFalse(self.record["evaluation_boundary"]["full_or_holdout_used"])
        self.assertFalse(
            self.record["evaluation_boundary"]["target_information_in_runtime"]
        )

    def test_quality_gate_is_browsing_only_and_fold_safe(self) -> None:
        self.assertEqual(
            self.candidate["hit_rate_at_10"], self.baseline["hit_rate_at_10"]
        )
        self.assertGreater(self.candidate["mrr"], self.baseline["mrr"])
        self.assertGreater(
            self.candidate["recommended_technical_score"],
            self.baseline["recommended_technical_score"],
        )
        for scenario in ("buying", "intent_override", "boundary"):
            self.assertEqual(
                self.candidate["scenario_metrics"][scenario],
                self.baseline["scenario_metrics"][scenario],
            )
        for index in range(1, 5):
            baseline = json.loads(
                (ROOT / f"docs/ab1_reports/fold_{index}_route_semantics.json").read_text(
                    encoding="utf-8"
                )
            )
            candidate = json.loads(
                (
                    ROOT
                    / self.record["fold_reports"][f"fold_{index}"]["path"]
                ).read_text(encoding="utf-8")
            )
            self.assertGreaterEqual(
                candidate["recommended_technical_score"],
                baseline["recommended_technical_score"],
            )

    def test_dense_route_is_actually_executed_without_fallback(self) -> None:
        diagnostics = self.candidate["retrieval_diagnostics"]
        self.assertEqual(diagnostics["executed_route_counts"]["dense"], 102)
        self.assertEqual(diagnostics["executed_route_counts"]["fusion"], 102)
        self.assertEqual(diagnostics["fallback_route_counts"], {})
        self.assertEqual(diagnostics["route_failure_counts"], {})
        self.assertEqual(diagnostics["route_semantics_unreported_responses"], 0)
        self.assertEqual(self.candidate["observed_run_counts"]["reported_fallbacks"], 0)

    def test_cost_is_disclosed_not_hidden(self) -> None:
        cost = self.record["cost"]
        self.assertGreater(
            cost["candidate_peak_rss_bytes"], cost["baseline_peak_rss_bytes"]
        )
        self.assertGreater(
            cost["candidate_initialization_ms"], cost["baseline_initialization_ms"]
        )
        self.assertLess(cost["candidate_retrieval_max_ms"], 250.0)


if __name__ == "__main__":
    unittest.main()
