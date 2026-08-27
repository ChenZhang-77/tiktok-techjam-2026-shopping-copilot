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

**Intent Assessment**:
The A-owned, cross-turn interpretation of current intent, its bounded confidence
or ordinal stability, conversation-derived evidence, source turn, and transition
reason. It is persisted or deterministically derived from persisted evidence.
_Avoid_: current-utterance label, probability of target hit

**Decision Evidence**:
A compact A-side view of non-label Candidate and state evidence available at the
should-ask decision point. Every field has a declared producer, meaning,
lifecycle, and missing-data fallback.
_Avoid_: Top-K text alone, evaluator diagnostics

**Query Plan**:
An A-owned structured trace of exact/category, active hard/soft, semantic/use-case,
and rejected/overridden evidence. In A10b it compiles to the existing single
`RetrievalRequest.query` string and does not cross the A/B seam.
_Avoid_: a shared contract change by default, full-history concatenation

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

**Offline Failure Class**:
The earliest causal execution stage explaining a Development-160 failure. The
canonical order is Extraction, State / Override, Intent / Strategy Routing,
Query Construction, Question Policy, Retrieval Recall, Ranking / Filtering,
and Response / Contract. Later contributing stages may be secondary causes.
_Avoid_: per-document taxonomy, evaluator timing as Agent behavior

**Offline Evaluation Evidence**:
Development-only target ASIN, hit/miss, target rank, and pre/post-rank position
used to diagnose failures. It may appear in offline reports but never in Agent
state, requests, runtime diagnostics, prompts, Strategy, rules, or models.
_Avoid_: runtime signal, holdout tuning

**Evaluation Validity Flag**:
An offline marker for evaluator/timing/data anomalies that may invalidate or
qualify a sample analysis. It is separate from the Agent failure taxonomy.
_Avoid_: timing failure as an Agent behavior class

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
