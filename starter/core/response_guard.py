from __future__ import annotations

from collections.abc import Iterable


ALLOWED_ASK_ATTRIBUTES = {
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
}


def _parent_asin(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("parent_asin", "")).strip()
    return str(item).strip()


def _safe_usage(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    prompt_tokens = value.get("prompt_tokens")
    completion_tokens = value.get("completion_tokens")
    if not isinstance(prompt_tokens, int) or prompt_tokens < 0:
        return None
    if not isinstance(completion_tokens, int) or completion_tokens < 0:
        return None
    return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}


def guard_response(
    response: object,
    *,
    catalog_ids: set[str],
    fallback_ids: Iterable[str],
    top_k: int,
    fallback_message: str = "Here are the closest matches I found.",
) -> dict:
    limit = max(0, int(top_k))
    payload = response if isinstance(response, dict) else {}

    message = payload.get("message")
    if not isinstance(message, str):
        message = fallback_message

    ask_attribute = payload.get("ask_attribute")
    if ask_attribute not in ALLOWED_ASK_ATTRIBUTES:
        ask_attribute = None

    recommendations: list[dict] = []
    seen: set[str] = set()
    raw_recommendations = payload.get("recommendations")
    if not isinstance(raw_recommendations, list):
        raw_recommendations = []
    for item in raw_recommendations:
        parent_asin = _parent_asin(item)
        if not parent_asin or parent_asin in seen or parent_asin not in catalog_ids:
            continue
        seen.add(parent_asin)
        recommendations.append({"parent_asin": parent_asin})
        if len(recommendations) >= limit:
            break

    if len(recommendations) < limit:
        for parent_asin in fallback_ids:
            parent_asin = str(parent_asin).strip()
            if not parent_asin or parent_asin in seen or parent_asin not in catalog_ids:
                continue
            seen.add(parent_asin)
            recommendations.append({"parent_asin": parent_asin})
            if len(recommendations) >= limit:
                break

    guarded = {
        "message": message,
        "ask_attribute": ask_attribute,
        "recommendations": recommendations[:limit],
    }
    usage = _safe_usage(payload.get("usage"))
    if usage is not None:
        guarded["usage"] = usage
    diagnostics = payload.get("diagnostics")
    if isinstance(diagnostics, dict):
        guarded["diagnostics"] = diagnostics
    return guarded
