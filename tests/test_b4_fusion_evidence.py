from __future__ import annotations

import hashlib
import json
import statistics
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS = ("hit_rate_at_10", "mrr", "recommended_technical_score")


class B4FusionEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads((ROOT / "docs/b4_fusion_cv.json").read_text(encoding="utf-8"))
        cls.reports = {
            name: json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
            for name, item in cls.record["raw_reports"].items()
        }

    def test_raw_reports_are_immutable_clean_development_evidence(self) -> None:
        self.assertEqual(len(self.reports), 25)
        for name, item in self.record["raw_reports"].items():
            artifact = ROOT / item["path"]
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), item["sha256"])
            report = self.reports[name]
            self.assertEqual(report["code_provenance"], {
                "commit": self.record["run_code_commit"],
                "worktree_clean": True,
            })
            self.assertEqual(report["evaluation"]["split"], "development")
            expected_mode = next(
                mode for mode in ("fusion", "structured", "lexical", "dense") if mode in name
            )
            self.assertEqual(report["evaluation"]["retrieval_mode"], expected_mode)
            if expected_mode == "fusion":
                expected_k = 10.0 if "k10" in name else 60.0
                self.assertEqual(report["evaluation"]["fusion_rrf_k"], expected_k)
                self.assertEqual(
                    report["evaluation"]["fallback_configuration"],
                    {"unavailable_route": "degrade_to_available_routes"},
                )
                self.assertEqual(
                    set(report["retrieval_diagnostics"]["route_overlap_counts"]),
                    {"lexical|structured", "lexical|dense", "structured|dense"},
                )
            if expected_mode in {"fusion", "dense"}:
                dense = report["evaluation"]["dense_configuration"]
                for field in ("model_id", "model_revision", "dimension", "cache_size_bytes", "build_seconds"):
                    self.assertEqual(dense[field], self.record["dense_configuration"][field])
            observed = report["observed_run_counts"]
            self.assertEqual(observed["respond_exceptions"], 0)
            self.assertEqual(observed["invalid_response_payloads"], 0)
            self.assertEqual(observed["reported_fallbacks"], 0)

    def test_fixed_fold_summary_is_derived_from_fusion_and_structured_reports(self) -> None:
        means = {method: {metric: [] for metric in METRICS} for method in (
            "structured",
            "fusion_k10",
            "fusion_k60",
        )}
        wins = 0
        losses = 0
        for fold_number in range(1, 5):
            fold_name = f"fold_{fold_number}"
            reports = {
                "structured": self.reports[f"{fold_name}_structured"],
                "fusion_k10": self.reports[f"{fold_name}_fusion_k10"],
                "fusion_k60": self.reports[f"{fold_name}_fusion_k60"],
            }
            for method, report in reports.items():
                recorded = self.record["fixed_cross_validation"][fold_name][method]
                self.assertEqual(recorded["hit_rate_at_10"], report["hit_rate_at_10"])
                self.assertEqual(
                    recorded["recommended_technical_score"],
                    report["recommended_technical_score"],
                )
                for metric in METRICS:
                    means[method][metric].append(report[metric])
            fusion_score = reports["fusion_k10"]["recommended_technical_score"]
            structured_score = reports["structured"]["recommended_technical_score"]
            wins += fusion_score > structured_score
            losses += fusion_score < structured_score

        recorded_means = self.record["fixed_cross_validation"]["mean"]
        for method, values in means.items():
            for metric, observations in values.items():
                self.assertAlmostEqual(
                    recorded_means[method][metric],
                    statistics.mean(observations),
                    places=6,
                )
        for k in (10, 60):
            method = f"fusion_k{k}"
            delta_key = f"{method}_delta_vs_structured"
            for metric in METRICS:
                self.assertAlmostEqual(
                    recorded_means[delta_key][metric],
                    recorded_means[method][metric] - recorded_means["structured"][metric],
                    places=6,
                )
        self.assertEqual(
            self.record["fixed_cross_validation"]["fusion_k10_technical_score_fold_wins_vs_structured"],
            wins,
        )
        self.assertEqual(
            self.record["fixed_cross_validation"]["fusion_k10_technical_score_fold_losses_vs_structured"],
            losses,
        )

    def test_development_and_cost_summary_match_the_retained_ablation_report(self) -> None:
        report = self.reports["development_fusion_k10"]
        for metric, value in self.record["development_160"]["fusion_k10"].items():
            self.assertEqual(value, report[metric])
        cost = self.record["operational_cost_fusion_k10"]
        self.assertEqual(cost["initialization_ms"], report["timing"]["initialization_ms"])
        self.assertEqual(cost["retrieval_mean_ms"], report["timing"]["retrieval"]["latency"]["mean_ms"])
        self.assertEqual(cost["retrieval_p50_ms"], report["timing"]["retrieval"]["latency"]["p50_ms"])
        self.assertEqual(cost["retrieval_p95_ms"], report["timing"]["retrieval"]["latency"]["p95_ms"])
        self.assertEqual(cost["fusion_mean_ms"], report["timing"]["retrieval"]["fusion_latency"]["mean_ms"])
        self.assertEqual(cost["peak_rss_bytes"], report["resources"]["peak_rss_bytes"])
        route_record = self.record["route_diagnostics_fusion_k10"]
        for route, value in route_record["mean_candidate_count"].items():
            self.assertEqual(
                value,
                report["retrieval_diagnostics"]["route_candidate_counts"][route]["mean"],
            )
        for pair, value in route_record["mean_overlap_count"].items():
            self.assertEqual(
                value,
                report["retrieval_diagnostics"]["route_overlap_counts"][pair]["mean"],
            )
        self.assertEqual(
            route_record["route_failure_counts"],
            report["retrieval_diagnostics"]["route_failure_counts"],
        )

    def test_scenario_deltas_and_hypothesis_are_derived_and_explicit(self) -> None:
        fusion = self.reports["development_fusion_k10"]["scenario_metrics"]
        structured = self.reports["development_structured"]["scenario_metrics"]
        for scenario, recorded in self.record["scenario_comparison_fusion_k10_vs_structured"].items():
            for metric in ("hit_rate_at_10", "mrr", "mttc", "recommended_technical_score"):
                self.assertAlmostEqual(
                    recorded[f"{metric}_delta"],
                    fusion[scenario][metric] - structured[scenario][metric],
                    places=6,
                )
        self.assertIn("RRF", self.record["hypothesis"])

    def test_unfused_ablations_are_hash_bound_and_final_split_is_untouched(self) -> None:
        for name in ("retained_structured", "lexical_only", "dense_only"):
            item = self.record["single_route_and_unfused_ablations"][name]
            artifact = ROOT / item["source"]
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), item["sha256"])
            report = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(report["code_provenance"]["commit"], self.record["run_code_commit"])
            self.assertTrue(report["code_provenance"]["worktree_clean"])
            for metric in METRICS:
                self.assertEqual(item[metric], report[metric])
        self.assertEqual(
            self.record["decision"],
            "retain_fusion_as_optional_ablation_reject_as_runtime_default",
        )
        self.assertEqual(self.record["runtime_default"], "structured")
        self.assertEqual(self.record["protocol"]["holdout_status"], "not_run_during_b4")
        self.assertEqual(self.record["protocol"]["full_status"], "not_run_during_b4")


if __name__ == "__main__":
    unittest.main()
