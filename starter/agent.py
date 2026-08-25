from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from starter.core.clarification import choose_clarification
from starter.core.context_engine import detect_no_preference_attributes, detect_override, extract_constraints, infer_intent
from starter.core.planner import Strategy, plan_strategy
from starter.core.query_builder import build_distilled_query
from starter.core.ranking import rerank_candidates
from starter.core.response_guard import guard_response
from starter.core.state import SessionState


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "please", "some",
    "that", "the", "this", "to", "want", "with", "would", "you", "looking",
}


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{key} {item}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


def _terms(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) > 1 and token.lower() not in STOPWORDS
    ]


class Agent:
    """Editable weak baseline: stateless BM25 retrieval with no LLM dependency."""

    def __init__(self, catalog_path: str | Path = "data/catalog.jsonl") -> None:
        self.catalog_path = Path(catalog_path)
        self.connection = sqlite3.connect(":memory:")
        self._sessions: dict[str, SessionState] = {}
        self._catalog_ids: set[str] = set()
        self._fallback_ids: list[str] = []
        self._product_texts: dict[str, str] = {}
        self._build_index()

    def _build_index(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "CREATE VIRTUAL TABLE products USING fts5("
            "parent_asin UNINDEXED, title, categories, features, details, store, description, "
            "tokenize='unicode61 remove_diacritics 2')"
        )
        batch: list[tuple[str, str, str, str, str, str, str]] = []
        with self.catalog_path.open(encoding="utf-8") as handle:
            for line in handle:
                product = json.loads(line)
                parent_asin = str(product["parent_asin"])
                self._catalog_ids.add(parent_asin)
                self._fallback_ids.append(parent_asin)
                product_text = " ".join(
                    (
                        _text(product.get("title")),
                        _text(product.get("categories")),
                        _text(product.get("features")),
                        _text(product.get("details")),
                        _text(product.get("store")),
                        _text(product.get("description")),
                    )
                )
                self._product_texts[parent_asin] = product_text
                batch.append(
                    (
                        parent_asin,
                        _text(product.get("title")),
                        _text(product.get("categories")),
                        _text(product.get("features")),
                        _text(product.get("details")),
                        _text(product.get("store")),
                        _text(product.get("description")),
                    )
                )
                if len(batch) >= 1000:
                    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
                    batch.clear()
        if batch:
            cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
        self.connection.commit()

    def reset(self, session_id: str, user_profile: dict) -> None:
        # The profile is anonymized and may be used for personalization.
        self._sessions[session_id] = SessionState(session_id=session_id, user_profile=dict(user_profile or {}))

    def _respond_impl(
        self,
        session_id: str,
        query_text: str,
        turn: int,
        top_k: int,
        strategy: Strategy | None = None,
    ) -> dict:
        if session_id not in self._sessions:
            raise RuntimeError("reset must be called before respond")
        unique_terms = list(dict.fromkeys(_terms(query_text)))[:40]
        expression = " OR ".join(f'"{term}"' for term in unique_terms)
        if not expression:
            recommendations: list[dict] = []
        else:
            rows = self.connection.execute(
                "SELECT parent_asin FROM products WHERE products MATCH ? "
                "ORDER BY bm25(products, 0.0, 6.0, 4.0, 2.5, 2.5, 1.5, 1.0) LIMIT ?",
                (expression, strategy.retrieval_depth if strategy else top_k),
            ).fetchall()
            candidate_ids = [str(row[0]) for row in rows]
            if strategy:
                candidate_ids = rerank_candidates(
                    candidate_ids,
                    product_texts=self._product_texts,
                    active_constraints=self._sessions[session_id].active_constraints,
                    lexical_weight=strategy.lexical_weight,
                    structured_weight=strategy.structured_weight,
                )
            recommendations = [{"parent_asin": parent_asin} for parent_asin in candidate_ids[:top_k]]
        return {
            "message": "Here are the closest matches I found.",
            "ask_attribute": None,
            "recommendations": recommendations,
            "diagnostics": {"strategy": strategy.to_dict()} if strategy else {},
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    def respond(
        self,
        session_id: str,
        user_message: str,
        turn: int,
        top_k: int,
    ) -> dict:
        state = self._sessions.get(session_id)
        query_text = user_message
        strategy = None
        if state is not None:
            state.record_user_turn(turn, user_message)
            constraints = extract_constraints(user_message, turn)
            state.apply_user_context(
                constraints=constraints,
                override=detect_override(user_message),
                no_preference_attributes=detect_no_preference_attributes(user_message),
            )
            state.intent = infer_intent(user_message, constraints)
            strategy = plan_strategy(state, turn=turn, top_k=top_k)
            state.previous_strategy = strategy.to_dict()
            query_text = build_distilled_query(user_message, state.active_constraints)
            state.previous_distilled_query = query_text
        try:
            response = self._respond_impl(session_id, query_text, turn, top_k, strategy)
        except Exception:
            response = {
                "message": "Here are the closest matches I found.",
                "ask_attribute": None,
                "recommendations": [],
                "diagnostics": {"strategy": strategy.to_dict()} if strategy else {},
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }
        if state is not None:
            raw_recommendations = response.get("recommendations") if isinstance(response, dict) else []
            candidate_texts = [
                self._product_texts.get(str(item.get("parent_asin", "")).strip(), "")
                for item in raw_recommendations
                if isinstance(item, dict)
            ]
            ask_attribute, question = choose_clarification(state, turn=turn, candidate_texts=candidate_texts)
            if ask_attribute:
                response["ask_attribute"] = ask_attribute
                base_message = response.get("message") if isinstance(response, dict) else ""
                response["message"] = f"{base_message} {question}".strip()
        guarded = guard_response(
            response,
            catalog_ids=self._catalog_ids,
            fallback_ids=self._fallback_ids,
            top_k=top_k,
        )
        if state is not None:
            diagnostics = guarded.get("diagnostics")
            state.previous_diagnostics = diagnostics if isinstance(diagnostics, dict) else None
            state.record_agent_response(guarded)
        return guarded
