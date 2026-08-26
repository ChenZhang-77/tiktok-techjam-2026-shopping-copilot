# 06 — Fuse Retrieval Routes with Candidate Provenance

**What to build:** Combine available lexical, structured, and retained semantic
Routes into one deterministic Candidate Pool while preserving each Route's rank
evidence and tolerating unavailable Routes.

**Blocked by:** 04 — Add structured evidence and safe relaxation; 05 — Benchmark a reproducible dense Route.

**Status:** complete

- [x] Fusion parameters are centralized configuration rather than scattered constants.
- [x] Candidates are deduplicated by catalog-valid parent ASIN with stable tie-breaking.
- [x] Candidate Provenance preserves every contributing Route rank.
- [x] Missing or failed Routes produce a valid degraded result and diagnostic reason.
- [x] Single-route and unfused ablations are retained for comparison.
- [x] Fixed Development Set cross-validation supports the retained fusion method.

## Comments

- B4 keeps Developer A's `Strategy` route-weight semantics unchanged. Fusion
  consumes `lexical_weight`, `structured_weight`, and `semantic_weight`; B4
  centralizes only the RRF constant, route availability, and deterministic
  tie-breaking mechanics.
- Final comparison reports were produced from clean commit `2fec159`. All 25
  fusion/structured/lexical/dense Development reports use that same revision;
  their hashes and derived summaries are bound in `docs/b4_fusion_cv.json`.
- `RRF_K=10` was stronger than `60`, but development 160 reached only
  HitRate@10 `0.75`, MRR `0.48662`, and TechnicalScore `0.637611`. It lost
  TechnicalScore on three of four fixed folds and trails retained structured
  retrieval by `0.015611` on the fold mean. Fusion remains an optional ablation;
  structured retrieval remains the runtime default.
- Fusion records per-route candidate counts, pairwise overlap, latency, and
  failure reasons. Missing routes degrade to available routes; complete route
  failure fills a bounded catalog fallback pool for Developer A.
- Dense configuration records the exact model/revision, 384-dimensional float32
  cache, compatibility status, `77501054` cache bytes, and `255.086887s` build.
  The retained K=10 run had p50/p95 retrieval latency of `36.578959ms` /
  `90.104333ms`; the fusion stage mean was `0.233717ms`.
- Holdout and full were not run during B4.
