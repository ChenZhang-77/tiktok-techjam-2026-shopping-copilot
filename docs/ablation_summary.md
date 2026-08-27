# Shopping Copilot - Ablation and Architecture Decisions

## Purpose

This is the human-readable decision summary for the verified retrieval/ranking
experiments. The checked-in JSON artifacts remain the numerical evidence. Do
not edit this document as a substitute for producing a new bound experiment
record.

## Baseline to Retained Runtime

Development-160 results:

| Variant | HitRate@10 | MRR | MTTC | TechnicalScore | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Official weak BM25 | 0.12500 | 0.068034 | 9.81000 | 0.106710 | Comparison only |
| Pure lexical | 0.71875 | 0.485851 | 5.40625 | 0.617005 | Reject as default |
| Constraint rank, no guarded filter | 0.76250 | 0.522693 | 5.31875 | 0.651683 | Ablation base |
| Retained structured path | 0.76250 | 0.526989 | 5.30625 | 0.653222 | Retain |
| Dense only | 0.33750 | 0.160501 | 8.21250 | 0.272650 | Reject as default |
| Weighted RRF, k=10 | 0.75000 | 0.486620 | 5.16875 | 0.637611 | Reject as default |
| Semantic rerank, Top 30 | 0.78125 | 0.484162 | 4.96875 | 0.656499 | Reject globally; retain experiment |
| A11 broad extraction candidate | 0.72500 | 0.479085 | 5.61250 | 0.613976 | Reject |
| A11 bounded extraction scope | 0.86250 | 0.545568 | 4.67500 | 0.721420 | Retain |
| AB1 route-execution semantics | 0.86250 | 0.545568 | 4.67500 | 0.721420 | Retain parity/observability |
| B8 rejected-constraint candidate | 0.86250 | 0.545568 | 4.67500 | 0.721420 | Revert; zero Development activation |
| B9 broad-Browsing conditional dense | 0.86250 | 0.547329 | 4.66875 | 0.722074 | Retain conditionally |

The current retained runtime combines bounded A11 extraction, AB1 route
diagnostics, and B9 local dense/RRF behind a narrow broad-Browsing gate. A11
passed all four fixed folds, AB1 preserved parity, and B9 was non-regressing on
all four folds.

## Why Bounded A11 Extraction Was Retained

Catalog-derived multi-word categories, clause/list-scoped positive/negative/
no-preference evidence, numeric/hyphen disambiguation, and injected catalog
path consistency gained 19 Development sessions and lost three. All four
fixed-fold technical scores improved.

The combined broad candidate was rejected during ablation. Its catalog feature,
feature-expiry, brand, and QueryPlan residual-cleanup components do not have
independent hash-bound reports, so their individual effects remain unproven.
Boundary technical score fell by `0.057083`, so the retained decision is strong
but not scenario-uniform. Evidence:
`docs/a11_extraction_scope_evidence.md`.

## Why AB1 Route Semantics Were Retained

AB1 preserves every Development metric, scenario, session outcome, and fixed
fold while separating requested Route weights from Routes that actually ran.
Across 726 retrievals, dense was requested 475 times and executed zero times by
the retained Hybrid path. This closes a truthfulness/diagnostics blocker without
claiming a ranking gain or active dense coverage. Evidence:
`docs/ab1_route_semantics_evidence.md`.

## Why B8 Rejected-Constraint Ranking Was Not Retained

The candidate used exact catalog evidence, a `0.80` confidence threshold, and
a capped `0.18` soft penalty. It passed deterministic behavior tests, including
neutral missing metadata, positive-overrides-rejection, and no-preference.
However, Development-160 contained zero rejected constraints across 726 turns.
Every metric, session, scenario, and fold therefore matched AB1 without
exercising the code. This failed the documented intended-bucket keep gate and
the candidate was reverted. Evidence:
`docs/b8_rejected_constraint_evidence.md`.

## Why B9 Conditional Dense Was Retained

B9 uses typed Browsing intent, positive Strategy dense weight, no more than one
active constraint, and a structured pool of at least 30 products. It ran dense
and weighted RRF on 102 of 725 Development retrieval turns. Buying, Intent
Override, and Boundary matched AB1 exactly; Browsing TechnicalScore improved by
`0.001633`, and no fold regressed.

The aggregate gain is deliberately described as small: HitRate@10 is unchanged,
MRR rises by `0.001761`, MTTC improves by `0.00625`, and no hit is gained or
lost. Startup warmup keeps dense p95 near `5.03 ms`, but initialization rises by
about `1.5 s` and observed peak RSS by about `546 MB`. The route is retained for
narrow Track 4 Browsing coverage and exact fallback, not as evidence for global
dense enablement. Evidence: `docs/b9_conditional_dense_evidence.md`.

## Why Structured Was Retained

The retained path adds cross-field hard/soft constraint ranking and guarded
filtering on top of the field-weighted lexical Candidate Pool.

Guarded filtering improved MRR from 0.522693 to 0.526989 without changing
HitRate@10, while retaining deterministic relaxation and fill when evidence is
sparse. This is a small numerical gain but an important robustness improvement:
hard constraints affect order without allowing sparse catalog fields to empty
the Top 10.

Evidence:

- `docs/b2_structured_cv.json`
- `docs/b7_pre_freeze_development.json`

## Why Dense-Only Was Rejected

The pinned `sentence-transformers/all-MiniLM-L6-v2` route was reproducible and
safe, but the product/query text representation did not preserve enough exact
catalog evidence. Dense-only HitRate@10 fell to 0.3375 and MRR to 0.160501.

The useful result is not "dense is bad." The evidence says this dense route is
not a safe global default for the provided catalog and simulator. It remains a
candidate for conditional recall only when offline failure analysis shows that
lexical/structured recall is the limiting factor.

Evidence: `docs/b3_dense_benchmark.json`.

## Why Weighted RRF Was Rejected

RRF successfully combined lexical, structured, and dense ranks and supplied
route provenance and fallbacks. The best tested constant, k=10, still trailed
the structured route by 0.015611 TechnicalScore on the fold mean and lost on
three of four folds.

Scenario evidence suggested a small Buying gain but Boundary, Browsing, and
Intent Override regression. Global fusion therefore added complexity without
robust value.

Evidence: `docs/b4_fusion_cv.json`.

## Why Semantic Reranking Was Not Enabled Globally

The pinned Top-30 CrossEncoder experiment produced a mixed result:

- HitRate@10: +0.01875.
- MRR: -0.042827.
- MTTC: improved by 0.3375 turns.
- TechnicalScore: +0.003277.
- Fold wins/losses: 2/2.
- Intent Override TechnicalScore: -0.102321.
- Added semantic latency: about 70.59 ms per retrieval.
- Historical in-process peak RSS: about 1.30 GB.

It gained ten sessions and lost seven. A global replacement would therefore
trade ranking quality, Intent Override safety, and operational cost for an
unstable aggregate improvement.

The next defensible semantic experiment is the B10a conditional,
constraint-preserving CrossEncoder:

- structured Top 3 anchored,
- positions 4-30 reranked,
- semantic score cannot override hard constraints,
- exact pre-rerank fallback.

Evidence: `docs/b5_semantic_rerank_cv.json`.

B9 now covers dense retrieval for its narrow broad-Browsing bucket. A
CrossEncoder remains a learned reranker rather than an LLM, and an actual LLM
ranker remains an explicit Track 4 gap. The same rule applies to profile
ranking, which remains disabled at weight 0.0.

## Runtime Cost and Reliability

Current B9 Development-160 evidence:

| Measure | Value |
| --- | ---: |
| Initialization | 3579.492208 ms |
| Mean retrieval latency | 21.733536 ms |
| p95 retrieval latency | 40.439958 ms |
| Max retrieval latency | 57.354458 ms |
| Dense mean / p95 latency | 4.701189 / 5.028500 ms |
| Peak RSS | 1109049344 bytes |
| Prompt/completion tokens | 0 / 0 |
| Response exceptions | 0 |
| Invalid payloads | 0 |
| Reported fallbacks | 0 |

Dense-cache corruption, missing routes, invalid semantic scores, backend
errors, and reranker timeouts have deterministic fallback tests. A timed-out
semantic worker is terminated and joined rather than left running.

## Honest Architecture Claim

Use this claim:

> We retain deterministic structured retrieval for every request and add pinned
> local dense/RRF only for a measured broad-Browsing bucket. Global dense and
> CrossEncoder variants were rejected; every optional failure returns the exact
> structured order.

Do not claim:

> The default Agent dynamically combines BM25, dense retrieval, RRF, and an LLM
> reranker on every turn.

## Protocol Limitation

The historical Full-200 result is not sealed evidence because the public
holdout was already exposed. Later work must use Development-160 fixed folds;
the organizer's private 800 sessions are the remaining external test.
