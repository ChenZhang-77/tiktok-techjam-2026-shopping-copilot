# A13-LR0 — Deadline-limited AI review diagnostic

## Predeclared scope (2026-08-31)

The coordinator authorized a small DeepSeek review test, then clarified that
competition TechnicalScore is the highest priority with one day remaining.
This supersedes the mandatory multi-family reference-build dependency for the
remaining deadline: AS0/AS1/AS2 are deferred, not passed. LR0 cannot create
AI-silver, open A13-C1, or authorize online model behavior.

- Comparator: clean `a92d909`; production behavior is untouched.
- Twelve synthetic, explicit-language cases, with expected semantics fixed
  before provider output. No legacy annotations, Development targets, catalog
  IDs, scenario labels, evaluator internals, or future replies in prompts.
- Flash proposes an UnderstandingDelta; Pro receives the same case and the
  Flash draft and returns a corrected delta. Both use JSON, temperature 0,
  thinking disabled, and at most 512 output tokens. This intentionally tests
  a same-family editor, NOT independent judges or semantic accuracy on real users.
- Reuse production `validate_understanding_delta` and the already tested
  `apply_understanding_delta` seam. Compare applied effects to synthetic expected
  effects; raw schema validity is secondary. Intent is held unchanged.
- At most 24 requests, 20-second transport timeout, 10-minute run budget, no
  retries/model sweeps. Stop on transport failure. Conservative peak-price
  estimate must remain below $1. Credentials are read only from an explicitly
  provided local environment file or process environment and never recorded.
- Retain the editor for further investigation only if it corrects at least two
  Flash errors, introduces zero regressions, and completes all twelve pairs.
  Otherwise stop this review route for the deadline. Even a passing result is
  only a lead: no runtime retention without a separately measured score gain.
- Score priority: fixed Development-160 TechnicalScore and four-fold/scenario
  checks; no Full/Holdout, target-specific rules, or evaluator changes. AI
  agreement, nicer wording, and synthetic pass rate are not competition gains.

Expected files: this record, one isolated experiment module, focused tests, and
small current-status/navigation updates. Do not expand AS0X infrastructure.
After LR0 disposition, move to A14 deterministic selection Shadow, then test
one selection-only candidate if the evidence supports it. Preserve no-LLM
runtime and explicit legacy fallback; no shared contract change.

Official API references checked on 2026-08-31:
[models/prices](https://api-docs.deepseek.com/quick_start/pricing/) and
[thinking control](https://api-docs.deepseek.com/guides/thinking_mode/).
Flash version is advertised as DeepSeek-V4-Flash-0731 and Pro as
DeepSeek-V4-Pro-0813; response-reported model identity is retained separately.

## Result

Pending execution. Missing credentials or service failure are inconclusive,
not evidence that AI review is ineffective.
