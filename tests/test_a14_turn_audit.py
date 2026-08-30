from __future__ import annotations

import copy
import unittest

from experiments.a14_turn_audit import (
    build_turn_audit,
    build_visible_baseline,
    compare_visible_traces,
)


class A14TurnAuditTest(unittest.TestCase):
    def test_summarizes_complete_a14_1_attribute_evidence_without_raw_text(self) -> None:
        attributes = (
            "category", "material", "color", "size", "style", "brand",
            "budget", "feature", "use_case", "other",
        )
        records = {
            attribute: {
                "attribute": attribute,
                "status": "available" if attribute == "material" else "unavailable",
                "source": "bounded_fixture",
                "lifecycle": "current_turn_full_pool",
                "value_range": "bounded",
                "candidate_coverage": 0.5 if attribute == "material" else None,
                "value_count": 2 if attribute == "material" else None,
                "rank_weighted_split": 0.25 if attribute == "material" else None,
                "answerability_status": "canonical_question",
                "actionability_status": "bounded_extractor",
                "comparability_family": (
                    "bounded_candidate_vocabulary_v1"
                    if attribute == "material"
                    else None
                ),
                "eligible": attribute == "material",
                "eligibility_status": (
                    "eligible" if attribute == "material" else "not_in_legacy_priority"
                ),
                "missing_data_behavior": "preserve_legacy_action",
            }
            for attribute in attributes
        }
        source = {
            "sessions": [{
                "sample_id": "public_0001",
                "turns": [{
                    "turn": 1,
                    "ask_attribute": "material",
                    "question_policy_flags": [],
                    "question_policy": {
                        "policy_version": "a14-1-attribute-evidence-v1",
                        "mode": "legacy_action_attribute_evidence",
                        "eligible_attributes": ["material"],
                        "baseline_action": "ask",
                        "baseline_attribute": "material",
                        "reason_code": "legacy_ask",
                        "evidence_status": "available",
                        "latency_ms": 0.1,
                        "attribute_evidence": records,
                    },
                    "message_sha256": "message",
                    "recommendations_sha256": "recommendations",
                    "visible_response_sha256": "visible",
                }],
            }],
        }

        audit = build_turn_audit(source)

        turn_records = audit["sessions"][0]["turns"][0]["attribute_evidence"]
        self.assertEqual(set(turn_records), set(attributes))
        self.assertEqual(
            audit["summary"]["attribute_evidence_status_counts"]["material"],
            {"available": 1},
        )
        self.assertEqual(
            audit["summary"]["attribute_eligibility_counts"]["material"],
            {"eligible": 1},
        )
        self.assertNotIn("candidate_text", str(audit).lower())

    def test_builds_a_target_free_question_trace_with_answer_outcomes(self) -> None:
        source = {
            "version": "r0-v3",
            "code_provenance": {"commit": "abc123"},
            "fold_manifest_version": "development-folds-v1",
            "baseline_metrics": {"hit_rate_at_10": 0.9},
            "observed_run_counts": {"respond_exceptions": 0},
            "input_sha256": {"dataset": "bound"},
            "sessions": [
                {
                    "sample_id": "public_0001",
                    "scenario_type": "Buying",
                    "target_parent_asin": "MUST_NOT_SURVIVE",
                    "turns": [
                        {
                            "turn": 1,
                            "ask_attribute": "feature",
                            "unproductive_reply": False,
                            "active_attributes": ["category"],
                            "no_preference_attributes": [],
                            "rejected_attributes": [],
                            "question_policy_flags": [],
                            "question_policy": {
                                "policy_version": "a14-0-legacy-parity-v1",
                                "mode": "legacy_parity",
                                "eligible_attributes": ["feature", "brand"],
                                "baseline_action": "ask",
                                "baseline_attribute": "feature",
                                "reason_code": "legacy_ask",
                                "evidence_status": "available",
                                "latency_ms": 0.1,
                            },
                            "message_sha256": "message-1",
                            "recommendations_sha256": "recommendations-1",
                            "visible_response_sha256": "visible-1",
                        },
                        {
                            "turn": 2,
                            "ask_attribute": "brand",
                            "unproductive_reply": True,
                            "active_attributes": ["category"],
                            "no_preference_attributes": [],
                            "rejected_attributes": [],
                            "question_policy_flags": [],
                            "question_policy": {
                                "policy_version": "a14-0-legacy-parity-v1",
                                "mode": "legacy_parity",
                                "eligible_attributes": ["brand"],
                                "baseline_action": "ask",
                                "baseline_attribute": "brand",
                                "reason_code": "legacy_ask",
                                "evidence_status": "degraded",
                                "latency_ms": 0.2,
                            },
                            "message_sha256": "message-2",
                            "recommendations_sha256": "recommendations-2",
                            "visible_response_sha256": "visible-2",
                        },
                        {
                            "turn": 3,
                            "ask_attribute": None,
                            "unproductive_reply": False,
                            "active_attributes": ["brand", "category"],
                            "no_preference_attributes": [],
                            "rejected_attributes": [],
                            "question_policy_flags": [],
                            "question_policy": {
                                "policy_version": "a14-0-legacy-parity-v1",
                                "mode": "legacy_parity",
                                "eligible_attributes": [],
                                "baseline_action": "stop",
                                "baseline_attribute": None,
                                "reason_code": "no_eligible_attribute",
                                "evidence_status": "available",
                                "latency_ms": 0.3,
                            },
                            "message_sha256": "message-3",
                            "recommendations_sha256": "recommendations-3",
                            "visible_response_sha256": "visible-3",
                        },
                    ],
                }
            ],
        }

        audit = build_turn_audit(source)

        turns = audit["sessions"][0]["turns"]
        self.assertEqual(
            [turn["answer_outcome"] for turn in turns],
            ["not_applicable", "unproductive", "new_active_evidence"],
        )
        self.assertEqual(audit["summary"]["ask_count"], 2)
        self.assertEqual(audit["summary"]["stop_count"], 1)
        self.assertEqual(audit["summary"]["answer_outcomes"]["unproductive"], 1)
        self.assertEqual(audit["summary"]["unproductive_reply_count"], 1)
        self.assertTrue(turns[1]["unproductive_reply"])
        self.assertEqual(audit["summary"]["policy_latency_ms"]["count"], 3)
        self.assertEqual(len(audit["question_trace_sha256"]), 64)
        self.assertNotIn("MUST_NOT_SURVIVE", str(audit))
        self.assertNotIn("target", str(audit).lower())

    def test_compares_visible_response_hashes_against_an_independent_baseline(self) -> None:
        source = {
            "code_provenance": {"commit": "base"},
            "fold_manifest_version": "development-folds-v1",
            "baseline_metrics": {"hit_rate_at_10": 0.9},
            "input_sha256": {"dataset": "bound"},
            "sessions": [
                {
                    "sample_id": "public_0001",
                    "scenario_type": "Buying",
                    "turns": [
                        {
                            "turn": 1,
                            "ask_attribute": "feature",
                            "unproductive_reply": False,
                            "active_attributes": ["category"],
                            "no_preference_attributes": [],
                            "rejected_attributes": [],
                            "question_policy_flags": [],
                            "question_policy": {
                                "policy_version": "a14-0-legacy-parity-v1",
                                "mode": "legacy_parity",
                                "eligible_attributes": ["feature"],
                                "baseline_action": "ask",
                                "baseline_attribute": "feature",
                                "reason_code": "legacy_ask",
                                "evidence_status": "available",
                                "latency_ms": 0.1,
                            },
                            "message_sha256": "message",
                            "recommendations_sha256": "recommendations",
                            "visible_response_sha256": "visible",
                        }
                    ],
                }
            ],
        }
        baseline = build_visible_baseline(source)
        current = build_turn_audit(source)

        self.assertTrue(compare_visible_traces(baseline, current)["exact"])

        changed = copy.deepcopy(current)
        changed["sessions"][0]["turns"][0]["message_sha256"] = "changed"
        comparison = compare_visible_traces(baseline, changed)
        self.assertFalse(comparison["exact"])
        self.assertEqual(comparison["message_mismatches"], 1)


if __name__ == "__main__":
    unittest.main()
