# 06 — Fuse Retrieval Routes with Candidate Provenance

**What to build:** Combine available lexical, structured, and retained semantic
Routes into one deterministic Candidate Pool while preserving each Route's rank
evidence and tolerating unavailable Routes.

**Blocked by:** 04 — Add structured evidence and safe relaxation; 05 — Benchmark a reproducible dense Route.

**Status:** in-progress

- [ ] Fusion parameters are centralized configuration rather than scattered constants.
- [ ] Candidates are deduplicated by catalog-valid parent ASIN with stable tie-breaking.
- [ ] Candidate Provenance preserves every contributing Route rank.
- [ ] Missing or failed Routes produce a valid degraded result and diagnostic reason.
- [ ] Single-route and unfused ablations are retained for comparison.
- [ ] Fixed Development Set cross-validation supports the retained fusion method.

## Comments

- B4 keeps Developer A's `Strategy` route-weight semantics unchanged. Fusion
  consumes `lexical_weight`, `structured_weight`, and `semantic_weight`; B4
  centralizes only the RRF constant, route availability, and deterministic
  tie-breaking mechanics.
