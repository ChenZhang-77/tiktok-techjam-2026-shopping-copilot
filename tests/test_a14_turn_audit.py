from __future__ import annotations

import unittest

from experiments.a14_turn_audit import build_turn_audit


class A14TurnAuditTest(unittest.TestCase):
    def test_builds_a_target_free_question_trace_with_answer_outcomes(self) -> None:
        source = {
            "version": "r0-v3",
            "code_provenance": {"commit": "abc123"},
            "fold_manifest_version": "development-folds-v1",
            "baseline_metrics": {"hit_rate_at_10": 0.9},
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
                            },
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
                            },
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
                            },
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
        self.assertEqual(len(audit["question_trace_sha256"]), 64)
        self.assertNotIn("MUST_NOT_SURVIVE", str(audit))
        self.assertNotIn("target", str(audit).lower())


if __name__ == "__main__":
    unittest.main()
