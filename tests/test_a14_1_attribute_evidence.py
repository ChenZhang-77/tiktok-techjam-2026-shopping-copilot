from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTES = {
    "category", "material", "color", "size", "style", "brand", "budget",
    "feature", "use_case", "other",
}


class A141AttributeEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/a14_1_attribute_evidence.json").read_text(encoding="utf-8")
        )
        cls.artifacts = cls.record["provenance"]["run_artifacts"]
        cls.audit = json.loads(
            (ROOT / cls.artifacts["coverage_audit"]["path"]).read_text(encoding="utf-8")
        )

    def test_inputs_and_reports_are_hash_bound(self) -> None:
        for group in ("inputs", "run_artifacts"):
            for item in self.record["provenance"][group].values():
                path = Path(item["path"])
                self.assertFalse(path.is_absolute())
                self.assertEqual(
                    hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                    item["sha256"],
                )
        self.assertEqual(
            self.audit["code_provenance"],
            {"commit": "4f615f4", "worktree_clean": True},
        )
        for path, digest in self.record["provenance"]["runtime_source_hashes"].items():
            self.assertFalse(Path(path).is_absolute())
            self.assertEqual(len(digest), 64)

    def test_all_ten_attributes_have_explicit_source_and_observed_status(self) -> None:
        matrix = self.audit["attribute_source_matrix"]
        status_counts = self.audit["summary"]["attribute_evidence_status_counts"]
        eligibility_counts = self.audit["summary"]["attribute_eligibility_counts"]
        self.assertEqual(set(matrix), ATTRIBUTES)
        self.assertEqual(set(status_counts), ATTRIBUTES)
        self.assertEqual(set(eligibility_counts), ATTRIBUTES)
        for attribute in ATTRIBUTES:
            self.assertEqual(sum(status_counts[attribute].values()), 649)
            self.assertEqual(sum(eligibility_counts[attribute].values()), 649)
            self.assertTrue(matrix[attribute]["source"])
            self.assertIn(
                matrix[attribute]["status"],
                {"available", "unavailable", "uncalibrated", "not_applicable"},
            )
        self.assertEqual(
            set(self.record["coverage"]["available"]),
            {"category", "material", "color", "style", "use_case"},
        )
        self.assertEqual(set(self.record["coverage"]["unavailable"]), {"size", "brand", "budget"})
        self.assertEqual(self.record["coverage"]["uncalibrated"], ["feature"])
        self.assertEqual(self.record["coverage"]["not_applicable"], ["other"])

    def test_visible_behavior_and_metric_parity_are_exact(self) -> None:
        parity = self.audit["parity"]
        self.assertTrue(parity["exact"])
        self.assertEqual(parity["compared_turns"], 649)
        for key in (
            "session_shape_mismatches", "turn_shape_mismatches",
            "message_mismatches", "recommendation_mismatches",
            "ask_attribute_mismatches",
        ):
            self.assertEqual(parity[key], 0)
        self.assertTrue(parity["input_hashes_match"])
        self.assertTrue(parity["metric_parity"])
        self.assertEqual(self.audit["summary"]["policy_violation_count"], 0)
        self.assertEqual(
            self.audit["visible_response_trace_sha256"],
            self.record["visible_behavior_parity"]["visible_response_trace_sha256"],
        )

    def test_development_folds_reliability_and_latency_derive_from_reports(self) -> None:
        overall = self.record["development_160"]
        raw = json.loads((ROOT / self.artifacts["development"]["path"]).read_text(encoding="utf-8"))
        for evidence_key, report_key in (
            ("sample_count", "sample_count"), ("hit_rate_at_10", "hit_rate_at_10"),
            ("mrr", "mrr"), ("mttc", "mttc"), ("efficiency", "efficiency"),
            ("technical_score", "recommended_technical_score"),
        ):
            self.assertEqual(overall[evidence_key], raw[report_key])
        self.assertEqual(raw["timing"]["responses"]["response_count"], overall["response_count"])
        for key in ("respond_exceptions", "invalid_response_payloads", "reported_fallbacks"):
            self.assertEqual(raw["observed_run_counts"][key], overall[key])
        self.assertEqual(self.audit["summary"]["policy_latency_ms"], overall["policy_latency_ms"])
        for fold_name, expected in self.record["folds"].items():
            fold = json.loads((ROOT / self.artifacts[fold_name]["path"]).read_text(encoding="utf-8"))
            for evidence_key, report_key in (
                ("sample_count", "sample_count"), ("hit_rate_at_10", "hit_rate_at_10"),
                ("mrr", "mrr"), ("mttc", "mttc"), ("efficiency", "efficiency"),
                ("technical_score", "recommended_technical_score"),
            ):
                self.assertEqual(expected[evidence_key], fold[report_key])

    def test_boundaries_and_next_gate_are_explicit(self) -> None:
        boundaries = self.record["boundaries"]
        self.assertFalse(boundaries["visible_behavior_changed"])
        self.assertFalse(boundaries["selection_behavior_changed"])
        self.assertFalse(boundaries["shared_contract_changed"])
        self.assertEqual(boundaries["llm_calls"], 0)
        self.assertEqual(boundaries["full_or_holdout_runs"], 0)
        self.assertIn("Wait for the A13", self.record["next_gate"])
        self.assertFalse(self.audit["protocol"]["full_or_holdout_used"])
        serialized = json.dumps(self.audit, sort_keys=True).lower()
        for forbidden in ("target_asin", "ground_truth", "candidate_text", "user_profile"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
