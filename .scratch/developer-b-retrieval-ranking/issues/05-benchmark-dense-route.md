# 05 — Benchmark a reproducible dense Route

**What to build:** Add one bounded local semantic-retrieval experiment with a
catalog-compatible cache and lexical fallback, then retain or reject it from
fixed Development Set cross-validation evidence.

**Blocked by:** 03 — Integrate the Retrieval / Ranking Plane with exact parity.

**Status:** in-progress

- [ ] Product/query text templates and model revision are recorded.
- [ ] Cache metadata verifies catalog checksum, dimensions, dtype, normalization, and model identity.
- [ ] Missing, incompatible, or corrupt cache state reaches deterministic lexical fallback.
- [ ] Build time, query latency, memory estimate, and cache size are recorded.
- [ ] No hosted vector database or per-evaluation embedding rebuild is required.
- [ ] The keep/reject decision is supported by fixed Development Set cross-validation.

## Comments

- Selected `sentence-transformers/all-MiniLM-L6-v2` at revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` for the bounded local benchmark. Package version is `sentence-transformers==5.7.0`; generated model/cache files remain ignored.
