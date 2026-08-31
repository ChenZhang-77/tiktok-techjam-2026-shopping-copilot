"""Competition delivery entry; the retained Control Plane is unchanged."""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path

from starter.agent import Agent as CoreAgent
from starter.retrieval.product_reranker import BudgetedRanker, ProductReranker
from starter.retrieval.conditional_dense import ConditionalDenseRetriever
from starter.retrieval.dense import DenseConfig
from starter.retrieval.semantic_ranker import DeepSeekSemanticRanker, SemanticRankError


@dataclass(frozen=True)
class DeliveryConfig:
    mode: str = "offline"
    max_calls: int = 0
    max_usd: float = 0.0
    max_seconds: float = 0.0

    def __post_init__(self):
        if self.mode not in {"offline", "llm"}:
            raise ValueError("mode must be offline or llm")
        if type(self.max_calls) is not int or self.max_calls < 0:
            raise ValueError("max_calls must be a nonnegative integer")
        for name in ("max_usd", "max_seconds"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")

    @classmethod
    def from_env(cls):
        return cls(mode=os.environ.get("SHOPPING_MODE", "offline"),
            max_calls=int(os.environ.get("SHOPPING_MAX_CALLS", "0")),
            max_usd=float(os.environ.get("SHOPPING_MAX_USD", "0")),
            max_seconds=float(os.environ.get("SHOPPING_MAX_SECONDS", "0")))


class _UnavailableRanker:
    def rank(self, request):
        raise SemanticRankError("no_key")


class Agent(CoreAgent):
    def __init__(self, catalog_path=None, *, config=None, retriever=None, backend=None,
                 strategy_config=None):
        self.delivery_config = config or DeliveryConfig.from_env()
        if retriever is None:
            catalog_path = catalog_path or os.environ.get("SHOPPING_CATALOG", "data/catalog.jsonl")
            retriever = ConditionalDenseRetriever.from_catalog(catalog_path, dense_config=DenseConfig(
                cache_dir=Path(os.environ.get("SHOPPING_DENSE_CACHE", "embeddings/minilm-l6-v2-v1")),
                model_cache_dir=Path(os.environ.get("SHOPPING_MODEL_CACHE", "models/huggingface/hub"))))
        self.local_retriever = retriever
        super().__init__(catalog_path, retriever=retriever, strategy_config=strategy_config)
        self.ledger = None
        self.reranker = None
        if self.delivery_config.mode == "llm":
            if backend is None:
                api_key = os.environ.get("DEEPSEEK_API_KEY", "")
                if api_key:
                    backend = DeepSeekSemanticRanker(api_key=api_key)
            self.ledger = BudgetedRanker(backend,
                max_calls=self.delivery_config.max_calls,
                max_usd=self.delivery_config.max_usd,
                max_seconds=self.delivery_config.max_seconds)
            self.reranker = ProductReranker(self.retriever,
                self.ledger if backend is not None else _UnavailableRanker())
            self.retriever = self.reranker

    def respond(self, session_id, user_message, turn, top_k):
        attempts_before = len(self.ledger.records) if self.ledger else 0
        reranks_before = len(self.reranker.records) if self.reranker else 0
        response = super().respond(session_id, user_message, turn, top_k)
        records = self.ledger.records if self.ledger else []
        for key in ("prompt_tokens", "completion_tokens"):
            response.setdefault("usage", {}).setdefault(key, 0)
            response["usage"][key] += sum(r[key] for r in records[attempts_before:])
        turn_status = "offline" if self.reranker is None else "skipped"
        reason = None
        if self.reranker and len(self.reranker.records) > reranks_before:
            reason = self.reranker.records[-1]["failure"]
            turn_status = "fallback" if reason else "success"
        response.setdefault("diagnostics", {})["delivery"] = {
            "requested_mode": self.delivery_config.mode,
            "turn_status": turn_status, "reason": reason,
            "attempts": len(records),
            "successes": sum(r["failure"] is None for r in records),
            "fallbacks": sum(bool(r["failure"]) for r in self.reranker.records) if self.reranker else 0,
            "cost_allowance_usd": self.ledger.total_cost if self.ledger else 0.0,
            "stop_reason": self.ledger.stop_reason if self.ledger else None,
        }
        return response

    def close(self):
        close = getattr(self.local_retriever, "close", None)
        if close is not None:
            close()
