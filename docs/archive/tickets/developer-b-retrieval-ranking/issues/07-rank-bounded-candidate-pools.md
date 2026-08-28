# 07 — Rank bounded Candidate Pools

**What to build:** Improve final ordering with constraint-aware evidence and one
reproducible semantic-reranking experiment over a bounded Candidate Pool, with
the pre-rerank order as the deterministic fallback.

**Blocked by:** 06 — Fuse Retrieval Routes with Candidate Provenance.

Status: complete

- [x] Hard and soft constraints remain distinct and current explicit intent dominates profile evidence.
- [x] Ranking does not double-count equivalent evidence without measurement.
- [x] Semantic reranking is bounded and never scans the full catalog online.
- [x] Reranker failure preserves the pre-rerank Candidate order.
- [x] MRR, HitRate@10, latency, and scenario tradeoffs are compared through fixed Development Set cross-validation.
- [x] Negative semantic results are documented and dead complexity is removed.

## Comments

- 2026-08-26: B5 resumed from clean commit `eb42795`. The experiment is fixed to
  the retained structured Candidate Pool followed by a local top-30 semantic
  reranker; the pre-rerank order is the failure fallback. Equivalent explicit
  constraints are being deduplicated before scoring, with hard evidence taking
  precedence over an equivalent soft duplicate.
- 2026-08-26: Clean revision `70876a5` produced Development-160
  HitRate@10/MRR/TechnicalScore `0.78125/0.484162/0.656499`. Relative to the
  retained structured path this is `+0.01875/-0.042827/+0.003277`, with two
  fold wins and two fold losses and an intent-override score regression of
  `-0.102321`. The reranker adds about `70.59 ms` mean retrieval latency and a
  large model-memory/cache cost, so it is rejected as the runtime default and
  retained only as one reproducible optional ablation/failure fixture. B5 did
  not run Holdout or Full.
