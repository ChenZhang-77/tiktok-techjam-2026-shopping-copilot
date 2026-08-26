# 05 — Benchmark a reproducible dense Route

**What to build:** Add one bounded local semantic-retrieval experiment with a
catalog-compatible cache and lexical fallback, then retain or reject it from
fixed Development Set cross-validation evidence.

**Blocked by:** 03 — Integrate the Retrieval / Ranking Plane with exact parity.

**Status:** complete

- [x] Product/query text templates and model revision are recorded.
- [x] Cache metadata verifies catalog checksum, dimensions, dtype, normalization, and model identity.
- [x] Missing, incompatible, or corrupt cache state reaches deterministic lexical fallback.
- [x] Build time, query latency, memory estimate, and cache size are recorded.
- [x] No hosted vector database or per-evaluation embedding rebuild is required.
- [x] The keep/reject decision is supported by fixed Development Set cross-validation.

## Comments

- Selected `sentence-transformers/all-MiniLM-L6-v2` at revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` for the bounded local benchmark. Package version is `sentence-transformers==5.7.0`; generated model/cache files remain ignored.
- Final raw Development reports were produced from clean commit `bc1196d` and
  embed their own commit/clean provenance. Evidence and hashes are recorded in
  `docs/b3_dense_benchmark.json`; holdout and full were not run.
- Dense-only Development 160: HitRate@10 `0.3375`, MRR `0.160501`, MTTC
  `8.2125`, TechnicalScore `0.27265`. It is materially weaker than retained
  structured retrieval, but contributes four complementary hits across three
  fixed folds; retain only for the B4 fusion ablation, not as the default Route.
- One-time cache build was `255.086887s` for 50,000 x 384 float32 normalized
  vectors. Final warm p50 query latency was `4.711167ms`; peak process RSS was
  `1115045888` bytes. Missing-cache smoke degraded to structured/BM25 with 20
  valid candidates.
- Runtime validates catalog/model/template metadata, ID order, and ID/vector
  hashes. Missing, incompatible, malformed, hash-mismatched, truncated-vector,
  and query-time model failures have deterministic fallback coverage.
- Final suite: 107 standard-library tests passed. Final Standards and Spec
  remediation reviews reported no findings.
