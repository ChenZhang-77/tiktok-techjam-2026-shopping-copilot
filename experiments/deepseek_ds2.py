"""DS2: DeepSeek reranks a bounded Browsing Top-20 candidate pool."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from pathlib import Path

from evaluator.local_evaluator import Agent, catalog_index, evaluate, load_jsonl
from evaluator.splits import filter_samples, load_split_manifest
from starter.contracts import RetrievalRequest, RetrievalResult
from starter.retrieval import HybridRetriever, StructuredConfig
from starter.retrieval.semantic_ranker import (
    DeepSeekSemanticRanker,
    SemanticRankItem,
    SemanticRankRequest,
)

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
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def evidence(candidate) -> str:
    return str(candidate.evidence_text or "")[:700]


class DS2Retriever:
    """Rerank Top-20 before Agent truncates the response to Top-10."""

    def __init__(self, base, ranker, records):
        self.base = base
        self.ranker = ranker
        self.records = records
        self.catalog_ids = base.catalog_ids
        self.fallback_ids = base.fallback_ids
        self.catalog_path = getattr(base, "catalog_path", None)

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        base = self.base.retrieve(request)
        if request.intent != "browsing" or len(base.candidates) < 20:
            return base
        pool = base.candidates[:20]
        items = tuple(
            SemanticRankItem(candidate.parent_asin, evidence(candidate))
            for candidate in pool
        )
        constraints = tuple(
            f"{item.get('attribute', '')}:{item.get('normalized_value', item.get('raw_value', ''))}"
            for item in request.active_constraints
            if isinstance(item, dict)
        )
        try:
            outcome = self.ranker.rank(
                SemanticRankRequest(
                    query=request.query,
                    active_constraints=constraints,
                    items=items,
                    timeout_ms=8000,
                )
            )
            by_id = {candidate.parent_asin: candidate for candidate in pool}
            ordered = [by_id[candidate_id] for candidate_id in outcome.ordered_ids]
            self.records.append({
                "activated": True,
                "shadow_changed": [candidate.parent_asin for candidate in pool] != list(outcome.ordered_ids),
                "prompt_tokens": outcome.usage.prompt_tokens,
                "completion_tokens": outcome.usage.completion_tokens,
                "latency_ms": round(outcome.latency_ms, 3),
                "provider_model": outcome.provider_model,
            })
            return replace(base, candidates=[*ordered, *base.candidates[20:]])
        except Exception as error:
            self.records.append({
                "activated": False,
                "fallback_reason": type(error).__name__,
                "fallback_detail": str(error)[:120],
            })
            return base

    def close(self) -> None:
        close = getattr(self.base, "close", None)
        if callable(close):
            close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DS2 DeepSeek Browsing Top-20 reranking.")
    parser.add_argument("--split", choices=("development", "holdout"), default="development")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output", default="/private/tmp/tiktok-techjam-deepseek-ds2.json")
    parser.add_argument("--max-tokens", type=int, default=384)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_local_env(root)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY is missing; configure .env.local first")
    samples = load_jsonl(root / "data/public_set.jsonl")
    manifest = load_split_manifest(root / "docs/public_split_v1.json")
    selected = filter_samples(samples, args.split, manifest)[: args.limit]
    catalog_ids, categories, products = catalog_index(root / "data/catalog.jsonl")
    records = []
    base = HybridRetriever(
        root / "data/catalog.jsonl",
        structured_config=StructuredConfig(enabled=True),
        constraint_rerank_enabled=True,
    )
    retriever = DS2Retriever(base, DeepSeekSemanticRanker(max_tokens=args.max_tokens), records)
    agent = Agent(root / "data/catalog.jsonl", retriever=retriever)
    try:
        result = evaluate(agent, selected, catalog_ids, categories, products)
    finally:
        retriever.close()
    prompt_tokens = sum(int(item.get("prompt_tokens", 0)) for item in records)
    completion_tokens = sum(int(item.get("completion_tokens", 0)) for item in records)
    cost = prompt_tokens / 1_000_000 * INPUT_PRICE_OFF_PEAK + completion_tokens / 1_000_000 * OUTPUT_PRICE_OFF_PEAK
    report = {
        "experiment": "DS2-deepseek-browsing-top20",
        "split": args.split,
        "sample_count": len(selected),
        "candidate_pool_size": 20,
        "api_calls": len(records),
        "successful_calls": sum(1 for item in records if item.get("activated")),
        "fallback_calls": sum(1 for item in records if not item.get("activated")),
        "pool_order_changes": sum(1 for item in records if item.get("shadow_changed")),
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
