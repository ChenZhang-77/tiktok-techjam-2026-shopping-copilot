from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starter.agent import Agent
from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalRequest, RetrievalResult


class _RecordingRetriever:
    catalog_ids = frozenset({"A", "B"})
    fallback_ids = ("A", "B")

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requests: list[RetrievalRequest] = []

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("simulated retrieval failure")
        return RetrievalResult(
            candidates=[
                Candidate(
                    parent_asin="A",
                    source="bm25",
                    diagnostics={"lexical_rank": 1, "final_rank": 1},
                    evidence_text="Leather running shoe Clothing Shoes black leather Example",
                )
            ],
            diagnostics=RetrievalDiagnostics(
                route="bm25",
                candidate_count=1,
                fallback_used=False,
                latency_ms=1.0,
            ),
        )


class _InvalidCandidatesRetriever(_RecordingRetriever):
    fallback_ids = ("A", "B", "C")
    catalog_ids = frozenset(fallback_ids)

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        self.requests.append(request)
        return RetrievalResult(
            candidates=[
                Candidate(parent_asin="A", source="bm25"),
                Candidate(parent_asin="A", source="bm25"),
                Candidate(parent_asin="NOT_IN_CATALOG", source="bm25"),
            ],
            diagnostics=RetrievalDiagnostics(
                route="bm25",
                candidate_count=3,
                fallback_used=False,
                latency_ms=1.0,
            ),
        )


class _FalseyRetriever(_RecordingRetriever):
    def __bool__(self) -> bool:
        return False


def _write_catalog(path: Path) -> None:
    rows = [
        {
            "parent_asin": "A",
            "title": "Leather running shoe",
            "categories": ["Clothing", "Shoes", "Trail Running Shoes"],
            "features": ["black leather"],
            "details": {},
            "store": "Example",
            "description": [],
        },
        {
            "parent_asin": "B",
            "title": "Cotton summer shirt",
            "categories": ["Clothing", "Shirts"],
            "features": ["cotton"],
            "details": {},
            "store": "Example",
            "description": [],
        },
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class AgentSmokeTest(unittest.TestCase):
    def test_full_candidate_pool_reaches_decision_evidence_without_public_raw_evidence(self) -> None:
        retriever = _RecordingRetriever()

        def retrieve(request: RetrievalRequest) -> RetrievalResult:
            retriever.requests.append(request)
            return RetrievalResult(
                candidates=[
                    Candidate("A", evidence_text="leather shoes"),
                    Candidate("B", evidence_text="leather shoes"),
                    Candidate("C", evidence_text="cotton shoes"),
                ],
                diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=3),
            )

        retriever.catalog_ids = frozenset({"A", "B", "C"})
        retriever.fallback_ids = ("A", "B", "C")
        retriever.retrieve = retrieve
        agent = Agent(retriever=retriever)
        agent.reset("decision-evidence", {})

        response = agent.respond("decision-evidence", "Show me product ideas", 1, 2)

        evidence = response["diagnostics"]["decision_evidence"]
        self.assertEqual(len(response["recommendations"]), 2)
        self.assertEqual(evidence["pool_size"], 3)
        self.assertEqual(evidence["evidence_candidate_count"], 3)
        self.assertIn("material", evidence["attribute_partition_scores"])
        self.assertNotIn("candidate_ids", evidence)
        self.assertNotIn("candidate_texts", evidence)

    def test_buying_intent_persists_after_a_no_preference_reply(self) -> None:
        retriever = _RecordingRetriever()
        agent = Agent(retriever=retriever)
        agent.reset("intent-persistence", {})

        first = agent.respond(
            "intent-persistence",
            "I need black leather shoes",
            1,
            2,
        )
        second = agent.respond(
            "intent-persistence",
            "I don't have an additional preference for size.",
            2,
            2,
        )

        self.assertEqual([request.intent for request in retriever.requests], ["buying", "buying"])
        self.assertEqual(second["diagnostics"]["intent_assessment"]["intent"], "buying")
        self.assertEqual(
            second["diagnostics"]["intent_assessment"]["transition_reason"],
            "retained",
        )
        self.assertEqual(first["diagnostics"]["intent_assessment"]["source_turn"], 1)
        self.assertEqual(second["diagnostics"]["intent_assessment"]["source_turn"], 1)

    def test_browsing_route_changes_only_after_specific_evidence(self) -> None:
        retriever = _RecordingRetriever()
        agent = Agent(retriever=retriever)
        agent.reset("intent-accumulation", {})

        agent.respond("intent-accumulation", "I'm just browsing shoes ideas", 1, 2)
        second = agent.respond(
            "intent-accumulation",
            "Black leather would work",
            2,
            2,
        )

        self.assertEqual([request.intent for request in retriever.requests], ["browsing", "buying"])
        self.assertEqual(
            second["diagnostics"]["strategy"]["intent"],
            second["diagnostics"]["intent_assessment"]["intent"],
        )
    def test_buying_and_browsing_execute_different_candidate_pool_plans(self) -> None:
        rows = [
            {
                "parent_asin": f"B{index:03d}",
                "title": "black leather walking shoes",
                "features": ["daily walking"],
            }
            for index in range(50)
        ] + [
            {
                "parent_asin": f"W{index:03d}",
                "title": "white canvas walking shoes",
                "features": ["daily walking"],
            }
            for index in range(50)
        ]
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            catalog_path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            agent = Agent(catalog_path)
            agent.reset("buying", {})
            agent.reset("browsing", {})

            buying = agent.respond("buying", "I need black leather walking shoes", 1, 10)
            browsing = agent.respond("browsing", "I am browsing shoes ideas", 1, 10)

        buying_retrieval = buying["diagnostics"]["retrieval"]
        browsing_retrieval = browsing["diagnostics"]["retrieval"]
        self.assertEqual(buying["diagnostics"]["strategy"]["intent"], "buying")
        self.assertEqual(browsing["diagnostics"]["strategy"]["intent"], "browsing")
        self.assertTrue(buying_retrieval["structured_filter_applied"])
        self.assertFalse(browsing_retrieval["structured_filter_applied"])
        self.assertEqual(buying_retrieval["route_candidate_counts"]["lexical"], 80)
        self.assertEqual(buying_retrieval["route_candidate_counts"]["structured"], 80)
        self.assertEqual(buying_retrieval["ranking_pool_sizes"]["post_structured_filter"], 50)
        self.assertEqual(browsing_retrieval["route_candidate_counts"]["lexical"], 100)
        self.assertEqual(browsing_retrieval["route_candidate_counts"]["structured"], 100)

    def test_candidate_pool_evidence_reaches_agent_clarification(self) -> None:
        def make_agent(*, include_evidence: bool) -> Agent:
            retriever = _RecordingRetriever()

            def retrieve(request: RetrievalRequest) -> RetrievalResult:
                retriever.requests.append(request)
                evidence = ("leather product", "cotton product") if include_evidence else ("", "")
                return RetrievalResult(
                    candidates=[
                        Candidate(parent_asin="A", evidence_text=evidence[0]),
                        Candidate(parent_asin="B", evidence_text=evidence[1]),
                    ],
                    diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=2),
                )

            retriever.retrieve = retrieve
            return Agent(retriever=retriever)

        evidence_agent = make_agent(include_evidence=True)
        empty_agent = make_agent(include_evidence=False)
        evidence_agent.reset("evidence", {})
        empty_agent.reset("empty", {})

        with_evidence = evidence_agent.respond("evidence", "Show me some product ideas", 1, 2)
        without_evidence = empty_agent.respond("empty", "Show me some product ideas", 1, 2)

        self.assertEqual(with_evidence["ask_attribute"], "material")
        self.assertEqual(without_evidence["ask_attribute"], "use_case")
    def test_explicit_falsey_retriever_is_not_replaced(self) -> None:
        retriever = _FalseyRetriever()

        agent = Agent(retriever=retriever)

        self.assertIs(agent.retriever, retriever)

    def test_response_guard_fill_is_reported_as_a_retrieval_fallback(self) -> None:
        agent = Agent(retriever=_InvalidCandidatesRetriever())
        agent.reset("s1", {})

        response = agent.respond("s1", "I need leather shoes", 1, 3)

        self.assertEqual(
            response["recommendations"],
            [{"parent_asin": "A"}, {"parent_asin": "B"}, {"parent_asin": "C"}],
        )
        self.assertTrue(response["diagnostics"]["fallback_used"])
        self.assertTrue(response["diagnostics"]["decision_evidence"]["degraded"])
        self.assertIsNone(
            response["diagnostics"]["decision_evidence"]["candidate_stability"]
        )

    def test_agent_routes_retrieval_through_the_public_seam(self) -> None:
        retriever = _RecordingRetriever()
        agent = Agent(retriever=retriever)
        agent.reset("s1", {})

        response = agent.respond("s1", "I need leather shoes", 1, 2)

        self.assertEqual(len(retriever.requests), 1)
        request = retriever.requests[0]
        self.assertEqual(request.session_id, "s1")
        self.assertEqual(request.intent, "buying")
        self.assertIn("leather", request.query)
        self.assertEqual(response["recommendations"], [{"parent_asin": "A"}, {"parent_asin": "B"}])
        self.assertEqual(response["diagnostics"]["retrieval"]["route"], "bm25")

    def test_agent_builds_catalog_vocabulary_for_multi_word_category_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            agent = Agent(catalog_path)
            agent.reset("catalog-context", {})

            response = agent.respond(
                "catalog-context",
                "I need trail running shoes.",
                1,
                2,
            )

        self.assertIn(
            "trail running shoes",
            response["diagnostics"]["query_plan"]["category_terms"],
        )

    def test_agent_query_excludes_no_preference_and_negative_clause_text(self) -> None:
        retriever = _RecordingRetriever()
        agent = Agent(retriever=retriever)
        agent.reset("scoped-query", {})
        agent.respond("scoped-query", "I need blue leather shoes.", 1, 2)

        response = agent.respond(
            "scoped-query",
            "I don't care about material, but waterproof is important; avoid black.",
            2,
            2,
        )

        query = retriever.requests[-1].query.lower()
        self.assertIn("waterproof", query)
        self.assertNotIn("don't care", query)
        self.assertNotIn("material", query)
        self.assertNotIn("black", query)
        self.assertIn("black", response["diagnostics"]["query_plan"]["excluded_terms"])

    def test_retrieval_failure_uses_catalog_fallback_without_leaking_exception(self) -> None:
        retriever = _RecordingRetriever(fail=True)
        agent = Agent(retriever=retriever)
        agent.reset("s1", {})

        response = agent.respond("s1", "I need leather shoes", 1, 2)

        self.assertEqual(response["recommendations"], [{"parent_asin": "A"}, {"parent_asin": "B"}])
        self.assertTrue(response["diagnostics"]["fallback_used"])
        self.assertEqual(response["diagnostics"]["retrieval"]["route"], "fallback")
        self.assertNotIn("simulated retrieval failure", json.dumps(response))

    def test_agent_visible_response_preserves_the_embedded_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            agent = Agent(catalog_path)
            agent.reset("s1", {})

            response = agent.respond("s1", "I need leather shoes", 1, 2)

            self.assertEqual(
                {
                    "message": response["message"],
                    "ask_attribute": response["ask_attribute"],
                    "recommendations": response["recommendations"],
                    "usage": response["usage"],
                },
                {
                    "message": "Here are the closest matches I found. Which specific feature matters most to you?",
                    "ask_attribute": "feature",
                    "recommendations": [{"parent_asin": "A"}, {"parent_asin": "B"}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                },
            )

    def test_agent_records_isolated_session_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            agent = Agent(catalog_path)

            agent.reset("s1", {"summary": "first"})
            agent.reset("s2", {"summary": "second"})
            first = agent.respond("s1", "I need leather shoes", 1, 2)
            second = agent.respond("s2", "I need a cotton shirt", 1, 2)
            third = agent.respond("s1", "Black is good", 2, 2)

            self.assertEqual(len(agent._sessions["s1"].raw_history), 2)
            self.assertEqual(len(agent._sessions["s2"].raw_history), 1)
            self.assertEqual(agent._sessions["s1"].raw_history[0].user_message, "I need leather shoes")
            self.assertEqual(agent._sessions["s2"].raw_history[0].user_message, "I need a cotton shirt")
            self.assertEqual(
                agent._sessions["s1"].previous_candidate_ids,
                agent._sessions["s1"].raw_history[-1].recommendation_ids,
            )
            self.assertEqual(agent._sessions["s1"].active_constraint_values("material"), ["leather"])
            self.assertEqual(agent._sessions["s1"].active_constraint_values("color"), ["black"])
            self.assertEqual(agent._sessions["s2"].active_constraint_values("material"), ["cotton"])
            self.assertIn("leather", agent._sessions["s1"].previous_distilled_query)
            self.assertIn("black", agent._sessions["s1"].previous_distilled_query)
            self.assertIn(agent._sessions["s1"].previous_strategy["intent"], {"buying", "browsing"})
            self.assertGreaterEqual(agent._sessions["s1"].previous_strategy["retrieval_depth"], 10)
            self.assertIn("strategy", first["diagnostics"])
            self.assertIn("active_constraints", first["diagnostics"])
            self.assertIn("distilled_query", first["diagnostics"])
            self.assertEqual(
                first["diagnostics"]["query_plan"]["rendered_query"],
                first["diagnostics"]["distilled_query"],
            )
            self.assertNotIn(
                "leather",
                third["diagnostics"]["query_plan"]["excluded_terms"],
            )
            self.assertEqual(agent._sessions["s1"].previous_diagnostics["strategy"], third["diagnostics"]["strategy"])
            self.assertIsNotNone(first["ask_attribute"])
            self.assertIn(first["ask_attribute"], agent._sessions["s1"].asked_attributes)
            self.assertTrue(first["recommendations"])
            self.assertTrue(second["recommendations"])

    def test_agent_override_rebuilds_query_from_active_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            agent = Agent(catalog_path)

            agent.reset("s1", {})
            agent.respond("s1", "I need leather shoes", 1, 2)
            agent.respond("s1", "Actually, ignore that. I need cotton instead.", 2, 2)

            state = agent._sessions["s1"]
            self.assertEqual(state.active_constraint_values("material"), ["cotton"])
            self.assertEqual([item["normalized_value"] for item in state.overridden_constraints], ["leather"])
            self.assertNotIn("leather", state.previous_distilled_query)
            self.assertIn("cotton", state.previous_distilled_query)
            self.assertIn("leather", state.previous_diagnostics["query_plan"]["excluded_terms"])
            self.assertEqual(state.previous_diagnostics["last_override"]["reason"], "attribute replacement")


if __name__ == "__main__":
    unittest.main()
