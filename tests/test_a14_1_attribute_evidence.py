from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess
import unittest
from collections import Counter


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTES = {
    "category", "material", "color", "size", "style", "brand", "budget",
    "feature", "use_case", "other",
}
BOUNDED_ATTRIBUTES = {"category", "material", "color", "style", "use_case"}
SOURCE_BY_ATTRIBUTE = {
    **{
        attribute: "candidate_evidence_text_bounded_vocabulary"
        for attribute in BOUNDED_ATTRIBUTES
    },
    "size": "candidate_field_tags_absent",
    "brand": "candidate_field_tags_absent",
    "budget": "candidate_field_tags_absent",
    "feature": "candidate_evidence_text_unstructured",
    "other": "controlled_legacy_fallback",
}
STATUSES_BY_SOURCE = {
    "candidate_evidence_text_bounded_vocabulary": {
        "available", "partial", "unavailable", "degraded",
    },
    "candidate_evidence_text_unstructured": {
        "unavailable", "uncalibrated", "degraded",
    },
    "candidate_field_tags_absent": {"unavailable"},
    "controlled_legacy_fallback": {"not_applicable"},
}
ELIGIBILITY_STATUSES = {
    "final_turn", "policy_state_invalid", "asked", "no_preference",
    "satisfied", "eligible", "not_in_legacy_priority",
}
LIFECYCLE = "current_turn_full_pool"
VALUE_RANGE = (
    "coverage_and_split_float_0_1;value_count_int_gte_0;"
    "null_when_not_comparable"
)
COMPARABILITY_FAMILY = "bounded_candidate_vocabulary_v1"


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
        cls.turn_audit = json.loads(
            (ROOT / cls.artifacts["turn_audit"]["path"]).read_text(encoding="utf-8")
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
            {"commit": "9d93765", "worktree_clean": True},
        )
        source_commit = self.record["provenance"]["runtime_source_commit"]
        for path, digest in self.record["provenance"]["runtime_source_hashes"].items():
            self.assertFalse(Path(path).is_absolute())
            historical_bytes = subprocess.check_output(
                ["git", "show", f"{source_commit}:{path}"],
                cwd=ROOT,
            )
            self.assertEqual(hashlib.sha256(historical_bytes).hexdigest(), digest)

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

        derived_status = {attribute: Counter() for attribute in ATTRIBUTES}
        derived_eligibility = {attribute: Counter() for attribute in ATTRIBUTES}
        turn_count = 0
        for session in self.turn_audit["sessions"]:
            for turn in session["turns"]:
                turn_count += 1
                records = turn["attribute_evidence"]
                self.assertEqual(set(records), ATTRIBUTES)
                eligible_attributes = set(turn["eligible_attributes"])
                for attribute, item in records.items():
                    self.assertEqual(item["attribute"], attribute)
                    for field in (
                        "source", "lifecycle", "value_range",
                        "answerability_status", "actionability_status",
                        "eligibility_status", "missing_data_behavior",
                    ):
                        self.assertIsInstance(item[field], str)
                        self.assertTrue(item[field].strip())
                    self.assertEqual(item["source"], SOURCE_BY_ATTRIBUTE[attribute])
                    self.assertIn(item["status"], STATUSES_BY_SOURCE[item["source"]])
                    self.assertEqual(item["lifecycle"], LIFECYCLE)
                    self.assertEqual(item["value_range"], VALUE_RANGE)
                    self.assertEqual(
                        item["answerability_status"],
                        "open_text_fallback" if attribute == "other" else "canonical_question",
                    )
                    self.assertEqual(
                        item["actionability_status"],
                        "residual_extractor" if attribute == "other"
                        else "bounded_or_residual_extractor" if attribute == "feature"
                        else "bounded_extractor",
                    )
                    self.assertIn(item["eligibility_status"], ELIGIBILITY_STATUSES)
                    self.assertEqual(item["eligible"], attribute in eligible_attributes)
                    self.assertEqual(
                        item["eligible"], item["eligibility_status"] == "eligible"
                    )
                    for field in ("candidate_coverage", "rank_weighted_split"):
                        value = item[field]
                        self.assertTrue(
                            value is None
                            or (
                                not isinstance(value, bool)
                                and isinstance(value, (int, float))
                                and math.isfinite(value)
                                and 0 <= value <= 1
                            )
                        )
                    value_count = item["value_count"]
                    self.assertTrue(
                        value_count is None
                        or (
                            not isinstance(value_count, bool)
                            and isinstance(value_count, int)
                            and value_count >= 0
                        )
                    )
                    numeric_values = (
                        item["candidate_coverage"],
                        item["value_count"],
                        item["rank_weighted_split"],
                    )
                    if item["status"] in {"available", "partial"}:
                        self.assertEqual(
                            item["comparability_family"], COMPARABILITY_FAMILY
                        )
                        self.assertTrue(all(value is not None for value in numeric_values))
                        if item["status"] == "available":
                            self.assertGreaterEqual(item["value_count"], 2)
                        else:
                            self.assertEqual(item["value_count"], 1)
                    else:
                        self.assertIsNone(item["comparability_family"])
                        self.assertTrue(all(value is None for value in numeric_values))
                    expected_missing = (
                        "comparable_within_family"
                        if item["status"] == "available"
                        else "controlled_legacy_fallback"
                        if item["status"] == "not_applicable"
                        else "preserve_legacy_action"
                    )
                    self.assertEqual(item["missing_data_behavior"], expected_missing)
                    derived_status[attribute][item["status"]] += 1
                    derived_eligibility[attribute][item["eligibility_status"]] += 1
        self.assertEqual(turn_count, 649)
        self.assertEqual(
            {key: dict(sorted(value.items())) for key, value in derived_status.items()},
            status_counts,
        )
        self.assertEqual(
            {
                key: dict(sorted(value.items()))
                for key, value in derived_eligibility.items()
            },
            eligibility_counts,
        )

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
        semantic_sessions = [
            {
                **session,
                "turns": [
                    {key: value for key, value in turn.items() if key != "latency_ms"}
                    for turn in session["turns"]
                ],
            }
            for session in self.turn_audit["sessions"]
        ]
        semantic_digest = hashlib.sha256(
            json.dumps(
                semantic_sessions,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(semantic_digest, self.audit["question_trace_sha256"])
        self.assertEqual(
            semantic_digest,
            self.record["visible_behavior_parity"]["question_trace_sha256"],
        )
        self.assertTrue(
            self.audit["repeatability"]["semantic_question_trace_equal"]
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
        self.assertEqual(
            self.turn_audit["summary"]["policy_latency_ms"],
            overall["policy_latency_ms"],
        )
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
        serialized = json.dumps(self.turn_audit, sort_keys=True).lower()
        for forbidden in ("target_asin", "ground_truth", "candidate_text", "user_profile"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
