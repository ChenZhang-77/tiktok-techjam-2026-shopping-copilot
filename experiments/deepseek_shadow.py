"""Run a bounded DeepSeek shadow pass without changing Agent responses."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from evaluator.local_evaluator import Agent, catalog_index, evaluate, load_jsonl
from evaluator.splits import filter_samples, load_split_manifest
from starter.retrieval.semantic_ranker import (
    DeepSeekSemanticRanker,
    SemanticRankItem,
    SemanticRankRequest,
)


INPUT_PRICE_OFF_PEAK = 0.22
OUTPUT_PRICE_OFF_PEAK = 0.66


def _load_local_env(root: Path) -> None:
    """Load simple KEY=value entries without executing the credentials file."""
    env_path = root / ".env.local"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def _hash_payload(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _evidence(product: dict) -> str:
    fields = ("title", "categories", "features", "details", "description", "store")
    return " ".join(str(product.get(field, "")) for field in fields)[:700]


class ShadowAgent(Agent):
    """Call the ranker after each response while returning the original response."""

    def __init__(self, *args, products: dict[str, dict], ranker: DeepSeekSemanticRanker, records: list[dict], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._products = products
        self._ranker = ranker
        self._records = records

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        response = super().respond(session_id, user_message, turn, top_k)
        recommendations = response.get("recommendations") if isinstance(response, dict) else []
        items: list[SemanticRankItem] = []
        for item in recommendations if isinstance(recommendations, list) else []:
            if not isinstance(item, dict):
                continue
            candidate_id = str(item.get("parent_asin", "")).strip()
            product = self._products.get(candidate_id)
            if candidate_id and product is not None:
                items.append(SemanticRankItem(candidate_id, _evidence(product)))
        if not items:
            return response

        diagnostics = response.get("diagnostics") if isinstance(response, dict) else {}
        state = diagnostics if isinstance(diagnostics, dict) else {}
        constraints = state.get("active_constraints", [])
        compact_constraints = []
        if isinstance(constraints, list):
            for constraint in constraints:
                if isinstance(constraint, dict):
                    compact_constraints.append(
                        f"{constraint.get('attribute', '')}:{constraint.get('value', '')}"
                    )
        try:
            outcome = self._ranker.rank(
                SemanticRankRequest(
                    query=user_message,
                    active_constraints=tuple(compact_constraints),
                    items=tuple(items),
                    timeout_ms=8000,
                )
            )
            pre_rank = [item.opaque_id for item in items]
            shadow_rank = list(outcome.ordered_ids)
            self._records.append(
                {
                    "session_id": session_id,
                    "turn": turn,
                    "eligible": True,
                    "activated": True,
                    "pre_rank": pre_rank,
                    "shadow_rank": shadow_rank,
                    "shadow_changed": pre_rank != shadow_rank,
                    "provider_model": outcome.provider_model,
                    "request_id_present": bool(outcome.provider_request_id),
                    "prompt_tokens": outcome.usage.prompt_tokens,
                    "completion_tokens": outcome.usage.completion_tokens,
                    "latency_ms": round(outcome.latency_ms, 3),
                    "prompt_hash": _hash_payload({"query": user_message, "constraints": compact_constraints}),
                    "config_hash": _hash_payload({"model": outcome.provider_model, "max_tokens": self._ranker.max_tokens}),
                }
            )
        except Exception as error:
            self._records.append(
                {
                    "session_id": session_id,
                    "turn": turn,
                    "eligible": True,
                    "activated": False,
                    "fallback_reason": type(error).__name__,
                    "exact_fallback": True,
                }
            )
        return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DeepSeek in non-invasive shadow mode.")
    parser.add_argument("--limit", type=int, default=5, help="Development samples to shadow; default 5.")
    parser.add_argument("--output", default="/private/tmp/tiktok-techjam-deepseek-shadow.json")
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()
    if args.limit <= 0:
        raise SystemExit("--limit must be positive")

    root = Path(__file__).resolve().parents[1]
    _load_local_env(root)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY is missing; configure .env.local first")

    samples = load_jsonl(root / "data/public_set.jsonl")
    manifest = load_split_manifest(root / "docs/public_split_v1.json")
    development = filter_samples(samples, "development", manifest)[: args.limit]
    catalog_ids, categories, products = catalog_index(root / "data/catalog.jsonl")
    records: list[dict] = []
    ranker = DeepSeekSemanticRanker(max_tokens=args.max_tokens)
    agent = ShadowAgent(root / "data/catalog.jsonl", products=products, ranker=ranker, records=records)
    try:
        baseline_result = evaluate(agent, development, catalog_ids, categories, products)
    finally:
        close = getattr(getattr(agent, "retriever", None), "close", None)
        if callable(close):
            close()

    prompt_tokens = sum(int(record.get("prompt_tokens", 0)) for record in records)
    completion_tokens = sum(int(record.get("completion_tokens", 0)) for record in records)
    cost = prompt_tokens / 1_000_000 * INPUT_PRICE_OFF_PEAK + completion_tokens / 1_000_000 * OUTPUT_PRICE_OFF_PEAK
    report = {
        "mode": "shadow",
        "sample_count": len(development),
        "user_visible_sort_changes": 0,
        "shadow_calls": len(records),
        "successful_calls": sum(1 for record in records if record.get("activated")),
        "fallback_calls": sum(1 for record in records if not record.get("activated")),
        "shadow_sort_changes": sum(1 for record in records if record.get("shadow_changed")),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd_off_peak": round(cost, 8),
        "pricing_snapshot": {
            "input_cache_miss_usd_per_million": INPUT_PRICE_OFF_PEAK,
            "output_usd_per_million": OUTPUT_PRICE_OFF_PEAK,
        },
        "baseline_metrics_unchanged_by_shadow": {
            key: baseline_result[key]
            for key in ("hit_rate_at_10", "mrr", "mttc", "efficiency", "recommended_technical_score")
        },
        "calls": records,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "calls"}, indent=2))


if __name__ == "__main__":
    main()
