from __future__ import annotations

import argparse
import copy
import json
import math
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
from starter.retrieval import HybridRetriever, StructuredConfig


class AgentObserver:
    def __init__(self, agent: object, *, catalog_ids: set[str]) -> None:
        self._agent = agent
        self._catalog_ids = catalog_ids
        self._respond_exceptions = 0
        self._invalid_response_payloads = 0
        self._reported_fallbacks = 0
        self._response_latencies_ms: list[float] = []

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

    def timing(self) -> dict:
        if not self._response_latencies_ms:
            return {
                "response_count": 0,
                "total_ms": 0.0,
                "mean_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "max_ms": 0.0,
            }
        ordered = sorted(self._response_latencies_ms)
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
    structured_filter: bool | None = None,
) -> dict:
    if fold_name and split != "development":
        raise ValueError("A development fold can only be used with the development split")

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
    structured_config = (
        StructuredConfig()
        if structured_filter is None
        else StructuredConfig(enabled=structured_filter)
    )
    retriever = HybridRetriever(catalog_path, structured_config=structured_config)
    observer = AgentObserver(
        Agent(catalog_path, retriever=retriever),
        catalog_ids=catalog_ids,
    )
    initialization_ms = (time.perf_counter() - initialization_started) * 1000.0
    evaluation_started = time.perf_counter()
    result = evaluate(observer, evaluation_samples, catalog_ids, categories, products)
    evaluation_wall_ms = (time.perf_counter() - evaluation_started) * 1000.0
    result = add_scenario_scores(result)
    result["observed_run_counts"] = observer.counts()
    result["timing"] = {
        "initialization_ms": round(initialization_ms, 6),
        "evaluation_wall_ms": round(evaluation_wall_ms, 6),
        "responses": observer.timing(),
    }
    result["evaluation"] = {
        "dataset": str(dataset_path),
        "split": split,
        "split_manifest": str(public_split_path) if split != "full" else None,
        "split_version": public_split.get("version") if split != "full" else None,
        "development_fold": fold_name,
        "development_fold_manifest": str(development_fold_path) if split == "development" else None,
        "development_fold_version": development_folds.get("version") if development_folds else None,
        "structured_filter": structured_config.enabled,
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
        const=True,
        dest="structured_filter",
        help="Explicitly enable the retained structured filter (the default).",
    )
    retrieval_mode.add_argument(
        "--lexical-only",
        action="store_const",
        const=False,
        dest="structured_filter",
        help="Disable structured filtering for the lexical ablation.",
    )
    parser.set_defaults(structured_filter=None)
    parser.add_argument("--output", default="results.json")
    args = parser.parse_args()

    result = evaluate_split(
        catalog_path=args.catalog,
        dataset_path=args.dataset,
        split=args.split,
        public_split_path=args.public_split,
        development_fold_path=args.development_fold_manifest,
        fold_name=args.fold,
        structured_filter=args.structured_filter,
    )
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "sessions"}, indent=2))


if __name__ == "__main__":
    main()
