from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from starter.agent import Agent as CoreAgent
from starter.delivery import Agent, DeliveryConfig
from starter.retrieval.hybrid import HybridRetriever
from starter.retrieval.semantic_ranker import ModelUsage, SemanticRankOutcome, SemanticRankError


class ReverseProvider:
    def rank(self, request):
        return SemanticRankOutcome(
            ordered_ids=tuple(item.opaque_id for item in reversed(request.items)),
            usage=ModelUsage(100, 20), provider_model="fixture", finish_reason="stop",
        )


class FailingProvider:
    def __init__(self, reason):
        self.reason = reason

    def rank(self, request):
        raise SemanticRankError(self.reason)


class InvalidProvider:
    def rank(self, request):
        return SemanticRankOutcome(ordered_ids=("invented-product",),
            usage=ModelUsage(100, 20), finish_reason="stop")


class DeliveryAgentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.catalog = Path(self.temp.name) / "catalog.jsonl"
        self.catalog.write_text("".join(json.dumps({
            "parent_asin": f"ITEM-{i:03d}", "title": f"Walking shoes {i}",
            "categories": ["Shoes"], "features": ["comfortable"],
            "description": [], "details": {}, "store": "Fixture",
        }) + "\n" for i in range(40)))

    def agent(self, **kwargs):
        return Agent(self.catalog, retriever=HybridRetriever(self.catalog), **kwargs)

    def test_offline_default_preserves_core_behavior_even_with_a_key(self):
        core = CoreAgent(self.catalog, retriever=HybridRetriever(self.catalog))
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "not-a-real-key"}, clear=True), \
                patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            agent = self.agent()
            for implementation in (core, agent):
                implementation.reset("test", {})
            expected = core.respond("test", "Show me shoes", 1, 10)
            actual = agent.respond("test", "Show me shoes", 1, 10)
        for key in ("message", "ask_attribute", "recommendations", "usage"):
            self.assertEqual(actual[key], expected[key])
        self.assertEqual(actual["diagnostics"]["delivery"]["requested_mode"], "offline")
        self.assertEqual(actual["diagnostics"]["delivery"]["attempts"], 0)

    def test_explicit_enhancement_reorders_only_existing_products_and_reports_usage(self):
        core = self.agent()
        enhanced = self.agent(config=DeliveryConfig(mode="llm", max_calls=2,
            max_usd=1, max_seconds=30), backend=ReverseProvider())
        for implementation in (core, enhanced):
            implementation.reset("test", {})
        expected = core.respond("test", "Show me shoes", 1, 10)
        actual = enhanced.respond("test", "Show me shoes", 1, 10)
        self.assertEqual(actual["recommendations"], list(reversed(expected["recommendations"])))
        self.assertEqual(actual["usage"], {"prompt_tokens": 100, "completion_tokens": 20})
        self.assertEqual(actual["diagnostics"]["delivery"]["turn_status"], "success")

    def test_missing_key_falls_back_without_attempting_network(self):
        with patch.dict("os.environ", {"SHOPPING_MODE": "llm", "SHOPPING_MAX_CALLS": "2",
                "SHOPPING_MAX_USD": "1", "SHOPPING_MAX_SECONDS": "30"}, clear=True), \
                patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            agent = self.agent()
            agent.reset("test", {})
            response = agent.respond("test", "Show me shoes", 1, 10)
        info = response["diagnostics"]["delivery"]
        self.assertEqual((info["turn_status"], info["reason"], info["attempts"]),
                         ("fallback", "no_key", 0))
        self.assertEqual(len(response["recommendations"]), 10)

    def test_provider_failure_and_invalid_ranking_preserve_pre_llm_order(self):
        for backend in (FailingProvider("provider_error"), InvalidProvider()):
            with self.subTest(backend=type(backend).__name__):
                core = self.agent(config=DeliveryConfig())
                enhanced = self.agent(config=DeliveryConfig("llm", 10, 1, 30), backend=backend)
                for implementation in (core, enhanced):
                    implementation.reset("test", {})
                expected = core.respond("test", "Show me shoes", 1, 10)
                actual = enhanced.respond("test", "Show me shoes", 1, 10)
                self.assertEqual(actual["recommendations"], expected["recommendations"])
                self.assertEqual(actual["diagnostics"]["delivery"]["turn_status"], "fallback")

    def test_exhausted_call_allowance_stops_paid_attempts_across_sessions(self):
        agent = self.agent(config=DeliveryConfig("llm", 1, 1, 30), backend=ReverseProvider())
        for session in ("first", "second"):
            agent.reset(session, {})
            response = agent.respond(session, "Show me shoes", 1, 10)
        info = response["diagnostics"]["delivery"]
        self.assertEqual((info["attempts"], info["successes"], info["reason"]), (1, 1, "call_budget"))

    def test_auth_failure_and_three_errors_disable_further_calls(self):
        for reason, attempts in (("http_401", 1), ("provider_error", 3)):
            with self.subTest(reason=reason):
                agent = self.agent(config=DeliveryConfig("llm", 20, 1, 30),
                                   backend=FailingProvider(reason))
                for index in range(4):
                    agent.reset(str(index), {})
                    response = agent.respond(str(index), "Show me shoes", 1, 10)
                info = response["diagnostics"]["delivery"]
                self.assertEqual(info["attempts"], attempts)
                self.assertEqual(info["fallbacks"], 4)
                self.assertIsNotNone(info["stop_reason"])

    def test_zero_cost_or_time_limit_falls_back_before_a_provider_attempt(self):
        for config in (DeliveryConfig("llm", 2, 0, 30), DeliveryConfig("llm", 2, 1, 0)):
            with self.subTest(config=config):
                agent = self.agent(config=config, backend=ReverseProvider())
                agent.reset("test", {})
                response = agent.respond("test", "Show me shoes", 1, 10)
                self.assertEqual(response["diagnostics"]["delivery"]["attempts"], 0)
                self.assertEqual(response["diagnostics"]["delivery"]["turn_status"], "fallback")

    def test_buying_is_skipped_not_reported_as_llm_failure(self):
        agent = self.agent(config=DeliveryConfig("llm", 2, 1, 30), backend=ReverseProvider())
        agent.reset("test", {})
        response = agent.respond("test", "I need black leather shoes", 1, 10)
        info = response["diagnostics"]["delivery"]
        self.assertEqual((info["turn_status"], info["attempts"], info["fallbacks"]), ("skipped", 0, 0))

    def test_invalid_configuration_fails_clearly_before_runtime(self):
        for kwargs in ({"mode": "unknown"}, {"max_calls": -1}, {"max_calls": True},
                       {"max_usd": float("nan")}, {"max_seconds": float("inf")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                DeliveryConfig(**kwargs)

    def test_provider_error_details_are_not_exposed(self):
        agent = self.agent(config=DeliveryConfig("llm", 2, 1, 30),
                           backend=FailingProvider("SECRET-provider-body"))
        agent.reset("test", {})
        response = agent.respond("test", "Show me shoes", 1, 10)
        self.assertNotIn("SECRET", json.dumps(response))


if __name__ == "__main__":
    unittest.main()
