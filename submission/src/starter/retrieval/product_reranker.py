"""Frozen F2 reranking/allowance logic, extracted from llm@a9e34ae.

Historical USD allowances are safeguards, not current pricing or an invoice.
No experiment/evaluator imports; behavior is retained for paired verification.
"""
from dataclasses import replace
from http.client import HTTPException
import hashlib
import json
import time

from starter.retrieval.semantic_ranker import (
    DeepSeekSemanticRanker, SemanticRankError, SemanticRankItem,
    SemanticRankRequest, validate_permutation,
)


def _key(row):
    return (str(row.get("attribute") or "").strip().lower(),
            str(row.get("normalized_value") or row.get("value") or row.get("raw_value") or "").strip().lower())


def _profiles(prefix, request):
    positive = {_key(c) for c in request.active_constraints if c.get("active", True)}
    hard = {_key(c) for c in request.active_constraints if c.get("active", True)
            and c.get("hard") and float(c.get("confidence") or 0) >= .75}
    rejected = {_key(c) for c in request.rejected_constraints
                if float(c.get("confidence") or 0) >= .75
                and _key(c)[0] not in request.no_preference_attributes} - positive
    return [(frozenset(hard & {_key(c) for c in item.diagnostics.get("structured_matches", [])}),
             frozenset(rejected & {_key(c) for c in item.diagnostics.get("rejected_constraint_matches", [])}))
            for item in prefix]


class BudgetedRanker:
    """One shared experiment budget; failed usage is unknown, never free."""

    def __init__(self, backend, *, max_calls=1400, max_usd=3.0, max_seconds=1800, journal=None):
        self.backend = backend
        self.max_calls = max_calls
        self.max_usd = max_usd
        self.max_seconds = max_seconds
        self.journal = journal
        self.records = []
        self.total_cost = 0.0
        self.consecutive_errors = 0
        self.stop_reason = None
        self.started = None

    def rank(self, request):
        now = time.monotonic()
        if self.started is None:
            self.started = now
        prompt = DeepSeekSemanticRanker._prompt(request)
        unknown_allowance = ((len(prompt.encode("utf-8")) * 2 + 4096) * .44 + 256 * 1.32) / 1e6
        if len(self.records) >= self.max_calls:
            self.stop_reason = "call_budget"
        elif self.total_cost + unknown_allowance > self.max_usd:
            self.stop_reason = "cost_budget"
        elif now - self.started >= self.max_seconds:
            self.stop_reason = "time_budget"
        if self.stop_reason:
            raise SemanticRankError(self.stop_reason)
        record = {"attempt": len(self.records) + 1,
            "request_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "prompt_tokens": 0, "completion_tokens": 0, "usage_known": False,
            "cost_allowance_usd": unknown_allowance, "failure": "incomplete_attempt"}
        outcome = None
        try:
            outcome = self.backend.rank(request)
            if outcome.fallback_reason:
                raise SemanticRankError(outcome.fallback_reason)
            counts = (outcome.usage.prompt_tokens, outcome.usage.completion_tokens)
            if any(type(n) is not int or n < 0 for n in counts) or counts[0] == 0:
                raise SemanticRankError("invalid_usage")
            record.update(prompt_tokens=counts[0], completion_tokens=counts[1], usage_known=True,
                cost_allowance_usd=(counts[0] * .44 + counts[1] * 1.32) / 1e6,
                provider_model=outcome.provider_model, finish_reason=outcome.finish_reason,
                prompt_cache_hit_tokens=outcome.usage.prompt_cache_hit_tokens,
                prompt_cache_miss_tokens=outcome.usage.prompt_cache_miss_tokens)
            if outcome.finish_reason != "stop":
                raise SemanticRankError("incomplete_response")
            validate_permutation(outcome.ordered_ids, tuple(i.opaque_id for i in request.items))
            record["failure"] = None
            self.consecutive_errors = 0
        except (SemanticRankError, ValueError, TypeError, AttributeError, HTTPException, OSError) as error:
            safe = {"no_key", "provider_error", "invalid_provider_json", "invalid_json_or_permutation",
                    "invalid_usage", "incomplete_response", "invalid_permutation"}
            reason = "provider_error" if isinstance(error, (HTTPException, OSError)) else str(error)
            record["failure"] = reason if reason in safe or (reason.startswith("http_") and reason[5:].isdigit()) else "invalid_outcome"
            self.consecutive_errors += 1
            if record["failure"] in {"http_401", "http_403", "no_key"}:
                self.stop_reason = "authorization_failure"
            elif self.consecutive_errors >= 3:
                self.stop_reason = "consecutive_errors"
        finally:
            record["latency_ms"] = (time.monotonic() - now) * 1000
            self.total_cost += record["cost_allowance_usd"]
            self.records.append(record)
            if self.journal:
                self.journal.write(json.dumps(record) + "\n")
                self.journal.flush()
            if self.journal and len(self.records) % 25 == 0:
                print(json.dumps({"attempts": len(self.records), "cost_allowance_usd": round(self.total_cost, 6),
                                  "failures": sum(bool(r["failure"]) for r in self.records)}), flush=True)
        if record["failure"]:
            raise SemanticRankError(record["failure"])
        return outcome


class ProductReranker:
    def __init__(self, base, ranker):
        self.base = base
        self.ranker = ranker
        self.records = []
        self.catalog_ids = base.catalog_ids
        self.fallback_ids = base.fallback_ids
        if hasattr(base, "catalog_path"):
            self.catalog_path = base.catalog_path

    def retrieve(self, request):
        result = self.base.retrieve(request)
        prefix = result.candidates[:min(10, request.top_k)]
        if request.intent != "browsing" or len(prefix) < 2 or result.diagnostics.fallback_used:
            return result
        aliases = [f"c{i}" for i in range(len(prefix))]
        started = time.perf_counter()
        reason = None
        ranked = prefix
        try:
            outcome = self.ranker.rank(SemanticRankRequest(query=request.query,
                active_constraints=tuple(f"{_key(c)[0]}={_key(c)[1]}"[:160]
                    for c in request.active_constraints if c.get("active", True))[:12],
                timeout_ms=8000, prompt_version="b10b-f1",
                items=tuple(SemanticRankItem(alias, candidate.evidence_text or "")
                            for alias, candidate in zip(aliases, prefix))))
            if outcome.fallback_reason:
                raise SemanticRankError(outcome.fallback_reason)
            validate_permutation(outcome.ordered_ids, aliases)
            profiles = _profiles(prefix, request)
            position = {a: i for i, a in enumerate(outcome.ordered_ids)}
            ranked = list(prefix)
            for profile in set(profiles):
                slots = [i for i, p in enumerate(profiles) if p == profile]
                preferred = sorted(slots, key=lambda i: position[aliases[i]])
                for slot, index in zip(slots, preferred):
                    ranked[slot] = prefix[index]
        except (SemanticRankError, ValueError) as error:
            reason = str(error) if isinstance(error, SemanticRankError) else "invalid_request"
        elapsed = (time.perf_counter() - started) * 1000
        self.records.append({"session_id": request.session_id, "turn": request.turn,
            "failure": reason, "changed": ranked != prefix,
            "membership_preserved": {c.parent_asin for c in ranked} == {c.parent_asin for c in prefix},
            "latency_ms": elapsed})
        diagnostics = result.diagnostics
        routes = list(diagnostics.executed_routes)
        fallback_route = diagnostics.fallback_route
        if reason and routes and not fallback_route:
            fallback_route = routes[0]
        if not reason and routes and "semantic_rerank" not in routes:
            routes.append("semantic_rerank")
        failures = dict(diagnostics.route_failures)
        if reason:
            failures["semantic_rerank"] = reason
        diagnostics = replace(diagnostics, fallback_used=bool(reason), fallback_route=fallback_route,
            executed_routes=routes, route_failures=failures, rerank_pool_size=len(prefix),
            latency_ms=(diagnostics.latency_ms or 0) + elapsed,
            stage_latencies_ms={**diagnostics.stage_latencies_ms, "semantic_rerank": elapsed})
        return replace(result, candidates=ranked + result.candidates[len(prefix):], diagnostics=diagnostics)
