# 08 — Harden Control Plane integration

**What to build:** Deliver inspectable retrieval evidence and predictable degraded
behavior to the Control Plane so adaptive strategy and clarification can use the
real Candidate Pool without depending on retrieval internals.

**Blocked by:** 07 — Rank bounded Candidate Pools.

Status: complete

- [x] Retrieval Diagnostics cover route sizes, overlap, filtering, relaxation, fallbacks, cache state, and stage latency.
- [x] Buying and Browsing Strategies produce measurably different retrieval execution.
- [x] Candidate-aware clarification receives evidence from the integrated Candidate Pool.
- [x] Dense, cache, fusion, ranking, and expensive-stage failure fixtures reach deterministic fallbacks.
- [x] End-to-end latency, initialization time, memory, cache size, and fallback counts are recorded.
- [x] No diagnostic field contains target, scenario, intent-card, behavior, or ground-truth data.

## Comments

- 2026-08-26: B6 started after rejecting semantic reranking as the runtime
  default. The retained structured path is being instrumented at the shared
  `Retriever.retrieve` seam with route/pool sizes, overlap, filter/relaxation,
  cache state, fallback reasons, and per-stage latency. Agent integration tests
  exercise distinct Buying/Browsing plans and compare candidate-aware
  clarification with and without Candidate Pool evidence.
- 2026-08-26: Clean revision `f19a57d` preserved Development-160 metrics at
  `0.7625/0.526989/0.653222` (HitRate@10/MRR/TechnicalScore), with zero runtime
  fallbacks or invalid responses. The report records 811 route observations,
  172 guarded-filter responses, two relaxation responses, cache readiness,
  `36.434035 ms` mean retrieval latency, `1244.555333 ms` initialization, and
  `573702144` peak RSS bytes. Six deterministic degraded-path fixtures and a
  recursive diagnostic leakage test pass. B6 did not run Holdout or Full.
