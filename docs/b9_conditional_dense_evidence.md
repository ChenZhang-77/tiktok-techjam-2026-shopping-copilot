# B9 Browsing-First Conditional Dense Evidence

## Decision

Retain B9 at clean runtime commit `b620357`. The default Agent now executes the
pinned local dense Route only for broad Browsing requests: Browsing intent,
positive Strategy dense weight, no more than one active constraint, and at
least 30 structured candidates. Buying, constrained Browsing, small pools, and
all degraded dense results preserve the exact retained structured order.

This closes the literal Browsing-dense part of the Track 4 hybrid-routing gap.
It does not enable global dense retrieval and does not claim an LLM ranker.

## Quality result

| Metric | AB1 baseline | B9 | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.862500 | 0.862500 | 0 |
| MRR | 0.545568 | 0.547329 | +0.001761 |
| MTTC | 4.675000 | 4.668750 | -0.006250 |
| Efficiency | 0.632500 | 0.633125 | +0.000625 |
| TechnicalScore | 0.721420 | 0.722074 | +0.000654 |

Only Browsing changed. Buying, Intent Override, and Boundary scenario outcomes
are exactly equal to AB1. Four Browsing sessions changed: three improved and
one reached the same rank one turn later; no hit was gained or lost.

The four fixed-fold TechnicalScore deltas are `+0.000238`, `0`, `0`, and
`+0.002375`. No fold regressed.

## Route truthfulness and fallback

Across 725 retrieval turns, dense was requested 474 times and actually executed
102 times; fusion also executed 102 times. The remaining 372 requested dense
turns were intentionally gated out. There were zero route failures, zero
fallbacks, and zero unreported AB1 route semantics in the retained evidence.

If the pinned cache/model is missing, incompatible, fails, or exceeds the
post-execution acceptance budget, B9 returns the exact pre-dense structured
Candidate order and reports the fallback. Gate skips are not reported as
failures.

## Cost and operational boundary

Startup warmup removed the measured 2–3 second first-query model-load spike.
The retained run measured dense mean/p95 latency of about `4.57/5.03 ms` and
overall retrieval p95/max of about `40.13/58.30 ms`.

The cost is material and must remain visible:

- initialization rose from about `2.12 s` to `3.63 s`;
- peak process RSS rose from about `563 MB` to `1.109 GB`;
- the embedding cache is about `77.5 MB`.

The gain is small and contains no additional hits, but it is fold-safe,
Browsing-only, makes the required dense Route genuinely active, and preserves
Buying/Intent Override. Do not widen the gate without a separate experiment.

No Full-200 or holdout run was used. Runtime requests and diagnostics contain
no target ASIN, target rank, hit/miss, scenario label, or evaluator behavior.
The next B-side module is B10a Constraint-Preserving CrossEncoder Rerank.
