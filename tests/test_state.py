from __future__ import annotations

import unittest

from starter.core.state import SessionState


class SessionStateTest(unittest.TestCase):
    def test_history_accumulates_and_records_agent_response(self) -> None:
        state = SessionState(session_id="s1", user_profile={"summary": "test"})

        state.record_user_turn(1, "I need leather shoes")
        state.record_agent_response({
            "message": "Here are matches.",
            "ask_attribute": "material",
            "recommendations": [{"parent_asin": "A"}, {"parent_asin": "B"}],
        })
        state.record_user_turn(2, "Black would be better")

        self.assertEqual(state.current_turn, 2)
        self.assertEqual(len(state.raw_history), 2)
        self.assertEqual(state.raw_history[0].user_message, "I need leather shoes")
        self.assertEqual(state.raw_history[0].ask_attribute, "material")
        self.assertEqual(state.asked_attributes, {"material"})
        self.assertEqual(state.previous_candidate_ids, ["A", "B"])

    def test_sessions_are_independent_objects(self) -> None:
        first = SessionState(session_id="s1", user_profile={})
        second = SessionState(session_id="s2", user_profile={})

        first.record_user_turn(1, "one")
        second.record_user_turn(1, "two")
        first.mark_no_preference("color")

        self.assertEqual(first.raw_history[0].user_message, "one")
        self.assertEqual(second.raw_history[0].user_message, "two")
        self.assertEqual(first.no_preference_attributes, {"color"})
        self.assertEqual(second.no_preference_attributes, set())


if __name__ == "__main__":
    unittest.main()
