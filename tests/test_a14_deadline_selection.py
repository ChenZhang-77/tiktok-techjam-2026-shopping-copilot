import unittest

from experiments.a14_deadline_selection import SelectionPolicy, score_sessions
from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalResult
from starter.core.state import SessionState
from starter.core.question_policy import QuestionPolicy


class DeadlineSelectionTest(unittest.TestCase):
    def test_malformed_state_preserves_guarded_legacy_stop(self):
        state = SessionState(session_id="synthetic", user_profile={})
        state.active_constraints = [None]
        args = dict(state=state, result=None, turn=2, top_k=10)
        expected = QuestionPolicy().decide(**args)
        observed = SelectionPolicy(candidate=True).decide(**args)
        self.assertEqual(observed, expected)

    def test_fold_score_uses_official_formula_including_misses(self):
        scored = score_sessions([
            {"hit": True, "reciprocal_rank": 1.0, "first_hit_turn": 1, "scenario_type": "buying"},
            {"hit": False, "reciprocal_rank": 0.0, "first_hit_turn": None, "scenario_type": "buying"},
        ])
        self.assertEqual(scored["recommended_technical_score"], 0.5)
        self.assertEqual(scored["mttc"], 6.0)
        self.assertEqual(scored["efficiency"], 0.5)

    def test_shadow_preserves_legacy_and_candidate_uses_covered_split(self):
        state = SessionState(session_id="synthetic", user_profile={})
        state.intent = "buying"
        state.asked_attributes.add("feature")
        result = RetrievalResult(candidates=[
            Candidate("A", evidence_text="cotton red"),
            Candidate("B", evidence_text="cotton blue"),
            Candidate("C", evidence_text="cotton red"),
            Candidate("D", evidence_text="leather blue"),
        ], diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=4))
        shadow = SelectionPolicy(candidate=False)
        trial = SelectionPolicy(candidate=True)
        args = dict(state=state, result=result, turn=2, top_k=4)
        self.assertEqual(shadow.decide(**args).decision.attribute, "material")
        self.assertEqual(trial.decide(**args).decision.attribute, "color")
        self.assertEqual(state.asked_attributes, {"feature"})

    def test_missing_or_final_turn_evidence_preserves_legacy(self):
        state = SessionState(session_id="synthetic", user_profile={})
        policy = SelectionPolicy(candidate=True)
        self.assertEqual(policy.decide(state=state, result=None, turn=1, top_k=10).decision.attribute, "feature")
        self.assertIsNone(policy.decide(state=state, result=None, turn=10, top_k=10).decision.attribute)
