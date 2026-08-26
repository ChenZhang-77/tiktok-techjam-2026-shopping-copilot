from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class B2StructuredEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads((ROOT / "docs/b2_structured_cv.json").read_text(encoding="utf-8"))
        cls.reports = {
            name: json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
            for name, item in cls.record["raw_reports"].items()
        }

    def test_raw_report_hashes_and_scenario_evidence_are_preserved(self) -> None:
        self.assertEqual(len(self.record["raw_reports"]), 15)
        for name, item in self.record["raw_reports"].items():
            artifact = ROOT / item["path"]
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), item["sha256"])
            report = self.reports[name]
            self.assertEqual(
                set(report["scenario_metrics"]),
                {"boundary", "browsing", "buying", "intent_override"},
            )
            expected_counts = (
                {"boundary": 8, "browsing": 64, "buying": 64, "intent_override": 24}
                if name.startswith("development_")
                else {"boundary": 2, "browsing": 16, "buying": 16, "intent_override": 6}
            )
            self.assertEqual(
                {scenario: metrics["sample_count"] for scenario, metrics in report["scenario_metrics"].items()},
                expected_counts,
            )
            self.assertTrue(all(value == 0 for key, value in report["observed_run_counts"].items() if key != "internal_fallbacks_note"))
            self.assertIn("retrieval", report["timing"])
            self.assertGreater(report["resources"]["peak_rss_bytes"], 0)

    def test_fixed_folds_support_the_incremental_retained_decision(self) -> None:
        cross_validation = self.record["fixed_cross_validation"]
        folds = cross_validation["folds"]

        self.assertEqual(cross_validation["fold_count"], 4)
        self.assertEqual(set(folds), {"fold_1", "fold_2", "fold_3", "fold_4"})
        metrics = ("hit_rate_at_10", "mrr", "mttc", "efficiency", "recommended_technical_score")
        for fold_name, summary in folds.items():
            for mode in ("lexical", "no_guarded_filter", "structured"):
                report = self.reports[f"{fold_name}_{mode}"]
                self.assertEqual(
                    summary[mode],
                    {metric: report[metric] for metric in metrics},
                )
            self.assertEqual(
                summary["structured"]["hit_rate_at_10"],
                summary["no_guarded_filter"]["hit_rate_at_10"],
            )

        for baseline, summary_key in (
            ("lexical", "mean_structured_delta_vs_lexical"),
            ("no_guarded_filter", "mean_structured_delta_vs_no_guarded_filter"),
        ):
            for metric in metrics:
                observed = sum(
                    fold["structured"][metric] - fold[baseline][metric]
                    for fold in folds.values()
                ) / len(folds)
                self.assertAlmostEqual(observed, cross_validation[summary_key][metric], places=7)

    def test_record_preserves_ablation_and_holdout_boundary(self) -> None:
        self.assertTrue(self.record["structured_config"]["enabled_by_default"])
        self.assertEqual(
            self.record["decision"],
            "retain_guarded_structured_filter_as_default",
        )
        self.assertTrue(self.record["modes"]["lexical"].startswith("Pure SQLite FTS5 BM25"))
        self.assertEqual(self.reports["development_lexical"]["evaluation"]["retrieval_mode"], "lexical")
        self.assertEqual(
            self.reports["development_no_guarded_filter"]["evaluation"]["retrieval_mode"],
            "no_guarded_filter",
        )
        self.assertEqual(self.record["holdout_status"], "not_run_during_b2")
        self.assertEqual(self.record["full_status"], "not_run_during_b2")

    def test_clean_development_run_has_no_observed_failures(self) -> None:
        development = self.record["development_160"]
        delta = development["structured_delta_vs_no_guarded_filter"]
        self.assertEqual(delta["hit_rate_at_10"], 0.0)
        self.assertGreater(delta["mrr"], 0.0)
        self.assertGreater(delta["recommended_technical_score"], 0.0)
        self.assertLessEqual(delta["mttc"], 0.0)
        for failures in development["observed_failures_by_mode"].values():
            self.assertTrue(all(value == 0 for value in failures.values()))

    def test_paired_cost_summary_matches_raw_reports(self) -> None:
        costs = self.record["paired_cost_development_160"]
        for mode in ("lexical", "no_guarded_filter", "structured"):
            report = self.reports[f"development_{mode}"]
            expected = {
                "initialization_ms": report["timing"]["initialization_ms"],
                "response_mean_ms": report["timing"]["responses"]["mean_ms"],
                "retrieval_mean_ms": report["timing"]["retrieval"]["latency"]["mean_ms"],
                "lexical_stage_mean_ms": report["timing"]["retrieval"]["lexical_latency"]["mean_ms"],
                "constraint_rerank_stage_mean_ms": report["timing"]["retrieval"]["constraint_rerank_latency"]["mean_ms"],
                "structured_filter_stage_mean_ms": report["timing"]["retrieval"]["structured_filter_latency"]["mean_ms"],
                "peak_rss_bytes": report["resources"]["peak_rss_bytes"],
            }
            self.assertEqual(costs[mode], expected)


if __name__ == "__main__":
    unittest.main()
