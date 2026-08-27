# A8 Stateful Intent Persistence — Retained Evidence

## Decision

Retain A8 at code commit `b3c4aeb`. The runtime now persists a complete
`IntentAssessment` across turns instead of re-inferring intent from only the
latest reply. The assessment contains `intent`, bounded `confidence`,
conversation-derived `evidence`, `source_turn`, and one of four transition
reasons: `retained`, `accumulated`, `relaxed`, or `explicit_override`.

This is a control-plane and explainability win with a modest Buying ordering
gain. It is **not** evidence of a robust aggregate score improvement.

## Experiment Record

- **ID and owner:** A8, Developer A.
- **Hypothesis:** persisted evidence and explicit hysteresis prevent normal
  clarification replies from flipping Buying to Browsing while still allowing
  real exploration, accumulated specificity, and overrides to change intent.
- **Failure class:** Intent / Strategy Routing.
- **Primary behavior:** persist and consume `IntentAssessment`; expose the
  transition through A-side diagnostics and `Strategy.reason`.
- **Comparator:** retained structured runtime in
  `docs/b2_reports/development_structured.json`.
- **Evaluation:** fixed Development-160 plus the four checked-in folds only.
- **Shared contract:** unchanged.
- **Leakage boundary:** no evaluator target, scenario label, hit/miss, target
  rank, or sample-specific rule enters runtime state, requests, diagnostics,
  rules, or models.

## Development-160 Result

| Metric | Baseline | A8 | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.7625 | 0.7625 | 0.0000 |
| MRR | 0.526989 | 0.529812 | +0.002823 |
| MTTC | 5.30625 | 5.35000 | +0.04375 |
| Technical score | 0.653222 | 0.653194 | -0.000028 |

There are zero gained and zero lost sessions; 12 successful sessions changed
first-hit timing or best rank. Scenario technical-score deltas are Boundary
`-0.005000`, Browsing `+0.000112`, Buying `+0.001640`, and Intent Override
`-0.003194`.

## Fold Evidence

| Fold | Overall score delta | Buying | Browsing | Intent Override |
| --- | ---: | ---: | ---: | ---: |
| 1 | +0.001154 | +0.004137 | 0.000000 | -0.003333 |
| 2 | -0.001417 | -0.001250 | 0.000000 | -0.006111 |
| 3 | -0.000217 | +0.000260 | +0.000447 | 0.000000 |
| 4 | +0.000366 | +0.003415 | 0.000000 | -0.003333 |

Buying improves in three folds and Browsing never regresses. Overall folds
straddle zero and Intent Override is slightly worse, so future work must not
describe A8 as a general score improvement. The keep gate is satisfied by
stable persisted semantics, tested transitions, the 3/4 Buying direction, no
Browsing regression, unchanged HitRate, and no target-specific behavior.

## Reliability and Rejected Variants

The clean run reports zero response exceptions, invalid payloads, or fallbacks,
uses zero model tokens, and adds no retrieval/model stage. Its observed mean
response latency is `44.29 ms`, mean retrieval latency `37.48 ms`, and peak RSS
`547,454,976` bytes; these are observations, not paired causal cost claims.

Rejected during bounded development experiments:

- unbounded sticky Buying: score `0.638267`, with two baseline hits lost;
- confidence-gated hard filtering: score `0.652686`; confidence was not a
  validated retrieval gate;
- clearing every free-form `feature` on override: HitRate `0.75` and Intent
  Override HitRate `0.625`; the cleanup scope was too broad.

## Next Step

Proceed to **AB0 DecisionEvidence availability**. AB0 must inventory the
producer, type, range, lifecycle, and fallback for each A9 signal without
changing whether the Agent asks. A8 confidence remains A-owned and must not
become a B-side ranking/filter gate without a coordinated, measured contract.

Machine-checkable evidence and immutable clean reports are in
`docs/a8_stateful_intent_evidence.json` and `docs/a8_reports/`.
