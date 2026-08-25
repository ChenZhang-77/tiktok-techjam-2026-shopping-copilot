# 02 — Add a parity Hybrid Retriever

**What to build:** Provide a standalone Hybrid Retriever that accepts the shared
Retrieval Request and returns catalog-valid ordered Candidates with provenance
and diagnostics while reproducing the current catalog, BM25, and local
constraint-ranking behavior.

**Blocked by:** 01 — Lock the A-side baseline and Development Set protocol.

**Status:** ready-for-agent

- [ ] The retriever loads exactly 50,000 unique catalog products without mutation.
- [ ] Product evidence preserves the current field order and BM25 field weighting.
- [ ] Empty queries, duplicate ASINs, and invalid requests have deterministic behavior.
- [ ] Candidate ordering matches the current embedded retrieval path for representative Buying and Browsing requests.
- [ ] Candidate Provenance and Retrieval Diagnostics contain no target or evaluator-only information.
- [ ] Initialization and query latency are measurable without changing candidate order.

## Comments

