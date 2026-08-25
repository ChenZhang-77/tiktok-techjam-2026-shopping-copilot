from __future__ import annotations

import argparse
import importlib.util
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
RUNS_DIR = ROOT / "experiments/runs"
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


class InteractiveSession:
    def __init__(
        self,
        *,
        index: int,
        sample: dict,
        catalog_path: Path,
        catalog_ids: set[str],
        categories: dict[str, list[str]],
        products: dict[str, dict],
        agent_cls: type[Agent] = Agent,
    ) -> None:
        self.index = index
        self.sample = sample
        self.catalog_ids = catalog_ids
        self.categories = categories
        self.products = products
        self.agent = agent_cls(catalog_path)
        self.session_id = f"visual_{uuid.uuid4().hex}"
        self.agent.reset(self.session_id, sample["user_profile"])

        self.target = str(sample["ground_truth"]["parent_asin"])
        self.target_product = products.get(self.target)
        intent_card, behavior = materialize_hidden_fields(sample, products)
        self.effective_sample = {**sample, "intent_card": intent_card, "behavior": behavior}
        self.disclosed: set[str] = set()
        self.boundary_used = False
        self.override_applied = sample["scenario_type"] != "intent_override"
        self.user_message = initial_message(
            self.effective_sample,
            coarse_category(categories.get(self.target, [])),
            self.disclosed,
        )
        self.turn = 1
        self.hit_turn: int | None = None
        self.best_rank: int | None = None
        self.done = False

    def start_payload(self) -> dict:
        return {
            "session_index": self.index,
            "session_id": self.session_id,
            "sample_id": self.sample.get("sample_id"),
            "scenario_type": self.sample.get("scenario_type"),
            "target": self.target,
            "target_product": _safe_product(self.target_product),
            "user_profile": self.sample.get("user_profile", {}),
            "max_turns": MAX_TURNS,
            "initial_user_message": self.user_message,
        }

    def final_payload(self) -> dict:
        return {
            "hit": self.hit_turn is not None,
            "first_hit_turn": self.hit_turn,
            "best_rank": self.best_rank,
            "reciprocal_rank": 0.0 if self.best_rank is None else 1.0 / self.best_rank,
        }

    def step(self) -> dict:
        if self.done:
            return {"done": True, "final": self.final_payload()}

        current_user_message = self.user_message
        current_turn = self.turn
        try:
            response = self.agent.respond(self.session_id, current_user_message, current_turn, TOP_K)
        except Exception as exc:
            response = {"message": "", "ask_attribute": None, "recommendations": []}
            error = f"{type(exc).__name__}: {exc}"
        else:
            error = None

        if not isinstance(response, dict) or not isinstance(response.get("message"), str):
            response = {"message": "", "ask_attribute": None, "recommendations": []}
            error = error or "Agent returned an invalid response payload."

        ranked = normalize_recommendations(response.get("recommendations"), self.catalog_ids)
        turn_rank = ranked.index(self.target) + 1 if self.override_applied and self.target in ranked else None
        if turn_rank is not None:
            self.best_rank = turn_rank
            self.hit_turn = current_turn

        recommendations = []
        for rank, parent_asin in enumerate(ranked, start=1):
            product = self.products.get(parent_asin)
            recommendations.append(
                {
                    "rank": rank,
                    "parent_asin": parent_asin,
                    "is_target": parent_asin == self.target,
                    "product": _safe_product(product),
                }
            )

        turn_payload = {
            "turn": current_turn,
            "user_message": current_user_message,
            "agent_message": response.get("message", ""),
            "ask_attribute": response.get("ask_attribute"),
            "recommendations": recommendations,
            "hit": turn_rank is not None,
            "target_rank": turn_rank,
            "override_applied": self.override_applied,
            "error": error,
            "next_user_message": None,
        }

        if turn_rank is not None or current_turn == MAX_TURNS:
            self.done = True
            return {"done": True, "turn": turn_payload, "final": self.final_payload()}

        override = self.effective_sample.get("behavior", {}).get("override") or {}
        if not self.override_applied and current_turn + 1 == int(override.get("turn", 3)):
            self.override_applied = True
            new_value = str(override.get("new_value", ""))
            if new_value:
                self.disclosed.add(new_value)
            self.user_message = str(override.get("message", "Actually, please ignore my earlier preference."))
        else:
            self.user_message, self.boundary_used = customer_reply(
                self.effective_sample,
                response.get("ask_attribute"),
                self.disclosed,
                self.boundary_used,
            )
        self.turn += 1
        turn_payload["next_user_message"] = self.user_message
        return {"done": False, "turn": turn_payload}


class TraceRunner:
    def __init__(self, catalog_path: Path, dataset_path: Path) -> None:
        self.catalog_path = catalog_path
        self.dataset_path = dataset_path
        self.samples = load_jsonl(dataset_path)
        self.catalog_ids, self.categories, self.products = catalog_index(catalog_path)
        self.active_sessions: dict[str, InteractiveSession] = {}
        self._agent_cache: dict[str, type[Agent]] = {"current": Agent}

    def _run_dir(self, experiment_id: str | None) -> Path | None:
        if not experiment_id or experiment_id == "current":
            return None
        candidate = (RUNS_DIR / experiment_id).resolve()
        runs_root = RUNS_DIR.resolve()
        if runs_root not in candidate.parents or candidate.name != experiment_id:
            raise ValueError("Invalid experiment id.")
        if not candidate.is_dir():
            raise ValueError(f"Unknown experiment: {experiment_id}")
        return candidate

    def _agent_class(self, experiment_id: str | None) -> type[Agent]:
        run_dir = self._run_dir(experiment_id)
        if run_dir is None:
            return Agent
        cache_key = run_dir.name
        if cache_key in self._agent_cache:
            return self._agent_cache[cache_key]
        snapshot = run_dir / "agent_snapshot.py"
        if not snapshot.exists():
            return Agent
        module_name = f"experiment_agent_{cache_key.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, snapshot)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load agent snapshot for {cache_key}.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        agent_cls = getattr(module, "Agent", None)
        if agent_cls is None:
            raise ValueError(f"agent_snapshot.py in {cache_key} does not define Agent.")
        self._agent_cache[cache_key] = agent_cls
        return agent_cls

    def _experiment_result(self, experiment_id: str | None) -> dict:
        run_dir = self._run_dir(experiment_id)
        result_path = run_dir / "results.json" if run_dir is not None else ROOT / "results.json"
        if result_path.exists():
            return json.loads(result_path.read_text(encoding="utf-8"))
        return {}

    def _split_sample_ids(self, experiment_id: str | None) -> set[str] | None:
        result = self._experiment_result(experiment_id)
        evaluation = result.get("evaluation") if isinstance(result.get("evaluation"), dict) else {}
        split = evaluation.get("split") or "full"
        if split == "full":
            return None
        manifest_path = ROOT / str(evaluation.get("split_manifest") or "docs/public_split_v1.json")
        if not manifest_path.exists():
            run_dir = self._run_dir(experiment_id)
            if run_dir is not None and (run_dir / "public_split_v1.json").exists():
                manifest_path = run_dir / "public_split_v1.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return set(str(sample_id) for sample_id in manifest[split])

    def experiments(self) -> list[dict]:
        items = [{
            "id": "current",
            "label": "Current workspace",
            "has_results": (ROOT / "results.json").exists(),
            "source": "results.json" if (ROOT / "results.json").exists() else "docs/baseline_results.json",
        }]
        if RUNS_DIR.exists():
            for run_dir in sorted([path for path in RUNS_DIR.iterdir() if path.is_dir()], reverse=True):
                metadata_path = run_dir / "metadata.json"
                metadata = {}
                if metadata_path.exists():
                    try:
                        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        metadata = {}
                label = metadata.get("name") or metadata.get("run_id") or run_dir.name
                items.append({
                    "id": run_dir.name,
                    "label": str(label),
                    "run_id": run_dir.name,
                    "created_at": metadata.get("created_at"),
                    "git_branch": metadata.get("git_branch"),
                    "git_commit": metadata.get("git_commit"),
                    "has_results": (run_dir / "results.json").exists(),
                    "source": f"experiments/runs/{run_dir.name}/results.json",
                })
        return items

    def overall_metrics(self, experiment_id: str | None = None) -> dict:
        run_dir = self._run_dir(experiment_id)
        result_path = run_dir / "results.json" if run_dir is not None else ROOT / "results.json"
        baseline_path = ROOT / "docs/baseline_results.json"
        source = f"experiments/runs/{run_dir.name}/results.json" if run_dir is not None else "results.json"
        if result_path.exists():
            data = json.loads(result_path.read_text(encoding="utf-8"))
        else:
            source = "docs/baseline_results.json"
            data = json.loads(baseline_path.read_text(encoding="utf-8"))
        return {
            "source": source,
            "sample_count": data.get("sample_count"),
            "hit_rate_at_10": data.get("hit_rate_at_10"),
            "mrr": data.get("mrr"),
            "mttc": data.get("mttc"),
            "efficiency": data.get("efficiency"),
            "technical_score": data.get("recommended_technical_score", data.get("technical_score")),
            "scenario_metrics": data.get("scenario_metrics", {}),
            "evaluation": data.get("evaluation", {}),
        }

    def session_summaries(self, experiment_id: str | None = None) -> list[dict]:
        selected = self._split_sample_ids(experiment_id)
        summaries: list[dict] = []
        for index, sample in enumerate(self.samples):
            if selected is not None and str(sample.get("sample_id")) not in selected:
                continue
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

    def start_session(self, index: int, experiment_id: str | None = None) -> dict:
        if index < 0 or index >= len(self.samples):
            raise ValueError(f"Session index out of range: {index}")
        session = InteractiveSession(
            index=index,
            sample=self.samples[index],
            catalog_path=self.catalog_path,
            catalog_ids=self.catalog_ids,
            categories=self.categories,
            products=self.products,
            agent_cls=self._agent_class(experiment_id),
        )
        run_id = uuid.uuid4().hex
        self.active_sessions[run_id] = session
        return {"run_id": run_id, **session.start_payload()}

    def next_turn(self, run_id: str) -> dict:
        session = self.active_sessions.get(run_id)
        if session is None:
            raise ValueError("Unknown run_id. Start a session first.")
        result = session.step()
        if result.get("done"):
            self.active_sessions.pop(run_id, None)
        return result

    def session_trace(self, index: int, experiment_id: str | None = None) -> dict:
        start = self.start_session(index, experiment_id)
        run_id = str(start["run_id"])
        turns: list[dict] = []
        final = None
        while True:
            result = self.next_turn(run_id)
            if result.get("turn"):
                turns.append(result["turn"])
            if result.get("done"):
                final = result.get("final")
                break
        return {"start": start, "turns": turns, "final": final}

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

            next_user_message = None
            will_continue = turn_rank is None and turn != MAX_TURNS
            if will_continue:
                override = effective_sample.get("behavior", {}).get("override") or {}
                if not override_applied and turn + 1 == int(override.get("turn", 3)):
                    next_user_message = str(override.get("message", "Actually, please ignore my earlier preference."))
                else:
                    preview_message, _ = customer_reply(
                        effective_sample,
                        response.get("ask_attribute"),
                        set(disclosed),
                        boundary_used,
                    )
                    next_user_message = preview_message

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
                    "next_user_message": next_user_message,
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
            query = parse_qs(parsed.query)
            experiment_id = query.get("experiment", ["current"])[0]
            try:
                self._send_json(self.runner.session_summaries(experiment_id))
            except ValueError as exc:
                self._send_json({"message": str(exc)}, status=400)
            return
        if parsed.path == "/api/experiments":
            self._send_json(self.runner.experiments())
            return
        if parsed.path == "/api/overall":
            query = parse_qs(parsed.query)
            experiment_id = query.get("experiment", ["current"])[0]
            try:
                self._send_json(self.runner.overall_metrics(experiment_id))
            except ValueError as exc:
                self._send_json({"message": str(exc)}, status=400)
            return
        if parsed.path == "/api/start":
            query = parse_qs(parsed.query)
            index = int(query.get("index", ["0"])[0])
            try:
                self._send_json(self.runner.start_session(index))
            except ValueError as exc:
                self._send_json({"message": str(exc)}, status=400)
            return
        if parsed.path == "/api/next":
            query = parse_qs(parsed.query)
            run_id = query.get("run_id", [""])[0]
            try:
                self._send_json(self.runner.next_turn(run_id))
            except ValueError as exc:
                self._send_json({"message": str(exc)}, status=400)
            return
        if parsed.path == "/api/session_trace":
            query = parse_qs(parsed.query)
            index = int(query.get("index", ["0"])[0])
            experiment_id = query.get("experiment", ["current"])[0]
            try:
                self._send_json(self.runner.session_trace(index, experiment_id))
            except ValueError as exc:
                self._send_json({"message": str(exc)}, status=400)
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
