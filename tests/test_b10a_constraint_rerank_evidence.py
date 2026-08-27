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


class B10aConstraintRerankEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/b10a_constraint_rerank_evidence.json").read_text(
                encoding="utf-8"
            )
        )
        cls.baseline = json.loads(
            (ROOT / cls.record["baseline"]["report"]).read_text(encoding="utf-8")
        )
        cls.top3 = json.loads(
            (ROOT / cls.record["top3_candidate"]["report"]).read_text(
                encoding="utf-8"
            )
        )
        cls.top5 = json.loads(
            (ROOT / cls.record["top5_candidate"]["report"]).read_text(
                encoding="utf-8"
            )
        )
        cls.parity = json.loads(
            (ROOT / cls.record["default_parity"]["report"]).read_text(
                encoding="utf-8"
            )
        )

    def test_hashes_and_development_only_clean_provenance(self) -> None:
        reports = [
            self.record["baseline"],
            self.record["top3_candidate"],
            self.record["top5_candidate"],
            self.record["default_parity"],
            *self.record["top3_fold_reports"].values(),
        ]
        for report in reports:
            path = ROOT / report.get("report", report.get("path"))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), report["sha256"])
        for report in reports[1:]:
            payload = json.loads(
                (ROOT / report.get("report", report.get("path"))).read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(payload["code_provenance"]["worktree_clean"])
            self.assertEqual(payload["evaluation"]["split"], "development")
        self.assertFalse(self.record["evaluation_boundary"]["full_or_holdout_used"])
        self.assertFalse(
            self.record["evaluation_boundary"]["target_information_in_runtime"]
        )

    def test_both_candidates_fail_the_predeclared_mrr_and_technical_gate(self) -> None:
        for candidate in (self.top3, self.top5):
            self.assertLess(candidate["mrr"], self.baseline["mrr"])
            self.assertLess(
                candidate["recommended_technical_score"],
                self.baseline["recommended_technical_score"],
            )
        fold_deltas = [
            item["technical_score_delta"]
            for item in self.record["top3_fold_reports"].values()
        ]
        self.assertEqual(sum(delta > 0 for delta in fold_deltas), 2)
        self.assertEqual(sum(delta < 0 for delta in fold_deltas), 2)

    def test_top3_route_executed_and_cost_is_bound_to_the_report(self) -> None:
        diagnostics = self.top3["retrieval_diagnostics"]
        self.assertEqual(diagnostics["executed_route_counts"]["semantic_rerank"], 707)
        self.assertEqual(diagnostics["rerank_pool_size"]["mean"], 27.0)
        self.assertEqual(diagnostics["route_failure_counts"], {})
        cost = self.record["top3_cost"]
        self.assertEqual(
            cost["semantic_rerank_mean_ms"],
            self.top3["timing"]["retrieval"]["semantic_rerank_latency"]["mean_ms"],
        )
        self.assertEqual(
            cost["semantic_rerank_max_ms"],
            self.top3["timing"]["retrieval"]["semantic_rerank_latency"]["max_ms"],
        )
        self.assertEqual(cost["peak_rss_bytes"], self.top3["resources"]["peak_rss_bytes"])
        self.assertEqual(self.top3["reported_token_usage"]["total_tokens"], 0)

    def test_current_default_remains_exactly_b9(self) -> None:
        for key in (*METRICS, "scenario_metrics", "sessions"):
            self.assertEqual(self.parity[key], self.baseline[key])
        session_bytes = json.dumps(
            self.parity["sessions"], sort_keys=True, separators=(",", ":")
        ).encode()
        self.assertEqual(
            hashlib.sha256(session_bytes).hexdigest(),
            self.record["default_parity"]["session_outcome_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
