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

The retained runtime is the structured path because it provides the strongest
stable balance of recall, ranking, efficiency, latency, memory, and simplicity.

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

The next defensible semantic experiment is conditional and
constraint-preserving, after A-side intent is stabilized:

- broad or low-confidence Browsing first, matching the literal Track 4 route,
- stable Buying only as a separate evidence-supported hypothesis,
- disabled immediately after Intent Override,
- structured Top 3 anchored,
- positions 4-30 reranked,
- semantic score cannot override hard constraints,
- exact pre-rerank fallback.

Evidence: `docs/b5_semantic_rerank_cv.json`.

Until such a route passes its gate, Browsing-dense retrieval and semantic
ranking remain explicit Track 4 coverage gaps rather than retained-runtime
claims. The same rule applies to profile ranking, which remains disabled at
weight 0.0.

## Runtime Cost and Reliability

Historical retained Development-160 evidence:

| Measure | Value |
| --- | ---: |
| Initialization | 1252.970375 ms |
| Mean retrieval latency | 36.870219 ms |
| p50 retrieval latency | 32.505333 ms |
| p95 retrieval latency | 82.687167 ms |
| Peak RSS | 574144512 bytes |
| Prompt/completion tokens | 0 / 0 |
| Response exceptions | 0 |
| Invalid payloads | 0 |
| Reported fallbacks | 0 |

Dense-cache corruption, missing routes, invalid semantic scores, backend
errors, and reranker timeouts have deterministic fallback tests. A timed-out
semantic worker is terminated and joined rather than left running.

## Honest Architecture Claim

Use this claim:

> We built and measured lexical, structured, dense, fusion, and semantic
> ranking paths, then retained the deterministic structured path because it was
> the strongest robust default. Optional semantic paths remain reproducible and
> failure-safe, and future work targets conditional activation rather than
> global complexity.

Do not claim:

> The default Agent dynamically combines BM25, dense retrieval, RRF, and an LLM
> reranker on every turn.

## Protocol Limitation

The historical Full-200 result is not sealed evidence because the public
holdout was already exposed. Later work must use Development-160 fixed folds;
the organizer's private 800 sessions are the remaining external test.
