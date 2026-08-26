from __future__ import annotations

import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from experiments.evaluation_reporting import (
    AgentObserver,
    add_scenario_scores,
    code_provenance,
    evaluate_split,
)
from starter.retrieval import DenseConfig, FusionConfig, RerankerConfig


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


class _InvalidStubAgent(_StubAgent):
    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        return {
            "message": "ok",
            "ask_attribute": "not_allowed",
            "recommendations": [{"parent_asin": "NOT_IN_CATALOG"}],
            "usage": {"prompt_tokens": -1, "completion_tokens": 0},
        }


class _RouteDiagnosticsStubAgent(_StubAgent):
    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        return {
            "message": "ok",
            "ask_attribute": None,
            "recommendations": [],
            "diagnostics": {
                "fallback_used": True,
                "retrieval": {
                    "latency_ms": 3.0,
                    "stage_latencies_ms": {"fusion": 0.25},
                    "route_candidate_counts": {"lexical": 10, "dense": 8},
                    "route_overlap_counts": {"lexical|dense": 4},
                    "route_failures": {"structured": "route_error"},
                    "structured_filter_applied": True,
                    "relaxed_constraints": [{"attribute": "material"}],
                    "filtered_pool_sizes": [{"before": 10, "after": 4}],
                    "cache_state": {"dense": "dense_cache_missing"},
                    "rerank_pool_size": 30,
                },
            },
        }


class _SubtlyInvalidStubAgent(_StubAgent):
    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        return {
            "message": "ok",
            "ask_attribute": None,
            "recommendations": [{"parent_asin": "VALID", "score": "high"}],
            "usage": {"prompt_tokens": True, "completion_tokens": 0},
            "unexpected": "not in the response contract",
        }


class DevelopmentReportingTest(unittest.TestCase):
    def test_semantic_rerank_mode_wraps_retained_structured_candidates(self) -> None:
        empty_result = {"scenario_metrics": {}}
        with (
            patch("experiments.evaluation_reporting.load_jsonl", return_value=[]),
            patch(
                "experiments.evaluation_reporting.load_split_manifest",
                return_value={"version": "test"},
            ),
            patch("experiments.evaluation_reporting.validate_development_fold_manifest"),
            patch("experiments.evaluation_reporting.filter_samples", return_value=[]),
            patch("experiments.evaluation_reporting.catalog_index", return_value=(set(), set(), {})),
            patch("experiments.evaluation_reporting.HybridRetriever") as hybrid,
            patch("experiments.evaluation_reporting.RerankingRetriever") as reranker,
            patch("experiments.evaluation_reporting.Agent", return_value=_StubAgent()),
            patch("experiments.evaluation_reporting.evaluate", return_value=empty_result),
            patch(
                "experiments.evaluation_reporting.code_provenance",
                return_value={"commit": "test", "worktree_clean": True},
            ),
        ):
            reranker.return_value.configuration_snapshot.return_value = {
                "candidate_limit": 30,
                "model_id": "cross-encoder/ms-marco-MiniLM-L2-v2",
            }
            report = evaluate_split(
                catalog_path="catalog.jsonl",
                dataset_path="dataset.jsonl",
                split="development",
                public_split_path="split.json",
                development_fold_path="folds.json",
                retrieval_mode="semantic_rerank",
                rerank_candidate_limit=30,
            )

        reranker.assert_called_once_with(
            hybrid.return_value,
            config=RerankerConfig(candidate_limit=30),
        )
        self.assertEqual(report["evaluation"]["retrieval_mode"], "semantic_rerank")
        self.assertTrue(report["evaluation"]["structured_filter"])
        self.assertEqual(report["evaluation"]["reranker_configuration"]["candidate_limit"], 30)
        self.assertEqual(
            report["evaluation"]["fallback_configuration"],
            {"semantic_rerank_failure": "exact_pre_rerank_candidate_order"},
        )

    def test_aggregates_route_candidate_overlap_and_failure_diagnostics(self) -> None:
        observer = AgentObserver(_RouteDiagnosticsStubAgent(), catalog_ids=set())

        observer.respond("session", "query", 1, 10)
        diagnostics = observer.retrieval_diagnostics()

        self.assertEqual(diagnostics["route_candidate_counts"]["lexical"]["mean"], 10.0)
        self.assertEqual(diagnostics["route_candidate_counts"]["dense"]["max"], 8)
        self.assertEqual(diagnostics["route_overlap_counts"]["lexical|dense"]["mean"], 4.0)
        self.assertEqual(diagnostics["route_failure_counts"], {"structured:route_error": 1})
        self.assertEqual(diagnostics["structured_filter_applied_responses"], 1)
        self.assertEqual(diagnostics["relaxed_constraint_responses"], 1)
        self.assertEqual(diagnostics["filtered_pool_step_count"], 1)
        self.assertEqual(diagnostics["cache_state_counts"], {"dense:dense_cache_missing": 1})
        self.assertEqual(diagnostics["rerank_pool_size"]["mean"], 30.0)

    def test_fusion_mode_uses_central_rrf_config_and_records_degraded_route_policy(self) -> None:
        empty_result = {"scenario_metrics": {}}
        with (
            patch("experiments.evaluation_reporting.load_jsonl", return_value=[]),
            patch(
                "experiments.evaluation_reporting.load_split_manifest",
                return_value={"version": "test"},
            ),
            patch("experiments.evaluation_reporting.validate_development_fold_manifest"),
            patch("experiments.evaluation_reporting.filter_samples", return_value=[]),
            patch("experiments.evaluation_reporting.catalog_index", return_value=(set(), set(), {})),
            patch("experiments.evaluation_reporting.FusionRetriever.from_catalog") as from_catalog,
            patch("experiments.evaluation_reporting.Agent", return_value=_StubAgent()),
            patch("experiments.evaluation_reporting.evaluate", return_value=empty_result),
            patch(
                "experiments.evaluation_reporting.code_provenance",
                return_value={"commit": "test", "worktree_clean": True},
            ),
        ):
            from_catalog.return_value.dense_configuration.return_value = {
                "model_id": "sentence-transformers/all-MiniLM-L6-v2",
                "dimension": 384,
                "cache_size_bytes": 1,
            }
            report = evaluate_split(
                catalog_path="catalog.jsonl",
                dataset_path="dataset.jsonl",
                split="development",
                public_split_path="split.json",
                development_fold_path="folds.json",
                retrieval_mode="fusion",
                fusion_rrf_k=10.0,
            )

        from_catalog.assert_called_once_with(
            "catalog.jsonl",
            config=FusionConfig(rrf_k=10.0),
            dense_config=DenseConfig(),
        )
        self.assertEqual(report["evaluation"]["retrieval_mode"], "fusion")
        self.assertEqual(report["evaluation"]["fusion_rrf_k"], 10.0)
        self.assertTrue(report["evaluation"]["structured_filter"])
        self.assertEqual(
            report["evaluation"]["dense_configuration"]["model_id"],
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        self.assertEqual(report["evaluation"]["dense_configuration"]["dimension"], 384)
        self.assertIn("cache_size_bytes", report["evaluation"]["dense_configuration"])
        self.assertEqual(
            report["evaluation"]["fallback_configuration"],
            {
                "unavailable_route": "degrade_to_available_routes",
                "all_routes_failed": "catalog_fallback_up_to_retrieval_depth",
            },
        )

    @patch("experiments.evaluation_reporting.subprocess.run")
    def test_code_provenance_marks_untracked_files_dirty(self, run: object) -> None:
        run.side_effect = [
            CompletedProcess([], 0, stdout="abc1234\n"),
            CompletedProcess([], 0, stdout="?? local_config.py\n"),
        ]

        provenance = code_provenance()

        self.assertEqual(provenance, {"commit": "abc1234", "worktree_clean": False})

    def test_counts_an_observably_invalid_public_payload(self) -> None:
        observer = AgentObserver(_InvalidStubAgent(), catalog_ids={"VALID"})

        observer.respond("session", "query", 1, 10)

        self.assertEqual(observer.counts()["invalid_response_payloads"], 1)

    def test_rejects_subtle_schema_violations(self) -> None:
        observer = AgentObserver(_SubtlyInvalidStubAgent(), catalog_ids={"VALID"})

        observer.respond("session", "query", 1, 10)

        self.assertEqual(observer.counts()["invalid_response_payloads"], 1)

    def test_records_response_latency(self) -> None:
        observer = AgentObserver(_StubAgent(), catalog_ids=set())

        observer.respond("session", "query", 1, 10)

        timing = observer.timing()
        self.assertEqual(timing["response_count"], 1)
        for field in ("total_ms", "mean_ms", "p50_ms", "p95_ms", "max_ms"):
            self.assertGreaterEqual(timing[field], 0.0)

    def test_observes_public_errors_and_reported_fallbacks(self) -> None:
        observer = AgentObserver(_StubAgent(), catalog_ids=set())

        observer.reset("session", {})
        observer.respond("session", "query", 1, 10)

        self.assertEqual(observer.counts(), {
            "respond_exceptions": 0,
            "invalid_response_payloads": 0,
            "reported_fallbacks": 1,
            "internal_fallbacks": 1,
            "internal_fallbacks_note": "B1 Agent diagnostics expose fallback_used at the public boundary.",
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
