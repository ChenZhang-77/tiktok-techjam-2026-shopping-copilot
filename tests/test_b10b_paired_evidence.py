import hashlib
import json
from pathlib import Path
from statistics import fmean
import unittest


class PairedEvidenceTest(unittest.TestCase):
    def test_bound_results_recompute_scores_and_preserve_source_and_decision(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads((root / "docs/b10b_paired_verification_result.json").read_text())
        folds = json.loads((root / "docs/development_folds_v1.json").read_text())["folds"]
        members = set().union(*map(set, folds.values()))
        for mode, rows in result["session_outcomes"].items():
            self.assertEqual(len(rows), 160)
            self.assertEqual({r["sample_id"] for r in rows}, members)
            arm = result["arms"][mode]
            groups = [(rows, arm)]
            groups += [([r for r in rows if r["sample_id"] in ids], arm["fixed_folds"][f])
                       for f, ids in folds.items()]
            groups += [([r for r in rows if r["scenario_type"] == scenario], metrics)
                       for scenario, metrics in arm["scenario_metrics"].items()]
            for selected, reported in groups:
                hr = round(fmean(r["hit"] for r in selected), 6)
                mrr = round(fmean(0 if r["best_rank"] is None else 1/r["best_rank"] for r in selected), 6)
                mttc = round(fmean(r["first_hit_turn"] if r["hit"] else 11 for r in selected), 6)
                efficiency = round((11-mttc)/10, 6)
                score = round(.5*hr + .3*mrr + .2*efficiency, 6)
                for key, expected in (("hit_rate_at_10", hr), ("mrr", mrr), ("mttc", mttc),
                                      ("efficiency", efficiency), ("recommended_technical_score", score)):
                    self.assertEqual(reported[key], expected)
        for path, digest in result["provenance"]["source_sha256"].items():
            self.assertEqual(hashlib.sha256((root/path).read_bytes()).hexdigest(), digest)
        for comparison in result["comparisons"].values():
            self.assertEqual(comparison["passes"], all(comparison["gates"].values()))
        verified = (result["source_and_inputs_unchanged"] and "repeat" in result["comparisons"]
                    and all(r["passes"] for r in result["comparisons"].values()))
        self.assertEqual(result["decision"] == "verified_optional_plan_two", verified)
        self.assertFalse(result["runtime_default_changed"])


if __name__ == "__main__":
    unittest.main()
