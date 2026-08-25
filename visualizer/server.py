from __future__ import annotations

import argparse
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluator.local_evaluator import (
    MAX_TURNS,
    TOP_K,
    catalog_index,
    coarse_category,
    customer_reply,
    initial_message,
    load_jsonl,
    materialize_hidden_fields,
    normalize_recommendations,
)
from starter.agent import Agent


STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _safe_product(product: dict | None) -> dict:
    if not product:
        return {}
    features = product.get("features") or []
    if isinstance(features, list):
        features = [str(item)[:180] for item in features[:3]]
    else:
        features = []
    return {
        "parent_asin": str(product.get("parent_asin", "")),
        "title": str(product.get("title") or "")[:240],
        "price": product.get("price"),
        "categories": product.get("categories") or [],
        "features": features,
        "store": str(product.get("store") or ""),
        "average_rating": product.get("average_rating"),
        "rating_number": product.get("rating_number"),
    }


def _sse(event: str, payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {body}\n\n".encode("utf-8")


class TraceRunner:
    def __init__(self, catalog_path: Path, dataset_path: Path) -> None:
        self.catalog_path = catalog_path
        self.dataset_path = dataset_path
        self.samples = load_jsonl(dataset_path)
        self.catalog_ids, self.categories, self.products = catalog_index(catalog_path)

    def session_summaries(self) -> list[dict]:
        summaries: list[dict] = []
        for index, sample in enumerate(self.samples):
            target = str(sample["ground_truth"]["parent_asin"])
            product = self.products.get(target)
            summaries.append(
                {
                    "index": index,
                    "sample_id": sample.get("sample_id"),
                    "scenario_type": sample.get("scenario_type"),
                    "target": target,
                    "target_title": str(product.get("title") or "") if product else "",
                    "category": coarse_category(self.categories.get(target, [])),
                }
            )
        return summaries

    def stream_session(self, index: int, delay_ms: int):
        if index < 0 or index >= len(self.samples):
            yield _sse("error", {"message": f"Session index out of range: {index}"})
            return

        sample = self.samples[index]
        agent = Agent(self.catalog_path)
        session_id = f"visual_{uuid.uuid4().hex}"
        agent.reset(session_id, sample["user_profile"])

        target = str(sample["ground_truth"]["parent_asin"])
        target_product = self.products.get(target)
        effective_intent_card, effective_behavior = materialize_hidden_fields(sample, self.products)
        effective_sample = {**sample, "intent_card": effective_intent_card, "behavior": effective_behavior}

        disclosed: set[str] = set()
        boundary_used = False
        override_applied = sample["scenario_type"] != "intent_override"
        user_message = initial_message(effective_sample, coarse_category(self.categories.get(target, [])), disclosed)
        hit_turn: int | None = None
        best_rank: int | None = None

        yield _sse(
            "start",
            {
                "session_index": index,
                "session_id": session_id,
                "sample_id": sample.get("sample_id"),
                "scenario_type": sample.get("scenario_type"),
                "target": target,
                "target_product": _safe_product(target_product),
                "user_profile": sample.get("user_profile", {}),
                "max_turns": MAX_TURNS,
            },
        )

        for turn in range(1, MAX_TURNS + 1):
            try:
                response = agent.respond(session_id, user_message, turn, TOP_K)
            except Exception as exc:
                response = {"message": "", "ask_attribute": None, "recommendations": []}
                error = f"{type(exc).__name__}: {exc}"
            else:
                error = None

            if not isinstance(response, dict) or not isinstance(response.get("message"), str):
                response = {"message": "", "ask_attribute": None, "recommendations": []}
                error = error or "Agent returned an invalid response payload."

            ranked = normalize_recommendations(response.get("recommendations"), self.catalog_ids)
            turn_rank = ranked.index(target) + 1 if override_applied and target in ranked else None
            if turn_rank is not None:
                best_rank = turn_rank
                hit_turn = turn

            recommendations = []
            for rank, parent_asin in enumerate(ranked, start=1):
                product = self.products.get(parent_asin)
                recommendations.append(
                    {
                        "rank": rank,
                        "parent_asin": parent_asin,
                        "is_target": parent_asin == target,
                        "product": _safe_product(product),
                    }
                )

            yield _sse(
                "turn",
                {
                    "turn": turn,
                    "user_message": user_message,
                    "agent_message": response.get("message", ""),
                    "ask_attribute": response.get("ask_attribute"),
                    "recommendations": recommendations,
                    "hit": turn_rank is not None,
                    "target_rank": turn_rank,
                    "override_applied": override_applied,
                    "error": error,
                },
            )

            if turn_rank is not None or turn == MAX_TURNS:
                break

            override = effective_sample.get("behavior", {}).get("override") or {}
            if not override_applied and turn + 1 == int(override.get("turn", 3)):
                override_applied = True
                new_value = str(override.get("new_value", ""))
                if new_value:
                    disclosed.add(new_value)
                user_message = str(override.get("message", "Actually, please ignore my earlier preference."))
            else:
                user_message, boundary_used = customer_reply(
                    effective_sample, response.get("ask_attribute"), disclosed, boundary_used
                )

            if delay_ms > 0:
                time.sleep(delay_ms / 1000)

        yield _sse(
            "done",
            {
                "hit": hit_turn is not None,
                "first_hit_turn": hit_turn,
                "best_rank": best_rank,
                "reciprocal_rank": 0.0 if best_rank is None else 1.0 / best_rank,
            },
        )


class VisualizerHandler(BaseHTTPRequestHandler):
    runner: TraceRunner

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _send_json(self, payload: object, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self._send_file(STATIC_DIR / "app.js", "text/javascript; charset=utf-8")
            return
        if parsed.path == "/styles.css":
            self._send_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/api/sessions":
            self._send_json(self.runner.session_summaries())
            return
        if parsed.path == "/events":
            query = parse_qs(parsed.query)
            index = int(query.get("index", ["0"])[0])
            delay_ms = int(query.get("delay_ms", ["700"])[0])

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            for chunk in self.runner.stream_session(index, delay_ms):
                self.wfile.write(chunk)
                self.wfile.flush()
            return
        self._send_json({"message": "Not found"}, status=404)


def main() -> None:
    parser = argparse.ArgumentParser(description="Realtime visualizer for one Track 4 session.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--catalog", default=str(ROOT / "data/catalog.jsonl"))
    parser.add_argument("--dataset", default=str(ROOT / "data/public_set.jsonl"))
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    dataset_path = Path(args.dataset)
    if not catalog_path.exists():
        raise SystemExit("Missing data/catalog.jsonl. Run ./scripts/download_catalog.sh first.")
    if not dataset_path.exists():
        raise SystemExit(f"Missing dataset: {dataset_path}")

    VisualizerHandler.runner = TraceRunner(catalog_path, dataset_path)
    server = ThreadingHTTPServer((args.host, args.port), VisualizerHandler)
    print(f"Visualizer running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
