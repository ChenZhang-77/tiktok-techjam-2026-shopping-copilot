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


class AB1RouteSemanticsEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/ab1_route_semantics_evidence.json").read_text(
                encoding="utf-8"
            )
        )
        cls.baseline = json.loads(
            (ROOT / cls.record["baseline"]["report"]).read_text(encoding="utf-8")
        )
        cls.candidate = json.loads(
            (ROOT / cls.record["candidate"]["report"]).read_text(encoding="utf-8")
        )

    def test_reports_are_hash_bound_clean_development_only_evidence(self) -> None:
        reports = [
            self.record["baseline"],
            self.record["candidate"],
            *self.record["fold_reports"].values(),
        ]
        for report in reports:
            path = ROOT / report.get("report", report.get("path"))
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                report["sha256"],
            )
        for report in [self.record["candidate"], *self.record["fold_reports"].values()]:
            payload = json.loads(
                (ROOT / report.get("report", report.get("path"))).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["code_provenance"]["commit"], "a676855")
            self.assertTrue(payload["code_provenance"]["worktree_clean"])
            self.assertEqual(payload["evaluation"]["split"], "development")
        self.assertFalse(self.record["evaluation_boundary"]["full_or_holdout_used"])
        self.assertFalse(self.record["evaluation_boundary"]["target_information_in_runtime"])

    def test_ab1_preserves_a11_metrics_sessions_scenarios_and_folds(self) -> None:
        for metric in METRICS:
            self.assertEqual(self.baseline[metric], self.candidate[metric])
            self.assertEqual(self.record["candidate"]["metrics"][metric], self.candidate[metric])
        self.assertEqual(self.baseline["sessions"], self.candidate["sessions"])
        self.assertEqual(self.baseline["scenario_metrics"], self.candidate["scenario_metrics"])
        session_bytes = json.dumps(
            self.candidate["sessions"], sort_keys=True, separators=(",", ":")
        ).encode()
        self.assertEqual(
            hashlib.sha256(session_bytes).hexdigest(),
            self.record["candidate"]["session_outcome_sha256"],
        )
        for index in range(1, 5):
            baseline = json.loads(
                (ROOT / f"docs/a11_reports/fold_{index}_scoped_extraction.json").read_text(
                    encoding="utf-8"
                )
            )
            candidate = json.loads(
                (
                    ROOT
                    / self.record["fold_reports"][f"fold_{index}"]["path"]
                ).read_text(encoding="utf-8")
            )
            for key in (*METRICS, "sessions", "scenario_metrics"):
                self.assertEqual(baseline[key], candidate[key])

    def test_default_route_execution_is_truthfully_observed(self) -> None:
        observed = self.candidate["retrieval_diagnostics"]
        recorded = self.record["candidate"]["observed_route_semantics"]

        self.assertEqual(observed["requested_route_counts"], recorded["requested_route_counts"])
        self.assertEqual(observed["executed_route_counts"], recorded["executed_route_counts"])
        self.assertEqual(
            observed["requested_not_executed_route_counts"],
            recorded["requested_not_executed_route_counts"],
        )
        self.assertEqual(observed["fallback_route_counts"], {})
        self.assertEqual(observed["route_semantics_unreported_responses"], 0)
        self.assertEqual(recorded["requested_route_counts"]["dense"], 475)
        self.assertNotIn("dense", recorded["executed_route_counts"])
        self.assertEqual(self.record["next_module"], "B8 Rejected-Constraint Ranking")


if __name__ == "__main__":
    unittest.main()
