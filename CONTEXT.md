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

**QueryPlan**:
An A-owned current-turn decomposition of category, hard, soft, semantic,
residual, and excluded evidence. It renders the existing single Distilled Query
for B; it is not a shared typed-query contract.
_Avoid_: RetrievalRequest schema extension, treating excluded terms as positive

**Catalog Vocabulary**:
An A-owned deterministic set of multi-word category phrases derived from the
frozen runtime catalog. The retained A11 vocabulary does not include broad
feature phrases or inferred single-word brands.
_Avoid_: target vocabulary, evaluator labels, unrestricted feature dictionary

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

**Over-Generality**:
A state in which the current intent leaves too many materially different
candidate interpretations for reliable ranking.
_Avoid_: simply having many search results

**Question Value**:
The expected reduction in decision-relevant uncertainty from asking one
clarifying question, weighed against its extra-turn cost.
_Avoid_: always ask when an attribute is missing

Current boundary: the A-side Candidate vocabulary supplies comparable partition
evidence only for category/material/color/style/use-case. Missing evidence for
feature/size/brand/budget/other is not a zero Question Value and must not be
ranked as though it were.

**Candidate Stability**:
How little the leading Candidate Pool changes under small, valid changes to the
query or active state. Low stability may justify clarification or a guarded
fallback.
_Avoid_: deterministic execution

**Decision Evidence**:
An A-side, label-free summary of the complete current Candidate Pool and
cross-turn state made available before clarification. It carries bounded
availability/status fields, never target data or raw Candidate text/IDs in
public diagnostics. An uncalibrated route-local score margin is not a gate.
_Avoid_: evaluator evidence, target rank, automatic should-ask rule

**Conditional Route**:
An optional retrieval or reranking route activated only for a declared,
observable subset of agent-side states and backed by a deterministic fallback.
_Avoid_: globally enabled experiment

**Semantic Interpreter**:
An optional A-owned Module proposed by A13. It may interpret a difficult current
user message behind a local ambiguity gate and return a validated
Understanding Delta. It is not a second Agent, a retrieval Route, or retained
runtime behavior until the A13 gates pass.
_Avoid_: LLM Agent, global intent parser, semantic ranking

**Understanding Delta**:
A bounded proposal containing current-message evidence for positive, rejected,
no-preference, override, intent-hint, or semantic-term changes. It cannot mutate
SessionState directly and is discarded as a whole when local validation fails.
_Avoid_: model-owned state, free-form reasoning, partial fallback

**Retained Runtime**:
The configuration enabled by default after passing the declared development
gate. For the current checkpoint, this is lexical retrieval plus structured
scoring for every request, with B9 local dense retrieval and weighted RRF only
behind the measured broad-Browsing gate. B12 adaptive depth is optional and
disabled by default.
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
