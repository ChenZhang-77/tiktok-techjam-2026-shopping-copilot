from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "docs" / "b12_adaptive_depth_evidence.json"


class B12AdaptiveDepthEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    def test_retained_policy_preserves_A_B_ownership_and_bounds(self) -> None:
        self.assertEqual(
            self.record["experiment"]["decision"],
            "retain_bounded_A_owned_adaptive_depth",
        )
        policy = self.record["policy"]
        self.assertEqual(policy["decision_owner"], "A_control_plane")
        self.assertEqual(
            policy["adaptive_gate"],
            {
                "intent": "buying",
                "intent_confidence_band": "high",
                "minimum_active_constraints": 2,
            },
        )
        self.assertEqual(policy["effective_depth"], "max(top_k, selected_depth_floor)")
        self.assertIn("only", policy["B_consumption"])

    def test_aggregate_gate_and_session_effect_are_exact(self) -> None:
        candidate = self.record["candidate"]
        self.assertEqual(
            candidate["delta_vs_b9"],
            {
                "hit_rate_at_10": 0.00625,
                "mrr": 0.002406,
                "mttc": -0.0625,
                "efficiency": 0.00625,
                "recommended_technical_score": 0.005096,
            },
        )
        self.assertEqual(candidate["session_changes"]["gained_hits"], 1)
        self.assertEqual(candidate["session_changes"]["lost_hits"], 0)

    def test_fold_tradeoff_and_cost_are_disclosed(self) -> None:
        folds = self.record["fold_reports"]
        self.assertLess(folds["fold_1"]["technical_score_delta"], 0)
        self.assertEqual(folds["fold_2"]["technical_score_delta"], 0)
        self.assertEqual(folds["fold_3"]["technical_score_delta"], 0)
        self.assertGreater(folds["fold_4"]["technical_score_delta"], 0)
        cost = self.record["cost"]
        self.assertLess(
            cost["candidate_lexical_candidate_mean"],
            cost["baseline_lexical_candidate_mean"],
        )
        self.assertIn("directional", cost["timing_interpretation"])

    def test_reports_are_hash_bound_and_respect_evaluation_boundary(self) -> None:
        files = {
            self.record["baseline"]["report"]: self.record["baseline"]["sha256"],
            self.record["candidate"]["report"]: self.record["candidate"]["sha256"],
        }
        files.update(
            (item["path"], item["sha256"])
            for item in self.record["fold_reports"].values()
        )
        for relative_path, expected in files.items():
            actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative_path)
        boundary = self.record["evaluation_boundary"]
        self.assertFalse(boundary["full_or_holdout_used"])
        self.assertFalse(boundary["target_information_in_runtime"])


if __name__ == "__main__":
    unittest.main()
