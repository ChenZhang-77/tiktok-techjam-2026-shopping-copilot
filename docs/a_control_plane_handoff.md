# A Control Plane Handoff

## Branch And Commit

- Branch: `dev/chenzhang-77-baseline-setup`
- Latest pushed baseline before this handoff: `744913c`
- Current handoff changes add diagnostics and shared contracts only.

## Completed A-Side Scope

- `SessionState` tracks per-session history, intent, active constraints, overridden constraints, rejected constraints, no-preference attributes, asked attributes, previous query, previous candidates, strategy, diagnostics, and override events.
- Context extraction handles category, material, color, size, style, brand, budget, feature, and use_case.
- Intent Override v2 deactivates stale attributes, resets category-level product context, clears previous candidate continuity, and records override events.
- Boundary / no-preference handling records ignored attributes and rejected values such as `except black` or `avoid leather`.
- Buying / Browsing routing produces a Strategy that changes retrieval depth and weights.
- Clarification is candidate-aware, avoids repeated and no-preference attributes, and returns recommendations with a question.
- Response Guard validates messages, ask attributes, recommendations, ASINs, duplicates, top_k, usage, and diagnostics.
- Diagnostics expose control-plane state for debugging and visualization.

## Shared Contract For B

Defined in `starter/contracts.py`:

- `RetrievalRequest`
- `Candidate`
- `RetrievalDiagnostics`
- `RetrievalResult`
- `validate_retrieval_request`

The intended B entry point is:

```text
HybridRetriever.retrieve(request: RetrievalRequest) -> RetrievalResult
```

or, if reranking is split:

```text
HybridRetriever.retrieve(request) -> RetrievalResult
Reranker.rank(request, candidates) -> RetrievalResult
```

## Data A Sends To B

A may send:

- `session_id`
- `turn`
- `top_k`
- distilled query
- Buying/Browsing intent
- Strategy
- active constraints
- no-preference attributes
- rejected constraints
- asked attributes

A must not send evaluator-only labels:

- `ground_truth`
- `target`
- `target_asin`
- `target_parent_asin`
- `scenario_type`
- `difficulty_bucket`
- `intent_card`
- `behavior`

This is covered by `tests/test_contracts.py`.

## Current Metrics

Latest validated A version:

```text
development
HitRate@10:      0.7625
TechnicalScore:  0.651683

full
HitRate@10:      0.765
TechnicalScore:  0.648726
```

## Tests

Latest local test gate:

```text
40 passed
```

## Current B Integration Status

B is not integrated yet.

The current runtime still uses the local baseline retrieval/ranking path. The shared contract is prepared so B can replace that path later without changing A's state, planning, clarification, or guard logic.

## Known Risks

- Current retrieval/ranking includes a local constraint-aware reranker that is already in the branch, but full B retrieval/fusion/reranking is not implemented here.
- The public evaluator is simulator-driven, so A policy changes should be validated on development and checked against full/holdout before finalizing.
- Diagnostics are for debugging and should not be treated as official submission output requirements.

## Next Step

Wait for B's retrieval/ranking interface, then adapt `starter/agent.py` to build a `RetrievalRequest`, call B's retriever, consume `RetrievalResult`, and preserve the existing response guard and state recording.
