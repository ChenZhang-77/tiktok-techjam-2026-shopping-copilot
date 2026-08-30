# A13-AS0 Offline Tooling Evidence

## Decision

**Keep the offline core contracts. A13-AS0 is not yet fully frozen and AS1F
must not start.**

The AS0T core-contract slice creates the source-neutral `applied_state_delta_v1`
projection, fresh-fixture and contamination preflight, automated-role
independence preflight, blind consensus, and fixed-denominator semantic gate.
It also freezes the first Candidate trigger and request configuration. It does
not create a fresh fixture, choose the independent reference-builder models,
call a provider, apply an LLM delta to runtime, or authorize A13-C1. AS0R exact
roles and AS0X execution runner/repair/provenance remain pending; this is not a
claim that the complete offline execution toolchain is ready.

## Frozen Candidate slice

The first Candidate trigger is `low_confidence_residual_feature`. This choice is
based on the existing target-free A13-S0 Shadow audit: all 67 eligible
Development turns were in this trigger. It is not selected from the exposed
legacy annotations or valid-34 scores.

The frozen Candidate request uses `deepseek-v4-flash`, expected model version
`DeepSeek-V4-Flash-0731`, non-thinking JSON output, temperature `0`, a `2500 ms`
hard timeout, and at most 256 completion tokens. DeepSeek's official model list
and pricing page were checked on 2026-08-30; the requested model is currently
listed, while old `deepseek-chat`/`deepseek-reasoner` aliases are deprecated.
Recheck the official model/version and pricing immediately before an authorized
run, and fail closed if the returned version differs from the frozen manifest:

- [DeepSeek models and pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [DeepSeek model list API](https://api-docs.deepseek.com/api/list-models/)

## Implemented offline seams

- All deterministic, Candidate, and AI-silver proposals use the same
  `apply_understanding_delta` function and production
  `SessionState.apply_user_context` semantics.
- Canonical ordering and JSON serialization make equivalent proposal ordering
  compare identically.
- Fresh fixtures require at least 60 items, at least 10 per reachable trigger,
  and at least 20 in the Candidate trigger.
- Legacy exact/lexical near-duplicates, semantic duplicate findings, forbidden
  target/evaluator keys, missing semantic-audit coverage, and unbalanced
  fixtures fail before scoring. The legacy collection must match its frozen
  60-item count and canonical content hash.
- Judge input contains only a run-salted opaque ID, prior state, and current
  message; private IDs, trigger/source fields are stripped.
- J1/J2/J3 must use three distinct model/version identities and three distinct
  families outside the Candidate family. The single adjudicator is stricter
  than the earlier majority-only wording: its family must differ from the
  Candidate and all three labeler families so a proxy Candidate cannot
  adjudicate and every possible 2/3 majority is safe. A separate semantic
  duplicate auditor is also preflighted. Every role's declared prompt/config
  hashes are compared with actual prompt files and canonical policy config
  objects; preflight also binds the manifest and comparator/validator/state code.
- `3/3` is unanimous; `2/3` remains pending until a matching blind adjudication;
  three-way disagreement, invalid adjudication, or adjudicator mismatch remains
  unresolved.
- Coverage, model exact agreement, semantic delta, net exact items, and repeat
  stability all use the complete frozen per-trigger denominator. Invalid and
  unresolved items never disappear from it. Scoring requires the complete
  frozen ID-to-trigger inventory and carries its fixture hash into the report;
  missing rows, relabeled triggers, or incomplete trigger inventories fail.

## Verification

The retained tests use synthetic items and labels only. They do not encode
expected labels for the exposed legacy 60 rows.

```text
tests.test_a13_ai_silver: 27 passed
tests.test_a13_as0_tooling_evidence: 2 passed
full suite: 409 passed
provider calls: 0
Full/Holdout runs: 0
```

The machine-readable evidence binds every contract/prompt/schema hash and both
implementation/test hashes in
[`a13_as0_offline_tooling_evidence.json`](a13_as0_offline_tooling_evidence.json).

## Remaining blocker

AS0R has prepared `role_manifest.pending.json`: the frozen Candidate identity
and all actual prompt/config hashes are filled. Its six independent reference
identities remain placeholders, and preflight correctly stops at
`invalid generator provider`. The generic template is also intentionally
invalid. Before AS1F, the team must freeze exact identities for:

1. one non-Candidate fresh-item generator;
2. one non-Candidate semantic duplicate auditor;
3. J1/J2/J3 from three distinct non-Candidate model families;
4. one adjudicator whose family differs from the Candidate and every labeler.

AS0X must then implement and test the isolated one-repair workflow, raw
request/response provenance, input/output hashes, raw-outside-Git storage, and
normalized summary runner. Only after both role and runner gates pass may the
coordinator give separate explicit authorization for reference-builder calls.
Until then:

```text
role_manifest_frozen = false
execution_runner_ready = false
fresh_fixture_frozen = false
ai_silver_frozen = false
reference_builder_provider_authorized = false
candidate_provider_authorized = false
A13_C1_authorized = false
```
