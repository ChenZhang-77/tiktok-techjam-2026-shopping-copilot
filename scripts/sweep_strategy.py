from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluator.local_evaluator import catalog_index, evaluate, filter_samples, load_jsonl, load_split_manifest
from starter.agent import Agent
from starter.core.planner import StrategyConfig


def candidate_configs() -> dict[str, StrategyConfig]:
    base = StrategyConfig()
    return {
        "current": base,
        "deeper-buying": StrategyConfig(buying_depth_sparse=80, buying_depth_constrained=100),
        "deeper-browsing": StrategyConfig(browsing_depth_sparse=140, browsing_depth_constrained=120),
        "shallower-browsing": StrategyConfig(browsing_depth_sparse=100, browsing_depth_constrained=80),
        "more-lexical-buying": StrategyConfig(buying_lexical_weight=0.78, buying_structured_weight=0.22),
        "more-structured-buying": StrategyConfig(buying_lexical_weight=0.66, buying_structured_weight=0.34),
        "more-lexical-browsing": StrategyConfig(browsing_lexical_weight=0.70, browsing_structured_weight=0.12),
        "more-structured-browsing": StrategyConfig(browsing_lexical_weight=0.54, browsing_structured_weight=0.28),
        "deeper-balanced": StrategyConfig(
            buying_depth_sparse=80,
            buying_depth_constrained=100,
            browsing_depth_sparse=140,
            browsing_depth_constrained=120,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep Agent control-plane strategy parameters.")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--split", choices=("development", "holdout", "full"), default="development")
    parser.add_argument("--split-manifest", default="docs/public_split_v1.json")
    parser.add_argument("--output", default="experiments/strategy_sweep.json")
    parser.add_argument("--only", default="", help="Comma-separated strategy names to run.")
    args = parser.parse_args()

    samples = load_jsonl(args.dataset)
    manifest = None
    if args.split != "full":
        manifest = load_split_manifest(args.split_manifest)
        samples = filter_samples(samples, args.split, manifest)

    catalog_ids, categories, products = catalog_index(args.catalog)
    configs = candidate_configs()
    if args.only:
        names = [item.strip() for item in args.only.split(",") if item.strip()]
        missing = [name for name in names if name not in configs]
        if missing:
            raise SystemExit(f"Unknown strategy name(s): {', '.join(missing)}")
        selected = [(name, configs[name]) for name in names]
    else:
        selected = list(configs.items())

    rows: list[dict] = []
    for name, config in selected:
        result = evaluate(Agent(args.catalog, strategy_config=config), samples, catalog_ids, categories, products)
        rows.append({
            "name": name,
            "split": args.split,
            "recommended_technical_score": result["recommended_technical_score"],
            "hit_rate_at_10": result["hit_rate_at_10"],
            "mrr": result["mrr"],
            "mttc": result["mttc"],
            "config": asdict(config),
        })
        print(
            f"{name:24s} score={result['recommended_technical_score']:.6f} "
            f"hit={result['hit_rate_at_10']:.6f} mrr={result['mrr']:.6f} mttc={result['mttc']:.6f}",
            flush=True,
        )

    rows.sort(key=lambda item: item["recommended_technical_score"], reverse=True)
    output = {
        "split": args.split,
        "split_version": manifest.get("version") if manifest else None,
        "results": rows,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    best = rows[0]
    print()
    print(f"best={best['name']} score={best['recommended_technical_score']:.6f}")
    print(f"saved={output_path}")


if __name__ == "__main__":
    main()
