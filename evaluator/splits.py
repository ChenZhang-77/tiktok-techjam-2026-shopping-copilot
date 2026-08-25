from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

SPLIT_VERSION = "public-split-v1"
SPLIT_SEED = "techjam-2026-public-split-v1"
HOLDOUT_COUNTS = {
    "buying": 16,
    "browsing": 16,
    "intent_override": 6,
    "boundary": 2,
}


def _split_key(sample: dict) -> str:
    source = f"{SPLIT_SEED}\0{sample['sample_id']}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def build_split_manifest(samples: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        grouped[str(sample["scenario_type"])].append(sample)

    development: list[str] = []
    holdout: list[str] = []
    for scenario, scenario_samples in sorted(grouped.items()):
        required = HOLDOUT_COUNTS.get(scenario)
        if required is None:
            raise ValueError(f"Unexpected scenario_type: {scenario}")
        if len(scenario_samples) < required:
            raise ValueError(f"Not enough samples for {scenario}: {len(scenario_samples)} < {required}")
        ordered = sorted(scenario_samples, key=_split_key)
        holdout.extend(str(sample["sample_id"]) for sample in ordered[:required])
        development.extend(str(sample["sample_id"]) for sample in ordered[required:])

    sample_ids = [str(sample["sample_id"]) for sample in samples]
    return {
        "version": SPLIT_VERSION,
        "seed": SPLIT_SEED,
        "dataset": "data/public_set.jsonl",
        "sample_count": len(samples),
        "development": sorted(development),
        "holdout": sorted(holdout),
        "counts": {
            "full": len(sample_ids),
            "development": len(development),
            "holdout": len(holdout),
            "development_by_scenario": dict(Counter(
                str(sample["scenario_type"]) for sample in samples if str(sample["sample_id"]) in development
            )),
            "holdout_by_scenario": dict(Counter(
                str(sample["scenario_type"]) for sample in samples if str(sample["sample_id"]) in holdout
            )),
        },
    }


def load_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_split_manifest(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def filter_samples(samples: list[dict], split: str, manifest: dict | None = None) -> list[dict]:
    if split == "full":
        return samples
    if manifest is None:
        raise ValueError("A split manifest is required for development or holdout evaluation.")
    if split not in {"development", "holdout"}:
        raise ValueError(f"Unknown split: {split}")
    selected = set(str(sample_id) for sample_id in manifest[split])
    return [sample for sample in samples if str(sample["sample_id"]) in selected]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deterministic public-set development/holdout split.")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--output", default="docs/public_split_v1.json")
    args = parser.parse_args()

    samples = load_jsonl(args.dataset)
    manifest = build_split_manifest(samples)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
