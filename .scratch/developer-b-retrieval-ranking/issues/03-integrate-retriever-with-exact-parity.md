# 03 — Integrate the Retrieval / Ranking Plane with exact parity

**What to build:** Route the Shopping Agent through the shared Hybrid Retriever
seam so the Control Plane no longer owns catalog indexing or BM25 mechanics,
while preserving customer-visible responses, clarification inputs, fallbacks,
and Development Set metrics.

**Blocked by:** 02 — Add a parity Hybrid Retriever.

**Status:** in-progress

- [ ] Agent responses satisfy the existing contract and smoke tests through the new seam.
- [ ] The legacy embedded retrieval path is removed only after all callers migrate.
- [ ] The complete test suite remains green.
- [ ] Development Set HitRate@10, MRR, MTTC, Efficiency, TechnicalScore, and scenario metrics exactly match ticket 01.
- [ ] Retrieval failure reaches a deterministic catalog-valid fallback without leaking an exception.

## Comments
