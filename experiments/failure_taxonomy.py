from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any, Iterable


CAUSE_ORDER = (
    "extraction",
    "state_override",
    "intent_strategy_routing",
    "query_construction",
    "question_policy",
    "retrieval_recall",
    "ranking_filtering",
    "response_contract",
)
FLAG_FIELD_BY_CAUSE = {
    "extraction": "extraction_flags",
    "state_override": "state_override_flags",
    "intent_strategy_routing": "intent_strategy_flags",
    "query_construction": "query_construction_flags",
    "question_policy": "question_policy_flags",
    "response_contract": "response_contract_flags",
}
RECOMMENDATION_PRIORITY = (
    "state_override",
    "intent_strategy_routing",
    "extraction",
    "query_construction",
    "question_policy",
    "response_contract",
    "retrieval_recall",
    "ranking_filtering",
)
EXPLORATION_MARKERS = ("exploring", "browse", "browsing", "not sure", "ideas")


def _minimum_rank(turns: Iterable[dict[str, Any]], field: str) -> int | None:
    ranks = [
        value
        for turn in turns
        if turn.get("eligible") is True
        for value in [turn.get(field)]
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
    ]
    return min(ranks) if ranks else None


def classify_miss(turns: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify one missed session from offline, evaluator-side turn evidence."""

    eligible = [turn for turn in turns if turn.get("eligible") is True]
    best_lexical_rank = _minimum_rank(eligible, "target_lexical_rank")
    best_final_rank = _minimum_rank(eligible, "target_final_rank")
    retrieval_observed = any(
        "missing_retrieval_trace" not in turn.get("evaluation_validity_flags", [])
        for turn in eligible
    )
    retrieval_cause = None
    if retrieval_observed:
        if best_lexical_rank is None:
            retrieval_cause = "retrieval_recall"
        elif best_final_rank is None or best_final_rank > 10:
            retrieval_cause = "ranking_filtering"
    state_override_flags = sorted(
        {
            str(flag)
            for turn in eligible
            for flag in turn.get("state_override_flags", [])
            if str(flag)
        }
    )
    missing_disclosed_value_count = max(
        (
            int(turn.get("missing_disclosed_values") or 0)
            for turn in eligible
            if isinstance(turn.get("missing_disclosed_values"), int)
            and not isinstance(turn.get("missing_disclosed_values"), bool)
        ),
        default=0,
    )
    unproductive_reply_count = sum(
        turn.get("unproductive_reply") is True for turn in eligible
    )
    evidence: dict[str, list[str]] = {}
    for cause, field in FLAG_FIELD_BY_CAUSE.items():
        flags = sorted(
            {
                str(flag)
                for turn in eligible
                for flag in turn.get(field, [])
                if str(flag)
            }
        )
        if flags:
            evidence[cause] = flags
    if state_override_flags:
        evidence["state_override"] = state_override_flags
    if missing_disclosed_value_count:
        evidence.setdefault("extraction", []).append(
            f"missing_disclosed_values:{missing_disclosed_value_count}"
        )
    if unproductive_reply_count >= 2:
        evidence.setdefault("question_policy", []).append(
            f"unproductive_replies:{unproductive_reply_count}"
        )
    if best_final_rank is not None and best_final_rank <= 10:
        evidence.setdefault("response_contract", []).append(
            "retrieved_top_k_target_not_scored"
        )

    observed_causes = [cause for cause in CAUSE_ORDER if evidence.get(cause)]
    if retrieval_cause is not None:
        observed_causes.append(retrieval_cause)
        observed_causes = [cause for cause in CAUSE_ORDER if cause in observed_causes]
    primary = observed_causes[0] if observed_causes else None
    secondary = [cause for cause in observed_causes if cause != primary]
    evaluation_validity_flags = sorted(
        {
            str(flag)
            for turn in turns
            for flag in turn.get("evaluation_validity_flags", [])
            if str(flag)
        }
    )
    return {
        "primary_cause": primary,
        "secondary_causes": secondary,
        "best_lexical_rank": best_lexical_rank,
        "best_final_rank": best_final_rank,
        "state_override_flags": state_override_flags,
        "missing_disclosed_value_count": missing_disclosed_value_count,
        "unproductive_reply_count": unproductive_reply_count,
        "evidence": evidence,
        "evaluation_validity_flags": evaluation_validity_flags,
    }


def summarize_failures(classifications: list[dict[str, Any]]) -> dict[str, Any]:
    primary_counts = Counter(str(item["primary_cause"]) for item in classifications)
    scenario_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in classifications:
        scenario_counts[str(item["scenario_type"])][str(item["primary_cause"])] += 1
    control_causes = {
        "extraction",
        "state_override",
        "intent_strategy_routing",
        "query_construction",
        "question_policy",
        "response_contract",
    }
    control_count = sum(primary_counts[cause] for cause in control_causes)
    retrieval_count = sum(
        primary_counts[cause]
        for cause in {"retrieval_recall", "ranking_filtering"}
    )
    return {
        "primary_cause_counts": dict(sorted(primary_counts.items())),
        "owner_counts": {
            "control_plane": control_count,
            "retrieval_ranking": retrieval_count,
        },
        "by_scenario": {
            scenario: dict(sorted(counts.items()))
            for scenario, counts in sorted(scenario_counts.items())
        },
    }


def _ratio(hits: int, sessions: int) -> dict[str, int | float]:
    return {
        "hits": hits,
        "sessions": sessions,
        "recall": round(hits / sessions, 6) if sessions else 0.0,
    }


def target_recall_summary(
    sessions: list[dict[str, Any]],
    *,
    depths: tuple[int, ...] = (10, 30, 60, 80, 100, 120),
) -> dict[str, dict[str, int | float]]:
    retained_hits = 0
    for session in sessions:
        eligible = [turn for turn in session.get("turns", []) if turn.get("eligible") is True]
        if _minimum_rank(eligible, "target_lexical_rank") is not None:
            retained_hits += 1
    summary = {"retained_depth": _ratio(retained_hits, len(sessions))}
    for depth in depths:
        observable = []
        for session in sessions:
            eligible = [turn for turn in session.get("turns", []) if turn.get("eligible") is True]
            if any(int(turn.get("retrieval_depth") or 0) >= depth for turn in eligible):
                observable.append(eligible)
        hits = sum(
            any(
                isinstance(turn.get("target_lexical_rank"), int)
                and not isinstance(turn.get("target_lexical_rank"), bool)
                and 0 < int(turn["target_lexical_rank"]) <= depth
                for turn in turns
            )
            for turns in observable
        )
        summary[f"at_{depth}"] = _ratio(hits, len(observable))
    return summary


def _normalized_text(value: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _contains_phrase(corpus: str, phrase: object) -> bool:
    normalized = _normalized_text(phrase)
    if not normalized:
        return False
    return normalized in corpus


def _constraint_records(
    diagnostics: dict[str, Any],
    fields: Iterable[str],
) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for field in fields:
        values = diagnostics.get(field)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict):
                value = str(
                    item.get("value")
                    or item.get("normalized_value")
                    or item.get("raw_value")
                    or ""
                ).strip()
                if value:
                    records.append((str(item.get("attribute") or ""), value))
    return records


def _expected_constraint(value: object) -> tuple[str, str]:
    from evaluator.local_evaluator import classify_constraint

    raw = str(value or "").strip()
    attribute = classify_constraint(raw)
    payload = raw
    prefix, separator, remainder = raw.partition(":")
    normalized_prefix = prefix.strip().lower().replace(" ", "_")
    if separator and normalized_prefix in {
        "category",
        "material",
        "color",
        "size",
        "style",
        "brand",
        "budget",
        "feature",
        "use_case",
        "other",
    }:
        attribute = normalized_prefix
        payload = remainder
    return attribute, _normalized_text(payload)


def _matching_records(
    expected: object,
    records: Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    expected_attribute, expected_value = _expected_constraint(expected)
    matches: list[tuple[str, str]] = []
    for attribute, value in records:
        normalized_value = _normalized_text(value)
        if attribute != expected_attribute or not normalized_value or not expected_value:
            continue
        if normalized_value in expected_value or expected_value in normalized_value:
            matches.append((attribute, value))
    return matches


def _values_corpus(values: Iterable[object]) -> str:
    return _normalized_text(" ".join(str(value) for value in values))


def audit_session(
    *,
    sample: dict[str, Any],
    evaluation_session: dict[str, Any],
    intent_card: dict[str, Any],
    behavior: dict[str, Any],
    response_turns: list[dict[str, Any]],
    retrieval_turns: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Build a target-free audit record from offline evaluator evidence."""

    target = str(sample["ground_truth"]["parent_asin"])
    override = behavior.get("override") if isinstance(behavior, dict) else None
    override = override if isinstance(override, dict) else {}
    eligible_start = int(override.get("turn") or 1)
    old_value = str(override.get("old_value") or "")
    expected_values = [
        str(value)
        for field in ("hard_constraints", "soft_preferences")
        for value in intent_card.get(field, [])
        if str(value).strip()
    ]
    messages: list[str] = []
    prior_intent: str | None = None
    asked_attributes: set[str] = set()
    audited_turns: list[dict[str, Any]] = []
    for response_turn in sorted(response_turns, key=lambda item: int(item["turn"])):
        turn = int(response_turn["turn"])
        user_message = str(response_turn.get("user_message") or "")
        messages.append(user_message)
        response = response_turn.get("response")
        response = response if isinstance(response, dict) else {}
        diagnostics = response.get("diagnostics")
        diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
        intent = diagnostics.get("intent")
        intent = str(intent) if isinstance(intent, str) else None
        retrieval_trace = retrieval_turns.get(turn, {})
        request = retrieval_trace.get("request")
        routes = retrieval_trace.get("routes")
        routes = routes if isinstance(routes, dict) else {}
        lexical_result = routes.get("lexical")
        final_result = routes.get("structured") or retrieval_trace.get("result")
        lexical_candidates = list(getattr(lexical_result, "candidates", []) or [])
        candidates = list(getattr(final_result, "candidates", []) or [])
        lexical_target_candidate = next(
            (candidate for candidate in lexical_candidates if candidate.parent_asin == target),
            None,
        )
        target_candidate = next(
            (candidate for candidate in candidates if candidate.parent_asin == target),
            None,
        )
        lexical_rank = None
        final_rank = None
        if lexical_target_candidate is not None:
            raw_lexical_rank = lexical_target_candidate.diagnostics.get("lexical_rank")
            if isinstance(raw_lexical_rank, int) and not isinstance(raw_lexical_rank, bool):
                lexical_rank = raw_lexical_rank
            elif lexical_target_candidate in lexical_candidates:
                lexical_rank = lexical_candidates.index(lexical_target_candidate) + 1
        if target_candidate is not None:
            raw_final_rank = target_candidate.diagnostics.get("final_rank")
            final_rank = (
                raw_final_rank
                if isinstance(raw_final_rank, int)
                and not isinstance(raw_final_rank, bool)
                and raw_final_rank > 0
                else candidates.index(target_candidate) + 1
            )

        message_corpus = _values_corpus(messages)
        disclosed = [value for value in expected_values if _contains_phrase(message_corpus, value)]
        active_records = _constraint_records(diagnostics, ("active_constraints",))
        inactive_records = _constraint_records(
            diagnostics,
            ("rejected_constraints", "overridden_constraints"),
        )
        query_corpus = _normalized_text(diagnostics.get("distilled_query"))
        missing_disclosed_values = [
            _normalized_text(value)
            for value in disclosed
            if not _matching_records(value, [*active_records, *inactive_records])
        ]
        extraction_flags = [
            f"disclosed_value_not_extracted:{value}"
            for value in missing_disclosed_values
        ]
        query_construction_flags: list[str] = []
        for value in disclosed:
            matched_active = _matching_records(value, active_records)
            if matched_active and not any(
                _contains_phrase(query_corpus, record_value)
                for _, record_value in matched_active
            ):
                query_construction_flags.append(
                    f"active_value_missing_from_query:{_expected_constraint(value)[1]}"
                )
        query_construction_flags.extend(
            f"inactive_value_present_in_query:{_normalized_text(value)}"
            for _, value in inactive_records
            if _contains_phrase(query_corpus, value)
        )

        state_override_flags: list[str] = []
        if turn >= eligible_start and old_value and _matching_records(old_value, active_records):
            state_override_flags.append("override_old_value_still_active")
        lowered_message = user_message.lower()
        intent_strategy_flags: list[str] = []
        if (
            prior_intent == "buying"
            and intent == "browsing"
            and not any(marker in lowered_message for marker in EXPLORATION_MARKERS)
            and "actually" not in lowered_message
        ):
            intent_strategy_flags.append("buying_to_browsing_without_exploration")
        if intent is not None:
            prior_intent = intent

        strategy = getattr(request, "strategy", None)
        retrieval_depth = getattr(strategy, "retrieval_depth", 0)
        strategy_intent = getattr(strategy, "intent", None)
        if intent and strategy_intent and intent != strategy_intent:
            intent_strategy_flags.append("diagnostic_intent_differs_from_strategy")

        ask_attribute = response.get("ask_attribute")
        no_preference = {
            str(value)
            for value in diagnostics.get("no_preference_attributes", [])
            if str(value)
        }
        question_policy_flags: list[str] = []
        if isinstance(ask_attribute, str) and ask_attribute:
            if ask_attribute in asked_attributes:
                question_policy_flags.append(f"repeated_attribute:{ask_attribute}")
            if ask_attribute in no_preference:
                question_policy_flags.append(
                    f"asked_no_preference_attribute:{ask_attribute}"
                )
            if turn >= 10:
                question_policy_flags.append("asked_on_final_turn")
            asked_attributes.add(ask_attribute)

        recommendations = response.get("recommendations")
        recommendation_ids = [
            str(item.get("parent_asin") or "")
            for item in recommendations
            if isinstance(item, dict) and str(item.get("parent_asin") or "")
        ] if isinstance(recommendations, list) else []
        response_contract_flags: list[str] = []
        if not isinstance(response, dict) or not isinstance(recommendations, list):
            response_contract_flags.append("invalid_response_shape")
        if len(recommendation_ids) != len(set(recommendation_ids)):
            response_contract_flags.append("duplicate_recommendation_ids")
        if final_rank is not None and final_rank <= 10 and target not in recommendation_ids:
            response_contract_flags.append(
                "retrieved_top_k_target_missing_from_response"
            )

        evaluation_validity_flags: list[str] = []
        if request is None or lexical_result is None or final_result is None:
            evaluation_validity_flags.append("missing_retrieval_trace")
        audited_turns.append(
            {
                "turn": turn,
                "eligible": turn >= eligible_start,
                "retrieval_depth": int(retrieval_depth or 0),
                "candidate_count": len(candidates),
                "lexical_candidate_count": len(lexical_candidates),
                "target_lexical_rank": lexical_rank,
                "target_final_rank": final_rank,
                "intent": intent,
                "ask_attribute": ask_attribute,
                "unproductive_reply": lowered_message.startswith(
                    "i don't have an additional preference"
                ),
                "extraction_flags": extraction_flags,
                "state_override_flags": state_override_flags,
                "intent_strategy_flags": intent_strategy_flags,
                "query_construction_flags": sorted(set(query_construction_flags)),
                "question_policy_flags": question_policy_flags,
                "response_contract_flags": response_contract_flags,
                "evaluation_validity_flags": evaluation_validity_flags,
                "missing_disclosed_values": len(missing_disclosed_values),
                "active_constraint_count": len(diagnostics.get("active_constraints", [])),
                "rejected_constraint_count": len(diagnostics.get("rejected_constraints", [])),
            }
        )

    audit = {
        "sample_id": str(sample["sample_id"]),
        "scenario_type": str(sample["scenario_type"]),
        "hit": bool(evaluation_session.get("hit")),
        "first_hit_turn": evaluation_session.get("first_hit_turn"),
        "best_rank": evaluation_session.get("best_rank"),
        "eligible_turn_start": eligible_start,
        "turns": audited_turns,
    }
    if not audit["hit"]:
        audit["classification"] = classify_miss(audited_turns)
    return audit


def _next_experiment(summary: dict[str, Any]) -> dict[str, str]:
    counts = summary["primary_cause_counts"]
    if not any(int(counts.get(cause, 0)) for cause in CAUSE_ORDER):
        return {
            "id": "R0",
            "reason": "repair or collect valid failure evidence before changing behavior",
        }
    dominant = max(
        RECOMMENDATION_PRIORITY,
        key=lambda cause: (
            int(counts.get(cause, 0)),
            -RECOMMENDATION_PRIORITY.index(cause),
        ),
    )
    experiment = {
        "extraction": ("A11", "harden extraction and clause scope"),
        "state_override": ("A8", "stabilize cross-turn state and override handling"),
        "intent_strategy_routing": ("A8", "stabilize intent assessment before B routing"),
        "query_construction": ("A10b", "make the internal QueryPlan auditable"),
        "question_policy": ("A9", "add the should-ask gate after AB0"),
        "retrieval_recall": ("B11", "test one lexical recall variable after AB1"),
        "ranking_filtering": ("B8", "test the earliest diagnosed ranking intervention"),
        "response_contract": ("R4", "repair response/contract loss before optimization"),
    }[dominant]
    return {"id": experiment[0], "reason": experiment[1]}


def build_report(
    audits: list[dict[str, Any]],
    *,
    provenance: dict[str, Any],
    fold_manifest: dict[str, Any] | None = None,
    baseline_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    misses = [audit for audit in audits if not audit.get("hit")]
    classifications = [
        {
            "sample_id": audit["sample_id"],
            "scenario_type": audit["scenario_type"],
            **audit["classification"],
        }
        for audit in misses
        if audit["classification"].get("primary_cause") in CAUSE_ORDER
    ]
    failure_summary = summarize_failures(classifications)
    fold_summary: dict[str, dict[str, Any]] = {}
    folds = fold_manifest.get("folds") if isinstance(fold_manifest, dict) else None
    if isinstance(folds, dict):
        audits_by_id = {str(audit["sample_id"]): audit for audit in audits}
        for fold_name, sample_ids in sorted(folds.items()):
            selected = [
                audits_by_id[str(sample_id)]
                for sample_id in sample_ids
                if str(sample_id) in audits_by_id
            ]
            selected_misses = [audit for audit in selected if not audit.get("hit")]
            fold_summary[str(fold_name)] = {
                "sample_count": len(selected),
                "hit_count": len(selected) - len(selected_misses),
                "miss_count": len(selected_misses),
                "primary_cause_counts": dict(
                    sorted(
                        Counter(
                            str(audit["classification"]["primary_cause"])
                            for audit in selected_misses
                            if audit["classification"].get("primary_cause") in CAUSE_ORDER
                        ).items()
                    )
                ),
            }
    evaluation_validity_counts = Counter(
        str(flag)
        for audit in audits
        for turn in audit.get("turns", [])
        for flag in turn.get("evaluation_validity_flags", [])
        if str(flag)
    )
    unclassified_invalid_miss_count = sum(
        audit["classification"].get("primary_cause") is None for audit in misses
    )
    return {
        "version": "r0-v2",
        "scope": "offline Development-160 failure analysis",
        "protocol": {
            "runtime_behavior_changed": False,
            "development_targets_used_offline_only": True,
            "target_identifiers_written_to_report": False,
            "full_or_holdout_used": False,
        },
        "code_provenance": dict(provenance),
        "sample_count": len(audits),
        "hit_count": len(audits) - len(misses),
        "miss_count": len(misses),
        "classified_miss_count": len(misses) - unclassified_invalid_miss_count,
        "unclassified_invalid_miss_count": unclassified_invalid_miss_count,
        "failure_summary": failure_summary,
        "target_recall": target_recall_summary(audits),
        "fold_manifest_version": (
            fold_manifest.get("version") if isinstance(fold_manifest, dict) else None
        ),
        "fold_summary": fold_summary,
        "evaluation_validity_counts": dict(sorted(evaluation_validity_counts.items())),
        "baseline_metrics": dict(baseline_metrics or {}),
        "experiment_record": {
            "id": "R0",
            "owner": "shared_offline_diagnostics",
            "diagnosed_failure_classes": list(CAUSE_ORDER),
            "primary_behavior_change": "none_offline_analysis_only",
            "hypothesis": (
                "Development-160 misses are dominated by an upstream canonical "
                "failure class that can select the next smallest experiment."
            ),
            "comparator": "retained_structured_development_160_baseline_same_runtime",
            "expected_files": [
                "experiments/failure_taxonomy.py",
                "tests/test_failure_taxonomy.py",
                "tests/test_r0_failure_taxonomy_evidence.py",
                "docs/r0_development_failure_taxonomy.json",
                "docs/r0_development_failure_taxonomy.md",
            ],
            "focused_tests": [
                "tests.test_failure_taxonomy",
                "tests.test_r0_failure_taxonomy_evidence",
            ],
            "fixed_development_folds": (
                fold_manifest.get("version") if isinstance(fold_manifest, dict) else None
            ),
            "gained_lost_sessions": {
                "gained": 0,
                "lost": 0,
                "reason": "no runtime behavior comparator",
            },
            "operational_impact": {
                "runtime_latency": "unchanged",
                "runtime_memory": "unchanged",
                "runtime_fallbacks": "unchanged",
                "note": "R0 executes only as an offline audit command.",
            },
            "keep_gate": (
                "Development-160 is complete, folds are fixed, target data stays "
                "offline, and the canonical primary/secondary rule is reviewable."
            ),
            "revert_gate": (
                "Revert if the audit changes runtime behavior, uses holdout/full for "
                "selection, leaks a target identifier, or cannot reproduce the folds."
            ),
            "decision": "retain_offline_audit_and_follow_dependency_order",
        },
        "next_experiment": _next_experiment(failure_summary),
        "sessions": audits,
    }


class _TracingRetriever:
    def __init__(self, retriever: object) -> None:
        self._retriever = retriever
        self.catalog_path = retriever.catalog_path
        self.catalog_ids = retriever.catalog_ids
        self.fallback_ids = retriever.fallback_ids
        self.turns_by_session: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)

    def retrieve(self, request: object) -> object:
        routes = self._retriever.retrieve_routes(request)
        result = routes["structured"]
        self.turns_by_session[str(request.session_id)][int(request.turn)] = {
            "request": request,
            "routes": routes,
        }
        return result

    def close(self) -> None:
        close = getattr(self._retriever, "close", None)
        if callable(close):
            close()


class _TracingAgent:
    def __init__(self, agent: object) -> None:
        self._agent = agent
        self._session_order: list[str] = []
        self.response_turns_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def reset(self, session_id: str, user_profile: dict) -> None:
        self._session_order.append(session_id)
        self._agent.reset(session_id, user_profile)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        response = self._agent.respond(session_id, user_message, turn, top_k)
        self.response_turns_by_session[session_id].append(
            {
                "turn": turn,
                "user_message": user_message,
                "response": response,
            }
        )
        return response

    @property
    def session_order(self) -> tuple[str, ...]:
        return tuple(self._session_order)


def run_development_audit(
    *,
    catalog_path: str | Path = "data/catalog.jsonl",
    dataset_path: str | Path = "data/public_set.jsonl",
    public_split_path: str | Path = "docs/public_split_v1.json",
    development_fold_path: str | Path = "docs/development_folds_v1.json",
) -> dict[str, Any]:
    """Run the retained Agent on Development-160 and classify misses offline."""

    from evaluator.local_evaluator import (
        catalog_index,
        evaluate,
        load_jsonl,
        materialize_hidden_fields,
    )
    from evaluator.splits import filter_samples, load_split_manifest
    from experiments.development_folds import validate_development_fold_manifest
    from experiments.evaluation_reporting import code_provenance
    from starter.agent import Agent
    from starter.retrieval import HybridRetriever, StructuredConfig

    samples = load_jsonl(dataset_path)
    public_split = load_split_manifest(public_split_path)
    development_folds = load_split_manifest(development_fold_path)
    validate_development_fold_manifest(samples, public_split, development_folds)
    development_samples = filter_samples(samples, "development", public_split)
    if len(development_samples) != 160:
        raise ValueError("R0 requires the fixed 160-session Development split")

    catalog_ids, categories, products = catalog_index(catalog_path)
    retriever = _TracingRetriever(
        HybridRetriever(catalog_path, structured_config=StructuredConfig(enabled=True))
    )
    tracing_agent = _TracingAgent(Agent(catalog_path, retriever=retriever))
    try:
        evaluation = evaluate(
            tracing_agent,
            development_samples,
            catalog_ids,
            categories,
            products,
        )
    finally:
        retriever.close()

    evaluation_sessions = evaluation.get("sessions", [])
    if not (
        len(development_samples)
        == len(evaluation_sessions)
        == len(tracing_agent.session_order)
    ):
        raise RuntimeError("R0 trace count does not match Development-160 evaluation")

    audits: list[dict[str, Any]] = []
    for sample, evaluation_session, runtime_session_id in zip(
        development_samples,
        evaluation_sessions,
        tracing_agent.session_order,
    ):
        effective_intent_card, effective_behavior = materialize_hidden_fields(
            sample,
            products,
        )
        audits.append(
            audit_session(
                sample=sample,
                evaluation_session=evaluation_session,
                intent_card=effective_intent_card,
                behavior=effective_behavior,
                response_turns=tracing_agent.response_turns_by_session[runtime_session_id],
                retrieval_turns=retriever.turns_by_session[runtime_session_id],
            )
        )

    baseline_metrics = {
        key: evaluation.get(key)
        for key in (
            "hit_rate_at_10",
            "mrr",
            "mttc",
            "efficiency",
            "recommended_technical_score",
            "scenario_metrics",
        )
    }
    return build_report(
        audits,
        provenance=code_provenance(),
        fold_manifest=development_folds,
        baseline_metrics=baseline_metrics,
    )


def render_markdown(report: dict[str, Any]) -> str:
    counts = report["failure_summary"]["primary_cause_counts"]
    owners = report["failure_summary"]["owner_counts"]
    lines = [
        "# R0 Development Failure Taxonomy",
        "",
        "This is an offline-only Development analysis. Target ranks were used only",
        "inside the audit and no target identifier is written to this report or any",
        "runtime request/diagnostic.",
        "",
        "## Outcome",
        "",
        f"- Sessions: {report['sample_count']}",
        f"- Hits: {report['hit_count']}",
        f"- Miss sessions: {report['miss_count']}",
        f"- Behavior-classified misses: {report['classified_miss_count']}",
        f"- Invalid misses left unclassified: {report['unclassified_invalid_miss_count']}",
        f"- Control Plane primary causes: {owners['control_plane']}",
        f"- Retrieval / Ranking primary causes: {owners['retrieval_ranking']}",
        "",
        "## Experiment record",
        "",
        "- **ID / owner:** R0 / shared offline diagnostics",
        "- **Primary behavior change:** none; offline analysis only",
        f"- **Hypothesis:** {report['experiment_record']['hypothesis']}",
        "- **Comparator:** retained structured Development-160 baseline, same runtime",
        "- **Gained / lost sessions:** 0 / 0; no runtime behavior comparator",
        "- **Latency / memory / fallback impact:** unchanged at runtime",
        "- **Keep gate:** complete fixed-fold Development evidence, canonical causes,",
        "  and no target leakage or runtime behavior change",
        "- **Revert gate:** any target leakage, holdout/full selection, runtime change,",
        "  or non-reproducible fold assignment",
        "- **Decision:** Retain offline audit tooling and evidence; follow the roadmap",
        "  dependency order",
        "",
        "## Primary causes",
        "",
        "| Cause | Misses |",
        "| --- | ---: |",
    ]
    for cause in CAUSE_ORDER:
        lines.append(f"| {cause} | {int(counts.get(cause, 0))} |")
    lines.extend(["", "## Fold consistency", ""])
    for fold_name, fold in report.get("fold_summary", {}).items():
        details = ", ".join(
            f"{cause}={count}"
            for cause, count in fold.get("primary_cause_counts", {}).items()
        ) or "no misses"
        lines.append(
            f"- **{fold_name}**: samples={fold['sample_count']}, "
            f"misses={fold['miss_count']}; {details}"
        )
    lines.extend(["", "## Scenario breakdown", ""])
    for scenario, scenario_counts in report["failure_summary"]["by_scenario"].items():
        details = ", ".join(
            f"{cause}={count}" for cause, count in scenario_counts.items()
        )
        lines.append(f"- **{scenario}**: {details}")
    lines.extend(
        [
            "",
            "## Target recall from retained lexical pools",
            "",
            "| Depth | Hits | Observable sessions | Recall |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for label, values in report["target_recall"].items():
        depth = label.removeprefix("at_").replace("retained_depth", "retained depth")
        lines.append(
            f"| {depth} | {values['hits']} | {values['sessions']} | {values['recall']:.6f} |"
        )
    recommendation = report["next_experiment"]
    lines.extend(
        [
            "",
            "## Recommended next experiment",
            "",
            f"**{recommendation['id']}** — {recommendation['reason']}.",
            "",
            "This recommendation is evidence-ranked but still subject to the dependency",
            "order in `docs/optimization_roadmap.md`.",
            "",
            "## Example misses",
            "",
        ]
    )
    examples: dict[str, list[str]] = defaultdict(list)
    for session in report["sessions"]:
        classification = session.get("classification")
        if not isinstance(classification, dict):
            continue
        cause = str(classification["primary_cause"])
        if len(examples[cause]) < 5:
            evidence = classification.get("evidence")
            cause_evidence = evidence.get(cause, []) if isinstance(evidence, dict) else []
            mechanism = str(cause_evidence[0]) if cause_evidence else "rank evidence only"
            examples[cause].append(f"{session['sample_id']} ({mechanism})")
    for cause in CAUSE_ORDER:
        if examples[cause]:
            lines.append(f"- **{cause}**: {', '.join(examples[cause])}")
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- The taxonomy is deterministic evidence triage, not a learned causal model.",
            "- `question_policy` requires direct evidence such as repeated or explicitly",
            "  unproductive customer replies.",
            "- `extraction` requires disclosed target-card evidence to be absent from active,",
            "  rejected, and overridden structured-state evidence. Query preservation does not",
            "  retroactively make an unrecognized constraint extracted.",
            "- `state_override` is reserved for stale or incorrectly removed state.",
            "- `intent_strategy_routing` covers an explainably wrong intent/Strategy after",
            "  extraction and state have been checked.",
            "- `query_construction` requires extracted active evidence to be omitted or",
            "  inactive evidence to be made positive in the distilled query.",
            "- Remaining misses are separated by whether the target entered the retained",
            "  Candidate Pool (`ranking_filtering`) or did not (`retrieval_recall`).",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run target-aware offline failure analysis on Development-160 only."
    )
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--public-split", default="docs/public_split_v1.json")
    parser.add_argument(
        "--development-fold-manifest",
        default="docs/development_folds_v1.json",
    )
    parser.add_argument(
        "--output-json",
        default="/private/tmp/shopping-copilot-r0-development.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="/private/tmp/shopping-copilot-r0-development.md",
    )
    args = parser.parse_args()

    report = run_development_audit(
        catalog_path=args.catalog,
        dataset_path=args.dataset,
        public_split_path=args.public_split,
        development_fold_path=args.development_fold_manifest,
    )
    json_path = Path(args.output_json)
    markdown_path = Path(args.output_markdown)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(markdown_path),
                "sample_count": report["sample_count"],
                "miss_count": report["miss_count"],
                "primary_cause_counts": report["failure_summary"][
                    "primary_cause_counts"
                ],
                "next_experiment": report["next_experiment"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
