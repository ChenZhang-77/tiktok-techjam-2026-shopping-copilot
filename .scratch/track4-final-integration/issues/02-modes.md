# 02 — Run one Agent in offline or bounded LLM-enhanced configuration

**What to build:** Same official interface, preserved offline behavior, exact F2
conditional reranking with truthful usage/fallback and bounded fake-provider tests.
**Blocked by:** 01 — Freeze delivery scope and baseline.
**Status:** completed

- [x] Offline does not call a provider, even if a key exists.
- [x] Enhancement preserves F2 eligibility, constraints and Top-10 membership.
- [x] Missing key, invalid response, provider error and exhausted limits fall back.
- [x] Diagnostics distinguish skip, success, fallback and actual token usage.
- [x] No runtime import from experiments, no evaluator data, tests and dual review pass.

314 full tests; 12 delivery tests. Both reviewers found the same P2 malformed-provider
exception gap; aa5df4e fixes it and both re-reviews pass. No paid verification.
