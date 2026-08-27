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

**Intent Confidence**:
An agent-side estimate of how stable and specific the current intent is, based
only on the conversation observed so far. It may guide questioning or retrieval
depth but must not use evaluator labels.
_Avoid_: probability of target hit, evaluation confidence

**Over-Generality**:
A state in which the current intent leaves too many materially different
candidate interpretations for reliable ranking.
_Avoid_: simply having many search results

**Question Value**:
The expected reduction in decision-relevant uncertainty from asking one
clarifying question, weighed against its extra-turn cost.
_Avoid_: always ask when an attribute is missing

**Candidate Stability**:
How little the leading Candidate Pool changes under small, valid changes to the
query or active state. Low stability may justify clarification or a guarded
fallback.
_Avoid_: deterministic execution

**Conditional Route**:
An optional retrieval or reranking route activated only for a declared,
observable subset of agent-side states and backed by a deterministic fallback.
_Avoid_: globally enabled experiment

**Retained Runtime**:
The configuration enabled by default after passing the declared development
gate. For the current checkpoint, this is lexical retrieval plus structured
scoring.
_Avoid_: every implemented path

**Rejected Ablation**:
An implemented experiment whose measured development tradeoff did not justify
retaining it in the default runtime. Its code or reports are not evidence that
the method is active.
_Avoid_: failed implementation

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

**Historical Final Public Result**:
The recorded full-200 result for a previously frozen configuration. It is useful
for transparent reporting but cannot become a new optimization target.
_Avoid_: fresh confirmation, unseen test result

**Private Evaluation**:
The organizer's unseen 800-session evaluation and the only remaining fully
external test of generalization.
_Avoid_: private training set
