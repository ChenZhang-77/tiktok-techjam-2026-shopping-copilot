from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TurnRecord:
    turn: int
    user_message: str
    agent_message: str = ""
    ask_attribute: str | None = None
    recommendation_ids: list[str] = field(default_factory=list)


@dataclass
class SessionState:
    session_id: str
    user_profile: dict
    current_turn: int = 0
    raw_history: list[TurnRecord] = field(default_factory=list)
    intent: str | None = None
    active_constraints: list[dict] = field(default_factory=list)
    overridden_constraints: list[dict] = field(default_factory=list)
    rejected_constraints: list[dict] = field(default_factory=list)
    no_preference_attributes: set[str] = field(default_factory=set)
    asked_attributes: set[str] = field(default_factory=set)
    previous_distilled_query: str = ""
    previous_candidate_ids: list[str] = field(default_factory=list)
    previous_strategy: dict | None = None
    previous_diagnostics: dict | None = None
    override_seen: bool = False

    def record_user_turn(self, turn: int, user_message: str) -> TurnRecord:
        self.current_turn = turn
        record = TurnRecord(turn=turn, user_message=str(user_message))
        self.raw_history.append(record)
        return record

    def add_constraints(self, constraints: list[dict]) -> None:
        existing = {
            (str(item.get("attribute")), str(item.get("normalized_value")))
            for item in self.active_constraints
            if item.get("active", True)
        }
        for constraint in constraints:
            key = (str(constraint.get("attribute")), str(constraint.get("normalized_value")))
            if not key[0] or not key[1] or key in existing:
                continue
            self.active_constraints.append(dict(constraint))
            existing.add(key)

    def apply_user_context(
        self,
        *,
        constraints: list[dict],
        override: bool = False,
        no_preference_attributes: list[str] | None = None,
    ) -> None:
        for attribute in no_preference_attributes or []:
            self.mark_no_preference(attribute)
            self._deactivate_attribute(attribute, destination=self.rejected_constraints)
        if override and constraints:
            self.override_seen = True
            for attribute in {str(item.get("attribute")) for item in constraints if item.get("attribute")}:
                self._deactivate_attribute(attribute, destination=self.overridden_constraints)
        filtered = [
            constraint
            for constraint in constraints
            if str(constraint.get("attribute")) not in self.no_preference_attributes
        ]
        self.add_constraints(filtered)

    def _deactivate_attribute(self, attribute: str, *, destination: list[dict]) -> None:
        kept: list[dict] = []
        for constraint in self.active_constraints:
            if constraint.get("attribute") != attribute or not constraint.get("active", True):
                kept.append(constraint)
                continue
            inactive = dict(constraint)
            inactive["active"] = False
            destination.append(inactive)
        self.active_constraints = kept

    def active_constraint_values(self, attribute: str | None = None) -> list[str]:
        values: list[str] = []
        for constraint in self.active_constraints:
            if not constraint.get("active", True):
                continue
            if attribute is not None and constraint.get("attribute") != attribute:
                continue
            value = str(constraint.get("normalized_value") or "").strip()
            if value:
                values.append(value)
        return values

    def record_agent_response(self, response: dict) -> None:
        if not self.raw_history:
            return
        latest = self.raw_history[-1]
        latest.agent_message = str(response.get("message", ""))
        ask_attribute = response.get("ask_attribute")
        latest.ask_attribute = ask_attribute if isinstance(ask_attribute, str) else None
        if latest.ask_attribute:
            self.asked_attributes.add(latest.ask_attribute)
        recommendations = response.get("recommendations")
        if isinstance(recommendations, list):
            latest.recommendation_ids = [
                str(item.get("parent_asin", "")).strip()
                for item in recommendations
                if isinstance(item, dict) and str(item.get("parent_asin", "")).strip()
            ]
        self.previous_candidate_ids = list(latest.recommendation_ids)

    def mark_no_preference(self, attribute: str) -> None:
        if attribute:
            self.no_preference_attributes.add(attribute)

    def has_asked(self, attribute: str) -> bool:
        return attribute in self.asked_attributes
