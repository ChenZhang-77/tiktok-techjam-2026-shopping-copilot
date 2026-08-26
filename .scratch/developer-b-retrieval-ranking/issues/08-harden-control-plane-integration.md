# 08 — Harden Control Plane integration

**What to build:** Deliver inspectable retrieval evidence and predictable degraded
behavior to the Control Plane so adaptive strategy and clarification can use the
real Candidate Pool without depending on retrieval internals.

**Blocked by:** 07 — Rank bounded Candidate Pools.

**Status:** in-progress

- [ ] Retrieval Diagnostics cover route sizes, overlap, filtering, relaxation, fallbacks, cache state, and stage latency.
- [ ] Buying and Browsing Strategies produce measurably different retrieval execution.
- [ ] Candidate-aware clarification receives evidence from the integrated Candidate Pool.
- [ ] Dense, cache, fusion, ranking, and expensive-stage failure fixtures reach deterministic fallbacks.
- [ ] End-to-end latency, initialization time, memory, cache size, and fallback counts are recorded.
- [ ] No diagnostic field contains target, scenario, intent-card, behavior, or ground-truth data.

## Comments

- 2026-08-26: B6 started after rejecting semantic reranking as the runtime
  default. The retained structured path is being instrumented at the shared
  `Retriever.retrieve` seam with route/pool sizes, overlap, filter/relaxation,
  cache state, fallback reasons, and per-stage latency. Agent integration tests
  exercise distinct Buying/Browsing plans and compare candidate-aware
  clarification with and without Candidate Pool evidence.
