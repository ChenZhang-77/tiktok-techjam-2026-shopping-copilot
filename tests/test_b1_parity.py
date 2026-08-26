from __future__ import annotations

import json
import unittest
from pathlib import Path


class B1ParityEvidenceTest(unittest.TestCase):
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
