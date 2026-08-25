# Shopping Copilot

This context describes the shared language for the Track 4 conversational
shopping system and its evidence-driven evaluation workflow.

## System language

**Shopping Agent**:
The customer-facing system that maintains a conversation and returns ranked
catalog recommendations.
_Avoid_: chatbot, search endpoint

**Control Plane**:
The part of the Shopping Agent that interprets conversation state, chooses a
strategy, asks clarifying questions, and guards the final response.
_Avoid_: dialogue backend, Agent logic

**Retrieval / Ranking Plane**:
The part of the Shopping Agent that finds catalog candidates, combines evidence,
orders candidates, and reports retrieval diagnostics to the Control Plane.
_Avoid_: search helper, B side

**Distilled Query**:
The current search expression derived from active customer intent without stale
or overridden preferences.
_Avoid_: full history, raw query

**Active Constraint**:
A current customer requirement or preference that may influence retrieval or
ranking and has not been overridden, rejected, or marked no-preference.
_Avoid_: slot, filter

**Candidate Pool**:
The ordered set of plausible catalog products available before the final Top 10
recommendations are selected.
_Avoid_: result list, recommendations

**Route**:
One independently observable source of candidate evidence, such as lexical,
structured, or semantic retrieval.
_Avoid_: branch, model

**Candidate Provenance**:
The route ranks and scoring evidence explaining how a catalog product entered
and moved within the Candidate Pool.
_Avoid_: debug metadata

**Retrieval Diagnostics**:
Non-label operational evidence about route availability, pool sizes, filtering,
fallbacks, latency, and candidate overlap.
_Avoid_: evaluator diagnostics, target data

## Evaluation language

**Development Set**:
The fixed 160 public sessions used for B-stage cross-validation, ablation, and
ordinary experiment selection.
_Avoid_: training set

**Exposed Holdout**:
The 40 public sessions previously included in a full-set evaluation and therefore
not suitable for confirmatory claims after later architecture changes.
_Avoid_: sealed holdout, validation set

**Final Public Run**:
The single full 200-session evaluation run performed after the B configuration
is frozen for public reporting, not for further tuning.
_Avoid_: holdout validation

**Private Evaluation**:
The organizer's unseen 800-session evaluation and the only remaining fully
external test of generalization.
_Avoid_: private training set
