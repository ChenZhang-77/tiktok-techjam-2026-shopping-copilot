from __future__ import annotations

from starter.core.state import SessionState


def _constraint_summary(items: list[dict]) -> list[dict]:
    return [
        {
            "attribute": str(item.get("attribute") or ""),
            "value": str(item.get("normalized_value") or item.get("raw_value") or ""),
            "source_turn": item.get("source_turn"),
            "confidence": item.get("confidence"),
            "hard": bool(item.get("hard")),
        }
        for item in items
    ]


def state_diagnostics(state: SessionState) -> dict:
    diagnostics = {
        "intent": state.intent,
        "intent_assessment": (
            state.intent_assessment.to_dict()
            if state.intent_assessment is not None
            else None
        ),
        "active_constraints": _constraint_summary(state.active_constraints),
        "overridden_constraints": _constraint_summary(state.overridden_constraints),
        "rejected_constraints": _constraint_summary(state.rejected_constraints),
        "no_preference_attributes": sorted(state.no_preference_attributes),
        "asked_attributes": sorted(state.asked_attributes),
        "distilled_query": state.previous_distilled_query,
        "previous_candidate_count": len(state.previous_candidate_ids),
        "override_seen": state.override_seen,
    }
    if state.override_events:
        diagnostics["last_override"] = state.override_events[-1]
    return diagnostics
