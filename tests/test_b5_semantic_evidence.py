from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS = ("hit_rate_at_10", "mrr", "mttc", "recommended_technical_score")


class B5SemanticEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads((ROOT / "docs/b5_semantic_rerank_cv.json").read_text())
        cls.reports = {
            name: json.loads((ROOT / item["path"]).read_text())
            for name, item in cls.record["raw_reports"].items()
        }

    def test_reports_are_hash_bound_clean_development_runs(self) -> None:
        for name, item in self.record["raw_reports"].items():
            artifact = ROOT / item["path"]
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), item["sha256"])
            report = self.reports[name]
            self.assertEqual(report["code_provenance"]["commit"], self.record["run_code_commit"])
            self.assertTrue(report["code_provenance"]["worktree_clean"])
            self.assertEqual(report["evaluation"]["split"], "development")
            self.assertEqual(report["evaluation"]["retrieval_mode"], "semantic_rerank")
            self.assertEqual(report["evaluation"]["reranker_configuration"]["candidate_limit"], 30)
            self.assertEqual(report["observed_run_counts"]["reported_fallbacks"], 0)

    def test_recorded_development_and_cross_validation_deltas_are_derived(self) -> None:
        structured = json.loads((ROOT / "docs/b2_reports/development_structured.json").read_text())
        semantic = self.reports["development"]
        for metric in METRICS:
            self.assertEqual(self.record["development_160"]["structured"][metric], structured[metric])
            self.assertEqual(self.record["development_160"]["semantic_rerank"][metric], semantic[metric])
            self.assertAlmostEqual(
                self.record["development_160"]["delta_semantic_vs_structured"][metric],
                semantic[metric] - structured[metric],
                places=6,
            )

        deltas = {metric: [] for metric in METRICS}
        wins = losses = 0
        for fold_number in range(1, 5):
            name = f"fold_{fold_number}"
            baseline = json.loads((ROOT / f"docs/b2_reports/{name}_structured.json").read_text())
            report = self.reports[name]
            for metric in METRICS:
                deltas[metric].append(report[metric] - baseline[metric])
            wins += report["recommended_technical_score"] > baseline["recommended_technical_score"]
            losses += report["recommended_technical_score"] < baseline["recommended_technical_score"]
        self.assertEqual(self.record["fixed_cross_validation"]["technical_score_fold_wins"], wins)
        self.assertEqual(self.record["fixed_cross_validation"]["technical_score_fold_losses"], losses)
        for metric in METRICS:
            self.assertAlmostEqual(
                self.record["fixed_cross_validation"]["mean_delta_semantic_vs_structured"][metric],
                sum(deltas[metric]) / 4,
                places=6,
            )

    def test_negative_tradeoffs_keep_structured_as_the_default(self) -> None:
        self.assertEqual(
            self.record["decision"],
            "reject_semantic_rerank_as_runtime_default_retain_as_reproducible_optional_ablation",
        )
        self.assertEqual(self.record["runtime_default"], "structured")
        self.assertEqual(self.record["holdout_status"], "not_run_during_b5")
        self.assertEqual(self.record["full_status"], "not_run_during_b5")
        self.assertLess(self.record["development_160"]["delta_semantic_vs_structured"]["mrr"], 0)
        self.assertLess(
            self.record["scenario_delta_semantic_vs_structured"]["intent_override"]
            ["recommended_technical_score"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
