# B12 Adaptive Candidate Depth Evidence

## Decision

Do not retain B12 as the default. Keep it as a reproducible exploratory option
at `46a9c53`, enabled only by `--adaptive-depth`. The ordinary Agent leaves the
flag off and exactly preserves the B9 default.

The candidate has a favorable Development-160 aggregate result, but no
contemporaneous keep/revert gate was recorded before the result was observed.
Its cross-validation gain is also concentrated in fold 4. Retrofitting a gate
after seeing those results would be post-hoc selection, so the evidence is not
strong enough to change the default.

## Experiment discipline

- Canonical failure class: Intent / Strategy Routing.
- Primary behavior: optional A-owned candidate-depth choice.
- Execution order: focused tests, aggregate Development-160, then four fixed
  folds after the aggregate looked favorable.
- Predeclared keep gate: unavailable.
- Predeclared revert gate: unavailable.
- Consequence: exploratory evidence only; not eligible for default retention.

The expected code, test, report, and documentation files are enumerated in the
machine-readable evidence. No post-hoc threshold is presented as if it had
been predeclared.

## Optional policy and default fallback

With `--adaptive-depth`, the gate requires Buying intent, A-owned high ordinal
confidence, and at least two active constraints. A selects
`min(buying_depth_sparse, buying_depth_constrained)`, currently 60. Effective
depth remains `max(top_k, selected_depth_floor)`.

The default flag is false. With the flag off—or with a missing assessment or a
non-gated request—the prior B9 intent/constraint depth mapping is unchanged. B
consumes only the validated `Strategy.retrieval_depth`; raw confidence never
crosses the seam and B does not parse `Strategy.reason`.

## Development-160 observation

| Metric | B9/default | Optional B12 | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.862500 | 0.868750 | +0.006250 |
| MRR | 0.547329 | 0.549735 | +0.002406 |
| MTTC | 4.668750 | 4.606250 | -0.062500 |
| Efficiency | 0.633125 | 0.639375 | +0.006250 |
| TechnicalScore | 0.722074 | 0.727170 | +0.005096 |

The current disabled-by-default run at `46a9c53` matches B9 exactly across
aggregate metrics, scenario metrics, and every session.

## Scenario and session tradeoffs

Browsing gains one hit and `0.012656` TechnicalScore. Buying TechnicalScore is
nearly flat at `+0.000085`, but Buying MRR regresses by `0.001799`.
Intent Override and Boundary are exact parity.

Only three sessions change:

- `public_0135`: Buying remains a turn-2 hit, but best rank worsens 4 to 6.
- `public_0178`: Buying arrives earlier at turn 5 instead of 7, but best rank
  worsens 7 to 9.
- `public_0195`: Browsing changes from a ten-turn miss to a turn-3 hit at rank 2.

The candidate has 716 responses versus 725 by default: `public_0195` saves
seven turns and `public_0178` saves two. The response reduction is not caused
only by the new hit.

## Fixed folds

| Fold | HitRate delta | MRR delta | MTTC delta | TechnicalScore delta |
| --- | ---: | ---: | ---: | ---: |
| fold_1 | 0 | -0.002083 | 0 | -0.000625 |
| fold_2 | 0 | 0 | 0 | 0 |
| fold_3 | 0 | 0 | 0 | 0 |
| fold_4 | +0.025000 | +0.011706 | -0.250000 | +0.021012 |

Each candidate fold and its B9 comparator are hash-bound. This is one negative,
two parity, and one positive fold—not a distributed cross-validation win.

## Cost and reliability

Observed mean lexical/structured candidates fall from `95.144828` to
`88.994413`. This is a deterministic observation, but the response mix differs
because two sessions finish earlier; it is not a controlled estimate of the
depth rule's isolated cost effect. The default and candidate reports were run
concurrently, so their latency and RSS values are not used for a causal claim.

The optional candidate has zero response exceptions, invalid payloads,
reported fallbacks, or Route failures. Dense and fusion execute 102 times.

## Boundary and reproducibility

- Development-160 and its four fixed folds only; no Full-200 or Holdout-40.
- Target data is used only for offline comparison and never enters runtime.
- `--adaptive-depth` is explicit and disabled by default.
- The A-owned ordinal signal is not presented as a calibrated probability.
- Raw reports and machine-derived consistency tests are stored under
  `docs/b12_reports/` and `tests/test_b12_adaptive_depth_evidence.py`.
