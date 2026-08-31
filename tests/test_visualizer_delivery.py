import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from visualizer import server


class VisualizerDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        self.catalog = self.root / "catalog.jsonl"
        self.catalog.write_text(json.dumps({"parent_asin": "A", "title": "shoes",
            "categories": ["Shoes"], "features": [], "details": {}}) + "\n")
        dataset = self.root / "public.jsonl"
        dataset.write_text(json.dumps({"sample_id": "synthetic", "scenario_type": "buying",
            "user_profile": {}, "ground_truth": {"parent_asin": "A"}}) + "\n")
        self.runner = server.TraceRunner(self.catalog, dataset)

    def test_missing_current_evidence_does_not_display_unrelated_baseline_score(self):
        (self.root / "docs/baseline_results.json").write_text(json.dumps({"mrr": .1}))
        with patch.object(server, "ROOT", self.root):
            metrics = self.runner.overall_metrics("current")
        self.assertIsNone(metrics["mrr"])
        self.assertEqual(metrics["evidence_status"], "missing_or_stale")

    def test_historical_metrics_do_not_authorize_running_current_code_as_old_snapshot(self):
        runs = self.root / "runs"
        (runs / "old").mkdir(parents=True)
        with patch.object(server, "RUNS_DIR", runs), \
                self.assertRaisesRegex(ValueError, "Historical.*read-only"):
            self.runner.start_session(0, "old")

    def test_visualizer_is_always_offline_even_with_an_inherited_llm_mode(self):
        with patch.dict("os.environ", {"SHOPPING_MODE": "llm", "DEEPSEEK_API_KEY": "fixture"}, clear=True), \
                patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            agent = server.Agent(self.catalog)
            agent.reset("visual", {})
            response = agent.respond("visual", "Show me shoes", 1, 1)
            agent.close()
        self.assertEqual(response["diagnostics"]["delivery"]["requested_mode"], "offline")

    def test_stream_exposes_agent_diagnostics_separately_and_releases_session(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            events = [json.loads(chunk.decode().split("data: ", 1)[1])
                      for chunk in self.runner.stream_session(0, 0, "current")]
        self.assertEqual(events[0]["execution_kind"], "live_offline_simulation")
        turn = next(event for event in events if "agent_message" in event)
        self.assertEqual(turn["agent_diagnostics"]["delivery"]["turn_status"], "offline")
        self.assertNotIn("target_rank", turn["agent_diagnostics"])
        self.assertNotIn("ground_truth", turn["agent_diagnostics"])
        self.assertEqual(self.runner.active_sessions, {})

    def test_stopping_stream_releases_session(self):
        stream = self.runner.stream_session(0, 0, "current")
        next(stream)
        self.assertEqual(len(self.runner.active_sessions), 1)
        stream.close()
        self.assertEqual(self.runner.active_sessions, {})


if __name__ == "__main__":
    unittest.main()
