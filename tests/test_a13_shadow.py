from __future__ import annotations

import unittest

from experiments.a13_shadow import (
    PairedShadowAgent,
    response_behavior_projection,
    summarize_shadow_diagnostics,
)


class _FixtureAgent:
    def __init__(self, diagnostics: list[dict | None], *, diverge: bool = False) -> None:
        self.diagnostics = list(diagnostics)
        self.diverge = diverge
        self.reset_calls: list[tuple[str, dict]] = []
        self.respond_calls: list[tuple[str, str, int, int]] = []

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.reset_calls.append((session_id, dict(user_profile)))

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        self.respond_calls.append((session_id, user_message, turn, top_k))
        return {
            "message": "different" if self.diverge else "same",
            "ask_attribute": None,
            "recommendations": [{"parent_asin": "A"}],
        }

    def semantic_diagnostics(self, session_id: str, turn: int) -> dict | None:
        return self.diagnostics[turn - 1]


class A13ShadowTest(unittest.TestCase):
    def test_paired_agent_returns_baseline_and_records_safe_shadow_summary(self) -> None:
        diagnostics = [
            {
                "status": "valid_shadow_delta",
                "trigger_signals": ["override_without_value"],
                "backend_called": True,
                "fallback_reason": None,
                "latency_ms": 10.0,
                "prompt_tokens": 20,
                "completion_tokens": 5,
            },
            {
                "status": "fallback",
                "trigger_signals": [],
                "backend_called": False,
                "fallback_reason": "ineligible",
                "latency_ms": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        ]
        baseline = _FixtureAgent([None, None])
        shadow = _FixtureAgent(diagnostics)
        paired = PairedShadowAgent(baseline, shadow)
        paired.reset("session-secret", {"profile": "private"})

        first = paired.respond("session-secret", "first private message", 1, 1)
        second = paired.respond("session-secret", "second private message", 2, 1)

        self.assertEqual(first["message"], "same")
        self.assertEqual(second["message"], "same")
        summary = paired.summary()
        self.assertEqual(summary["response_count"], 2)
        self.assertEqual(summary["exact_response_mismatches"], 0)
        self.assertEqual(summary["public_response_mismatches"], 0)
        self.assertEqual(summary["eligible_turns"], 1)
        self.assertEqual(summary["backend_called_turns"], 1)
        self.assertEqual(summary["valid_delta_turns"], 1)
        self.assertEqual(summary["fallback_reasons"], {"ineligible": 1})
        self.assertEqual(summary["trigger_counts"], {"override_without_value": 1})
        self.assertEqual(summary["prompt_tokens"], 20)
        self.assertEqual(summary["completion_tokens"], 5)
        rendered = repr(summary).lower()
        self.assertNotIn("session-secret", rendered)
        self.assertNotIn("private message", rendered)
        self.assertNotIn("profile", rendered)

    def test_public_response_divergence_is_counted_but_baseline_is_still_returned(self) -> None:
        baseline = _FixtureAgent([None])
        shadow = _FixtureAgent([None], diverge=True)
        paired = PairedShadowAgent(baseline, shadow)
        paired.reset("session", {})

        response = paired.respond("session", "message", 1, 1)

        self.assertEqual(response["message"], "same")
        self.assertEqual(paired.summary()["exact_response_mismatches"], 1)
        self.assertEqual(paired.summary()["public_response_mismatches"], 1)

    def test_behavior_projection_ignores_only_operational_latency(self) -> None:
        response = {
            "message": "same",
            "ask_attribute": None,
            "recommendations": [{"parent_asin": "A"}],
            "diagnostics": {
                "retrieval": {
                    "route": "fixture",
                    "latency_ms": 1.0,
                    "stage_latencies_ms": {"lexical": 0.5},
                }
            },
        }
        slower = {
            **response,
            "diagnostics": {
                "retrieval": {
                    "route": "fixture",
                    "latency_ms": 9.0,
                    "stage_latencies_ms": {"lexical": 8.0},
                }
            },
        }
        changed_route = {
            **response,
            "diagnostics": {"retrieval": {"route": "different", "latency_ms": 1.0}},
        }

        self.assertEqual(
            response_behavior_projection(response),
            response_behavior_projection(slower),
        )
        self.assertNotEqual(
            response_behavior_projection(response),
            response_behavior_projection(changed_route),
        )

    def test_summarizer_handles_empty_and_percentile_latency_inputs(self) -> None:
        empty = summarize_shadow_diagnostics([], public_response_mismatches=0)
        self.assertEqual(empty["response_count"], 0)
        self.assertEqual(empty["latency_ms"], {"p50": 0.0, "p95": 0.0, "max": 0.0})

        populated = summarize_shadow_diagnostics(
            [
                {
                    "status": "fallback",
                    "trigger_signals": ["one"],
                    "backend_called": True,
                    "fallback_reason": "timeout",
                    "latency_ms": value,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }
                for value in (1.0, 2.0, 100.0)
            ],
            public_response_mismatches=0,
        )
        self.assertEqual(populated["latency_ms"], {"p50": 2.0, "p95": 100.0, "max": 100.0})


if __name__ == "__main__":
    unittest.main()
