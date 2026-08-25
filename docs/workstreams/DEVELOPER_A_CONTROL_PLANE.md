# Developer A Workstream - Agent / Control Plane

## 1. How to use this document

This is the standalone workstream brief for Developer A or a new coding-agent
conversation taking over the Agent / Control Plane.

This is the current implementation-phase allocation, not a permanent statement
about team members. If ownership changes, update both workstream documents and
the shared handoff status together.

At the start of a new conversation:

1. confirm the current Git branch and working tree,
2. read AGENTS.md completely,
3. read this document,
4. read README.md, docs/competition_specification.md,
   docs/agent_api_contract.json, docs/evaluation_config.json, and
   starter/agent.py,
5. confirm the shared contracts with Developer B before changing them,
6. work on a feature/experiment branch, never directly on main,
7. do not push, merge, or open a PR unless the user explicitly asks.

AGENTS.md and the official participant kit override this document if they
conflict.

## 2. Mission

Developer A owns the user-dialogue side of the system:

    What did the user say?
      -> What do they currently mean?
      -> How should this turn search?
      -> What should the Agent ask next?
      -> Is the final response valid?

The goal is a deterministic, inspectable Control Plane that maintains current
intent, produces a useful retrieval request for Developer B's plane, and safely
orchestrates the public Agent API.

Developer A optimizes primarily for:

- correct multi-turn state,
- Intent Override behavior,
- Boundary / no-preference behavior,
- useful proactive clarification,
- lower MTTC / higher Efficiency,
- reliable orchestration and fallbacks.

## 3. Primary ownership

### 3.1 SessionState

Maintain one isolated state per session_id.

State must cover:

- current turn,
- raw history for audit,
- current Buying/Browsing intent,
- active constraints,
- overridden/rejected constraints,
- no-preference attributes,
- attributes already asked,
- user_profile as a weak prior,
- previous distilled query,
- previous candidate IDs,
- previous strategy and relevant diagnostics,
- whether an Intent Override has occurred.

Do not use raw full-history concatenation as the retrieval query.

Suggested helper behavior:

- return active constraints,
- find constraints by attribute,
- deactivate conflicting attributes,
- mark no-preference,
- check whether an attribute was already asked,
- record the previous strategy and candidate summary.

### 3.2 Context and constraint extraction

Extract or preserve:

- category,
- material,
- color,
- size,
- style,
- brand,
- budget,
- feature,
- use_case.

For each extracted value preserve:

- raw value,
- normalized value,
- source turn,
- source text,
- confidence,
- hard versus soft status,
- active/inactive status.

If classification is uncertain, preserve the raw phrase as soft feature
evidence. Do not discard potentially useful text.

Catalog price and explicit details keys are sparse. Do not turn uncertain
budget, material, color, brand, style, or size signals into broad hard filters.

### 3.3 Intent Override

When the user changes their mind:

1. identify the new constraint or phrase,
2. deactivate conflicting old values,
3. preserve old values for audit,
4. rebuild the distilled query from active state,
5. discard stale candidate continuity,
6. set an override event for planning and telemetry.

The query sent to retrieval must never contain both old and new conflicting
values.

### 3.4 Boundary and no preference

When a user says an attribute does not matter:

1. record the attribute in no-preference state,
2. deactivate a conflicting soft constraint when appropriate,
3. do not ask the same attribute again,
4. continue using the remaining evidence,
5. still return valid recommendations when candidates exist.

### 3.5 Buying / Browsing Router

Infer the route only from observable messages and state.

Buying evidence may include:

- concrete must-have constraints,
- explicit size, material, color, brand, or budget,
- several specific active constraints,
- high-confidence category plus requirement.

Browsing evidence may include:

- broad or exploratory wording,
- a vague use case,
- few concrete constraints,
- low-confidence or diverse candidate evidence.

The router is not complete unless its output changes real execution through the
Strategy contract.

### 3.6 Strategy Planner

Produce a Strategy for Developer B's retrieval/ranking plane.

The Strategy should be able to express:

- Buying or Browsing intent,
- lexical, semantic, and structured route contributions,
- retrieval and rerank depth,
- hard-filter permission,
- filter confidence/relaxation policy,
- clarification requirement,
- preferred ask_attribute,
- fallback/degraded mode,
- a short human-readable reason.

Exact fields and defaults are shared contracts. Coordinate changes with
Developer B before implementation.

Developer A owns when and why per-turn Strategy values change. Developer B owns
the retrieval/fusion mechanics and supplies evidence-backed default values or
safe ranges. Neither side changes route-weight semantics alone.

### 3.7 Clarification

Clarification is a P1 capability, not a decorative final feature.

Default policy:

1. use candidate evidence to choose feature or material when informative,
2. use color, style, size, use_case, brand, budget, or category only when
   current state and candidate diversity justify it,
3. use other when no typed attribute is clearly useful,
4. never repeat an exhausted/no-preference attribute,
5. normally return current best recommendations and one useful question
   together.

Do not restore the old fixed question orders:

    category -> budget -> size -> material -> feature
    use_case -> style -> feature -> material

Current public data shows those orders waste turns. Do not hardcode public
sample IDs, target values, or simulator-specific answers.

For over-general requests:

- detect a large or low-confidence candidate pool,
- use RetrievalDiagnostics to choose a partitioning question,
- avoid adding retrieval branches that only add noise,
- record why clarification was selected.

### 3.8 Response Guard

Before returning from Agent.respond:

- message is a string,
- ask_attribute is allowed or None,
- recommendations is a list,
- every ASIN exists in the frozen catalog,
- duplicate ASINs are removed without reordering,
- no more than top_k items are returned,
- fill toward top_k from a safe fallback pool when possible,
- usage is validated only when present,
- safe fallbacks prevent avoidable exceptions.

### 3.9 starter/agent.py orchestration

Developer A is the primary owner of starter/agent.py.

It should orchestrate:

    state update
      -> intent route
      -> strategy plan
      -> distilled query
      -> Developer B retrieval
      -> Developer B ranking
      -> clarification
      -> response guard
      -> state/telemetry record

Keep retrieval and ranking internals out of starter/agent.py.

## 4. Files owned by this workstream

These are target locations, created only when the responsibility is real:

    starter/agent.py
    starter/contracts.py
    starter/core/state.py
    starter/core/context_engine.py
    starter/core/intent_router.py
    starter/core/planner.py
    starter/core/query_builder.py
    starter/core/clarification.py
    starter/core/response_guard.py
    starter/utils/telemetry.py

    tests/test_state.py
    tests/test_override.py
    tests/test_boundary.py
    tests/test_clarification.py
    tests/test_response_guard.py
    tests/test_agent_smoke.py

Do not create every file up front. Start with the smallest vertical slice and
split modules only when responsibilities become real.

## 5. Explicit non-ownership

Developer A does not own:

- BM25 internals,
- catalog indexing,
- dense model/index/cache implementation,
- RRF or other fusion internals,
- constraint score internals,
- semantic reranker implementation,
- retrieval latency/cache optimization.

Developer A may use a retrieval stub while Developer B works independently.
Do not implement a second competing retrieval stack inside Control Plane files.

## 6. Shared contract with Developer B

The two workstreams must agree on these concepts before parallel work.

### 6.1 Inputs A sends to B

At minimum:

- distilled query,
- active constraints with confidence and hard/soft status,
- Buying/Browsing intent,
- Strategy,
- top_k,
- current session/turn context needed for diagnostics.

Do not send:

- ground_truth,
- target ASIN,
- scenario_type,
- difficulty_bucket,
- intent_card,
- evaluator-only behavior.

### 6.2 Results B returns to A

At minimum:

- ranked Candidate list,
- RetrievalDiagnostics,
- fallback/degraded-mode information,
- enough score/rank provenance for debugging.

Useful stable seam:

    HybridRetriever.retrieve(query, state, strategy)
        -> candidates, diagnostics

Optional ranking seam:

    Reranker.rank(query, state, candidates, strategy)
        -> ranked_candidates

### 6.3 Contract-change rule

Before changing a shared type or interface:

1. describe the need and expected caller impact,
2. update or add contract tests,
3. notify Developer B,
4. avoid simultaneous edits to the same shared file,
5. keep the change small and backward-compatible when possible.

## 7. Implementation order

### A0 - Shared baseline and contracts

- Reconfirm official baseline.
- Agree on SessionState, Constraint, Strategy, Candidate, and
  RetrievalDiagnostics seams.
- Use Python 3.10+.
- Confirm the development split; do not inspect sealed holdout.

### A1 - Stateful lexical vertical slice

- Keep official BM25 behavior through a stub/stable retriever.
- Add state accumulation.
- Add query distillation.
- Add override and no-preference behavior.
- Add response guard.
- Preserve baseline parity where intended.

### A2 - Data-aware clarification

- Add asked/no-preference tracking.
- Ask candidate-aware feature/material first when informative.
- Add other fallback.
- Return recommendations and clarification together.
- Inspect traces with the local visualizer.

### A3 - Router and planner

- Add observable Buying/Browsing routing.
- Make route output change Strategy.
- Add over-generality behavior.
- Record human-readable planning reasons.

### A4 - Integration with Developer B

- Replace retrieval stub with HybridRetriever.
- Pass only shared-contract data.
- Consume diagnostics for clarification/adaptation.
- Test dense/reranker failure paths.

### A5 - Evaluation and hardening

- Run focused tests.
- Evaluate on development.
- Use development cross-validation for keep/revert decisions.
- Keep sealed holdout unopened until final freeze.
- Record MTTC/Efficiency changes and scenario diagnostics.

## 8. Required tests

At minimum:

- reset creates isolated state,
- two constraints accumulate without duplication,
- provenance and source turn are preserved,
- hard and soft evidence remain distinguishable,
- Intent Override deactivates stale intent,
- distilled query excludes overridden values,
- no-preference is recorded,
- an exhausted attribute is not asked again,
- clarification does not suppress valid recommendations,
- router output changes Strategy,
- illegal ask_attribute is corrected,
- duplicate/invalid ASINs are removed,
- fallback candidates fill toward top_k,
- multi-turn Agent responses satisfy the public API,
- exceptions from Developer B's optional stages reach a safe response.

Tests must never read or depend on ground_truth.

## 9. Evaluation and manual review

Use named development experiments:

    ./scripts/start_experiment.sh control-state-v1
    ./scripts/start_experiment.sh clarification-v1
    ./scripts/start_experiment.sh router-v1

For each run record:

- hypothesis,
- code/config change,
- development subset,
- overall and per-scenario metrics,
- MTTC/Efficiency effect,
- fallback/error counts,
- keep/revert decision.

Use the visualizer for public-set debugging only. It may show target labels to a
human reviewer, but Agent runtime must receive only reset/respond inputs.

Do not tune from the sealed holdout or repeatedly inspect the full 200.

## 10. Handoff to Developer B

Provide:

- current shared contracts,
- fixture SessionState objects,
- example Buying and Browsing Strategies,
- distilled-query examples,
- active/overridden/no-preference examples,
- expected diagnostics fields,
- failing integration tests or open questions,
- branch and commit SHA used for the handoff.

Developer B should be able to test retrieval/ranking without importing
Control Plane implementation internals.

## 11. Definition of done for A

Developer A's workstream is ready for integration when:

- starter/agent.py remains small orchestration code,
- SessionState is isolated and deterministic,
- active state handles accumulation, override, and no-preference,
- query construction uses active state only,
- Buying/Browsing routing changes Strategy,
- clarification is candidate-aware and non-repetitive,
- valid recommendations are returned alongside clarification when possible,
- Response Guard enforces the public contract,
- Developer B can integrate through stable seams,
- focused tests pass,
- development metrics and visual traces are recorded,
- no evaluator/data/label leakage exists,
- no changes were committed directly to, merged into, or pushed to main.

## 12. New-conversation status template

At the end of a work session, leave:

    Branch:
    Commit:
    Gate:
    Completed:
    Tests:
    Development metrics:
    Visual traces inspected:
    Shared-contract changes:
    Waiting on Developer B:
    Known risks:
    Next smallest step:
