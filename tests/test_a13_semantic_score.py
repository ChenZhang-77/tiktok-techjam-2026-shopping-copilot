import unittest
import io
import json
from dataclasses import replace
import time

from experiments.a13_semantic_score import ProcessBackend, TrialAgent, TrialInterpreter
from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalResult
from starter.core.semantic_understanding import (BackendResult, ConstraintEvidence, FakeSemanticBackend,
    SemanticUnderstandingError, UnderstandingRequest)


class FixtureRetriever:
    catalog_ids = frozenset({"A", "B"})
    fallback_ids = ("A", "B")

    def retrieve(self, request):
        return RetrievalResult([Candidate("A"), Candidate("B")],
                              RetrievalDiagnostics(route="fixture", candidate_count=2))


def proposal():
    return {"intent_hint": None, "positive_constraints": [{"attribute": "feature",
            "value": "arch support", "evidence_span": "arch support", "hard": False}],
            "rejected_constraints": [], "no_preference_attributes": [],
            "override_attributes": [], "semantic_terms": [], "abstain": False}


def blocked_provider(connection, key, request):
    time.sleep(10)


class SemanticScoreTest(unittest.TestCase):
    def test_slow_journal_records_final_deadline_disposition(self):
        class SlowJournal(io.StringIO):
            def flush(self): time.sleep(.02)
        journal = SlowJournal()
        backend = FakeSemanticBackend(BackendResult(proposal(), prompt_tokens=100, completion_tokens=50))
        interpreter = TrialInterpreter(backend, journal=journal)
        request = UnderstandingRequest("arch support", 1, deterministic_constraints=(
            ConstraintEvidence("feature", "arch support", confidence=.35),),
            deadline_monotonic_ms=time.monotonic() * 1000 + 5)
        outcome = interpreter.interpret(request)
        self.assertIsNone(outcome.delta)
        final = interpreter.records[-1]
        self.assertEqual(final["fallback_reason"], "deadline_exceeded")
        self.assertEqual(final["status"], "fallback")
        self.assertGreaterEqual(final["latency_ms"], 20)
        self.assertEqual(json.loads(journal.getvalue().splitlines()[-1])["fallback_reason"], "deadline_exceeded")

    def test_journal_failure_cannot_apply_a_prepared_proposal(self):
        class BrokenJournal:
            def write(self, text):
                raise OSError("synthetic log failure")
        backend = FakeSemanticBackend(BackendResult(proposal(), prompt_tokens=100, completion_tokens=50))
        interpreter = TrialInterpreter(backend, journal=BrokenJournal())
        agent = TrialAgent(retriever=FixtureRetriever(), semantic_interpreter=interpreter, candidate=True)
        baseline = TrialAgent(retriever=FixtureRetriever())
        for a in (agent, baseline): a.reset("synthetic", {})
        message = "I need something with arch support"
        actual, expected = agent.respond("synthetic", message, 1, 2), baseline.respond("synthetic", message, 1, 2)
        actual.pop("usage"); expected.pop("usage")
        self.assertEqual(actual, expected)
        self.assertFalse(agent.records[-1]["applied"])
        self.assertEqual(interpreter.stop_reason, "journal_failure")

    def test_expired_and_late_proposals_never_return_a_delta(self):
        class SlowBackend(FakeSemanticBackend):
            def infer(self, request):
                time.sleep(.02)
                return super().infer(request)
        request = UnderstandingRequest("arch support", 1, deterministic_constraints=(
            ConstraintEvidence("feature", "arch support", confidence=.35),))
        for late in (False, True):
            backend_type = SlowBackend if late else FakeSemanticBackend
            backend = backend_type(BackendResult(proposal(), prompt_tokens=100, completion_tokens=50))
            interpreter = TrialInterpreter(backend)
            bounded = replace(request, deadline_monotonic_ms=time.monotonic() * 1000 + (5 if late else -1))
            outcome = interpreter.interpret(bounded)
            self.assertIsNone(outcome.delta)
            self.assertEqual(outcome.fallback_reason, "deadline_exceeded")
            self.assertEqual(backend.calls, int(late))
            self.assertEqual(outcome.prompt_tokens, 100 if late else 0)

    def test_budget_and_repeated_provider_errors_stop_future_calls(self):
        request = UnderstandingRequest("arch support", 1, deterministic_constraints=(
            ConstraintEvidence("feature", "arch support", confidence=.35),))
        for error, count in (("http_401", 1), ("provider_error", 3)):
            backend = FakeSemanticBackend(error=SemanticUnderstandingError(error))
            interpreter = TrialInterpreter(backend)
            for _ in range(4): interpreter.interpret(request)
            self.assertEqual(backend.calls, count)
        for options in ({"max_calls": 0}, {"max_usd": 0}):
            backend = FakeSemanticBackend()
            interpreter = TrialInterpreter(backend, **options)
            self.assertIsNone(interpreter.interpret(request).delta)
            self.assertEqual(backend.calls, 0)

    def test_shadow_preserves_full_agent_behavior_and_duplicate_turn_does_not_recall(self):
        backend = FakeSemanticBackend(BackendResult(proposal(), prompt_tokens=100, completion_tokens=50))
        agent = TrialAgent(retriever=FixtureRetriever(), semantic_interpreter=TrialInterpreter(backend))
        baseline = TrialAgent(retriever=FixtureRetriever())
        for a in (agent, baseline): a.reset("synthetic", {})
        message = "I need something with arch support"
        actual, expected = agent.respond("synthetic", message, 1, 2), baseline.respond("synthetic", message, 1, 2)
        actual.pop("usage"); expected.pop("usage")
        self.assertEqual(actual, expected)
        agent.respond("synthetic", message, 1, 2)
        self.assertEqual(backend.calls, 1)

    def test_no_key_abstain_and_invalid_output_preserve_visible_behavior(self):
        for payload, key in ((proposal(), False), ({**proposal(), "positive_constraints": [], "abstain": True}, True),
                             ({**proposal(), "extra": "ignored"}, True)):
            backend = FakeSemanticBackend(BackendResult(payload, prompt_tokens=100, completion_tokens=50))
            interpreter = TrialInterpreter(backend, key_available=key)
            agent = TrialAgent(retriever=FixtureRetriever(), semantic_interpreter=interpreter, candidate=True)
            baseline = TrialAgent(retriever=FixtureRetriever())
            for a in (agent, baseline): a.reset("synthetic", {})
            actual = agent.respond("synthetic", "I need something with arch support", 1, 2)
            expected = baseline.respond("synthetic", "I need something with arch support", 1, 2)
            actual.pop("usage"); expected.pop("usage")
            self.assertEqual(actual, expected)
            self.assertFalse(agent.records[-1]["applied"])
            if not key: self.assertEqual(backend.calls, 0)

    def test_conflicting_current_no_preference_cannot_be_reversed(self):
        backend = FakeSemanticBackend(BackendResult(proposal(), prompt_tokens=100, completion_tokens=50))
        interpreter = TrialInterpreter(backend)
        request = UnderstandingRequest("arch support", 1,
            deterministic_constraints=(ConstraintEvidence("feature", "arch support", confidence=.35),),
            deterministic_no_preference_attributes=("feature",))
        outcome = interpreter.interpret(request)
        self.assertIsNone(outcome.delta)

    def test_hard_timeout_terminates_provider_and_discards_proposal(self):
        request = UnderstandingRequest("arch support", 1, deterministic_constraints=(
            ConstraintEvidence("feature", "arch support", confidence=.35),))
        backend = ProcessBackend("synthetic", worker=blocked_provider, timeout_seconds=.05)
        interpreter = TrialInterpreter(backend)
        started = time.monotonic()
        outcome = interpreter.interpret(request)
        self.assertIsNone(outcome.delta)
        self.assertEqual(outcome.fallback_reason, "timeout")
        self.assertLess(time.monotonic() - started, 2)

    def test_provider_failure_preserves_agent_and_counts_unknown_cost(self):
        interpreter = TrialInterpreter(FakeSemanticBackend(error=SemanticUnderstandingError("provider_error")))
        agent = TrialAgent(retriever=FixtureRetriever(), semantic_interpreter=interpreter, candidate=True)
        baseline = TrialAgent(retriever=FixtureRetriever())
        for a in (agent, baseline):
            a.reset("synthetic", {})
        message = "I need something with arch support"
        observed = agent.respond("synthetic", message, 1, 2)
        self.assertEqual(observed, baseline.respond("synthetic", message, 1, 2))
        self.assertEqual(interpreter.records[-1]["fallback_reason"], "provider_error")
        self.assertGreater(interpreter.total_cost, 0)

    def test_candidate_applies_validated_feature_at_agent_boundary(self):
        interpreter = TrialInterpreter(FakeSemanticBackend(BackendResult(proposal(), prompt_tokens=100, completion_tokens=50)))
        agent = TrialAgent(retriever=FixtureRetriever(), semantic_interpreter=interpreter, candidate=True)
        agent.reset("synthetic", {})
        response = agent.respond("synthetic", "I need something with arch support", 1, 2)
        self.assertTrue(agent.records[-1]["applied"])
        self.assertEqual([(c["attribute"], c["value"]) for c in response["diagnostics"]["active_constraints"]],
                         [("feature", "arch support")])
        self.assertEqual(response["usage"], {"prompt_tokens": 100, "completion_tokens": 50})
        self.assertEqual([r["parent_asin"] for r in response["recommendations"]], ["A", "B"])
