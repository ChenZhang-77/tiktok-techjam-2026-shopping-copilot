from __future__ import annotations

import argparse
import copy
import json
import math
import resource
import subprocess
import sys
import time
from pathlib import Path

from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
from evaluator.splits import filter_samples, load_split_manifest
from experiments.development_folds import (
    filter_development_fold,
    validate_development_fold_manifest,
)
from starter.agent import Agent
from starter.contracts import validate_agent_response
from starter.core.response_guard import ALLOWED_ASK_ATTRIBUTES
from starter.retrieval import (
    ConditionalDenseConfig,
    ConditionalDenseRetriever,
    DenseConfig,
    DenseRetriever,
    FusionConfig,
    FusionRetriever,
    HybridRetriever,
    RerankerConfig,
    RerankingRetriever,
    StructuredConfig,
)
from starter.retrieval.fusion import fusion_fallback_configuration


def code_provenance() -> dict:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "worktree_clean": False}
    return {"commit": commit or None, "worktree_clean": not status.strip()}


class AgentObserver:
    def __init__(self, agent: object, *, catalog_ids: set[str]) -> None:
        self._agent = agent
        self._catalog_ids = catalog_ids
        self._respond_exceptions = 0
        self._invalid_response_payloads = 0
        self._reported_fallbacks = 0
        self._response_latencies_ms: list[float] = []
        self._retrieval_latencies_ms: list[float] = []
        self._retrieval_stage_latencies_ms: dict[str, list[float]] = {}
        self._route_candidate_counts: dict[str, list[int]] = {}
        self._route_overlap_counts: dict[str, list[int]] = {}
        self._route_failure_counts: dict[str, int] = {}
        self._requested_route_counts: dict[str, int] = {}
        self._executed_route_counts: dict[str, int] = {}
        self._requested_not_executed_route_counts: dict[str, int] = {}
        self._fallback_route_counts: dict[str, int] = {}
        self._route_semantics_unreported_responses = 0
        self._structured_filter_applied_responses = 0
        self._relaxed_constraint_responses = 0
        self._filtered_pool_step_count = 0
        self._cache_state_counts: dict[str, int] = {}
        self._rerank_pool_sizes: list[int] = []

    def reset(self, session_id: str, user_profile: dict) -> None:
        self._agent.reset(session_id, user_profile)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        started = time.perf_counter()
        try:
            response = self._agent.respond(session_id, user_message, turn, top_k)
        except Exception:
            self._respond_exceptions += 1
            raise
        finally:
            self._response_latencies_ms.append((time.perf_counter() - started) * 1000.0)
        if not self._is_valid_response(response, top_k):
            self._invalid_response_payloads += 1
        diagnostics = response.get("diagnostics") if isinstance(response, dict) else None
        if isinstance(diagnostics, dict) and diagnostics.get("fallback_used") is True:
            self._reported_fallbacks += 1
        retrieval = diagnostics.get("retrieval") if isinstance(diagnostics, dict) else None
        if isinstance(retrieval, dict):
            total_latency = retrieval.get("latency_ms")
            if isinstance(total_latency, (int, float)) and not isinstance(total_latency, bool):
                self._retrieval_latencies_ms.append(float(total_latency))
            stage_latencies = retrieval.get("stage_latencies_ms")
            if isinstance(stage_latencies, dict):
                for stage, value in stage_latencies.items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        self._retrieval_stage_latencies_ms.setdefault(str(stage), []).append(
                            float(value)
                        )
            for field_name, destination in (
                ("route_candidate_counts", self._route_candidate_counts),
                ("route_overlap_counts", self._route_overlap_counts),
            ):
                values = retrieval.get(field_name)
                if isinstance(values, dict):
                    for name, value in values.items():
                        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                            destination.setdefault(str(name), []).append(value)
            failures = retrieval.get("route_failures")
            if isinstance(failures, dict):
                for route, reason in failures.items():
                    if isinstance(reason, str):
                        key = f"{route}:{reason}"
                        self._route_failure_counts[key] = self._route_failure_counts.get(key, 0) + 1
            requested_weights = retrieval.get("requested_route_weights")
            executed_routes = retrieval.get("executed_routes")
            if (
                not isinstance(requested_weights, dict)
                or not requested_weights
                or not isinstance(executed_routes, list)
                or not executed_routes
            ):
                self._route_semantics_unreported_responses += 1
            valid_executed = {
                route
                for route in executed_routes
                if isinstance(executed_routes, list)
                and isinstance(route, str)
                and route
            } if isinstance(executed_routes, list) else set()
            for route in valid_executed:
                self._executed_route_counts[route] = (
                    self._executed_route_counts.get(route, 0) + 1
                )
            if isinstance(requested_weights, dict):
                for route, weight in requested_weights.items():
                    if (
                        isinstance(route, str)
                        and route
                        and isinstance(weight, (int, float))
                        and not isinstance(weight, bool)
                        and math.isfinite(weight)
                        and weight > 0
                    ):
                        self._requested_route_counts[route] = (
                            self._requested_route_counts.get(route, 0) + 1
                        )
                        if route not in valid_executed:
                            self._requested_not_executed_route_counts[route] = (
                                self._requested_not_executed_route_counts.get(route, 0)
                                + 1
                            )
            fallback_route = retrieval.get("fallback_route")
            if isinstance(fallback_route, str) and fallback_route:
                self._fallback_route_counts[fallback_route] = (
                    self._fallback_route_counts.get(fallback_route, 0) + 1
                )
            if retrieval.get("structured_filter_applied") is True:
                self._structured_filter_applied_responses += 1
            relaxed = retrieval.get("relaxed_constraints")
            if isinstance(relaxed, list) and relaxed:
                self._relaxed_constraint_responses += 1
            pool_steps = retrieval.get("filtered_pool_sizes")
            if isinstance(pool_steps, list):
                self._filtered_pool_step_count += len(pool_steps)
            cache_state = retrieval.get("cache_state")
            if isinstance(cache_state, dict):
                for stage, state in cache_state.items():
                    if isinstance(state, str):
                        key = f"{stage}:{state}"
                        self._cache_state_counts[key] = self._cache_state_counts.get(key, 0) + 1
            rerank_pool_size = retrieval.get("rerank_pool_size")
            if (
                isinstance(rerank_pool_size, int)
                and not isinstance(rerank_pool_size, bool)
                and rerank_pool_size > 0
            ):
                self._rerank_pool_sizes.append(rerank_pool_size)
        return response

    def _is_valid_response(self, response: object, top_k: int) -> bool:
        try:
            validate_agent_response(
                response,
                catalog_ids=self._catalog_ids,
                top_k=top_k,
                allowed_ask_attributes=ALLOWED_ASK_ATTRIBUTES,
            )
        except ValueError:
            return False
        return True

    def counts(self) -> dict:
        return {
            "respond_exceptions": self._respond_exceptions,
            "invalid_response_payloads": self._invalid_response_payloads,
            "reported_fallbacks": self._reported_fallbacks,
            "internal_fallbacks": self._reported_fallbacks,
            "internal_fallbacks_note": "B1 Agent diagnostics expose fallback_used at the public boundary.",
        }

    @staticmethod
    def _timing_summary(values: list[float]) -> dict:
        if not values:
            return {
                "response_count": 0,
                "total_ms": 0.0,
                "mean_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "max_ms": 0.0,
            }
        ordered = sorted(values)
        count = len(ordered)

        def percentile(fraction: float) -> float:
            index = max(0, math.ceil(fraction * count) - 1)
            return ordered[index]

        total = sum(ordered)
        return {
            "response_count": count,
            "total_ms": round(total, 6),
            "mean_ms": round(total / count, 6),
            "p50_ms": round(percentile(0.50), 6),
            "p95_ms": round(percentile(0.95), 6),
            "max_ms": round(ordered[-1], 6),
        }

    def timing(self) -> dict:
        return self._timing_summary(self._response_latencies_ms)

    def retrieval_timing(self) -> dict:
        timings = {"latency": self._timing_summary(self._retrieval_latencies_ms)}
        timings.update(
            {
                f"{stage}_latency": self._timing_summary(values)
                for stage, values in self._retrieval_stage_latencies_ms.items()
            }
        )
        return timings

    @staticmethod
    def _count_summary(values: list[int]) -> dict:
        return {
            "response_count": len(values),
            "total": sum(values),
            "mean": round(sum(values) / len(values), 6),
            "min": min(values),
            "max": max(values),
        }

    def retrieval_diagnostics(self) -> dict:
        return {
            "route_candidate_counts": {
                route: self._count_summary(values)
                for route, values in self._route_candidate_counts.items()
            },
            "route_overlap_counts": {
                pair: self._count_summary(values)
                for pair, values in self._route_overlap_counts.items()
            },
            "route_failure_counts": dict(self._route_failure_counts),
            "requested_route_counts": dict(self._requested_route_counts),
            "executed_route_counts": dict(self._executed_route_counts),
            "requested_not_executed_route_counts": dict(
                self._requested_not_executed_route_counts
            ),
            "fallback_route_counts": dict(self._fallback_route_counts),
            "route_semantics_unreported_responses": (
                self._route_semantics_unreported_responses
            ),
            "structured_filter_applied_responses": self._structured_filter_applied_responses,
            "relaxed_constraint_responses": self._relaxed_constraint_responses,
            "filtered_pool_step_count": self._filtered_pool_step_count,
            "cache_state_counts": dict(self._cache_state_counts),
            "rerank_pool_size": (
                self._count_summary(self._rerank_pool_sizes)
                if self._rerank_pool_sizes
                else None
            ),
        }


def add_scenario_scores(result: dict) -> dict:
    report = copy.deepcopy(result)
    for metrics in report.get("scenario_metrics", {}).values():
        mttc = metrics.get("mttc")
        if mttc is None:
            efficiency = 0.0
        else:
            efficiency = max(0.0, min(1.0, (11.0 - float(mttc)) / 10.0))
        technical_score = (
            0.50 * float(metrics.get("hit_rate_at_10") or 0.0)
            + 0.30 * float(metrics.get("mrr") or 0.0)
            + 0.20 * efficiency
        )
        metrics["efficiency"] = round(efficiency, 6)
        metrics["recommended_technical_score"] = round(technical_score, 6)
    return report


def evaluate_split(
    *,
    catalog_path: str | Path,
    dataset_path: str | Path,
    split: str,
    public_split_path: str | Path,
    development_fold_path: str | Path,
    fold_name: str | None = None,
    retrieval_mode: str = "structured",
    fusion_rrf_k: float = 60.0,
    rerank_candidate_limit: int = 30,
    conditional_dense_config: ConditionalDenseConfig | None = None,
    constraint_reranker_config: RerankerConfig | None = None,
) -> dict:
    if fold_name and split != "development":
        raise ValueError("A development fold can only be used with the development split")
    if retrieval_mode not in {
        "structured",
        "no_guarded_filter",
        "lexical",
        "dense",
        "fusion",
        "semantic_rerank",
        "conditional_dense",
        "constraint_preserving_rerank",
    }:
        raise ValueError(
            "retrieval_mode must be structured, no_guarded_filter, lexical, dense, fusion, "
            "semantic_rerank, conditional_dense, or constraint_preserving_rerank"
        )

    samples = load_jsonl(dataset_path)
    public_split = load_split_manifest(public_split_path)
    development_folds = None
    if split == "development":
        development_folds = load_split_manifest(development_fold_path)
        validate_development_fold_manifest(samples, public_split, development_folds)

    evaluation_samples = filter_samples(samples, split, public_split if split != "full" else None)
    if fold_name and development_folds is not None:
        evaluation_samples = filter_development_fold(evaluation_samples, development_folds, fold_name)

    initialization_started = time.perf_counter()
    catalog_ids, categories, products = catalog_index(catalog_path)
    structured_filter_enabled = retrieval_mode in {
        "structured",
        "fusion",
        "semantic_rerank",
        "conditional_dense",
        "constraint_preserving_rerank",
    }
    structured_config = StructuredConfig(enabled=structured_filter_enabled)
    dense_config = DenseConfig()
    conditional_dense_configuration = None
    if retrieval_mode in {"conditional_dense", "constraint_preserving_rerank"}:
        conditional_config = (
            conditional_dense_config
            if conditional_dense_config is not None
            else ConditionalDenseConfig()
        )
        conditional_dense_retriever = ConditionalDenseRetriever.from_catalog(
            catalog_path,
            config=conditional_config,
            dense_config=dense_config,
        )
        dense_configuration = conditional_dense_retriever.dense_configuration()
        conditional_dense_configuration = (
            conditional_dense_retriever.configuration_snapshot()
        )
        if retrieval_mode == "constraint_preserving_rerank":
            reranker_config = (
                constraint_reranker_config
                if constraint_reranker_config is not None
                else RerankerConfig(
                    candidate_limit=rerank_candidate_limit,
                    anchor_count=3,
                    base_score_weight=0.35,
                    minimum_constraint_confidence=0.75,
                    constraint_guard_enabled=True,
                )
            )
            retriever = RerankingRetriever(
                conditional_dense_retriever,
                config=reranker_config,
            )
        else:
            retriever = conditional_dense_retriever
    elif retrieval_mode == "fusion":
        retriever = FusionRetriever.from_catalog(
            catalog_path,
            config=FusionConfig(rrf_k=fusion_rrf_k),
            dense_config=dense_config,
        )
        dense_configuration = retriever.dense_configuration()
    elif retrieval_mode == "dense":
        retriever = DenseRetriever(catalog_path, config=dense_config)
        dense_configuration = retriever.configuration_snapshot()
    else:
        hybrid = HybridRetriever(
            catalog_path,
            structured_config=structured_config,
            constraint_rerank_enabled=retrieval_mode != "lexical",
        )
        if retrieval_mode == "semantic_rerank":
            retriever = RerankingRetriever(
                hybrid,
                config=RerankerConfig(candidate_limit=rerank_candidate_limit),
            )
        else:
            retriever = hybrid
        dense_configuration = None
    reranker_configuration = (
        retriever.configuration_snapshot()
        if retrieval_mode in {"semantic_rerank", "constraint_preserving_rerank"}
        else None
    )
    observer = AgentObserver(
        Agent(catalog_path, retriever=retriever),
        catalog_ids=catalog_ids,
    )
    initialization_ms = (time.perf_counter() - initialization_started) * 1000.0
    evaluation_started = time.perf_counter()
    try:
        result = evaluate(observer, evaluation_samples, catalog_ids, categories, products)
    finally:
        close_retriever = getattr(retriever, "close", None)
        if callable(close_retriever):
            close_retriever()
    evaluation_wall_ms = (time.perf_counter() - evaluation_started) * 1000.0
    result = add_scenario_scores(result)
    result["code_provenance"] = code_provenance()
    result["observed_run_counts"] = observer.counts()
    result["retrieval_diagnostics"] = observer.retrieval_diagnostics()
    result["timing"] = {
        "initialization_ms": round(initialization_ms, 6),
        "evaluation_wall_ms": round(evaluation_wall_ms, 6),
        "responses": observer.timing(),
        "retrieval": observer.retrieval_timing(),
    }
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result["resources"] = {
        "peak_rss_bytes": int(peak_rss if sys.platform == "darwin" else peak_rss * 1024),
        "peak_rss_kind": "process_peak_rss",
    }
    result["evaluation"] = {
        "dataset": str(dataset_path),
        "split": split,
        "split_manifest": str(public_split_path) if split != "full" else None,
        "split_version": public_split.get("version") if split != "full" else None,
        "development_fold": fold_name,
        "development_fold_manifest": str(development_fold_path) if split == "development" else None,
        "development_fold_version": development_folds.get("version") if development_folds else None,
        "retrieval_mode": retrieval_mode,
        "structured_filter": structured_filter_enabled,
        "fusion_rrf_k": fusion_rrf_k if retrieval_mode == "fusion" else None,
        "conditional_dense_configuration": conditional_dense_configuration,
        "reranker_configuration": reranker_configuration,
        "dense_configuration": (
            dense_configuration
        ),
        "fallback_configuration": (
            {"retrieval_mode": "structured", "structured_filter": True}
            if retrieval_mode == "dense"
            else (
                fusion_fallback_configuration()
                if retrieval_mode == "fusion"
                else (
                    {
                        "gate_skip": "exact_structured_order",
                        "dense_failure": "exact_structured_order",
                        "slow_dense_result": "exact_structured_order_after_execution",
                    }
                    if retrieval_mode == "conditional_dense"
                    else (
                        {
                            "conditional_dense_gate_skip": "exact_structured_order",
                            "conditional_dense_degradation": "exact_structured_order",
                            "semantic_rerank_failure": (
                                "exact_pre_rerank_candidate_order"
                            ),
                        }
                        if retrieval_mode == "constraint_preserving_rerank"
                        else (
                            {
                                "semantic_rerank_failure": (
                                    "exact_pre_rerank_candidate_order"
                                )
                            }
                            if retrieval_mode == "semantic_rerank"
                            else None
                        )
                    )
                )
            )
        ),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a scored experiment report without modifying the evaluator.")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--split", choices=("development", "holdout", "full"), default="development")
    parser.add_argument("--public-split", default="docs/public_split_v1.json")
    parser.add_argument("--development-fold-manifest", default="docs/development_folds_v1.json")
    parser.add_argument("--fold", choices=("fold_1", "fold_2", "fold_3", "fold_4"))
    retrieval_mode = parser.add_mutually_exclusive_group()
    retrieval_mode.add_argument(
        "--structured-filter",
        action="store_const",
        const="structured",
        dest="retrieval_mode",
        help="Explicitly enable the retained structured filter (the default).",
    )
    retrieval_mode.add_argument(
        "--no-guarded-filter",
        action="store_const",
        const="no_guarded_filter",
        dest="retrieval_mode",
        help="Keep the B1 constraint reranker but disable guarded structured filtering.",
    )
    retrieval_mode.add_argument(
        "--semantic-rerank",
        action="store_const",
        const="semantic_rerank",
        dest="retrieval_mode",
        help="Rerank the retained structured Candidate Pool with the pinned local CrossEncoder.",
    )
    retrieval_mode.add_argument(
        "--fusion",
        action="store_const",
        const="fusion",
        dest="retrieval_mode",
        help="Fuse weighted lexical, structured, and available dense Route rankings.",
    )
    retrieval_mode.add_argument(
        "--conditional-dense",
        action="store_const",
        const="conditional_dense",
        dest="retrieval_mode",
        help="Fuse dense only for broad Browsing and preserve exact structured fallback.",
    )
    retrieval_mode.add_argument(
        "--constraint-preserving-rerank",
        action="store_const",
        const="constraint_preserving_rerank",
        dest="retrieval_mode",
        help=(
            "Apply the Top-3-anchored local CrossEncoder to ranks 4-30 after "
            "the retained conditional-dense route."
        ),
    )
    retrieval_mode.add_argument(
        "--dense-only",
        action="store_const",
        const="dense",
        dest="retrieval_mode",
        help="Run the cached local dense route with lexical fallback.",
    )
    retrieval_mode.add_argument(
        "--lexical-only",
        action="store_const",
        const="lexical",
        dest="retrieval_mode",
        help="Run pure BM25 without constraint reranking or guarded filtering.",
    )
    parser.set_defaults(retrieval_mode="structured")
    parser.add_argument(
        "--rrf-k",
        type=float,
        default=60.0,
        help="Weighted reciprocal-rank-fusion constant used by --fusion.",
    )
    parser.add_argument(
        "--rerank-limit",
        type=int,
        default=30,
        help=(
            "Maximum candidates considered by --semantic-rerank or "
            "--constraint-preserving-rerank (1-100)."
        ),
    )
    parser.add_argument(
        "--rerank-anchor-count",
        type=int,
        default=3,
        help="Protected prefix size for --constraint-preserving-rerank.",
    )
    parser.add_argument(
        "--rerank-base-score-weight",
        type=float,
        default=0.35,
        help="Retained base-score weight for --constraint-preserving-rerank.",
    )
    parser.add_argument(
        "--conditional-dense-max-active-constraints",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--conditional-dense-min-base-candidates",
        type=int,
        default=30,
    )
    parser.add_argument(
        "--conditional-dense-max-accepted-latency-ms",
        type=float,
        default=250.0,
    )
    parser.add_argument("--output", default="results.json")
    args = parser.parse_args()

    constraint_reranker_config = None
    if args.retrieval_mode == "constraint_preserving_rerank":
        constraint_reranker_config = RerankerConfig(
            candidate_limit=args.rerank_limit,
            anchor_count=args.rerank_anchor_count,
            base_score_weight=args.rerank_base_score_weight,
            minimum_constraint_confidence=0.75,
            constraint_guard_enabled=True,
        )

    result = evaluate_split(
        catalog_path=args.catalog,
        dataset_path=args.dataset,
        split=args.split,
        public_split_path=args.public_split,
        development_fold_path=args.development_fold_manifest,
        fold_name=args.fold,
        retrieval_mode=args.retrieval_mode,
        fusion_rrf_k=args.rrf_k,
        rerank_candidate_limit=args.rerank_limit,
        conditional_dense_config=ConditionalDenseConfig(
            max_active_constraints=args.conditional_dense_max_active_constraints,
            min_base_candidates=args.conditional_dense_min_base_candidates,
            rrf_k=args.rrf_k,
            max_accepted_dense_latency_ms=(
                args.conditional_dense_max_accepted_latency_ms
            ),
        ),
        constraint_reranker_config=constraint_reranker_config,
    )
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "sessions"}, indent=2))


if __name__ == "__main__":
    main()
