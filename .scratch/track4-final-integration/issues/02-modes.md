# 02 — Run one Agent in offline or bounded LLM-enhanced configuration

**What to build:** Same official interface, preserved offline behavior, exact F2
conditional reranking with truthful usage/fallback and bounded fake-provider tests.
**Blocked by:** 01 — Freeze delivery scope and baseline.
**Status:** ready-for-agent

- [ ] Offline does not call a provider, even if a key exists.
- [ ] Enhancement preserves F2 eligibility, constraints and Top-10 membership.
- [ ] Missing key, invalid response, provider error and exhausted limits fall back.
- [ ] Diagnostics distinguish skip, success, fallback and actual token usage.
- [ ] No runtime import from experiments, no evaluator data, tests and dual review pass.
