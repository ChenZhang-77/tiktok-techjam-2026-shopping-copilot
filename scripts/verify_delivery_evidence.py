"""Independently recompute package metrics and verify tested runtime hashes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def summary(rows):
    count = len(rows)
    hr = sum(bool(r["hit"]) for r in rows) / count
    mrr = sum(1 / r["best_rank"] if r["best_rank"] else 0 for r in rows) / count
    mttc = sum(r["first_hit_turn"] if r["hit"] else 11 for r in rows) / count
    # Match the published evaluator's six-decimal component rounding before score.
    hr, mrr, mttc = round(hr, 6), round(mrr, 6), round(mttc, 6)
    efficiency = max(0, min(1, (11 - mttc) / 10))
    return {"sample_count": count, "hit_rate_at_10": round(hr, 6), "mrr": round(mrr, 6),
            "mttc": round(mttc, 6), "efficiency": round(efficiency, 6),
            "recommended_technical_score": round(.5 * hr + .3 * mrr + .2 * efficiency, 6)}


def main():
    report = json.loads((ROOT / "docs/delivery_reports/offline_package.json").read_text())
    manifest_path = ROOT / "docs/delivery_reports/tested_bundle_manifest.json"
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == report["bundle_manifest_sha256"]
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest.items():
        if name.endswith(".py"):
            assert hashlib.sha256((ROOT / "submission" / name).read_bytes()).hexdigest() == expected, name
    folds = json.loads((ROOT / "docs/development_folds_v1.json").read_text())["folds"]
    assert report["parity"] and report["external_llm_calls"] == 0
    assert report["baseline"]["sessions"] == report["delivery"]["sessions"]
    assert report["baseline"]["runtime"]["trace_sha256"] == report["delivery"]["runtime"]["trace_sha256"]
    for arm in ("baseline", "delivery"):
        result = report[arm]
        for key, expected in summary(result["sessions"]).items():
            assert result[key] == expected, (arm, key, result[key], expected)
        for fold, members in folds.items():
            expected = summary([s for s in result["sessions"] if s["sample_id"] in members])
            for key, value in expected.items():
                assert result["fixed_folds"][fold][key] == value, (arm, fold, key)
        assert result["runtime"]["fallbacks"] == 0
        assert result["sample_count"] == 160
    print("Package evidence verified: runtime hashes, arithmetic, four folds, source/delivery parity")
    final_path = ROOT / "docs/delivery_reports/final_public_full200.json"
    if final_path.exists():
        final = json.loads(final_path.read_text())
        freeze_path = ROOT / "docs/delivery_reports/final_public_freeze.json"
        freeze = json.loads(freeze_path.read_text())
        assert hashlib.sha256(freeze_path.read_bytes()).hexdigest() == final["freeze_sha256"]
        marker = json.loads(Path(str(freeze_path) + ".started").read_text())
        assert marker["freeze_sha256"] == final["freeze_sha256"]
        assert final["acceptance_passed"] and final["source_and_inputs_unchanged"]
        assert final["external_llm_calls"] == 0 and final["evaluation"]["mode"] == "offline"
        assert final["evaluation"]["split"] == "full"
        assert freeze["configuration"] == {"mode": "offline", "retrieval_mode": "conditional_dense",
                                            "max_calls": 0, "max_usd": 0, "max_seconds": 0}
        for name, expected in freeze["bundle_files_sha256"].items():
            if name.endswith(".py"):
                assert hashlib.sha256((ROOT / "submission" / name).read_bytes()).hexdigest() == expected, name
        for name in ("catalog", "dataset"):
            assert freeze["input_sha256"][name] == report["input_sha256"][name], name
        assert freeze["evaluator_sha256"] == report["evaluator_sha256"]
        assert freeze["vector_sha256"] == report["model_asset_sha256"]
        result = final["result"]
        samples = [json.loads(line) for line in (ROOT / "data/public_set.jsonl").read_text().splitlines() if line]
        assert len(result["sessions"]) == len(samples) == 200
        assert {r["sample_id"] for r in result["sessions"]} == {r["sample_id"] for r in samples}
        development_ids = {r["sample_id"] for r in report["delivery"]["sessions"]}
        assert [r for r in result["sessions"] if r["sample_id"] in development_ids] == report["delivery"]["sessions"]
        for key, value in summary(result["sessions"]).items():
            assert result[key] == value, ("full200", key)
        for scenario, metrics in result["scenario_metrics"].items():
            rows = [r for r in result["sessions"] if r["scenario_type"] == scenario]
            assert len(rows) == sum(s["scenario_type"] == scenario for s in samples)
            for key, value in summary(rows).items():
                assert metrics[key] == value, ("full200", scenario, key)
        for field in ("fallbacks", "invalid_responses", "response_exceptions"):
            assert final["runtime"][field] == 0, field
        assert result["reported_token_usage"]["total_tokens"] == 0
        print("Full200 evidence verified: frozen offline runtime, input hashes, 200 outcomes, arithmetic and failure counters")


if __name__ == "__main__":
    main()
