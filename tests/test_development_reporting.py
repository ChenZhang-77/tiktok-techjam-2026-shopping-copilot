from __future__ import annotations

import unittest

from experiments.development_reporting import AgentObserver, add_scenario_scores


class _StubAgent:
    def reset(self, session_id: str, user_profile: dict) -> None:
        pass

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        return {
            "message": "ok",
            "ask_attribute": None,
            "recommendations": [],
            "diagnostics": {"fallback_used": True},
        }


class DevelopmentReportingTest(unittest.TestCase):
    def test_observes_public_errors_and_reported_fallbacks(self) -> None:
        observer = AgentObserver(_StubAgent())

        observer.reset("session", {})
        observer.respond("session", "query", 1, 10)

        self.assertEqual(observer.counts(), {
            "respond_exceptions": 0,
            "invalid_response_payloads": 0,
            "reported_fallbacks": 1,
            "internal_fallbacks": None,
            "internal_fallbacks_note": "Not observable through the A-side public Agent interface.",
        })

    def test_adds_efficiency_and_technical_score_to_each_scenario(self) -> None:
        raw = {
            "scenario_metrics": {
                "buying": {
                    "sample_count": 2,
                    "hit_rate_at_10": 0.5,
                    "mrr": 0.25,
                    "mttc": 6.5,
                }
            }
        }

        report = add_scenario_scores(raw)

        self.assertEqual(report["scenario_metrics"]["buying"], {
            "sample_count": 2,
            "hit_rate_at_10": 0.5,
            "mrr": 0.25,
            "mttc": 6.5,
            "efficiency": 0.45,
            "recommended_technical_score": 0.415,
        })
        self.assertNotIn("efficiency", raw["scenario_metrics"]["buying"])


if __name__ == "__main__":
    unittest.main()
