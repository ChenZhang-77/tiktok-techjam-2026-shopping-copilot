import unittest
import hashlib
import json
from http.client import IncompleteRead
from pathlib import Path
from statistics import fmean
from dataclasses import replace
from unittest.mock import Mock

from experiments.b10b_full_rerank import BudgetedRanker, ProductReranker, TracedAgent
from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalRequest, RetrievalResult
from starter.core.planner import Strategy
from starter.retrieval.semantic_ranker import (FakeSemanticRanker, ModelUsage,
    SemanticRankError, SemanticRankItem, SemanticRankOutcome, SemanticRankRequest)


class BaseRetriever:
    catalog_ids = frozenset({"A", "B", "C", "D"})
    fallback_ids = ("A", "B", "C", "D")

    def retrieve(self, request):
        return RetrievalResult(
            candidates=[Candidate(i, evidence_text="cotton blue shoes") for i in self.fallback_ids],
            diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=4),
        )


def request():
    return RetrievalRequest(session_id="synthetic", turn=1, top_k=3,
        query="blue shoes", intent="browsing", strategy=Strategy(
            intent="browsing", lexical_weight=.6, structured_weight=.2,
            semantic_weight=.2, retrieval_depth=10, allow_hard_filter=False,
            clarification_enabled=True, fallback_mode="broad_lexical", reason="synthetic"))


class FullRerankTest(unittest.TestCase):
    def test_bound_evidence_recomputes_metrics_and_frozen_sources(self):
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads((root / "docs/b10b_full_rerank_result.json").read_text())
        folds = json.loads((root / "docs/development_folds_v1.json").read_text())["folds"]
        expected = set().union(*map(set, folds.values()))
        for mode, rows in evidence["session_outcomes"].items():
            self.assertEqual(len(rows), 160)
            self.assertEqual({r["sample_id"] for r in rows}, expected)
            groups = [(rows, evidence["arms"][mode])]
            groups += [([r for r in rows if r["sample_id"] in members],
                        evidence["arms"][mode]["fixed_folds"][fold]) for fold, members in folds.items()]
            for sessions, reported in groups:
                hr = round(sum(r["hit"] for r in sessions) / len(sessions), 6)
                mrr = round(fmean(0 if r["best_rank"] is None else 1 / r["best_rank"] for r in sessions), 6)
                mttc = round(fmean(r["first_hit_turn"] if r["hit"] else 11 for r in sessions), 6)
                score = round(.5 * hr + .3 * mrr + .2 * (11 - mttc) / 10, 6)
                for key, value in (("hit_rate_at_10", hr), ("mrr", mrr), ("mttc", mttc),
                                   ("recommended_technical_score", score)):
                    self.assertEqual(reported[key], value)
        for path, digest in evidence["provenance"]["source_sha256"].items():
            self.assertEqual(hashlib.sha256((root / path).read_bytes()).hexdigest(), digest)
        all_pass = all(c["passes"] for c in evidence["comparisons"].values())
        self.assertEqual(evidence["recommendation"] == "retain_as_opt_in_candidate",
                         all_pass and "repeat" in evidence["comparisons"])
        self.assertFalse(evidence["runtime_default_changed"])

    def test_truncated_transport_falls_back_and_trips_error_limit(self):
        backend = Mock()
        backend.rank.side_effect = IncompleteRead(b"partial")
        ledger = BudgetedRanker(backend)
        retriever = ProductReranker(BaseRetriever(), ledger)
        for _ in range(4):
            result = retriever.retrieve(request())
            self.assertEqual([c.parent_asin for c in result.candidates], ["A", "B", "C", "D"])
            self.assertTrue(result.diagnostics.fallback_used)
        self.assertEqual(backend.rank.call_count, 3)
        self.assertTrue(all(r["failure"] for r in ledger.records))
        self.assertEqual(ledger.stop_reason, "consecutive_errors")

    def test_cost_auth_and_consecutive_errors_stop_calls(self):
        item_request = SemanticRankRequest("shoes", (), (SemanticRankItem("c0", "blue"),))
        for error, count in (("http_401", 1), ("provider_error", 3)):
            backend = Mock()
            backend.rank.side_effect = SemanticRankError(error)
            ledger = BudgetedRanker(backend)
            for _ in range(count + 1):
                with self.assertRaises(SemanticRankError):
                    ledger.rank(item_request)
            self.assertEqual(backend.rank.call_count, count)
        backend = Mock()
        ledger = BudgetedRanker(backend, max_usd=0)
        with self.assertRaisesRegex(SemanticRankError, "cost_budget"):
            ledger.rank(item_request)
        backend.rank.assert_not_called()
        ledger = BudgetedRanker(backend, max_seconds=0)
        with self.assertRaisesRegex(SemanticRankError, "time_budget"):
            ledger.rank(item_request)
        backend.rank.assert_not_called()

    def test_known_usage_survives_incomplete_response_and_unknown_usage_is_reserved(self):
        item_request = SemanticRankRequest("shoes", (), (SemanticRankItem("c0", "blue"),))
        backend = Mock()
        backend.rank.return_value = SemanticRankOutcome(("c0",), usage=ModelUsage(100, 20), finish_reason="length")
        ledger = BudgetedRanker(backend)
        with self.assertRaisesRegex(SemanticRankError, "incomplete_response"):
            ledger.rank(item_request)
        self.assertEqual(ledger.records[0]["prompt_tokens"], 100)
        self.assertTrue(ledger.records[0]["usage_known"])
        backend.rank.return_value = SemanticRankOutcome(("c0",), finish_reason="stop")
        with self.assertRaisesRegex(SemanticRankError, "invalid_usage"):
            ledger.rank(item_request)
        self.assertFalse(ledger.records[1]["usage_known"])

    def test_rejected_match_profile_cannot_cross_unmatched_item(self):
        base = BaseRetriever()
        original = base.retrieve(request())
        original.candidates[1] = replace(original.candidates[1], diagnostics={
            "rejected_constraint_matches": [{"attribute": "color", "value": "red"}]})
        base.retrieve = Mock(return_value=original)
        rejected = [{"attribute": "color", "normalized_value": "red", "confidence": .9}]
        result = ProductReranker(base, FakeSemanticRanker(["c1", "c2", "c0"])).retrieve(
            replace(request(), rejected_constraints=rejected))
        self.assertEqual([c.parent_asin for c in result.candidates], ["C", "B", "A", "D"])

    def test_agent_reports_usage_and_provider_only_sees_aliases(self):
        backend = Mock()
        backend.rank.return_value = SemanticRankOutcome(("c2", "c1", "c0"),
            usage=ModelUsage(100, 20), provider_model="synthetic", finish_reason="stop")
        budget = BudgetedRanker(backend)
        agent = TracedAgent(retriever=ProductReranker(BaseRetriever(), budget), ledger=budget)
        agent.reset("synthetic", {})
        response = agent.respond("synthetic", "I am browsing shoes", 1, 3)
        self.assertEqual(response["usage"], {"prompt_tokens": 100, "completion_tokens": 20})
        sent = backend.rank.call_args.args[0]
        self.assertEqual([i.opaque_id for i in sent.items], ["c0", "c1", "c2"])
        self.assertEqual([r["parent_asin"] for r in response["recommendations"]], ["C", "B", "A"])
        self.assertAlmostEqual(budget.total_cost, .0000704)

    def test_budget_counts_attempts_and_reserves_unknown_failures(self):
        backend = Mock()
        backend.rank.side_effect = SemanticRankError("provider_error")
        budgeted = BudgetedRanker(backend, max_calls=1)
        item_request = SemanticRankRequest("shoes", (), (SemanticRankItem("c0", "blue"),))
        with self.assertRaises(SemanticRankError):
            budgeted.rank(item_request)
        self.assertGreater(budgeted.total_cost, 0)
        with self.assertRaisesRegex(SemanticRankError, "call_budget"):
            budgeted.rank(item_request)
        self.assertEqual(backend.rank.call_count, 1)
        self.assertEqual(len(budgeted.records), 1)

    def test_invalid_permutation_preserves_entire_candidate_order(self):
        retriever = ProductReranker(BaseRetriever(), FakeSemanticRanker(["c0", "c0", "c2"]))
        result = retriever.retrieve(request())
        self.assertEqual([c.parent_asin for c in result.candidates], ["A", "B", "C", "D"])
        self.assertTrue(result.diagnostics.fallback_used)

    def test_permutation_preserves_hard_profiles_and_unranked_suffix(self):
        base = BaseRetriever()
        original = base.retrieve(request())
        original.candidates[0] = replace(original.candidates[0], diagnostics={
            "structured_matches": [{"attribute": "color", "value": "blue"}]})
        base.retrieve = Mock(return_value=original)
        ranker = FakeSemanticRanker(["c2", "c1", "c0"])
        result = ProductReranker(base, ranker).retrieve(replace(request(),
            active_constraints=[{"attribute": "color", "normalized_value": "blue",
                                 "confidence": .9, "hard": True}]))
        self.assertEqual([c.parent_asin for c in result.candidates], ["A", "C", "B", "D"])

    def test_buying_and_upstream_fallback_do_not_call_provider(self):
        ranker = FakeSemanticRanker()
        base = BaseRetriever()
        self.assertEqual(ProductReranker(base, ranker).retrieve(
            replace(request(), intent="buying")).candidates, base.retrieve(request()).candidates)
        original = base.retrieve(request())
        base.retrieve = Mock(return_value=replace(original,
            diagnostics=replace(original.diagnostics, fallback_used=True)))
        self.assertEqual(ProductReranker(base, ranker).retrieve(request()), base.retrieve(request()))
        self.assertEqual(ranker.calls, 0)
