# 02 — Add a parity Hybrid Retriever

**What to build:** Provide a standalone Hybrid Retriever that accepts the shared
Retrieval Request and returns catalog-valid ordered Candidates with provenance
and diagnostics while reproducing the current catalog, BM25, and local
constraint-ranking behavior.

**Blocked by:** 01 — Lock the A-side baseline and Development Set protocol.

Status: completed

- [x] The retriever loads exactly 50,000 unique catalog products without mutation.
- [x] Product evidence preserves the current field order and BM25 field weighting.
- [x] Empty queries, duplicate ASINs, and invalid requests have deterministic behavior.
- [x] Candidate ordering matches the current embedded retrieval path for representative Buying and Browsing requests.
- [x] Candidate Provenance and Retrieval Diagnostics contain no target or evaluator-only information.
- [x] Initialization and query latency are measurable without changing candidate order.

## Comments

- Added the standalone `HybridRetriever.retrieve(RetrievalRequest) -> RetrievalResult`
  seam without changing the Agent runtime path.
- Locked literal Buying, Browsing, field-weight, and equal-score catalog-order
  goldens captured from the embedded baseline before B1b integration.
- Loaded 50,000 unique products read-only; a local sample measured about 1012 ms
  initialization and 15.2 ms query latency on the current machine.
- Bounded retrieval depth at 500 candidates and reject malformed requests,
  duplicate ASINs, and evaluator-only fields recursively.
- Verified 71 standard-library tests and passed Standards/Spec review with no
  actionable findings. The Agent and official evaluator remain unchanged.
