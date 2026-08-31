"""Run the bundled Agent through the unmodified official Development evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items()
                if k not in {"delivery", "latency_ms", "stage_latencies_ms"}}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


class Observer:
    def __init__(self, agent):
        self.agent = agent
        self.trace = []
        self.latencies = []
        self.routes = {}
        self.fallbacks = 0

    def reset(self, session_id, user_profile):
        self.agent.reset(session_id, user_profile)

    def respond(self, session_id, user_message, turn, top_k):
        started = time.perf_counter()
        response = self.agent.respond(session_id, user_message, turn, top_k)
        self.latencies.append((time.perf_counter() - started) * 1000)
        self.trace.append({"turn": turn, "input": user_message, "response": stable(response)})
        self.fallbacks += bool(response.get("diagnostics", {}).get("fallback_used"))
        for route in response.get("diagnostics", {}).get("retrieval", {}).get("executed_routes", []):
            self.routes[route] = self.routes.get(route, 0) + 1
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.jsonl"))
    parser.add_argument("--cache-dir", type=Path, default=Path("embeddings/minilm-l6-v2-v1"))
    parser.add_argument("--model-cache-dir", type=Path, default=Path("models/huggingface/hub"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("use a new report path")
    bundle = Path(__file__).resolve().parents[1]
    kit = args.kit_root.resolve()
    manifest = json.loads((bundle / "MANIFEST.json").read_text())
    for name, expected in manifest.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe manifest entry")
        if sha(bundle / relative) != expected:
            raise ValueError(f"bundle integrity failure: {name}")
    sys.path.insert(0, str(kit))
    sys.path.insert(0, str(bundle / "src"))
    sys.path.insert(0, str(bundle))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    # This command is never a paid runner, irrespective of inherited credentials.
    import urllib.request
    def forbidden(*_args, **_kwargs):
        raise RuntimeError("network forbidden in offline package evaluation")
    urllib.request.urlopen = forbidden
    from agent import Agent
    from starter.agent import Agent as CoreAgent
    from starter.delivery import DeliveryConfig
    from starter.contracts import RetrievalRequest
    from starter.core.planner import Strategy
    from starter.retrieval import ConditionalDenseRetriever, DenseConfig
    from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl, metric_summary
    from evaluator.splits import filter_samples, load_split_manifest

    split_path = bundle / "evaluation/public_split_v1.json"
    folds_path = bundle / "evaluation/development_folds_v1.json"
    samples_path = kit / "data/public_set.jsonl"
    split = load_split_manifest(split_path)
    samples = filter_samples(load_jsonl(samples_path), "development", split)
    folds = load_split_manifest(folds_path)["folds"]
    if len(samples) != 160 or set().union(*(set(v) for v in folds.values())) != {s["sample_id"] for s in samples}:
        raise ValueError("fixed Development-160/fold population mismatch")
    if sum(len(v) for v in folds.values()) != 160:
        raise ValueError("fold membership is not a partition")
    ids, categories, products = catalog_index(args.catalog)
    if len(ids) != 50000:
        raise ValueError("expected the frozen 50,000-product catalog")

    def score(rows):
        result = metric_summary(rows)
        efficiency = max(0.0, min(1.0, (11 - result["mttc"]) / 10))
        result["efficiency"] = round(efficiency, 6)
        result["recommended_technical_score"] = round(
            .5 * result["hit_rate_at_10"] + .3 * result["mrr"] + .2 * efficiency, 6)
        return result

    def run(delivery):
        started = time.perf_counter()
        retriever = ConditionalDenseRetriever.from_catalog(args.catalog, dense_config=DenseConfig(
            cache_dir=args.cache_dir, model_cache_dir=args.model_cache_dir))
        try:
            warm = retriever.retrieve(RetrievalRequest("synthetic_warmup", 1, 10, "shoes", "browsing",
                Strategy("browsing", .6, .2, .2, 120, False, True, "broad_lexical", "synthetic prewarm")))
            agent = Agent(args.catalog, config=DeliveryConfig(), retriever=retriever) if delivery else CoreAgent(args.catalog, retriever=retriever)
            observer = Observer(agent)
            initialization = (time.perf_counter() - started) * 1000
            result = evaluate(observer, samples, ids, categories, products)
            result.update(score(result["sessions"]))
            result["fixed_folds"] = {name: score([s for s in result["sessions"] if s["sample_id"] in members])
                                     for name, members in folds.items()}
            result["scenario_metrics"] = {name: score([s for s in result["sessions"] if s["scenario_type"] == name])
                                          for name in sorted({s["scenario_type"] for s in result["sessions"]})}
            result["runtime"] = {"initialization_ms": initialization, "respond_count": len(observer.trace),
                "response_p95_ms": sorted(observer.latencies)[int(.95 * (len(observer.latencies) - 1))],
                "response_max_ms": max(observer.latencies), "fallbacks": observer.fallbacks,
                "routes": observer.routes, "warmup": warm.diagnostics.to_dict(),
                "trace_sha256": hashlib.sha256(json.dumps(observer.trace, sort_keys=True).encode()).hexdigest(),
                "elapsed_seconds": time.perf_counter() - started}
            return result, observer.trace
        finally:
            retriever.close()

    core, core_trace = run(False)
    delivery, delivery_trace = run(True)
    parity = core_trace == delivery_trace and core["sessions"] == delivery["sessions"] and core["fixed_folds"] == delivery["fixed_folds"]
    report = {"scope": "independent package offline Development-160; actual retrieval; synthetic prewarm",
        "evaluation": {"split": "development", "retrieval_mode": "conditional_dense", "mode": "offline"},
        "parity": parity, "baseline": core, "delivery": delivery, "external_llm_calls": 0,
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)},
        "bundle_manifest_sha256": sha(bundle / "MANIFEST.json"),
        "input_sha256": {"catalog": sha(args.catalog), "dataset": sha(samples_path),
            "split": sha(split_path), "folds": sha(folds_path)},
        "evaluator_sha256": {p.relative_to(kit).as_posix(): sha(p) for p in sorted((kit / "evaluator").glob("*.py"))},
        "model_asset_sha256": {name: sha(args.cache_dir / name) for name in ("metadata.json", "ids.json", "vectors.npy")},
        "limitations": ["Same-machine prepared environment, not a fresh dependency install on another machine",
            "Synthetic prewarm, not every possible cold-start condition", "No new real LLM verification"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"parity": parity, **score(delivery["sessions"]), "runtime": delivery["runtime"]}))
    if not parity or delivery["runtime"]["fallbacks"] or len(delivery["sessions"]) != 160:
        raise SystemExit("offline package acceptance failed; inspect report")


if __name__ == "__main__":
    main()
