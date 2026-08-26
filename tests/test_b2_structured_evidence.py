from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class B2StructuredEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads((ROOT / "docs/b2_structured_cv.json").read_text(encoding="utf-8"))

    def test_fixed_folds_support_the_retained_decision(self) -> None:
        cross_validation = self.record["fixed_cross_validation"]
        folds = cross_validation["folds"]

        self.assertEqual(cross_validation["fold_count"], 4)
        self.assertEqual(set(folds), {"fold_1", "fold_2", "fold_3", "fold_4"})
        self.assertTrue(
            all(fold["delta"]["hit_rate_at_10"] == 0.0 for fold in folds.values())
        )
        for metric in ("mrr", "mttc", "recommended_technical_score"):
            observed_mean = round(
                sum(fold["delta"][metric] for fold in folds.values()) / len(folds),
                6,
            )
            self.assertEqual(observed_mean, cross_validation["mean_delta"][metric])

    def test_record_preserves_ablation_and_holdout_boundary(self) -> None:
        self.assertTrue(self.record["structured_config"]["enabled_by_default"])
        self.assertEqual(
            self.record["decision"],
            "retain_guarded_structured_filter_as_default",
        )
        self.assertEqual(self.record["lexical_ablation"], "retained_via_explicit_--lexical-only")
        self.assertEqual(self.record["holdout_status"], "not_run_during_b2")
        self.assertEqual(self.record["full_status"], "not_run_during_b2")

    def test_clean_development_run_has_no_observed_failures(self) -> None:
        development = self.record["development_160"]
        self.assertEqual(development["delta"]["hit_rate_at_10"], 0.0)
        self.assertGreater(development["delta"]["mrr"], 0.0)
        self.assertGreater(development["delta"]["recommended_technical_score"], 0.0)
        self.assertLessEqual(development["delta"]["mttc"], 0.0)
        self.assertTrue(all(value == 0 for value in development["observed_run_counts"].values()))


if __name__ == "__main__":
    unittest.main()
