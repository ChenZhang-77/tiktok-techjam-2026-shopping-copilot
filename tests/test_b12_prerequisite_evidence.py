from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from starter.core.context_engine import IntentAssessment
from starter.core.planner import plan_strategy
from starter.core.state import SessionState


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "docs" / "b12_prerequisite_evidence.json"


class B12PrerequisiteEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    def test_prerequisite_failure_is_explicit_and_non_behavioral(self) -> None:
        self.assertEqual(
            self.record["decision"],
            "do_not_start_confidence_adaptive_depth_until_A_owned_gate_is_coordinated",
        )
        prerequisites = self.record["prerequisites"]
        self.assertTrue(prerequisites["stable_persistent_intent_assessment"])
        self.assertTrue(prerequisites["typed_retrieval_depth_already_consumed_by_B"])
        self.assertFalse(prerequisites["A8_confidence_authorized_as_B_side_gate"])
        self.assertFalse(prerequisites["AB1_defined_confidence_to_depth_semantics"])
        self.assertFalse(prerequisites["all_required_inputs_satisfied"])
        self.assertEqual(self.record["runtime_files_changed"], [])

    def test_current_depth_mapping_is_described_without_claiming_confidence_use(self) -> None:
        behavior = self.record["current_behavior"]
        self.assertEqual(behavior["mapping_inputs"], ["intent", "active_constraint_count"])
        self.assertEqual(
            behavior["mapping_does_not_use"],
            ["IntentAssessment.confidence", "IntentAssessment.confidence_band"],
        )
        self.assertEqual(
            behavior["default_depths"],
            {
                "buying_sparse": 60,
                "buying_constrained": 80,
                "browsing_sparse": 120,
                "browsing_constrained": 100,
            },
        )
        contract = self.record["contract_evidence"]
        self.assertFalse(contract["A8_B_side_gate"])
        self.assertFalse(contract["AB1_request_schema_changed"])

        a8 = json.loads(
            (ROOT / "docs" / "a8_stateful_intent_evidence.json").read_text(
                encoding="utf-8"
            )
        )
        ab1 = json.loads(
            (ROOT / "docs" / "ab1_route_semantics_evidence.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(a8["confidence_semantics"]["B_side_gate"])
        self.assertFalse(ab1["shared_contract"]["request_schema_changed"])
        self.assertFalse(
            ab1["shared_contract"]["strategy_weight_semantics_changed"]
        )

    def test_current_planner_does_not_turn_confidence_into_depth(self) -> None:
        depths = []
        for confidence in (0.60, 0.72, 0.90):
            state = SessionState(session_id=f"confidence-{confidence}", user_profile={})
            state.set_intent_assessment(
                IntentAssessment(
                    intent="buying",
                    confidence=confidence,
                    evidence=(),
                    source_turn=1,
                    transition_reason="accumulated",
                )
            )
            depths.append(plan_strategy(state, turn=1, top_k=10).retrieval_depth)
        self.assertEqual(depths, [60, 60, 60])

    def test_evaluation_boundary_and_source_hashes_are_reproducible(self) -> None:
        boundary = self.record["evaluation_boundary"]
        self.assertFalse(boundary["development_160_behavior_run"])
        self.assertFalse(boundary["fixed_fold_behavior_runs"])
        self.assertFalse(boundary["holdout_or_full_used"])
        self.assertFalse(boundary["target_information_used"])
        for relative_path, expected in self.record["file_sha256"].items():
            actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative_path)


if __name__ == "__main__":
    unittest.main()
