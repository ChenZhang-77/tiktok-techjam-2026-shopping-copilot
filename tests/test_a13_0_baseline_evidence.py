from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from evaluator.splits import build_split_manifest, load_jsonl
from experiments.development_folds import build_development_fold_manifest


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
        catalog = load_jsonl(ROOT / "data/catalog.jsonl")
        self.assertEqual(len(catalog), self.record["provenance"]["catalog_rows"])
        self.assertEqual(
            len({str(item["parent_asin"]) for item in catalog}),
            self.record["provenance"]["catalog_unique_parent_asins"],
        )

        public_samples = load_jsonl(ROOT / "data/public_set.jsonl")
        split = json.loads(
            (ROOT / "docs/public_split_v1.json").read_text(encoding="utf-8")
        )
        folds = json.loads(
            (ROOT / "docs/development_folds_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(build_split_manifest(public_samples), split)
        self.assertEqual(
            build_development_fold_manifest(public_samples, split),
            folds,
        )

    def test_raw_reports_are_tracked_and_hash_bound(self) -> None:
        for item in self.record["provenance"]["run_artifacts"].values():
            path = Path(item["path"])
            self.assertFalse(path.is_absolute())
            self.assertEqual(path.parts[0:2], ("docs", "a13_0_reports"))
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                item["sha256"],
            )

    def test_development_metrics_folds_and_reliability_are_bound(self) -> None:
        overall = self.record["development_160"]
        raw_overall = json.loads(
            (ROOT / self.record["provenance"]["run_artifacts"]["development"]["path"])
            .read_text(encoding="utf-8")
        )
        self.assertEqual(overall["sample_count"], 160)
        for evidence_key, report_key in (
            ("sample_count", "sample_count"),
            ("hit_rate_at_10", "hit_rate_at_10"),
            ("mrr", "mrr"),
            ("mttc", "mttc"),
            ("efficiency", "efficiency"),
            ("technical_score", "recommended_technical_score"),
        ):
            self.assertEqual(overall[evidence_key], raw_overall[report_key])
        self.assertEqual(overall["response_count"], 649)
        self.assertEqual(overall["respond_exceptions"], 0)
        self.assertEqual(overall["invalid_response_payloads"], 0)
        self.assertEqual(overall["reported_fallbacks"], 0)
        self.assertEqual(
            {name: fold["sample_count"] for name, fold in self.record["folds"].items()},
            {"fold_1": 40, "fold_2": 40, "fold_3": 40, "fold_4": 40},
        )
        for fold_name, fold in self.record["folds"].items():
            raw_fold = json.loads(
                (
                    ROOT
                    / self.record["provenance"]["run_artifacts"][fold_name]["path"]
                ).read_text(encoding="utf-8")
            )
            for evidence_key, report_key in (
                ("sample_count", "sample_count"),
                ("hit_rate_at_10", "hit_rate_at_10"),
                ("mrr", "mrr"),
                ("mttc", "mttc"),
                ("efficiency", "efficiency"),
                ("technical_score", "recommended_technical_score"),
            ):
                self.assertEqual(fold[evidence_key], raw_fold[report_key])

    def test_refreshed_taxonomy_is_complete_and_target_free(self) -> None:
        taxonomy = self.record["failure_taxonomy"]
        raw_taxonomy = json.loads(
            (ROOT / self.record["provenance"]["run_artifacts"]["taxonomy_json"]["path"])
            .read_text(encoding="utf-8")
        )
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
        self.assertEqual(
            taxonomy["primary_cause_counts"],
            raw_taxonomy["failure_summary"]["primary_cause_counts"],
        )
        self.assertEqual(taxonomy["next_investigation"], raw_taxonomy["next_investigation"])
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

    def test_exact_commands_and_final_suite_result_are_recorded(self) -> None:
        commands = self.record["tests"]["commands_executed"]
        evaluation_commands = [
            command for command in commands if "experiments.evaluation_reporting" in command
        ]
        self.assertEqual(len(evaluation_commands), 5)
        self.assertTrue(any("experiments.failure_taxonomy" in command for command in commands))
        self.assertEqual(self.record["tests"]["full_suite_after_review_fixes"], "304 passed")


if __name__ == "__main__":
    unittest.main()
