# AB1 Shared Contract and Active-Route Semantics Evidence

## Decision

Retain AB1 at clean code commit `e992b89`. It appends truthful requested,
executed, and fallback Route observations to `RetrievalDiagnostics` while
preserving the existing `RetrievalRequest`, single distilled `query`, Strategy
weights, dialogue policy, and `HybridRetriever.retrieve` seam.

## Frozen semantics

- `requested_route_weights` is either the legacy empty object or maps exactly
  `lexical`, `structured`, and `dense` to finite requested weights in `[0, 1]`.
  `Strategy.semantic_weight` maps to the B-owned `dense` Route name.
- `executed_routes` is an ordered unique list of stages that actually ran from
  the closed inventory: `lexical`, `structured`, `dense`, `fusion`,
  `semantic_rerank`, and `catalog_fallback`.
- `fallback_route` is `null` when a reported execution did not fall back.
  Otherwise it must be a frozen execution name, `fallback_used` must be true,
  and that Route must appear in `executed_routes`.
- A successful downstream stage such as `semantic_rerank` preserves any
  upstream fallback route and failure evidence.
- `{}` plus `[]` means a legacy producer did not report AB1 semantics. In that
  case, `fallback_route=null` is unavailable evidence, not proof of success.
- The fields are appended with `{}`, `[]`, and `null` defaults, so the original
  positional `RetrievalDiagnostics` signature remains compatible.

The default Browsing Strategy may request a non-zero dense weight. The retained
Hybrid retriever still executes only lexical and structured Routes; AB1 makes
that distinction visible instead of activating dense retrieval.

## Development-160 parity

| Metric | A11 baseline | AB1 | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.862500 | 0.862500 | 0 |
| MRR | 0.545568 | 0.545568 | 0 |
| MTTC | 4.675000 | 4.675000 | 0 |
| Efficiency | 0.632500 | 0.632500 | 0 |
| Technical score | 0.721420 | 0.721420 | 0 |

All 160 session outcomes, all scenario metrics, and all four fixed-fold reports
match A11 exactly. There were zero response exceptions, invalid payloads, or
fallbacks. No Full-200 or holdout evaluation was run.

## Route execution observation

Across 726 retrieval responses:

| Route | Requested | Executed | Requested but not executed |
| --- | ---: | ---: | ---: |
| lexical | 726 | 726 | 0 |
| structured | 726 | 726 | 0 |
| dense | 475 | 0 | 475 |

All 726 responses reported AB1 semantics. This is the expected retained-default
behavior and is not evidence of active dense retrieval.

## Compatibility and ownership

- Shared request schema: unchanged.
- SessionState crosses the A/B seam: no.
- Query components cross independently: no.
- Strategy weight meaning: unchanged.
- Question policy: unchanged.
- B owns Route execution and fallback reporting; A continues to own whether to
  ask and when Strategy changes.
- Runtime diagnostics contain no target ASIN, target rank, hit/miss, scenario
  label, or other evaluator-only data.

Machine-checkable evidence is in `docs/ab1_route_semantics_evidence.json` and
`docs/ab1_reports/`. The next dependency-ordered module is B8
Rejected-Constraint Ranking.
