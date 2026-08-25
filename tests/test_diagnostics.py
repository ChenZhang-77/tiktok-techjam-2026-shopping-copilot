from __future__ import annotations

import unittest

from starter.core.diagnostics import state_diagnostics
from starter.core.state import SessionState


class DiagnosticsTest(unittest.TestCase):
    def test_state_diagnostics_summarize_control_plane_state(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.previous_distilled_query = "black shoes"
        state.asked_attributes.add("material")
        state.no_preference_attributes.add("brand")
        state.apply_user_context(constraints=[
            {
                "attribute": "color",
                "normalized_value": "black",
                "source_turn": 1,
                "confidence": 0.8,
                "hard": True,
            }
        ])

        diagnostics = state_diagnostics(state)

        self.assertEqual(diagnostics["intent"], "buying")
        self.assertEqual(diagnostics["active_constraints"][0]["attribute"], "color")
        self.assertEqual(diagnostics["asked_attributes"], ["material"])
        self.assertEqual(diagnostics["no_preference_attributes"], ["brand"])
        self.assertEqual(diagnostics["distilled_query"], "black shoes")


if __name__ == "__main__":
    unittest.main()
