# 03 — Integrate the Retrieval / Ranking Plane with exact parity

**What to build:** Route the Shopping Agent through the shared Hybrid Retriever
seam so the Control Plane no longer owns catalog indexing or BM25 mechanics,
while preserving customer-visible responses, clarification inputs, fallbacks,
and Development Set metrics.

**Blocked by:** 02 — Add a parity Hybrid Retriever.

**Status:** completed

- [x] Agent responses satisfy the existing contract and smoke tests through the new seam.
- [x] The legacy embedded retrieval path is removed only after all callers migrate.
- [x] The complete test suite remains green.
- [x] Development Set HitRate@10, MRR, MTTC, Efficiency, TechnicalScore, and scenario metrics exactly match ticket 01.
- [x] Retrieval failure reaches a deterministic catalog-valid fallback without leaking an exception.

## Comments

- Agent now builds `RetrievalRequest`, consumes `RetrievalResult`, and keeps
  Control Plane state, clarification, and Response Guard ownership unchanged.
- Removed SQLite, FTS5, BM25, and product-text indexing mechanics from Agent.
- Response Guard catalog fill and retriever failures both produce truthful,
  catalog-valid fallback diagnostics without leaking exception text.
- `docs/b1_development_parity_report.json` exactly matches B0 for all overall
  metrics, all four scenario metric groups, and all 160 session outcomes.
- Recorded zero respond exceptions, invalid payloads, reported fallbacks, and
  internal retrieval fallbacks on the Development Set; holdout/full were not run.
- Verified 79 standard-library tests and passed final Standards/Spec review with
  no actionable findings.
