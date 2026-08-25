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
