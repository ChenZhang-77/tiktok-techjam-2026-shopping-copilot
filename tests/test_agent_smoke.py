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


def _write_catalog(path: Path) -> None:
    rows = [
        {
            "parent_asin": "A",
            "title": "Leather running shoe",
            "categories": ["Clothing", "Shoes"],
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
            self.assertEqual(state.previous_diagnostics["last_override"]["reason"], "attribute replacement")


if __name__ == "__main__":
    unittest.main()
