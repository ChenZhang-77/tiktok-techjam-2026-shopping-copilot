# B8 Rejected-Constraint Ranking Evidence

## Decision

Do not retain B8 in the default runtime. The bounded candidate was implemented
and tested at clean commit `f53a7ee`, then reverted at `3952788` because the
fixed Development-160 evaluator never supplied a rejected constraint. This is
a coverage failure, not a ranking regression or a successful optimization.

## Candidate behavior

The single tested variable was a soft negative ranking signal:

- only an exact catalog-text match could count as negative product evidence;
- rejection confidence had to be at least `0.80`;
- the total penalty was capped at `0.18` and never hard-filtered a product;
- missing product evidence and lower-confidence rejections were neutral;
- a current active preference for the same attribute/value suppressed an older
  rejection;
- `no_preference_attributes` suppressed both positive and negative influence;
- Candidate diagnostics exposed the total penalty and matched
  attribute/value/confidence evidence.

Focused tests passed `86/86`; the candidate full suite passed `243/243`.

## Development-160 result

| Metric | AB1 baseline | B8 candidate | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.862500 | 0.862500 | 0 |
| MRR | 0.545568 | 0.545568 | 0 |
| MTTC | 4.675000 | 4.675000 | 0 |
| Efficiency | 0.632500 | 0.632500 | 0 |
| TechnicalScore | 0.721420 | 0.721420 | 0 |

All scenario metrics, all 160 session outcomes, and all four fixed folds are
also identical. The decisive observation is activation, not parity:

| Activation measure | Count |
| --- | ---: |
| Development sessions | 160 |
| Retrieval turns | 726 |
| Turns carrying any rejected constraint | 0 |
| Total observed rejected constraints | 0 |

The target-aware audit was Development-only and offline. Target ASIN, target
rank, hit/miss, scenario labels, and evaluator behavior never entered the
Agent, `RetrievalRequest`, ranking rule, or runtime diagnostics.

## Why parity did not pass the keep gate

The B8 gate requires improvement in rejection/override cases with fold-level
support and no material overall loss. With zero activation, the candidate had
no opportunity to change any result. Treating exact parity as proof would make
an untested hidden behavior part of the default runtime.

The candidate commit and hash-bound reports remain available for a future
evaluation set that contains real rejection turns. Do not tune it on Full-200
or the exposed 40-session holdout. The next dependency-ordered B-side module is
B9 Browsing-First Conditional Dense Route.
