"""DS1: DeepSeek reranks the existing Browsing Top-10 only."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from evaluator.local_evaluator import Agent, catalog_index, evaluate, load_jsonl
from evaluator.splits import filter_samples, load_split_manifest
from experiments.development_folds import filter_development_fold
from starter.retrieval.semantic_ranker import (
    DeepSeekSemanticRanker,
    SemanticRankItem,
    SemanticRankRequest,
)
from starter.retrieval import HybridRetriever, StructuredConfig


INPUT_PRICE_OFF_PEAK = 0.22
OUTPUT_PRICE_OFF_PEAK = 0.66


def load_local_env(root: Path) -> None:
    env_path = root / ".env.local"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() and value.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def evidence(product: dict) -> str:
    return " ".join(
        str(product.get(field, ""))
        for field in ("title", "categories", "features", "details", "description", "store")
    )[:700]


class DS1Agent(Agent):
    def __init__(self, *args, products: dict[str, dict], ranker: DeepSeekSemanticRanker, records: list[dict], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.products = products
        self.ranker = ranker
        self.records = records

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        response = super().respond(session_id, user_message, turn, top_k)
        diagnostics = response.get("diagnostics", {}) if isinstance(response, dict) else {}
        if not isinstance(diagnostics, dict) or diagnostics.get("intent") != "browsing":
            return response
        recommendations = response.get("recommendations", [])
        if not isinstance(recommendations, list) or len(recommendations) < 2:
            return response
        recommendations = recommendations[:10]
        items = []
        by_id = {}
        for item in recommendations:
            if not isinstance(item, dict):
                continue
            candidate_id = str(item.get("parent_asin", "")).strip()
            product = self.products.get(candidate_id)
            if candidate_id and product is not None:
                items.append(SemanticRankItem(candidate_id, evidence(product)))
                by_id[candidate_id] = item
        if len(items) < 2:
            return response
        constraints = diagnostics.get("active_constraints", [])
        compact_constraints = tuple(
            f"{item.get('attribute', '')}:{item.get('value', '')}"
            for item in constraints
            if isinstance(item, dict)
        )
        try:
            outcome = self.ranker.rank(
                SemanticRankRequest(
                    query=user_message,
                    active_constraints=compact_constraints,
                    items=tuple(items),
                    timeout_ms=8000,
                )
            )
            ordered = [by_id[candidate_id] for candidate_id in outcome.ordered_ids]
            response["recommendations"] = ordered + response.get("recommendations", [])[10:]
            self.records.append({
                "turn": turn,
                "activated": True,
                "shadow_changed": [item.get("parent_asin") for item in recommendations] != list(outcome.ordered_ids),
                "prompt_tokens": outcome.usage.prompt_tokens,
                "completion_tokens": outcome.usage.completion_tokens,
                "latency_ms": round(outcome.latency_ms, 3),
                "provider_model": outcome.provider_model,
            })
        except Exception as error:
            self.records.append({"turn": turn, "activated": False, "fallback_reason": type(error).__name__})
        return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DS1 DeepSeek Top-10 reranking on Development.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--split", choices=("development", "holdout"), default="development")
    parser.add_argument("--fold", choices=("fold_1", "fold_2", "fold_3", "fold_4"))
    parser.add_argument("--output", default="/private/tmp/tiktok-techjam-deepseek-ds1.json")
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_local_env(root)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY is missing; configure .env.local first")
    samples = load_jsonl(root / "data/public_set.jsonl")
    manifest = load_split_manifest(root / "docs/public_split_v1.json")
    development = filter_samples(samples, args.split, manifest)
    if args.fold:
        if args.split != "development":
            raise SystemExit("--fold can only be used with --split development")
        folds = load_split_manifest(root / "docs/development_folds_v1.json")
        development = filter_development_fold(development, folds, args.fold)
    development = development[: args.limit]
    catalog_ids, categories, products = catalog_index(root / "data/catalog.jsonl")
    records: list[dict] = []
    agent = DS1Agent(
        root / "data/catalog.jsonl",
        products=products,
        ranker=DeepSeekSemanticRanker(max_tokens=args.max_tokens),
        records=records,
        retriever=HybridRetriever(
            root / "data/catalog.jsonl",
            structured_config=StructuredConfig(enabled=True),
            constraint_rerank_enabled=True,
        ),
    )
    try:
        result = evaluate(agent, development, catalog_ids, categories, products)
    finally:
        close = getattr(getattr(agent, "retriever", None), "close", None)
        if callable(close):
            close()
    prompt_tokens = sum(int(item.get("prompt_tokens", 0)) for item in records)
    completion_tokens = sum(int(item.get("completion_tokens", 0)) for item in records)
    cost = prompt_tokens / 1_000_000 * INPUT_PRICE_OFF_PEAK + completion_tokens / 1_000_000 * OUTPUT_PRICE_OFF_PEAK
    report = {
        "experiment": "DS1-deepseek-browsing-top10",
        "split": args.split,
        "sample_count": len(development),
        "fold": args.fold,
        "api_calls": len(records),
        "successful_calls": sum(1 for item in records if item.get("activated")),
        "fallback_calls": sum(1 for item in records if not item.get("activated")),
        "shadow_sort_changes": sum(1 for item in records if item.get("shadow_changed")),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd_off_peak": round(cost, 8),
        "metrics": {key: result[key] for key in ("hit_rate_at_10", "mrr", "mttc", "efficiency", "recommended_technical_score")},
        "sessions": result["sessions"],
        "calls": records,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"sessions", "calls"}}, indent=2))


if __name__ == "__main__":
    main()
