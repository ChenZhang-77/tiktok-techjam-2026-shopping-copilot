# B12 Adaptive Candidate Depth Evidence

## Decision

Retain B12 at runtime commit `0f47710`. A now maps its existing persistent,
ordinal `IntentAssessment` into the existing bounded
`Strategy.retrieval_depth` field for one narrow case. B continues to consume
only that typed depth; it does not receive raw confidence or implement a second
intent policy.

The candidate improves every aggregate Development-160 quality metric while
reducing the mean lexical and structured candidate count. The improvement is
concentrated rather than uniform: one fold regresses slightly, two are exact
parity, and one improves materially.

## Exact policy

The adaptive gate requires all of the following:

- Buying intent;
- A-owned `IntentAssessment.confidence_band == "high"`;
- at least two active constraints.

When the gate is true, A selects
`min(buying_depth_sparse, buying_depth_constrained)`, which is 60 under the
current default configuration. Effective depth is always
`max(top_k, selected_depth_floor)`, so a larger requested Top K is never
truncated. Strategy diagnostics record `depth policy=adaptive_narrow`.

When the assessment is missing, confidence is not high, or the request is not
narrow Buying, the previous intent-and-active-constraint mapping is preserved
exactly. This is the fixed fallback.

## Development-160 result

| Metric | B9 baseline | B12 | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.862500 | 0.868750 | +0.006250 |
| MRR | 0.547329 | 0.549735 | +0.002406 |
| MTTC | 4.668750 | 4.606250 | -0.062500 |
| Efficiency | 0.633125 | 0.639375 | +0.006250 |
| TechnicalScore | 0.722074 | 0.727170 | +0.005096 |

Three sessions changed. One previously missed Browsing session became a hit;
no session lost a hit. The Buying scenario TechnicalScore increased by
`0.000085`, Browsing by `0.012656`, and Intent Override and Boundary remained
exactly equal.

## Fixed folds

| Fold | HitRate delta | MRR delta | TechnicalScore delta |
| --- | ---: | ---: | ---: |
| fold_1 | 0 | -0.002083 | -0.000625 |
| fold_2 | 0 | 0 | 0 |
| fold_3 | 0 | 0 | 0 |
| fold_4 | +0.025000 | +0.011706 | +0.021012 |

This is not a four-fold universal gain. The keep decision accepts the small
fold-1 rank regression because aggregate HitRate, MRR, MTTC, and
TechnicalScore all improve, no hit is lost, and candidate cost falls. Future
tuning must not target fold 1 or fold 4 individually.

## Cost and reliability

Mean lexical and structured candidate count fell from `95.144828` to
`88.994413`, a deterministic reduction of `6.150415` candidates per executed
retrieval response. In separate single-process runs, mean retrieval latency
fell from about `21.73 ms` to `21.07 ms`, and p95 from about `40.44 ms` to
`39.02 ms`. Peak RSS was effectively unchanged at about `1.109 GB`.

The timing and RSS comparison is directional rather than a controlled causal
benchmark. The candidate produced 716 responses instead of 725 because it
reached one additional target earlier. There were zero response exceptions,
invalid payloads, reported fallbacks, or Route failures. Dense and fusion still
executed 102 times.

## Boundary and reproducibility

- Selection used Development-160 and all four fixed folds only.
- Full-200 and the exposed Holdout-40 were not run.
- Evaluator target information was used only for offline metric/session
  comparison and never entered state, Strategy, request, diagnostics,
  retrieval, or ranking.
- The confidence value remains an A-owned ordinal stability signal, not a
  calibrated probability.
- B consumes the existing validated `retrieval_depth`; no request schema or
  B-side confidence gate was added.

Machine-checkable evidence is in `docs/b12_adaptive_depth_evidence.json`, with
raw reports under `docs/b12_reports/`.
