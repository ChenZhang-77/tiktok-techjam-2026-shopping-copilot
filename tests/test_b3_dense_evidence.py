from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS = ("hit_rate_at_10", "mrr", "mttc", "recommended_technical_score")


class B3DenseEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads((ROOT / "docs/b3_dense_benchmark.json").read_text(encoding="utf-8"))
        cls.cache_metadata = json.loads(
            (ROOT / cls.record["cache_metadata_artifact"]).read_text(encoding="utf-8")
        )
        cls.reports = {
            name: json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
            for name, item in cls.record["raw_reports"].items()
        }

    def test_raw_reports_are_immutable_development_dense_evidence(self) -> None:
        self.assertEqual(len(self.reports), 5)
        for name, item in self.record["raw_reports"].items():
            artifact = ROOT / item["path"]
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), item["sha256"])
            report = self.reports[name]
            self.assertEqual(report["code_provenance"]["commit"], self.record["run_code_commit"])
            self.assertTrue(report["code_provenance"]["worktree_clean"])
            self.assertEqual(report["evaluation"]["retrieval_mode"], "dense")
            self.assertFalse(report["evaluation"]["structured_filter"])
            self.assertEqual(
                report["evaluation"]["fallback_configuration"],
                {"retrieval_mode": "structured", "structured_filter": True},
            )
            self.assertEqual(report["evaluation"]["split"], "development")
            self.assertEqual(
                set(report["scenario_metrics"]),
                {"boundary", "browsing", "buying", "intent_override"},
            )
            observed = report["observed_run_counts"]
            self.assertTrue(
                all(value == 0 for key, value in observed.items() if key != "internal_fallbacks_note"),
                name,
            )

    def test_fold_summary_and_deltas_are_derived_from_raw_reports(self) -> None:
        folds = self.record["fixed_cross_validation"]
        observed_deltas = {metric: [] for metric in METRICS}
        total_complementary_hits = 0
        oracle_union_rates = []

        for fold_number in range(1, 5):
            fold_name = f"fold_{fold_number}"
            summary = folds[fold_name]
            dense = self.reports[f"{fold_name}_dense"]
            structured = json.loads(
                (ROOT / f"docs/b2_reports/{fold_name}_structured.json").read_text(encoding="utf-8")
            )
            self.assertEqual(summary["dense"], {metric: dense[metric] for metric in METRICS})
            self.assertEqual(summary["structured"], {metric: structured[metric] for metric in METRICS})

            dense_hits = {item["sample_id"] for item in dense["sessions"] if item["hit"]}
            structured_hits = {item["sample_id"] for item in structured["sessions"] if item["hit"]}
            complementary_hits = len(dense_hits - structured_hits)
            oracle_union_rate = len(dense_hits | structured_hits) / dense["sample_count"]
            self.assertEqual(summary["dense_only_complementary_hits"], complementary_hits)
            self.assertAlmostEqual(summary["oracle_union_hit_rate_at_10"], oracle_union_rate)
            total_complementary_hits += complementary_hits
            oracle_union_rates.append(oracle_union_rate)

            for metric in METRICS:
                observed_deltas[metric].append(dense[metric] - structured[metric])

        self.assertEqual(folds["complementary_hit_count"], total_complementary_hits)
        self.assertAlmostEqual(
            folds["mean_oracle_union_hit_rate_at_10"],
            sum(oracle_union_rates) / len(oracle_union_rates),
        )
        for metric in METRICS:
            self.assertAlmostEqual(
                folds["mean_dense_delta_vs_structured"][metric],
                sum(observed_deltas[metric]) / len(observed_deltas[metric]),
                places=6,
            )

    def test_development_and_cost_summary_match_raw_report(self) -> None:
        report = self.reports["development_dense"]
        summary = self.record["development_160"]
        for metric in (*METRICS, "efficiency"):
            self.assertEqual(summary[metric], report[metric])
        for key in ("respond_exceptions", "invalid_response_payloads", "reported_fallbacks"):
            self.assertEqual(summary[key], report["observed_run_counts"][key])
        self.assertEqual(summary["initialization_ms"], report["timing"]["initialization_ms"])
        latency = report["timing"]["retrieval"]["dense_latency"]
        self.assertEqual(summary["dense_query_mean_ms_including_cold_start"], latency["mean_ms"])
        self.assertEqual(summary["dense_query_p50_ms"], latency["p50_ms"])
        self.assertEqual(summary["dense_query_p95_ms"], latency["p95_ms"])
        self.assertEqual(summary["dense_query_cold_start_max_ms"], latency["max_ms"])
        self.assertEqual(summary["peak_rss_bytes"], report["resources"]["peak_rss_bytes"])

    def test_cache_metadata_records_reproducible_local_artifacts(self) -> None:
        self.assertEqual(self.cache_metadata["model_id"], "sentence-transformers/all-MiniLM-L6-v2")
        self.assertEqual(
            self.cache_metadata["model_revision"],
            "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        )
        self.assertEqual(self.cache_metadata["dimension"], 384)
        self.assertEqual(self.cache_metadata["dtype"], "float32")
        self.assertTrue(self.cache_metadata["normalized"])
        self.assertEqual(self.cache_metadata["product_count"], 50_000)
        self.assertEqual(
            set(self.cache_metadata["generated_artifact_sha256"]),
            {"metadata.json", "ids.json", "vectors.npy"},
        )
        self.assertEqual(
            self.cache_metadata["ids_sha256"],
            self.cache_metadata["generated_artifact_sha256"]["ids.json"],
        )
        self.assertEqual(
            self.cache_metadata["vectors_sha256"],
            self.cache_metadata["generated_artifact_sha256"]["vectors.npy"],
        )
        self.assertTrue(self.cache_metadata["generated_cache_policy"].startswith("not_committed"))

    def test_operational_paths_match_cache_and_structured_evidence(self) -> None:
        paths = self.record["operational_paths"]
        cache_hit = paths["cache_hit_development_160"]
        development = self.record["development_160"]
        self.assertEqual(cache_hit["reported_fallbacks"], development["reported_fallbacks"])
        self.assertEqual(cache_hit["initialization_ms"], development["initialization_ms"])
        self.assertEqual(cache_hit["dense_query_p50_ms"], development["dense_query_p50_ms"])
        self.assertEqual(cache_hit["peak_rss_bytes"], development["peak_rss_bytes"])

        cache_miss = paths["cache_miss_smoke"]
        cache_miss_artifact = ROOT / cache_miss["artifact"]
        self.assertEqual(
            hashlib.sha256(cache_miss_artifact.read_bytes()).hexdigest(),
            cache_miss["sha256"],
        )
        cache_miss_report = json.loads(cache_miss_artifact.read_text(encoding="utf-8"))
        for key in ("initialization_ms", "query_ms", "route", "fallback_used", "candidate_count"):
            self.assertEqual(cache_miss[key], cache_miss_report[key])
        self.assertIn(cache_miss["reason"], cache_miss_report["notes"])

        structured = json.loads(
            (ROOT / paths["structured_baseline_development_160"]["source"]).read_text(
                encoding="utf-8"
            )
        )
        baseline = paths["structured_baseline_development_160"]
        self.assertEqual(baseline["initialization_ms"], structured["timing"]["initialization_ms"])
        self.assertEqual(
            baseline["retrieval_mean_ms"], structured["timing"]["retrieval"]["latency"]["mean_ms"]
        )
        self.assertEqual(
            baseline["retrieval_p50_ms"], structured["timing"]["retrieval"]["latency"]["p50_ms"]
        )
        self.assertEqual(
            baseline["retrieval_p95_ms"], structured["timing"]["retrieval"]["latency"]["p95_ms"]
        )
        self.assertEqual(baseline["peak_rss_bytes"], structured["resources"]["peak_rss_bytes"])

    def test_decision_keeps_dense_bounded_to_b4_and_preserves_final_split_boundary(self) -> None:
        self.assertEqual(self.record["decision"], "retain_for_b4_fusion_ablation_only_not_default")
        self.assertEqual(self.record["holdout_status"], "not_run_during_b3")
        self.assertEqual(self.record["full_status"], "not_run_during_b3")


if __name__ == "__main__":
    unittest.main()
