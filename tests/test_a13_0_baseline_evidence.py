from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class A130BaselineEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/a13_0_baseline_evidence.json").read_text(encoding="utf-8")
        )

    def test_inputs_are_hash_bound_to_the_verified_development_protocol(self) -> None:
        for item in self.record["provenance"]["inputs"].values():
            path = ROOT / item["path"]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                item["sha256"],
            )
        self.assertEqual(self.record["provenance"]["catalog_rows"], 50000)
        self.assertEqual(self.record["provenance"]["catalog_unique_parent_asins"], 50000)
        self.assertTrue(self.record["provenance"]["split_exact_rebuild"])
        self.assertTrue(self.record["provenance"]["folds_exact_rebuild"])

    def test_development_metrics_folds_and_reliability_are_bound(self) -> None:
        overall = self.record["development_160"]
        self.assertEqual(overall["sample_count"], 160)
        self.assertEqual(overall["hit_rate_at_10"], 0.925)
        self.assertEqual(overall["mrr"], 0.55276)
        self.assertEqual(overall["mttc"], 4.13125)
        self.assertEqual(overall["technical_score"], 0.765703)
        self.assertEqual(overall["response_count"], 649)
        self.assertEqual(overall["respond_exceptions"], 0)
        self.assertEqual(overall["invalid_response_payloads"], 0)
        self.assertEqual(overall["reported_fallbacks"], 0)
        self.assertEqual(
            {name: fold["sample_count"] for name, fold in self.record["folds"].items()},
            {"fold_1": 40, "fold_2": 40, "fold_3": 40, "fold_4": 40},
        )

    def test_refreshed_taxonomy_is_complete_and_target_free(self) -> None:
        taxonomy = self.record["failure_taxonomy"]
        self.assertEqual(taxonomy["hit_count"], 148)
        self.assertEqual(taxonomy["miss_count"], 12)
        self.assertEqual(taxonomy["classified_miss_count"], 12)
        self.assertEqual(taxonomy["unclassified_invalid_miss_count"], 0)
        self.assertEqual(taxonomy["evaluation_validity_counts"], {})
        self.assertEqual(
            taxonomy["primary_cause_counts"],
            {"question_policy": 10, "state_override": 2},
        )
        self.assertEqual(len(taxonomy["misses"]), 12)
        serialized = json.dumps(taxonomy, sort_keys=True).lower()
        self.assertNotIn("target_asin", serialized)
        self.assertNotIn("ground_truth", serialized)

    def test_stale_a9_recommendation_is_isolated_without_runtime_change(self) -> None:
        disposition = self.record["recommendation_disposition"]
        self.assertFalse(disposition["next_experiment_key_present"])
        self.assertEqual(
            disposition["next_investigation"]["dominant_failure_class"],
            "question_policy",
        )
        self.assertEqual(
            disposition["next_investigation"]["selection_authority"],
            "docs/optimization_roadmap.md",
        )
        self.assertEqual(disposition["historical_a9_status"], "rejected_and_reverted")
        self.assertFalse(self.record["boundaries"]["runtime_behavior_changed"])
        self.assertFalse(self.record["boundaries"]["shared_contract_changed"])
        self.assertFalse(self.record["boundaries"]["route_weight_semantics_changed"])
        self.assertEqual(self.record["boundaries"]["deepseek_api_calls"], 0)
        self.assertEqual(self.record["boundaries"]["full_or_holdout_runs"], 0)


if __name__ == "__main__":
    unittest.main()
