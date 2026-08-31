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


if __name__ == "__main__":
    main()
