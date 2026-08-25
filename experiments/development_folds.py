from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


FOLD_VERSION = "development-folds-v1"
FOLD_SEED = "techjam-2026-development-folds-v1"
FOLD_COUNT = 4


def _fold_key(sample_id: str) -> str:
    source = f"{FOLD_SEED}\0{sample_id}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def build_development_fold_manifest(
    samples: list[dict],
    public_split_manifest: dict,
    *,
    fold_count: int = FOLD_COUNT,
) -> dict:
    if fold_count != FOLD_COUNT:
        raise ValueError(f"{FOLD_VERSION} is fixed at {FOLD_COUNT} folds")

    development_ids = [str(sample_id) for sample_id in public_split_manifest["development"]]
    if len(development_ids) != len(set(development_ids)):
        raise ValueError("Development Set contains duplicate sample IDs")

    samples_by_id = {str(sample["sample_id"]): sample for sample in samples}
    missing = set(development_ids) - set(samples_by_id)
    if missing:
        raise ValueError(f"Development Set sample IDs are missing from the dataset: {sorted(missing)}")

    grouped: dict[str, list[str]] = defaultdict(list)
    for sample_id in development_ids:
        scenario = str(samples_by_id[sample_id]["scenario_type"])
        grouped[scenario].append(sample_id)

    folds = {f"fold_{index + 1}": [] for index in range(fold_count)}
    for scenario_ids in grouped.values():
        for index, sample_id in enumerate(sorted(scenario_ids, key=_fold_key)):
            folds[f"fold_{index % fold_count + 1}"].append(sample_id)

    return {
        "version": FOLD_VERSION,
        "seed": FOLD_SEED,
        "dataset": str(public_split_manifest.get("dataset") or "data/public_set.jsonl"),
        "public_split_version": str(public_split_manifest.get("version") or ""),
        "sample_count": len(development_ids),
        "fold_count": fold_count,
        "folds": {name: sorted(sample_ids) for name, sample_ids in folds.items()},
    }


def validate_development_fold_manifest(
    samples: list[dict],
    public_split_manifest: dict,
    manifest: dict,
) -> None:
    if manifest.get("version") != FOLD_VERSION:
        raise ValueError(f"Unexpected development-fold version: {manifest.get('version')}")
    if manifest.get("public_split_version") != public_split_manifest.get("version"):
        raise ValueError("Development folds do not match the public split version")

    folds = manifest.get("folds")
    fold_count = manifest.get("fold_count")
    if not isinstance(folds, dict) or not isinstance(fold_count, int) or len(folds) != fold_count:
        raise ValueError("Development fold count does not match the fold mapping")

    assignments: list[str] = []
    for fold_ids in folds.values():
        if not isinstance(fold_ids, list):
            raise ValueError("Every development fold must be a list of sample IDs")
        assignments.extend(str(sample_id) for sample_id in fold_ids)

    duplicate_ids = sorted(sample_id for sample_id, count in Counter(assignments).items() if count > 1)
    if duplicate_ids:
        raise ValueError(f"Development sample IDs assigned to multiple folds: {duplicate_ids}")

    development_ids = {str(sample_id) for sample_id in public_split_manifest["development"]}
    assigned_ids = set(assignments)
    missing = sorted(development_ids - assigned_ids)
    unexpected = sorted(assigned_ids - development_ids)
    if missing or unexpected:
        raise ValueError(f"Development fold coverage mismatch; missing={missing}, unexpected={unexpected}")
    if manifest.get("sample_count") != len(development_ids):
        raise ValueError("Development fold sample count is incorrect")

    samples_by_id = {str(sample["sample_id"]): sample for sample in samples}
    absent_from_dataset = sorted(assigned_ids - set(samples_by_id))
    if absent_from_dataset:
        raise ValueError(f"Development fold IDs are missing from the dataset: {absent_from_dataset}")

    scenario_counts_by_fold: dict[str, list[int]] = defaultdict(list)
    scenarios = sorted({str(samples_by_id[sample_id]["scenario_type"]) for sample_id in assigned_ids})
    for fold_ids in folds.values():
        fold_counts = Counter(str(samples_by_id[str(sample_id)]["scenario_type"]) for sample_id in fold_ids)
        for scenario in scenarios:
            scenario_counts_by_fold[scenario].append(fold_counts[scenario])
    for scenario, counts in scenario_counts_by_fold.items():
        if max(counts) - min(counts) > 1:
            raise ValueError(f"Development folds are not stratified for scenario: {scenario}")


def filter_development_fold(samples: list[dict], manifest: dict, fold_name: str) -> list[dict]:
    folds = manifest.get("folds")
    if not isinstance(folds, dict) or fold_name not in folds:
        raise ValueError(f"Unknown development fold: {fold_name}")
    selected_ids = {str(sample_id) for sample_id in folds[fold_name]}
    return [sample for sample in samples if str(sample["sample_id"]) in selected_ids]


def _load_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deterministic folds within the Development Set.")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--public-split", default="docs/public_split_v1.json")
    parser.add_argument("--output", default="docs/development_folds_v1.json")
    args = parser.parse_args()

    samples = _load_jsonl(args.dataset)
    public_split = json.loads(Path(args.public_split).read_text(encoding="utf-8"))
    manifest = build_development_fold_manifest(samples, public_split)
    validate_development_fold_manifest(samples, public_split, manifest)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "sample_count": manifest["sample_count"], "fold_count": manifest["fold_count"]}))


if __name__ == "__main__":
    main()
