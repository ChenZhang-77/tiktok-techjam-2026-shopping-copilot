# 07 — Rank bounded Candidate Pools

**What to build:** Improve final ordering with constraint-aware evidence and one
reproducible semantic-reranking experiment over a bounded Candidate Pool, with
the pre-rerank order as the deterministic fallback.

**Blocked by:** 06 — Fuse Retrieval Routes with Candidate Provenance.

**Status:** ready-for-agent

- [ ] Hard and soft constraints remain distinct and current explicit intent dominates profile evidence.
- [ ] Ranking does not double-count equivalent evidence without measurement.
- [ ] Semantic reranking is bounded and never scans the full catalog online.
- [ ] Reranker failure preserves the pre-rerank Candidate order.
- [ ] MRR, HitRate@10, latency, and scenario tradeoffs are compared through fixed Development Set cross-validation.
- [ ] Negative semantic results are documented and dead complexity is removed.

## Comments

