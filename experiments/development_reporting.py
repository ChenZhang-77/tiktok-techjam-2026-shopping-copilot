from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
from evaluator.splits import filter_samples, load_split_manifest
from experiments.development_folds import (
    filter_development_fold,
    validate_development_fold_manifest,
)
from starter.agent import Agent


class AgentObserver:
    def __init__(self, agent: object) -> None:
        self._agent = agent
        self._respond_exceptions = 0
        self._invalid_response_payloads = 0
        self._reported_fallbacks = 0

    def reset(self, session_id: str, user_profile: dict) -> None:
        self._agent.reset(session_id, user_profile)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        try:
            response = self._agent.respond(session_id, user_message, turn, top_k)
        except Exception:
            self._respond_exceptions += 1
            raise
        if (
            not isinstance(response, dict)
            or not isinstance(response.get("message"), str)
            or not isinstance(response.get("recommendations"), list)
        ):
            self._invalid_response_payloads += 1
        diagnostics = response.get("diagnostics") if isinstance(response, dict) else None
        if isinstance(diagnostics, dict) and diagnostics.get("fallback_used") is True:
            self._reported_fallbacks += 1
        return response

    def counts(self) -> dict:
        return {
            "respond_exceptions": self._respond_exceptions,
            "invalid_response_payloads": self._invalid_response_payloads,
            "reported_fallbacks": self._reported_fallbacks,
            "internal_fallbacks": None,
            "internal_fallbacks_note": "Not observable through the A-side public Agent interface.",
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


def evaluate_development(
    *,
    catalog_path: str | Path,
    dataset_path: str | Path,
    public_split_path: str | Path,
    development_fold_path: str | Path,
    fold_name: str | None = None,
) -> dict:
    samples = load_jsonl(dataset_path)
    public_split = load_split_manifest(public_split_path)
    development_folds = load_split_manifest(development_fold_path)
    validate_development_fold_manifest(samples, public_split, development_folds)
    development_samples = filter_samples(samples, "development", public_split)
    evaluation_samples = (
        filter_development_fold(development_samples, development_folds, fold_name)
        if fold_name
        else development_samples
    )

    catalog_ids, categories, products = catalog_index(catalog_path)
    observer = AgentObserver(Agent(catalog_path))
    result = evaluate(observer, evaluation_samples, catalog_ids, categories, products)
    result = add_scenario_scores(result)
    result["observed_run_counts"] = observer.counts()
    result["evaluation"] = {
        "dataset": str(dataset_path),
        "split": "development",
        "split_manifest": str(public_split_path),
        "split_version": public_split.get("version"),
        "development_fold": fold_name,
        "development_fold_manifest": str(development_fold_path),
        "development_fold_version": development_folds.get("version"),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a scored Development Set experiment report.")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--public-split", default="docs/public_split_v1.json")
    parser.add_argument("--development-fold-manifest", default="docs/development_folds_v1.json")
    parser.add_argument("--fold", choices=("fold_1", "fold_2", "fold_3", "fold_4"))
    parser.add_argument("--output", default="results.json")
    args = parser.parse_args()

    result = evaluate_development(
        catalog_path=args.catalog,
        dataset_path=args.dataset,
        public_split_path=args.public_split,
        development_fold_path=args.development_fold_manifest,
        fold_name=args.fold,
    )
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "sessions"}, indent=2))


if __name__ == "__main__":
    main()
