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
        dataset.write_text(json.dumps({"sample_id": "public_0001", "scenario_type": "buying",
            "user_profile": {}, "ground_truth": {"parent_asin": "A"}}) + "\n")
        self.runner = server.TraceRunner(self.catalog, dataset)

    def test_missing_current_evidence_does_not_display_unrelated_baseline_score(self):
        (self.root / "docs/baseline_results.json").write_text(json.dumps({"mrr": .1}))
        with patch.object(server, "ROOT", self.root):
            metrics = self.runner.overall_metrics("current")
        self.assertIsNone(metrics["mrr"])
        self.assertEqual(metrics["evidence_status"], "missing_or_stale")

    def test_historical_metrics_allow_selected_session_replay(self):
        runs = self.root / "runs"
        old = runs / "old"
        old.mkdir(parents=True)
        (old / "results.json").write_text(json.dumps({"evaluation": {"split": "full"}}))
        with patch.object(server, "RUNS_DIR", runs):
            start = self.runner.start_session(0, "old")
        self.assertEqual(start["source_index"], 0)
        self.assertEqual(start["session_index"], 1)

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

    def test_legacy_start_endpoint_allows_historical_session_replay(self):
        runs = self.root / "runs"
        old = runs / "old"
        old.mkdir(parents=True)
        (old / "results.json").write_text(json.dumps({"evaluation": {"split": "full"}}))
        handler = object.__new__(server.VisualizerHandler)
        handler.path = "/api/start?experiment=old&index=0"
        handler.runner = self.runner
        with patch.object(server, "RUNS_DIR", runs), patch.object(handler, "_send_json") as send:
            handler.do_GET()
        self.assertEqual(send.call_args.args[0]["source_index"], 0)
        self.assertEqual(len(self.runner.active_sessions), 1)

    def test_current_workspace_uses_all_loaded_samples_by_default(self):
        summaries = self.runner.session_summaries("current")
        self.assertEqual([item["display_index"] for item in summaries], [1])
        self.assertEqual(summaries[0]["source_index"], 0)

    def test_current_metrics_do_not_mix_a_different_split(self):
        metrics = self.runner.overall_metrics("current")
        self.assertEqual(metrics["loaded_session_count"], 1)
        self.assertIsNone(metrics["sample_count"])

    def test_filtered_session_numbers_are_contiguous(self):
        dataset = self.catalog.parent / "three.jsonl"
        rows = [
            {"sample_id": "public_0001", "scenario_type": "buying",
             "user_profile": {}, "ground_truth": {"parent_asin": "A"}},
            {"sample_id": "public_0002", "scenario_type": "browsing",
             "user_profile": {}, "ground_truth": {"parent_asin": "A"}},
            {"sample_id": "public_0003", "scenario_type": "buying",
             "user_profile": {}, "ground_truth": {"parent_asin": "A"}},
        ]
        dataset.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        manifest = self.root / "split.json"
        manifest.write_text(json.dumps({"development": ["public_0001", "public_0003"]}))
        runner = server.TraceRunner(self.catalog, dataset,
                                    default_split="development", split_manifest_path=manifest)
        summaries = runner.session_summaries("current")
        self.assertEqual([item["display_index"] for item in summaries], [1, 2])
        self.assertEqual([item["source_index"] for item in summaries], [0, 2])


if __name__ == "__main__":
    unittest.main()
