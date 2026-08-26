from __future__ import annotations

import json
import hashlib
import unittest
from pathlib import Path


class B1ParityEvidenceTest(unittest.TestCase):
    def test_b1_metadata_records_reproducible_provenance_and_decision(self) -> None:
        metadata = json.loads(Path("docs/b1_development_parity.json").read_text(encoding="utf-8"))
        report_bytes = Path(metadata["report_artifact"]).read_bytes()

        self.assertEqual(hashlib.sha256(report_bytes).hexdigest(), metadata["report_artifact_sha256"])
        self.assertEqual(metadata["run_code_commit"], "b66b8ce")
        self.assertFalse(metadata["run_worktree_dirty"])
        self.assertEqual(metadata["split"], "development")
        self.assertEqual(metadata["decision"], "keep_exact_parity_integration")
        self.assertEqual(
            set(metadata["strategy_config"]),
            {
                "buying_depth_sparse",
                "buying_depth_constrained",
                "browsing_depth_sparse",
                "browsing_depth_constrained",
                "buying_lexical_weight",
                "buying_structured_weight",
                "browsing_lexical_weight",
                "browsing_structured_weight",
                "browsing_semantic_weight",
            },
        )
        for field in ("hypothesis", "result", "models"):
            self.assertIn(field, metadata)

    def test_b1_report_exactly_matches_b0_metrics_and_session_outcomes(self) -> None:
        baseline = json.loads(Path("docs/b0_development_baseline.json").read_text(encoding="utf-8"))
        b0_report = json.loads(Path("docs/b0_development_report.json").read_text(encoding="utf-8"))
        b1_report = json.loads(Path("docs/b1_development_parity_report.json").read_text(encoding="utf-8"))

        metric_fields = (
            "sample_count",
            "hit_rate_at_10",
            "mrr",
            "mttc",
            "efficiency",
            "recommended_technical_score",
        )
        self.assertEqual(
            {field: b1_report[field] for field in metric_fields},
            baseline["metrics"],
        )
        self.assertEqual(b1_report["scenario_metrics"], baseline["scenario_metrics"])
        self.assertEqual(b1_report["sessions"], b0_report["sessions"])
        self.assertEqual(
            b1_report["observed_run_counts"],
            {
                "respond_exceptions": 0,
                "invalid_response_payloads": 0,
                "reported_fallbacks": 0,
                "internal_fallbacks": 0,
                "internal_fallbacks_note": (
                    "B1 Agent diagnostics expose fallback_used at the public boundary."
                ),
            },
        )


if __name__ == "__main__":
    unittest.main()
