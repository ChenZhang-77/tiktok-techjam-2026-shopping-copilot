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


class B8RejectedConstraintEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/b8_rejected_constraint_evidence.json").read_text(
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
            self.record["activation_audit"],
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
            self.assertEqual(payload["code_provenance"]["commit"], "f53a7ee")
            self.assertTrue(payload["code_provenance"]["worktree_clean"])
            self.assertEqual(payload["evaluation"]["split"], "development")
        self.assertFalse(self.record["evaluation_boundary"]["full_or_holdout_used"])
        self.assertFalse(
            self.record["evaluation_boundary"]["target_information_in_runtime"]
        )

    def test_zero_activation_makes_metric_parity_non_evidence(self) -> None:
        for metric in METRICS:
            self.assertEqual(self.baseline[metric], self.candidate[metric])
        self.assertEqual(self.baseline["sessions"], self.candidate["sessions"])
        self.assertEqual(
            self.baseline["scenario_metrics"],
            self.candidate["scenario_metrics"],
        )
        activation = self.record["activation_audit"]
        self.assertEqual(activation["sample_count"], 160)
        self.assertEqual(activation["retrieval_turn_count"], 726)
        self.assertEqual(activation["turns_with_rejected_constraints"], 0)
        self.assertEqual(activation["observed_rejected_constraint_count"], 0)
        self.assertEqual(
            self.record["experiment"]["decision"],
            "do_not_retain_zero_development_coverage",
        )

    def test_all_fixed_folds_preserve_the_ab1_outcomes(self) -> None:
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
            for key in (*METRICS, "sessions", "scenario_metrics"):
                self.assertEqual(baseline[key], candidate[key])


if __name__ == "__main__":
    unittest.main()
