from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from typing import Any


A14_ATTRIBUTES = (
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
)
A14_ATTRIBUTE_STATUSES = {
    "available",
    "partial",
    "unavailable",
    "uncalibrated",
    "degraded",
    "not_applicable",
}
A14_ATTRIBUTE_DIAGNOSTIC_FIELDS = (
    "attribute",
    "status",
    "source",
    "lifecycle",
    "value_range",
    "candidate_coverage",
    "value_count",
    "rank_weighted_split",
    "answerability_status",
    "actionability_status",
    "comparability_family",
    "eligible",
    "eligibility_status",
    "missing_data_behavior",
)
A14_BOUNDED_ATTRIBUTES = {
    "category",
    "material",
    "color",
    "style",
    "use_case",
}
A14_SOURCE_BY_ATTRIBUTE = {
    **{
        attribute: "candidate_evidence_text_bounded_vocabulary"
        for attribute in A14_BOUNDED_ATTRIBUTES
    },
    "size": "candidate_field_tags_absent",
    "brand": "candidate_field_tags_absent",
    "budget": "candidate_field_tags_absent",
    "feature": "candidate_evidence_text_unstructured",
    "other": "controlled_legacy_fallback",
}
A14_STATUSES_BY_SOURCE = {
    "candidate_evidence_text_bounded_vocabulary": {
        "available",
        "partial",
        "unavailable",
        "degraded",
    },
    "candidate_evidence_text_unstructured": {
        "unavailable",
        "uncalibrated",
        "degraded",
    },
    "candidate_field_tags_absent": {"unavailable"},
    "controlled_legacy_fallback": {"not_applicable"},
}
A14_LIFECYCLE = "current_turn_full_pool"
A14_VALUE_RANGE = (
    "coverage_and_split_float_0_1;value_count_int_gte_0;"
    "null_when_not_comparable"
)
A14_ELIGIBILITY_STATUSES = {
    "final_turn",
    "policy_state_invalid",
    "asked",
    "no_preference",
    "satisfied",
    "eligible",
    "not_in_legacy_priority",
}
A14_COMPARABILITY_FAMILY = "bounded_candidate_vocabulary_v1"
A14_QUESTION_POLICY_FIELDS = {
    "policy_version",
    "mode",
    "eligible_attributes",
    "baseline_action",
    "baseline_attribute",
    "reason_code",
    "evidence_status",
    "attribute_evidence",
    "fallback_used",
    "fallback_reason",
    "latency_ms",
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )


def _sha256_file(path: str | Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _latency_summary(values: list[float]) -> dict[str, int | float | None]:
    if not values:
        return {"count": 0, "mean": None, "p95": None, "max": None}
    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, (95 * len(ordered) + 99) // 100 - 1))
    return {
        "count": len(ordered),
        "mean": round(sum(ordered) / len(ordered), 6),
        "p95": round(ordered[p95_index], 6),
        "max": round(ordered[-1], 6),
    }


def _answer_outcome(
    turn: dict[str, Any],
    *,
    previous_ask_attribute: str | None,
) -> str:
    if previous_ask_attribute is None:
        return "not_applicable"
    no_preference = {str(item) for item in turn.get("no_preference_attributes", [])}
    rejected = {str(item) for item in turn.get("rejected_attributes", [])}
    active = {str(item) for item in turn.get("active_attributes", [])}
    if previous_ask_attribute in no_preference:
        return "no_preference"
    if previous_ask_attribute in rejected:
        return "rejected_evidence"
    if previous_ask_attribute in active:
        return "new_active_evidence"
    if turn.get("unproductive_reply") is True:
        return "unproductive"
    return "other_response"


def build_turn_audit(source: dict[str, Any]) -> dict[str, Any]:
    """Build a bounded A14-0 trace from an offline Development audit."""

    sessions: list[dict[str, Any]] = []
    action_counts: Counter[str] = Counter()
    attribute_counts: Counter[str] = Counter()
    evidence_statuses: Counter[str] = Counter()
    answer_outcomes: Counter[str] = Counter()
    policy_violation_count = 0
    unproductive_reply_count = 0
    policy_latencies_ms: list[float] = []
    attribute_status_counts = {
        attribute: Counter() for attribute in A14_ATTRIBUTES
    }
    attribute_eligibility_counts = {
        attribute: Counter() for attribute in A14_ATTRIBUTES
    }

    for source_session in source.get("sessions", []):
        previous_ask_attribute: str | None = None
        turns: list[dict[str, Any]] = []
        for source_turn in source_session.get("turns", []):
            question_policy = source_turn.get("question_policy")
            if not isinstance(question_policy, dict) or not question_policy.get(
                "policy_version"
            ):
                raise ValueError("A14-0 requires Question Policy diagnostics on every turn")
            unknown_policy_fields = (
                set(question_policy) - A14_QUESTION_POLICY_FIELDS
            )
            if unknown_policy_fields:
                raise ValueError(
                    "Question Policy diagnostics contain unknown fields: "
                    + ", ".join(sorted(str(field) for field in unknown_policy_fields))
                )
            outcome = _answer_outcome(
                source_turn,
                previous_ask_attribute=previous_ask_attribute,
            )
            ask_attribute = source_turn.get("ask_attribute")
            ask_attribute = ask_attribute if isinstance(ask_attribute, str) else None
            action = str(question_policy.get("baseline_action") or "")
            baseline_attribute = question_policy.get("baseline_attribute")
            baseline_attribute = (
                baseline_attribute if isinstance(baseline_attribute, str) else None
            )
            evidence_status = str(question_policy.get("evidence_status") or "")
            raw_latency_ms = question_policy.get("latency_ms")
            latency_ms = (
                float(raw_latency_ms)
                if isinstance(raw_latency_ms, (int, float))
                and not isinstance(raw_latency_ms, bool)
                and raw_latency_ms >= 0
                else None
            )
            policy_flags = sorted(
                str(flag) for flag in source_turn.get("question_policy_flags", [])
            )
            raw_attribute_evidence = question_policy.get("attribute_evidence")
            attribute_evidence: dict[str, dict[str, object]] = {}
            if isinstance(raw_attribute_evidence, dict):
                if set(raw_attribute_evidence) != set(A14_ATTRIBUTES):
                    raise ValueError(
                        "A14-1 requires evidence for exactly all ten attributes"
                    )
                for evidence_attribute in A14_ATTRIBUTES:
                    raw_record = raw_attribute_evidence[evidence_attribute]
                    if not isinstance(raw_record, dict):
                        raise ValueError("attribute evidence records must be objects")
                    if set(raw_record) != set(A14_ATTRIBUTE_DIAGNOSTIC_FIELDS):
                        raise ValueError(
                            "attribute evidence records must use the exact closed schema"
                        )
                    if raw_record.get("attribute") != evidence_attribute:
                        raise ValueError("attribute evidence key and record must agree")
                    status = str(raw_record.get("status") or "")
                    if status not in A14_ATTRIBUTE_STATUSES:
                        raise ValueError("attribute evidence status is not allowed")
                    for field in (
                        "source",
                        "lifecycle",
                        "value_range",
                        "answerability_status",
                        "actionability_status",
                        "eligibility_status",
                        "missing_data_behavior",
                    ):
                        if not isinstance(raw_record.get(field), str) or not str(
                            raw_record[field]
                        ).strip():
                            raise ValueError(
                                f"attribute evidence {field} must be non-empty"
                            )
                    evidence_source = str(raw_record["source"])
                    if evidence_source != A14_SOURCE_BY_ATTRIBUTE[evidence_attribute]:
                        raise ValueError(
                            "attribute evidence source is inconsistent with attribute"
                        )
                    if status not in A14_STATUSES_BY_SOURCE[evidence_source]:
                        raise ValueError(
                            "attribute evidence status is inconsistent with source"
                        )
                    if raw_record["lifecycle"] != A14_LIFECYCLE:
                        raise ValueError("attribute evidence lifecycle is not allowed")
                    if raw_record["value_range"] != A14_VALUE_RANGE:
                        raise ValueError("attribute evidence value range is not allowed")
                    expected_answerability = (
                        "open_text_fallback"
                        if evidence_attribute == "other"
                        else "canonical_question"
                    )
                    if raw_record["answerability_status"] != expected_answerability:
                        raise ValueError(
                            "attribute evidence answerability is inconsistent"
                        )
                    expected_actionability = (
                        "residual_extractor"
                        if evidence_attribute == "other"
                        else "bounded_or_residual_extractor"
                        if evidence_attribute == "feature"
                        else "bounded_extractor"
                    )
                    if raw_record["actionability_status"] != expected_actionability:
                        raise ValueError(
                            "attribute evidence actionability is inconsistent"
                        )
                    eligibility_status = str(raw_record["eligibility_status"])
                    if eligibility_status not in A14_ELIGIBILITY_STATUSES:
                        raise ValueError(
                            "attribute evidence eligibility status is not allowed"
                        )
                    eligible_value = raw_record.get("eligible")
                    if not isinstance(eligible_value, bool):
                        raise ValueError("attribute evidence eligible must be boolean")
                    expected_eligible = evidence_attribute in {
                        str(item)
                        for item in question_policy.get("eligible_attributes", [])
                    }
                    if eligible_value != expected_eligible:
                        raise ValueError(
                            "attribute evidence eligibility must match policy eligibility"
                        )
                    if eligible_value != (eligibility_status == "eligible"):
                        raise ValueError(
                            "attribute evidence eligibility status is inconsistent"
                        )
                    coverage = raw_record.get("candidate_coverage")
                    split = raw_record.get("rank_weighted_split")
                    for field, value in (
                        ("candidate_coverage", coverage),
                        ("rank_weighted_split", split),
                    ):
                        if value is not None and (
                            isinstance(value, bool)
                            or not isinstance(value, (int, float))
                            or not math.isfinite(value)
                            or not 0 <= value <= 1
                        ):
                            raise ValueError(
                                f"attribute evidence {field} must be null or 0..1"
                            )
                    value_count = raw_record.get("value_count")
                    if value_count is not None and (
                        isinstance(value_count, bool)
                        or not isinstance(value_count, int)
                        or value_count < 0
                    ):
                        raise ValueError(
                            "attribute evidence value_count must be null or >= 0"
                        )
                    family = raw_record.get("comparability_family")
                    if family is not None and (
                        not isinstance(family, str) or not family.strip()
                    ):
                        raise ValueError(
                            "comparability_family must be null or non-empty"
                        )
                    numeric_values = (coverage, value_count, split)
                    if status in {"available", "partial"}:
                        if (
                            family != A14_COMPARABILITY_FAMILY
                            or any(value is None for value in numeric_values)
                        ):
                            raise ValueError(
                                "comparable evidence requires family and numeric values"
                            )
                        if status == "available" and value_count < 2:
                            raise ValueError(
                                "available evidence requires at least two values"
                            )
                        if status == "partial" and value_count != 1:
                            raise ValueError(
                                "partial evidence requires exactly one value"
                            )
                    elif family is not None or any(
                        value is not None for value in numeric_values
                    ):
                        raise ValueError(
                            "non-comparable evidence must not publish numeric values"
                        )
                    expected_missing_behavior = (
                        "comparable_within_family"
                        if status == "available"
                        else "controlled_legacy_fallback"
                        if status == "not_applicable"
                        else "preserve_legacy_action"
                    )
                    if (
                        raw_record.get("missing_data_behavior")
                        != expected_missing_behavior
                    ):
                        raise ValueError(
                            "attribute evidence missing-data behavior is inconsistent"
                        )
                    record = {
                        field: raw_record.get(field)
                        for field in A14_ATTRIBUTE_DIAGNOSTIC_FIELDS
                    }
                    attribute_evidence[evidence_attribute] = record
                    attribute_status_counts[evidence_attribute][status] += 1
                    attribute_eligibility_counts[evidence_attribute][
                        str(raw_record.get("eligibility_status") or "")
                    ] += 1
            elif str(question_policy.get("policy_version") or "").startswith(
                "a14-1-"
            ):
                raise ValueError("A14-1 diagnostics require attribute evidence")
            unproductive_reply = source_turn.get("unproductive_reply") is True
            turn = {
                "turn": int(source_turn["turn"]),
                "policy_version": str(question_policy.get("policy_version") or ""),
                "mode": str(question_policy.get("mode") or ""),
                "eligible_attributes": [
                    str(attribute)
                    for attribute in question_policy.get("eligible_attributes", [])
                ],
                "baseline_action": action,
                "baseline_attribute": baseline_attribute,
                "ask_attribute": ask_attribute,
                "reason_code": str(question_policy.get("reason_code") or ""),
                "evidence_status": evidence_status,
                "answer_outcome": outcome,
                "unproductive_reply": unproductive_reply,
                "latency_ms": latency_ms,
                "message_sha256": str(source_turn.get("message_sha256") or ""),
                "recommendations_sha256": str(
                    source_turn.get("recommendations_sha256") or ""
                ),
                "visible_response_sha256": str(
                    source_turn.get("visible_response_sha256") or ""
                ),
                "policy_flags": policy_flags,
                "attribute_evidence": attribute_evidence,
            }
            turns.append(turn)
            action_counts[action] += 1
            if baseline_attribute is not None:
                attribute_counts[baseline_attribute] += 1
            evidence_statuses[evidence_status] += 1
            answer_outcomes[outcome] += 1
            policy_violation_count += len(policy_flags)
            unproductive_reply_count += int(unproductive_reply)
            if latency_ms is not None:
                policy_latencies_ms.append(latency_ms)
            previous_ask_attribute = ask_attribute
        sessions.append(
            {
                "sample_id": str(source_session.get("sample_id") or ""),
                "scenario_type": str(source_session.get("scenario_type") or ""),
                "turns": turns,
            }
        )

    semantic_sessions = [
        {
            **session,
            "turns": [
                {
                    key: value
                    for key, value in turn.items()
                    if key != "latency_ms"
                }
                for turn in session["turns"]
            ],
        }
        for session in sessions
    ]
    canonical_trace = json.dumps(
        semantic_sessions,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    visible_trace = [
        {
            "sample_id": session["sample_id"],
            "turns": [
                {
                    "turn": turn["turn"],
                    "ask_attribute": turn["ask_attribute"],
                    "message_sha256": turn["message_sha256"],
                    "recommendations_sha256": turn["recommendations_sha256"],
                    "visible_response_sha256": turn["visible_response_sha256"],
                }
                for turn in session["turns"]
            ],
        }
        for session in sessions
    ]
    return {
        "version": "a14-0-turn-audit-v1",
        "scope": "offline Development-160 Question Policy trace",
        "protocol": {
            "full_or_holdout_used": False,
            "candidate_ids_or_text_recorded": False,
            "private_product_identifiers_recorded": False,
            "behavior_parity_status": "unverified_without_baseline",
            "question_trace_excludes_operational_latency": True,
        },
        "code_provenance": dict(source.get("code_provenance") or {}),
        "fold_manifest_version": source.get("fold_manifest_version"),
        "baseline_metrics": dict(source.get("baseline_metrics") or {}),
        "observed_run_counts": dict(source.get("observed_run_counts") or {}),
        "input_sha256": dict(source.get("input_sha256") or {}),
        "question_trace_sha256": hashlib.sha256(canonical_trace).hexdigest(),
        "visible_response_trace_sha256": _sha256_json(visible_trace),
        "summary": {
            "session_count": len(sessions),
            "turn_count": sum(len(session["turns"]) for session in sessions),
            "ask_count": action_counts["ask"],
            "stop_count": action_counts["stop"],
            "attribute_counts": dict(sorted(attribute_counts.items())),
            "evidence_statuses": dict(sorted(evidence_statuses.items())),
            "answer_outcomes": dict(sorted(answer_outcomes.items())),
            "unproductive_reply_count": unproductive_reply_count,
            "policy_violation_count": policy_violation_count,
            "policy_latency_ms": _latency_summary(policy_latencies_ms),
            "attribute_evidence_status_counts": {
                attribute: dict(sorted(counts.items()))
                for attribute, counts in attribute_status_counts.items()
                if counts
            },
            "attribute_eligibility_counts": {
                attribute: dict(sorted(counts.items()))
                for attribute, counts in attribute_eligibility_counts.items()
                if counts
            },
        },
        "sessions": sessions,
    }


def build_visible_baseline(source: dict[str, Any]) -> dict[str, Any]:
    """Freeze only safe hashes of the legacy public response trace."""

    sessions = [
        {
            "sample_id": str(session.get("sample_id") or ""),
            "turns": [
                {
                    "turn": int(turn["turn"]),
                    "ask_attribute": (
                        turn.get("ask_attribute")
                        if isinstance(turn.get("ask_attribute"), str)
                        else None
                    ),
                    "message_sha256": str(turn.get("message_sha256") or ""),
                    "recommendations_sha256": str(
                        turn.get("recommendations_sha256") or ""
                    ),
                    "visible_response_sha256": str(
                        turn.get("visible_response_sha256") or ""
                    ),
                }
                for turn in session.get("turns", [])
            ],
        }
        for session in source.get("sessions", [])
    ]
    return {
        "version": "a14-0-visible-baseline-v1",
        "scope": "fixed Development-160 legacy public response trace hashes",
        "protocol": {
            "full_or_holdout_used": False,
            "candidate_ids_or_text_recorded": False,
            "private_product_identifiers_recorded": False,
        },
        "code_provenance": dict(source.get("code_provenance") or {}),
        "fold_manifest_version": source.get("fold_manifest_version"),
        "baseline_metrics": dict(source.get("baseline_metrics") or {}),
        "observed_run_counts": dict(source.get("observed_run_counts") or {}),
        "input_sha256": dict(source.get("input_sha256") or {}),
        "visible_response_trace_sha256": _sha256_json(sessions),
        "sessions": sessions,
    }


def compare_visible_traces(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    """Compare safe legacy/current hashes and report exact parity."""

    baseline_sessions = {
        str(session.get("sample_id") or ""): session
        for session in baseline.get("sessions", [])
    }
    current_sessions = {
        str(session.get("sample_id") or ""): session
        for session in current.get("sessions", [])
    }
    session_mismatches = sorted(set(baseline_sessions) ^ set(current_sessions))
    message_mismatches = 0
    recommendation_mismatches = 0
    ask_mismatches = 0
    turn_shape_mismatches = 0
    compared_turns = 0
    for sample_id in sorted(set(baseline_sessions) & set(current_sessions)):
        baseline_turns = {
            int(turn["turn"]): turn
            for turn in baseline_sessions[sample_id].get("turns", [])
        }
        current_turns = {
            int(turn["turn"]): turn
            for turn in current_sessions[sample_id].get("turns", [])
        }
        turn_shape_mismatches += len(set(baseline_turns) ^ set(current_turns))
        for turn_number in sorted(set(baseline_turns) & set(current_turns)):
            compared_turns += 1
            before = baseline_turns[turn_number]
            after = current_turns[turn_number]
            message_mismatches += int(
                before.get("message_sha256") != after.get("message_sha256")
            )
            recommendation_mismatches += int(
                before.get("recommendations_sha256")
                != after.get("recommendations_sha256")
            )
            ask_mismatches += int(
                before.get("ask_attribute") != after.get("ask_attribute")
            )
    input_hashes_match = baseline.get("input_sha256") == current.get("input_sha256")
    metric_parity = baseline.get("baseline_metrics") == current.get("baseline_metrics")
    mismatch_count = (
        len(session_mismatches)
        + turn_shape_mismatches
        + message_mismatches
        + recommendation_mismatches
        + ask_mismatches
    )
    exact = mismatch_count == 0 and input_hashes_match and metric_parity
    return {
        "exact": exact,
        "compared_turns": compared_turns,
        "session_shape_mismatches": len(session_mismatches),
        "turn_shape_mismatches": turn_shape_mismatches,
        "message_mismatches": message_mismatches,
        "recommendation_mismatches": recommendation_mismatches,
        "ask_attribute_mismatches": ask_mismatches,
        "input_hashes_match": input_hashes_match,
        "metric_parity": metric_parity,
    }


def run_development_turn_audit(
    *,
    catalog_path: str | Path = "data/catalog.jsonl",
    dataset_path: str | Path = "data/public_set.jsonl",
    public_split_path: str | Path = "docs/public_split_v1.json",
    development_fold_path: str | Path = "docs/development_folds_v1.json",
    baseline_trace: dict[str, Any] | None = None,
    capture_baseline: bool = False,
) -> dict[str, Any]:
    """Run the current Agent on Development-160 and build the A14-0 trace."""

    from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
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
        raise ValueError("A14-0 requires the fixed 160-session Development split")

    catalog_ids, categories, products = catalog_index(catalog_path)
    retriever = HybridRetriever(
        catalog_path,
        structured_config=StructuredConfig(enabled=True),
    )
    responses_by_session: dict[str, list[dict[str, Any]]] = {}
    session_order: list[str] = []

    class TracingAgent:
        def __init__(self) -> None:
            self._agent = Agent(catalog_path, retriever=retriever)

        def reset(self, session_id: str, user_profile: dict) -> None:
            session_order.append(session_id)
            responses_by_session[session_id] = []
            self._agent.reset(session_id, user_profile)

        def respond(
            self,
            session_id: str,
            user_message: str,
            turn: int,
            top_k: int,
        ) -> dict:
            response = self._agent.respond(session_id, user_message, turn, top_k)
            responses_by_session[session_id].append(
                {
                    "turn": turn,
                    "user_message": user_message,
                    "response": response,
                    "policy_latency_ms": getattr(
                        getattr(self._agent, "question_policy", None),
                        "last_latency_ms",
                        None,
                    ),
                }
            )
            return response

    try:
        evaluation = evaluate(
            TracingAgent(),
            development_samples,
            catalog_ids,
            categories,
            products,
        )
    finally:
        retriever.close()

    if len(session_order) != len(development_samples):
        raise RuntimeError("A14-0 trace count does not match Development-160")
    sessions: list[dict[str, Any]] = []
    for sample, session_id in zip(development_samples, session_order):
        asked_attributes: set[str] = set()
        turns: list[dict[str, Any]] = []
        for response_turn in responses_by_session[session_id]:
            response = response_turn["response"]
            diagnostics = response.get("diagnostics")
            diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
            question_policy = diagnostics.get("question_policy")
            question_policy = (
                dict(question_policy) if isinstance(question_policy, dict) else {}
            )
            question_policy["latency_ms"] = response_turn.get("policy_latency_ms")
            ask_attribute = response.get("ask_attribute")
            ask_attribute = ask_attribute if isinstance(ask_attribute, str) else None
            no_preference = {
                str(attribute)
                for attribute in diagnostics.get("no_preference_attributes", [])
            }
            policy_flags: list[str] = []
            if ask_attribute is not None:
                if ask_attribute in asked_attributes:
                    policy_flags.append(f"repeated_attribute:{ask_attribute}")
                if ask_attribute in no_preference:
                    policy_flags.append(
                        f"asked_no_preference_attribute:{ask_attribute}"
                    )
                if int(response_turn["turn"]) >= 10:
                    policy_flags.append("asked_on_final_turn")
                asked_attributes.add(ask_attribute)
                eligible_attributes = {
                    str(attribute)
                    for attribute in question_policy.get("eligible_attributes", [])
                }
                if ask_attribute not in eligible_attributes:
                    policy_flags.append(f"asked_ineligible_attribute:{ask_attribute}")
            baseline_action = question_policy.get("baseline_action")
            baseline_attribute = question_policy.get("baseline_attribute")
            if (
                baseline_action == "ask"
                and baseline_attribute != ask_attribute
            ) or (baseline_action == "stop" and ask_attribute is not None):
                policy_flags.append("baseline_output_mismatch")
            active_attributes = sorted(
                {
                    str(item.get("attribute"))
                    for item in diagnostics.get("active_constraints", [])
                    if isinstance(item, dict)
                    and item.get("active", True)
                    and str(item.get("attribute") or "")
                }
            )
            if ask_attribute in active_attributes and ask_attribute != "other":
                policy_flags.append(f"asked_known_attribute:{ask_attribute}")
            rejected_attributes = sorted(
                {
                    str(item.get("attribute"))
                    for item in diagnostics.get("rejected_constraints", [])
                    if isinstance(item, dict) and str(item.get("attribute") or "")
                }
            )
            recommendations = [
                str(item.get("parent_asin") or "")
                for item in response.get("recommendations", [])
                if isinstance(item, dict) and str(item.get("parent_asin") or "")
            ]
            message = str(response.get("message") or "")
            visible_response = {
                "message": message,
                "ask_attribute": ask_attribute,
                "recommendations": recommendations,
            }
            turns.append(
                {
                    "turn": int(response_turn["turn"]),
                    "ask_attribute": ask_attribute,
                    "unproductive_reply": str(
                        response_turn.get("user_message") or ""
                    ).lower().startswith("i don't have an additional preference"),
                    "active_attributes": active_attributes,
                    "no_preference_attributes": sorted(no_preference),
                    "rejected_attributes": rejected_attributes,
                    "question_policy_flags": sorted(policy_flags),
                    "question_policy": question_policy,
                    "message_sha256": _sha256_json(message),
                    "recommendations_sha256": _sha256_json(recommendations),
                    "visible_response_sha256": _sha256_json(visible_response),
                }
            )
        sessions.append(
            {
                "sample_id": str(sample.get("sample_id") or ""),
                "scenario_type": str(sample.get("scenario_type") or ""),
                "turns": turns,
            }
        )

    source = {
        "code_provenance": code_provenance(),
        "fold_manifest_version": development_folds.get("version"),
        "baseline_metrics": {
            key: evaluation.get(key)
            for key in (
                "hit_rate_at_10",
                "mrr",
                "mttc",
                "efficiency",
                "recommended_technical_score",
                "scenario_metrics",
            )
        },
        "observed_run_counts": dict(evaluation.get("observed_run_counts") or {}),
        "input_sha256": {
            "catalog": _sha256_file(catalog_path),
            "dataset": _sha256_file(dataset_path),
            "public_split": _sha256_file(public_split_path),
            "development_folds": _sha256_file(development_fold_path),
            "evaluation_config": _sha256_file("docs/evaluation_config.json"),
            "local_evaluator": _sha256_file("evaluator/local_evaluator.py"),
            "splits": _sha256_file("evaluator/splits.py"),
        },
        "sessions": sessions,
    }
    if capture_baseline:
        return build_visible_baseline(source)
    audit = build_turn_audit(source)
    if baseline_trace is None:
        raise ValueError("A14-0 current audit requires a fixed legacy baseline trace")
    parity = compare_visible_traces(baseline_trace, audit)
    audit["parity"] = parity
    audit["protocol"]["behavior_parity_status"] = (
        "verified_exact" if parity["exact"] else "mismatch"
    )
    if not parity["exact"]:
        raise RuntimeError(f"A14-0 visible behavior parity failed: {parity}")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a target-free A14-0 Question Policy turn trace."
    )
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--public-split", default="docs/public_split_v1.json")
    parser.add_argument(
        "--development-fold-manifest",
        default="docs/development_folds_v1.json",
    )
    parser.add_argument(
        "--output",
        default="/private/tmp/shopping-copilot-a14-0-turn-audit.json",
    )
    parser.add_argument(
        "--baseline",
        help="Fixed legacy visible-trace JSON used for exact parity comparison.",
    )
    parser.add_argument(
        "--capture-baseline",
        action="store_true",
        help="Capture safe visible-response hashes without requiring QuestionPolicy.",
    )
    args = parser.parse_args()
    if args.capture_baseline and args.baseline:
        parser.error("--capture-baseline and --baseline are mutually exclusive")
    if not args.capture_baseline and not args.baseline:
        parser.error("current A14-0 audit requires --baseline")
    baseline_trace = None
    if args.baseline:
        baseline_trace = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    audit = run_development_turn_audit(
        catalog_path=args.catalog,
        dataset_path=args.dataset,
        public_split_path=args.public_split,
        development_fold_path=args.development_fold_manifest,
        baseline_trace=baseline_trace,
        capture_baseline=args.capture_baseline,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = audit.get("summary")
    if not isinstance(summary, dict):
        summary = {
            "session_count": len(audit.get("sessions", [])),
            "turn_count": sum(
                len(session.get("turns", []))
                for session in audit.get("sessions", [])
            ),
        }
    print(
        json.dumps(
            {
                "output": str(output),
                "session_count": summary["session_count"],
                "turn_count": summary["turn_count"],
                "question_trace_sha256": audit.get("question_trace_sha256"),
                "visible_response_trace_sha256": audit[
                    "visible_response_trace_sha256"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
