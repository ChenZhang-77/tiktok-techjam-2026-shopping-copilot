from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starter.agent import Agent


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
    def test_agent_records_isolated_session_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            agent = Agent(catalog_path)

            agent.reset("s1", {"summary": "first"})
            agent.reset("s2", {"summary": "second"})
            first = agent.respond("s1", "I need leather shoes", 1, 2)
            second = agent.respond("s2", "I need a cotton shirt", 1, 2)
            agent.respond("s1", "Black is good", 2, 2)

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


if __name__ == "__main__":
    unittest.main()
