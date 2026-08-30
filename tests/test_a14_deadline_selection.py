import unittest
import hashlib
import json
from pathlib import Path

from experiments.a14_deadline_selection import SelectionPolicy, score_sessions
from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalResult
from starter.core.state import SessionState
from starter.core.question_policy import QuestionPolicy


class DeadlineSelectionTest(unittest.TestCase):
    def test_bound_evidence_recomputes_all_metrics_and_current_sources(self):
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads((root / "docs/a14_deadline_selection_result.json").read_text())
        folds = json.loads((root / "docs/development_folds_v1.json").read_text())["folds"]
        for mode, sessions in evidence["session_outcomes"].items():
            self.assertEqual(len(sessions), 160)
            for key, value in score_sessions(sessions).items():
                self.assertEqual(evidence["arms"][mode][key], value)
            for fold, members in folds.items():
                self.assertEqual(evidence["arms"][mode]["fixed_folds"][fold],
                    score_sessions([s for s in sessions if s["sample_id"] in members]))
        for path, digest in evidence["runtime_and_evaluator_sha256"].items():
            self.assertEqual(hashlib.sha256((root / path).read_bytes()).hexdigest(), digest)
        self.assertEqual(hashlib.sha256((root / "experiments/a14_deadline_selection.py").read_bytes()).hexdigest(),
                         evidence["summary"]["provenance"]["source_sha256"])
        self.assertTrue(evidence["summary"]["shadow_visible_parity"])
        self.assertFalse(evidence["summary"]["runtime_default_changed"])

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
