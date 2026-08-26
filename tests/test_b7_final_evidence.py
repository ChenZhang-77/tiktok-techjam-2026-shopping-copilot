import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "docs" / "b7_final_public_run.json"
SUMMARY_PATH = ROOT / "docs" / "b7_final_public_summary.json"


class B7FinalEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report_bytes = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_bytes)
        cls.summary = json.loads(SUMMARY_PATH.read_text())

    def test_report_is_bound_to_the_frozen_clean_commit(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.report_bytes).hexdigest(),
            "13ffaa619149e27f068961b66079ed494639e3d1a90645ae8bfa064b46a05b3b",
        )
        self.assertEqual(self.report["code_provenance"]["commit"], "98d3325")
        self.assertTrue(self.report["code_provenance"]["worktree_clean"])

    def test_report_is_the_full_structured_run(self) -> None:
        self.assertEqual(self.report["sample_count"], 200)
        self.assertEqual(self.report["evaluation"]["split"], "full")
        self.assertEqual(self.report["evaluation"]["retrieval_mode"], "structured")
        self.assertTrue(self.report["evaluation"]["structured_filter"])
        self.assertEqual(
            set(self.report["scenario_metrics"]),
            {"boundary", "browsing", "buying", "intent_override"},
        )

    def test_final_run_has_no_reported_failures(self) -> None:
        counts = self.report["observed_run_counts"]
        self.assertEqual(counts["respond_exceptions"], 0)
        self.assertEqual(counts["invalid_response_payloads"], 0)
        self.assertEqual(counts["reported_fallbacks"], 0)
        self.assertEqual(counts["internal_fallbacks"], 0)

    def test_summary_discloses_non_confirmatory_protocol(self) -> None:
        protocol = self.summary["protocol"]
        self.assertTrue(protocol["single_final_public_run"])
        self.assertFalse(protocol["separate_holdout_run"])
        self.assertFalse(protocol["post_run_tuning"])
        self.assertFalse(protocol["confirmatory"])
        self.assertEqual(self.summary["report"]["sha256"], hashlib.sha256(self.report_bytes).hexdigest())


if __name__ == "__main__":
    unittest.main()
