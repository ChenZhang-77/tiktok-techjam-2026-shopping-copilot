from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


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

    for source_session in source.get("sessions", []):
        previous_ask_attribute: str | None = None
        turns: list[dict[str, Any]] = []
        for source_turn in source_session.get("turns", []):
            question_policy = source_turn.get("question_policy")
            if not isinstance(question_policy, dict):
                raise ValueError("A14-0 requires Question Policy diagnostics on every turn")
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
            policy_flags = sorted(
                str(flag) for flag in source_turn.get("question_policy_flags", [])
            )
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
                "policy_flags": policy_flags,
            }
            turns.append(turn)
            action_counts[action] += 1
            if baseline_attribute is not None:
                attribute_counts[baseline_attribute] += 1
            evidence_statuses[evidence_status] += 1
            answer_outcomes[outcome] += 1
            policy_violation_count += len(policy_flags)
            previous_ask_attribute = ask_attribute
        sessions.append(
            {
                "sample_id": str(source_session.get("sample_id") or ""),
                "scenario_type": str(source_session.get("scenario_type") or ""),
                "turns": turns,
            }
        )

    canonical_trace = json.dumps(
        sessions,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return {
        "version": "a14-0-turn-audit-v1",
        "scope": "offline Development-160 Question Policy trace",
        "protocol": {
            "runtime_behavior_changed": False,
            "full_or_holdout_used": False,
            "candidate_ids_or_text_recorded": False,
            "private_product_identifiers_recorded": False,
        },
        "code_provenance": dict(source.get("code_provenance") or {}),
        "fold_manifest_version": source.get("fold_manifest_version"),
        "baseline_metrics": dict(source.get("baseline_metrics") or {}),
        "question_trace_sha256": hashlib.sha256(canonical_trace).hexdigest(),
        "summary": {
            "session_count": len(sessions),
            "turn_count": sum(len(session["turns"]) for session in sessions),
            "ask_count": action_counts["ask"],
            "stop_count": action_counts["stop"],
            "attribute_counts": dict(sorted(attribute_counts.items())),
            "evidence_statuses": dict(sorted(evidence_statuses.items())),
            "answer_outcomes": dict(sorted(answer_outcomes.items())),
            "policy_violation_count": policy_violation_count,
        },
        "sessions": sessions,
    }


def run_development_turn_audit(
    *,
    catalog_path: str | Path = "data/catalog.jsonl",
    dataset_path: str | Path = "data/public_set.jsonl",
    public_split_path: str | Path = "docs/public_split_v1.json",
    development_fold_path: str | Path = "docs/development_folds_v1.json",
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
                question_policy if isinstance(question_policy, dict) else {}
            )
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
            rejected_attributes = sorted(
                {
                    str(item.get("attribute"))
                    for item in diagnostics.get("rejected_constraints", [])
                    if isinstance(item, dict) and str(item.get("attribute") or "")
                }
            )
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
                "response_exception_count",
                "invalid_response_count",
                "fallback_response_count",
            )
        },
        "sessions": sessions,
    }
    audit = build_turn_audit(source)
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
    args = parser.parse_args()
    audit = run_development_turn_audit(
        catalog_path=args.catalog,
        dataset_path=args.dataset,
        public_split_path=args.public_split,
        development_fold_path=args.development_fold_manifest,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "session_count": audit["summary"]["session_count"],
                "turn_count": audit["summary"]["turn_count"],
                "question_trace_sha256": audit["question_trace_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
