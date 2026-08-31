"""One frozen offline Full200 public report; never a tuning or paid runner."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time

from evaluate_offline import Observer, sha


def snapshot(bundle, args):
    manifest = json.loads((bundle / "MANIFEST.json").read_text())
    for name, expected in manifest.items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or sha(bundle / path) != expected:
            raise ValueError(f"bundle integrity failure: {name}")
    return {
        "scope": "frozen offline Full200 public reporting; exposed, not unseen validation",
        "configuration": {"mode": "offline", "retrieval_mode": "conditional_dense",
                          "max_calls": 0, "max_usd": 0, "max_seconds": 0},
        "bundle_manifest_sha256": sha(bundle / "MANIFEST.json"),
        "bundle_files_sha256": manifest,
        "input_sha256": {"catalog": sha(args.catalog),
                         "dataset": sha(args.kit_root / "data/public_set.jsonl")},
        "evaluator_sha256": {p.relative_to(args.kit_root).as_posix(): sha(p)
                             for p in sorted((args.kit_root / "evaluator").glob("*.py"))},
        "vector_sha256": {name: sha(args.cache_dir / name)
                          for name in ("metadata.json", "ids.json", "vectors.npy")},
        "local_model_sha256": {p.relative_to(args.model_cache_dir).as_posix(): sha(p)
                               for p in sorted(args.model_cache_dir.rglob("*")) if p.is_file()},
    }


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.jsonl"))
    parser.add_argument("--cache-dir", type=Path, default=Path("embeddings/minilm-l6-v2-v1"))
    parser.add_argument("--model-cache-dir", type=Path, default=Path("models/huggingface/hub"))
    parser.add_argument("--freeze-file", type=Path, required=True)
    parser.add_argument("--freeze-only", action="store_true", help="Record hashes without running any sessions")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.freeze_only and args.freeze_file.exists():
        parser.error("freeze already exists; it is immutable")
    if not args.freeze_only and (args.output is None or args.output.exists()):
        parser.error("a new output path is required")
    marker = Path(str(args.freeze_file) + ".started")
    if marker.exists():
        parser.error("this frozen public run already started; do not automatically rerun")
    bundle = Path(__file__).resolve().parents[1]
    frozen = snapshot(bundle, args)
    if not frozen["evaluator_sha256"] or not frozen["local_model_sha256"]:
        parser.error("evaluator and prepared local model files are required")
    if args.freeze_only:
        write_new(args.freeze_file, frozen)
        print("Frozen hashes recorded; no sessions run and no network calls.")
        return
    if json.loads(args.freeze_file.read_text()) != frozen:
        parser.error("source/configuration/inputs changed since freeze")

    sys.path.insert(0, str(args.kit_root.resolve()))
    sys.path.insert(0, str(bundle / "src"))
    sys.path.insert(0, str(bundle))
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    import urllib.request
    def forbidden(*_args, **_kwargs):
        raise RuntimeError("network forbidden in final offline public report")
    urllib.request.urlopen = forbidden
    from agent import Agent
    from starter.delivery import DeliveryConfig
    from starter.contracts import RetrievalRequest, validate_agent_response
    from starter.core.planner import Strategy
    from starter.retrieval import ConditionalDenseRetriever, DenseConfig
    from evaluator.local_evaluator import (
        ALLOWED_ATTRIBUTES, catalog_index, evaluate, load_jsonl, metric_summary,
    )
    samples = load_jsonl(args.kit_root / "data/public_set.jsonl")
    if len(samples) != 200 or len({s["sample_id"] for s in samples}) != 200:
        raise ValueError("expected exactly 200 unique public sessions")
    ids, categories, products = catalog_index(args.catalog)
    if len(ids) != 50000:
        raise ValueError("expected the frozen 50,000-product catalog")

    class ValidatedObserver(Observer):
        invalid_responses = 0
        response_exceptions = 0

        def respond(self, session_id, user_message, turn, top_k):
            try:
                response = super().respond(session_id, user_message, turn, top_k)
            except Exception:
                self.response_exceptions += 1
                raise
            try:
                validate_agent_response(response, catalog_ids=ids, top_k=top_k,
                                        allowed_ask_attributes=ALLOWED_ATTRIBUTES)
            except ValueError:
                self.invalid_responses += 1
                raise
            return response

    def score(rows):
        metrics = metric_summary(rows)
        efficiency = max(0.0, min(1.0, (11 - metrics["mttc"]) / 10))
        metrics["efficiency"] = round(efficiency, 6)
        metrics["recommended_technical_score"] = round(
            .5 * metrics["hit_rate_at_10"] + .3 * metrics["mrr"] + .2 * efficiency, 6)
        return metrics

    write_new(marker, {"started_utc": datetime.now(timezone.utc).isoformat(),
                       "freeze_sha256": sha(args.freeze_file)})
    started = time.perf_counter()
    retriever = ConditionalDenseRetriever.from_catalog(args.catalog, dense_config=DenseConfig(
        cache_dir=args.cache_dir, model_cache_dir=args.model_cache_dir))
    try:
        warm = retriever.retrieve(RetrievalRequest("synthetic_warmup", 1, 10, "shoes", "browsing",
            Strategy("browsing", .6, .2, .2, 120, False, True, "broad_lexical", "synthetic prewarm")))
        agent = Agent(args.catalog, config=DeliveryConfig(), retriever=retriever)
        observer = ValidatedObserver(agent)
        initialization = (time.perf_counter() - started) * 1000
        result = evaluate(observer, samples, ids, categories, products)
        result.update(score(result["sessions"]))
        result["scenario_metrics"] = {name: score([s for s in result["sessions"] if s["scenario_type"] == name])
                                      for name in sorted({s["scenario_type"] for s in samples})}
        runtime = {"initialization_ms": initialization, "respond_count": len(observer.trace),
            "response_p95_ms": sorted(observer.latencies)[int(.95 * (len(observer.latencies) - 1))],
            "response_max_ms": max(observer.latencies), "fallbacks": observer.fallbacks,
            "invalid_responses": observer.invalid_responses, "response_exceptions": observer.response_exceptions,
            "routes": observer.routes, "warmup": warm.diagnostics.to_dict(),
            "trace_sha256": hashlib.sha256(json.dumps(observer.trace, sort_keys=True).encode()).hexdigest(),
            "elapsed_seconds": time.perf_counter() - started}
        unchanged = snapshot(bundle, args) == frozen
        passed = unchanged and len(result["sessions"]) == 200 and not any((observer.fallbacks,
            observer.invalid_responses, observer.response_exceptions))
        report = {"scope": frozen["scope"], "evaluation": {"split": "full", **frozen["configuration"]},
            "freeze_sha256": sha(args.freeze_file), "result": result, "runtime": runtime,
            "external_llm_calls": 0, "acceptance_passed": passed,
            "source_and_inputs_unchanged": unchanged,
            "environment": {"python": platform.python_version(), "platform": platform.platform(),
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)},
            "limitations": ["Exposed public set; not unseen validation or a tuning input",
                "Prepared same-machine dependencies/assets; no fresh-install or other-host guarantee",
                "Synthetic prewarm; timing includes local initialization, not dependency/model download",
                "Offline only; historical F2 is not new live package verification"]}
        write_new(args.output, report)
        print(json.dumps({"acceptance_passed": passed, **score(result["sessions"]), "runtime": runtime}))
        if not passed:
            raise SystemExit("Final public gate failed; keep the report, do not tune or automatically rerun")
    finally:
        retriever.close()


if __name__ == "__main__":
    main()
