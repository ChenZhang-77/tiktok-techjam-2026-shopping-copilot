from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Protocol

from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
from evaluator.splits import filter_samples, load_split_manifest
from experiments.development_folds import validate_development_fold_manifest
from experiments.evaluation_reporting import code_provenance
from starter.agent import Agent
from starter.core.semantic_understanding import (
    FakeSemanticBackend,
    GuardedSemanticInterpreter,
    InterpreterConfig,
)


VOLATILE_RESPONSE_FIELDS = {"latency_ms", "stage_latencies_ms"}


def response_behavior_projection(value: object) -> object:
    """Remove only measured latency while retaining all behavior and route fields."""

    if isinstance(value, dict):
        return {
            key: response_behavior_projection(item)
            for key, item in value.items()
            if key not in VOLATILE_RESPONSE_FIELDS
        }
    if isinstance(value, list):
        return [response_behavior_projection(item) for item in value]
    return value


class ShadowAgent(Protocol):
    def reset(self, session_id: str, user_profile: dict) -> None:
        ...

    def respond(
        self,
        session_id: str,
        user_message: str,
        turn: int,
        top_k: int,
    ) -> dict:
        ...

    def semantic_diagnostics(
        self,
        session_id: str,
        turn: int,
    ) -> dict[str, object] | None:
        ...


class PairedShadowAgent:
    """Return the comparator response while auditing a Shadow Agent turn-for-turn."""

    def __init__(self, baseline: ShadowAgent, shadow: ShadowAgent) -> None:
        self.baseline = baseline
        self.shadow = shadow
        self._diagnostics: list[dict[str, object]] = []
        self._exact_response_mismatches = 0
        self._public_response_mismatches = 0

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.baseline.reset(session_id, user_profile)
        self.shadow.reset(session_id, user_profile)

    def respond(
        self,
        session_id: str,
        user_message: str,
        turn: int,
        top_k: int,
    ) -> dict:
        baseline_response = self.baseline.respond(
            session_id,
            user_message,
            turn,
            top_k,
        )
        shadow_response = self.shadow.respond(
            session_id,
            user_message,
            turn,
            top_k,
        )
        if shadow_response != baseline_response:
            self._exact_response_mismatches += 1
        if response_behavior_projection(shadow_response) != response_behavior_projection(
            baseline_response
        ):
            self._public_response_mismatches += 1
        diagnostics = self.shadow.semantic_diagnostics(session_id, turn)
        self._diagnostics.append(
            diagnostics
            if diagnostics is not None
            else {
                "status": "fallback",
                "trigger_signals": [],
                "backend_called": False,
                "fallback_reason": "diagnostics_unavailable",
                "latency_ms": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }
        )
        return baseline_response

    def summary(self) -> dict[str, object]:
        return summarize_shadow_diagnostics(
            self._diagnostics,
            public_response_mismatches=self._public_response_mismatches,
            exact_response_mismatches=self._exact_response_mismatches,
        )


def summarize_shadow_diagnostics(
    diagnostics: list[dict[str, object]],
    *,
    public_response_mismatches: int,
    exact_response_mismatches: int | None = None,
) -> dict[str, object]:
    trigger_counts: Counter[str] = Counter()
    fallback_reasons: Counter[str] = Counter()
    eligible_turns = 0
    backend_called_turns = 0
    valid_delta_turns = 0
    prompt_tokens = 0
    completion_tokens = 0
    latencies: list[float] = []
    for item in diagnostics:
        signals = item.get("trigger_signals")
        valid_signals = [
            signal
            for signal in signals
            if isinstance(signals, list) and isinstance(signal, str) and signal
        ] if isinstance(signals, list) else []
        trigger_counts.update(valid_signals)
        if valid_signals:
            eligible_turns += 1
        backend_called = item.get("backend_called") is True
        if backend_called:
            backend_called_turns += 1
            latency = item.get("latency_ms")
            if (
                isinstance(latency, (int, float))
                and not isinstance(latency, bool)
                and math.isfinite(latency)
                and latency >= 0
            ):
                latencies.append(float(latency))
        if item.get("status") == "valid_shadow_delta":
            valid_delta_turns += 1
        fallback_reason = item.get("fallback_reason")
        if isinstance(fallback_reason, str) and fallback_reason:
            fallback_reasons[fallback_reason] += 1
        for key, destination in (
            ("prompt_tokens", "prompt"),
            ("completion_tokens", "completion"),
        ):
            value = item.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                if destination == "prompt":
                    prompt_tokens += value
                else:
                    completion_tokens += value

    ordered = sorted(latencies)

    def percentile(fraction: float) -> float:
        if not ordered:
            return 0.0
        index = max(0, math.ceil(fraction * len(ordered)) - 1)
        return round(ordered[index], 6)

    return {
        "response_count": len(diagnostics),
        "exact_response_mismatches": (
            public_response_mismatches
            if exact_response_mismatches is None
            else exact_response_mismatches
        ),
        "public_response_mismatches": public_response_mismatches,
        "eligible_turns": eligible_turns,
        "backend_called_turns": backend_called_turns,
        "valid_delta_turns": valid_delta_turns,
        "fallback_reasons": dict(sorted(fallback_reasons.items())),
        "trigger_counts": dict(sorted(trigger_counts.items())),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": {
            "p50": percentile(0.50),
            "p95": percentile(0.95),
            "max": round(ordered[-1], 6) if ordered else 0.0,
        },
    }


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _abstain_payload() -> dict[str, object]:
    return {
        "intent_hint": None,
        "positive_constraints": [],
        "rejected_constraints": [],
        "no_preference_attributes": [],
        "override_attributes": [],
        "semantic_terms": [],
        "abstain": True,
    }


def run_development_shadow(
    *,
    mode: str,
    catalog_path: str | Path = "data/catalog.jsonl",
    dataset_path: str | Path = "data/public_set.jsonl",
    public_split_path: str | Path = "docs/public_split_v1.json",
    development_fold_path: str | Path = "docs/development_folds_v1.json",
) -> dict[str, object]:
    if mode not in {"disabled", "no_key", "fake"}:
        raise ValueError("A13 offline Shadow mode must be disabled, no_key, or fake")
    samples = load_jsonl(dataset_path)
    split = load_split_manifest(public_split_path)
    folds = load_split_manifest(development_fold_path)
    validate_development_fold_manifest(samples, split, folds)
    development = filter_samples(samples, "development", split)
    if len(development) != 160:
        raise ValueError("A13-S0 requires the fixed Development-160 split")

    catalog_ids, categories, products = catalog_index(catalog_path)
    backend = FakeSemanticBackend(_abstain_payload())
    config = {
        "disabled": InterpreterConfig(enabled=False, key_available=True),
        "no_key": InterpreterConfig(enabled=True, key_available=False),
        "fake": InterpreterConfig(enabled=True, key_available=True),
    }[mode]
    baseline = Agent(catalog_path)
    shadow = Agent(
        catalog_path,
        semantic_interpreter=GuardedSemanticInterpreter(backend, config=config),
    )
    paired = PairedShadowAgent(baseline, shadow)
    try:
        evaluation = evaluate(
            paired,
            development,
            catalog_ids,
            categories,
            products,
        )
    finally:
        for agent in (baseline, shadow):
            close = getattr(agent.retriever, "close", None)
            if callable(close):
                close()

    return {
        "version": "a13-s0-offline-shadow-v1",
        "mode": mode,
        "code_provenance": code_provenance(),
        "inputs": {
            "catalog_sha256": _sha256(catalog_path),
            "public_set_sha256": _sha256(dataset_path),
            "public_split_sha256": _sha256(public_split_path),
            "development_folds_sha256": _sha256(development_fold_path),
        },
        "evaluation": evaluation,
        "shadow": {
            **paired.summary(),
            "fake_backend_calls": backend.calls,
            "remote_api_calls": 0,
        },
        "boundaries": {
            "split": "development",
            "sample_count": len(development),
            "public_response_source": "deterministic_comparator",
            "llm_transport_implemented": False,
            "api_key_read": False,
            "full_or_holdout_runs": 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run A13-S0 offline disabled/no-key/fake Shadow parity."
    )
    parser.add_argument("--mode", choices=("disabled", "no_key", "fake"), required=True)
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run_development_shadow(mode=args.mode, catalog_path=args.catalog)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "technical_score": report["evaluation"]["recommended_technical_score"],
                "shadow": report["shadow"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
