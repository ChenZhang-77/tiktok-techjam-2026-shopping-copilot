# 09 — Freeze, review, and hand off the Retrieval / Ranking Plane

**What to build:** Freeze the simplest evidence-supported B configuration,
reproduce it from a clean start, review it against both repository standards and
the Track 4 specification, and provide a defensible integration handoff.

**Blocked by:** 08 — Harden Control Plane integration.

Status: complete

- [x] Retained features have overall and per-scenario ablations plus keep/reject decisions.
- [x] Setup, cache, evaluation, fallback, and clean-start commands are reproducible.
- [x] Tests and failure fixtures pass from the frozen configuration.
- [x] A Standards and Spec code review has no unresolved blocking findings.
- [x] One Final Public Run is recorded after freeze with the Exposed Holdout limitation disclosed and no subsequent tuning.
- [x] The handoff records branch, commit, metrics, latency, memory, cache, shared-contract changes, risks, and team contribution boundaries.

## Comments

- 2026-08-26: B7 started with `structured` frozen as the runtime default. The
  review fixed point is Developer A's last pre-B commit `2280bf7`, and the
  pre-freeze reviewed head is `316ffe5`. Holdout and Full remain untouched
  while Standards/Spec review, clean-cache reproduction, and the final test
  gate are completed.
- 2026-08-26: The final parallel review of code-behavior commit `5b66df5`
  reports zero hard Standards violations, zero Spec findings, and zero blockers.
  One non-blocking Repeated Switches judgment is deferred because experiment
  modes are frozen. The full 140-test suite, process-isolated reranker fold
  smoke, exact structured Development-160 parity, and six-file clean-cache
  reproduction pass. The separate Holdout was not run.
- 2026-08-26: Frozen commit `98d3325` passed all 144 tests from a clean worktree,
  then the single Full-200 Final Public Run completed with HitRate@10 `0.765`,
  MRR `0.517355`, MTTC `5.375`, and TechnicalScore `0.650207`. It reported zero
  exceptions, invalid responses, or fallbacks. No separate Holdout run or
  post-run tuning occurred. The non-confirmatory result and complete A/B
  ownership boundary are recorded in `docs/b_retrieval_ranking_handoff.md`.
