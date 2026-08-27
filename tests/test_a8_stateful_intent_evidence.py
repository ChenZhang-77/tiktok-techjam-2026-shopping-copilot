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


class A8StatefulIntentEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/a8_stateful_intent_evidence.json").read_text(encoding="utf-8")
        )
        cls.candidate = {
            name: json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
            for name, item in cls.record["raw_reports"].items()
        }
        cls.baseline = {
            name: json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
            for name, item in cls.record["comparator_reports"].items()
        }

    def test_reports_are_hash_bound_clean_development_runs(self) -> None:
        for group_name in ("raw_reports", "comparator_reports"):
            for item in self.record[group_name].values():
                artifact = ROOT / item["path"]
                self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), item["sha256"])
        for name, report in self.candidate.items():
            self.assertEqual(report["code_provenance"]["commit"], self.record["run_code_commit"])
            self.assertTrue(report["code_provenance"]["worktree_clean"])
            self.assertEqual(report["evaluation"]["split"], "development")
            self.assertEqual(
                report["evaluation"]["development_fold"],
                None if name == "development" else name,
            )

    def test_development_metrics_and_deltas_are_derived(self) -> None:
        summary = self.record["development_160"]
        for metric in METRICS:
            self.assertEqual(summary["baseline"][metric], self.baseline["development"][metric])
            self.assertEqual(summary["candidate"][metric], self.candidate["development"][metric])
            self.assertAlmostEqual(
                summary["delta"][metric],
                self.candidate["development"][metric] - self.baseline["development"][metric],
                places=6,
            )
        baseline_sessions = {item["sample_id"]: item for item in self.baseline["development"]["sessions"]}
        gained = []
        lost = []
        changed = 0
        for candidate in self.candidate["development"]["sessions"]:
            baseline = baseline_sessions[candidate["sample_id"]]
            if any(candidate[key] != baseline[key] for key in ("hit", "first_hit_turn", "best_rank", "reciprocal_rank")):
                changed += 1
            if candidate["hit"] and not baseline["hit"]:
                gained.append(candidate["sample_id"])
            if baseline["hit"] and not candidate["hit"]:
                lost.append(candidate["sample_id"])
        self.assertEqual(summary["gained_sessions"], gained)
        self.assertEqual(summary["lost_sessions"], lost)
        self.assertEqual(summary["changed_session_count"], changed)

    def test_fixed_fold_tradeoff_supports_the_bounded_claim(self) -> None:
        cross_validation = self.record["fixed_cross_validation"]
        positive_buying = 0
        for fold in ("fold_1", "fold_2", "fold_3", "fold_4"):
            observed = (
                self.candidate[fold]["recommended_technical_score"]
                - self.baseline[fold]["recommended_technical_score"]
            )
            self.assertAlmostEqual(cross_validation["fold_score_delta"][fold], observed, places=6)
            for scenario, key in (
                ("buying", "buying_score_delta"),
                ("browsing", "browsing_score_delta"),
                ("intent_override", "intent_override_score_delta"),
            ):
                scenario_delta = (
                    self.candidate[fold]["scenario_metrics"][scenario]["recommended_technical_score"]
                    - self.baseline[fold]["scenario_metrics"][scenario]["recommended_technical_score"]
                )
                self.assertAlmostEqual(cross_validation[key][fold], scenario_delta, places=6)
            positive_buying += cross_validation["buying_score_delta"][fold] > 0
            self.assertGreaterEqual(cross_validation["browsing_score_delta"][fold], 0)
        self.assertEqual(positive_buying, 3)

    def test_decision_preserves_scope_and_evaluation_boundary(self) -> None:
        self.assertEqual(
            self.record["decision"],
            "retain_stateful_intent_assessment_with_disclosed_tradeoff",
        )
        self.assertEqual(self.record["contract_change"], "none")
        self.assertEqual(self.record["next_module"], "AB0 DecisionEvidence availability")
        self.assertEqual(self.record["holdout_status"], "not_run_during_A8")
        self.assertEqual(self.record["full_status"], "not_run_during_A8")
        self.assertEqual(self.record["development_160"]["gained_sessions"], [])
        self.assertEqual(self.record["development_160"]["lost_sessions"], [])
        confidence = self.record["confidence_semantics"]
        self.assertEqual(confidence["kind"], "A-owned ordinal stability signal, not a calibrated probability")
        self.assertFalse(confidence["B_side_gate"])


if __name__ == "__main__":
    unittest.main()
