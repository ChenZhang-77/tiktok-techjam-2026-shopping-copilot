# A14 Question Policy Optimization Plan

## Status and Authority

This document is the authoritative design and experiment plan for the next
Question Policy optimization phase. It does not authorize a runtime behavior
change by itself. `AGENTS.md` still owns safety, ownership, and evaluation
rules; `docs/current_status.md` owns checkout-specific facts and metrics; and
`docs/optimization_roadmap.md` owns whole-project dependency order.

Planning and evidence-only work may begin before the A13 review gate closes.
Any A14 behavior-changing Candidate must remain separate from an active A13 or
B10b LLM experiment so metric attribution stays meaningful.

Current checkpoint: A14-0 is retained at `f594601`, and A14-1 is retained at
final runtime/audit source `9d93765`. All ten attributes now have closed-schema evidence source/status and
missing-data behavior while all 649 fixed Development responses and fold
metrics remain unchanged. Records are in
`docs/a14_0_question_policy_evidence.md` and
`docs/a14_1_attribute_evidence.md`. A14-S1 and all Candidate behavior still
wait for the A13 review disposition.

## Executive Decision

A14 will not begin by tuning another broad should-ask threshold or by letting
an LLM control the conversation. It will first build a deep A-owned `Question
Policy` Module with one runtime Interface, retain the current ask opportunity,
and improve which attribute is asked using complete, status-aware evidence.

The guiding objective is:

> Ask one non-repeating question that is likely to produce evidence the current
> Control Plane can use to change the Candidate Pool decision. Missing evidence
> is not low Question Value. Stop behavior and optional LLM behavior are later,
> separately measured slices.

The recommended shape combines three design conclusions:

1. one deep Module hides evidence construction, eligibility, selection,
   fallback, rendering, and optional model handling from `Agent`;
2. a guarded lexicographic cascade is the first deterministic policy, rather
   than a highly tunable global weighted formula;
3. synthetic safe-policy improvement, an offline LLM teacher, and an online
   LLM advisor are separate optional adapters, not requirements for the first
   Candidate.

## Why the Earlier Approaches Failed

### A9 did not establish a useful stop rule

The local evaluator scores current recommendations before it generates the
next customer reply. A valid question therefore does not delay a hit on the
current turn. If `ask_attribute=None` after a miss, the simulator asks the
Agent to choose a specific attribute and reveals no new preference. The tested
A9 concentration/stability gate consequently removed future information and
regressed HitRate, MTTC, and TechnicalScore.

This is an evaluator-mechanism fact, not a claim that real users should always
be questioned. Competition metrics and real conversation cost must be reported
separately.

### A10a compared incomplete evidence as though it were complete

Candidate partition evidence is currently comparable only for category,
material, color, style, and use case. Feature, size, brand, budget, and other
are not equivalently represented. A10a protected feature-first behavior but
still allowed supported later attributes to outrank uncovered attributes. Its
regression demonstrates the required invariant:

```text
unavailable evidence != zero Question Value
partial evidence != comparable evidence
```

### The current policy hides two decisions in one priority list

`starter/core/clarification.py` currently mixes eligibility, special cases,
attribute scoring, fallback order, and question rendering. `Agent` separately
constructs `DecisionEvidence`. This makes it possible for evidence and the
decision to drift or for missing-data semantics to spread across callers.

## Non-Negotiable Boundaries

- Use only current messages, persisted A-side state, the current
  `RetrievalResult`, and frozen catalog-derived evidence at runtime.
- Never use target ASIN, hit/miss, target rank, scenario type, intent card, or
  evaluator reply rules in the runtime policy, prompt, model, diagnostics, or
  configuration.
- Do not change `RetrievalRequest`, `RetrievalResult`, Strategy weights, or B
  route semantics for the first A14 slices.
- Recommendations remain available while asking.
- Ask at most one official attribute and never ask on turn 10.
- Never repeat an asked, no-preference, or already satisfied attribute.
- Missing, partial, uncalibrated, and degraded evidence are distinct states.
- `top_score_margin` remains unusable while
  `score_margin_usable=false`.
- Optional model failure must preserve the deterministic decision exactly.
- Do not activate A13 semantic understanding, B10b semantic ranking, and A14
  LLM Question Policy in the same metric experiment.
- Optimize only on Development-160 and its four fixed folds. Full-200 and the
  exposed holdout remain unavailable for selection.

## Recommended Deep Module

### External Interface

The seam belongs after retrieval and before `response_guard`:

```text
state updated and Strategy planned
  -> Retriever.retrieve(...)
  -> QuestionPolicy.decide(...)
  -> attach at most one question to the current recommendations
  -> response_guard
  -> SessionState.record_agent_response(...)
```

Illustrative Interface:

```python
@dataclass(frozen=True)
class QuestionDecision:
    action: Literal["ask", "stop"]
    attribute: str | None
    question: str
    reason_code: str
    evidence_status: str


@dataclass(frozen=True)
class QuestionPolicyOutcome:
    decision: QuestionDecision
    decision_evidence: DecisionEvidence
    diagnostics: dict[str, object]
    usage: dict[str, int]


class QuestionPolicy:
    def decide(
        self,
        *,
        state: SessionState,
        result: RetrievalResult | None,
        turn: int,
        top_k: int,
        response_fallback_used: bool = False,
    ) -> QuestionPolicyOutcome:
        ...
```

`Agent` learns one Interface. The Module hides Candidate scanning,
`DecisionEvidence` construction, per-attribute evidence, Question Value,
fallback tiers, optional LLM handling, and question text. This creates leverage
for callers and locality for policy changes and tests.

The Interface is read-only and total:

- it does not mutate `SessionState`, `RetrievalResult`, recommendations, or the
  response;
- `record_agent_response` remains the only place that commits the selected
  attribute to `asked_attributes`;
- an ask decision has one allowed attribute and non-empty canonical text;
- a stop decision has no attribute and empty question text;
- internal failures return a guarded deterministic fallback rather than
  failing `Agent.respond`;
- public diagnostics contain bounded statuses and reasons, not Candidate IDs,
  raw Candidate text, profiles, or evaluator-only data.

### Internal Order

```text
1. validate the current state/result snapshot
2. apply final-turn and eligibility guards
3. build Decision Evidence from that same result snapshot
4. build per-attribute evidence with explicit availability status
5. establish deterministic legacy action
6. run the guarded selection cascade
7. optionally consult one bounded advisor on an ambiguous shortlist
8. validate the proposal against the eligible set
9. render canonical question text
10. return bounded diagnostics and usage
```

Private implementation may contain an eligibility guard, evidence compiler,
selection cascade, question renderer, and final decision guard. They remain
internal unless two real adapters require a seam.

## Attribute Evidence

Every allowed attribute needs an explicit record rather than a missing map
entry:

```python
@dataclass(frozen=True)
class AttributeQuestionEvidence:
    attribute: str
    status: Literal[
        "available",
        "partial",
        "unavailable",
        "uncalibrated",
        "degraded",
        "not_applicable",
    ]
    candidate_coverage: float | None
    value_count: int | None
    rank_weighted_split: float | None
    answerability_status: str
    actionability_status: str
    comparability_family: str | None
```

Initial source audit:

| Attribute | First evidence source | Required handling |
| --- | --- | --- |
| category/material/color/style/use_case | current bounded Candidate vocabulary | retain explicit coverage/status |
| feature | bounded phrases from Candidate evidence; optional clustering later | do not treat generic text diversity as a calibrated value |
| size/brand/budget | verify field-tagged Candidate evidence before use | unavailable/partial until source and parsing are proven |
| other | no comparable partition by definition | controlled legacy fallback only |

If B must define field semantics or produce a new diagnostic, open a separate
coordinated AB experiment. Do not add B-owned meanings to Candidate diagnostics
inside an A14 behavior slice.

## Deterministic Selection Strategy

The first Candidate should use a guarded lexicographic cascade, not a global
sum of many tunable weights:

```text
eligibility
  -> evidence health and comparability family
  -> likely answerability
  -> actionability by current extraction/state/query pipeline
  -> rank-weighted Candidate split
  -> Buying/Browsing intent fit
  -> current legacy priority as tie-break/fallback
```

Question Value remains the conceptual objective:

```text
Question Value
  = likelihood of a productive answer
  x ability to turn that answer into active evidence
  x expected change in decision-relevant Candidate uncertainty
  - extra-turn and repetition risk
```

The initial runtime policy should not pretend these terms are calibrated
probabilities. Numeric values may be compared only inside a declared
comparability family. When evidence is unavailable, partial, out-of-
distribution, or unstable, preserve the legacy action rather than treating the
attribute as low value.

Rank-weighted split is preferred over raw full-pool diversity: differences in
and near Top-K matter more than vocabulary variety deep in the Candidate Pool.
Counterfactual calculations, if used, may filter or summarize the existing
Candidate Pool but must not perform a second retrieval or build another search
stack in the Control Plane.

## Ask/Stop Policy

A14's first behavior Candidate preserves the baseline ask opportunity. Initial
stop reasons are limited to:

- final turn;
- no eligible attribute;
- all eligible attributes are explicitly proven non-actionable;
- invalid state prevents even a safe legacy action.

Candidate Pool size, Top-K stability, missing partitions, degraded retrieval,
or an uncalibrated score margin cannot independently trigger stop.

A broader product-oriented stop rule may be opened only after attribute
selection is stable and the turn audit exists. It is a separate experiment
with both competition metrics and a declared real-UX question-cost objective.

## Better Alternatives to a Hand-Tuned Score

### Counterfactual Question Audit

Development-only offline analysis may fork a missed turn across every legal
attribute and record whether each action discloses new evidence and changes a
later rank or hit. Target information may be used only to score and diagnose
these offline branches. It must not become a runtime feature or training label.

This audit supplies:

- productive-answer opportunity by attribute and state;
- chosen-action regret against the offline best legal action;
- cases where no runtime-visible signal distinguishes the better question;
- a decision on whether deterministic evidence, synthetic training, or an LLM
  advisor is justified.

### Catalog-Only Safe Policy Improvement

Instead of fitting many Development thresholds, select frozen catalog products
with a fixed hash independently of public sample membership and build synthetic
trajectories. Generate vague, partial, no-preference, correction, and override
states; enumerate legal questions; replay the real deterministic pipeline; and
learn a small frozen decision tree or table. Public target membership must not
control sampling, features, rewards, or policy artifacts.

An alternative action may replace the legacy action only when its conservative
lower-bound uplift is positive in grouped synthetic folds. Out-of-distribution,
missing, or invalid policy artifacts fall back to the legacy action. The
trainer and synthetic labels never ship in runtime.

This approach is optional after a deterministic Candidate. Synthetic behavior
has distribution risk and cannot replace Development cross-validation.

## Optional LLM Roles

LLM use is justified only where language semantics, not hidden target access,
is the missing capability.

Preferred roles:

1. act offline as a teacher that clusters a frozen, hash-bound set of grounded
   catalog feature phrases into two to four answerable concepts; the result
   must pass deterministic validation before becoming policy evidence and is
   not an online-advisor input;
2. let an online advisor rerank a deterministic shortlist when comparable
   Question Value estimates are close;
3. act offline as a teacher for synthetic question generation, followed by
   deterministic validation and optional distillation;
4. generate clearer user-facing wording after the deterministic attribute is
   fixed.

The local evaluator replies according to `ask_attribute`, not prose quality.
LLM wording may improve real UX, Impact, and demo quality, but should not be
claimed as a TechnicalScore mechanism.

An online advisor is an internal seam with at least a deterministic/fake
adapter and a provider adapter. Unlike the separate offline feature teacher,
it receives only an eligible shortlist and bounded aggregate evidence; it does
not receive or cluster raw feature phrases. It may return existing proposal
IDs, confidence, and closed reason codes. It cannot:

- decide stop in its first Candidate;
- create a new attribute or bypass eligibility;
- mutate state or recommendations;
- see Candidate IDs, targets, scenario labels, evaluator rules, or raw user
  profiles;
- make more than one external call in a turn;
- run in the same metric experiment as active A13 or B10b LLM behavior.

No key, timeout, malformed output, unknown proposal, low confidence, or
provider failure discards the whole proposal and preserves the deterministic
decision.

## Experiment Sequence

### A14-0 - Turn Audit and Module Parity

Primary behavior change: none.

**Retained on 2026-08-30.** The Module, clean legacy comparator, target-free
turn audit, source/input hashes, Development/fold parity, latency, and review
fixes are bound by `docs/a14_0_question_policy_evidence.md`.

- retain per-turn eligible attributes, baseline action, reason, answer outcome,
  and safe evidence statuses;
- move existing evidence/clarification orchestration behind the one-entry-point
  Module;
- preserve every recommendation and `ask_attribute` trace;
- bind a full Development turn trace and focused/full tests.

Keep only with exact behavior and metric parity, zero leakage, and acceptable
incremental latency.

### A14-1 - Attribute Evidence Coverage

Primary behavior change: none.

**Retained on 2026-08-30.** Ten explicit records distinguish bounded available
evidence, uncalibrated feature text, unavailable field-tagged size/brand/budget
evidence, and the controlled `other` fallback. Exact visible and metric parity,
coverage counts, latency, and gates are bound in
`docs/a14_1_attribute_evidence.md`.

- produce explicit status for all ten allowed attributes;
- prove source, lifecycle, range, comparability, and missing-data behavior;
- add feature/size/brand/budget evidence only where the current Candidate data
  supports it;
- retain baseline action while auditing coverage.

Do not open global selection while uncovered attributes can still be confused
with zero value.

### A14-S1 - Deterministic Selection Shadow

Primary behavior change: none.

- compute the cascade's proposed attribute while returning the legacy action;
- compare predicted productive answers with actual next-turn state changes;
- run the offline counterfactual audit on Development misses;
- predeclare the exact Candidate bucket and keep/revert gate.

### A14-C1 - Selection-Only Candidate

Primary behavior change: which eligible attribute is asked.

- preserve ask opportunity, recommendations, retrieval, state mutation order,
  and question templates;
- activate only evidence families proven comparable in A14-1/S1;
- use legacy fallback for unsupported and out-of-distribution states.

This is the first recommended metric-changing experiment.

### A14-S2 - Catalog-Only Learned Policy Shadow

Primary behavior change: none.

- build and hash a deterministic policy artifact from grouped synthetic folds;
- log baseline versus proposed action, lower-bound uplift, OOD, and fallback;
- keep the runtime action unchanged.

Open only if A14-C1 leaves a diagnosed, runtime-observable selection bucket.

### A14-C2 - Safe Policy Candidate

Primary behavior change: selection override in one supported bucket.

- activate only positive conservative-uplift actions;
- retain exact legacy fallback for missing/corrupt artifacts and OOD states;
- do not combine with stop or LLM behavior.

### A14-S3T - Offline LLM Teacher Shadow or No-Go

Primary behavior change: none. This slice is independent of the online advisor
and does not authorize a runtime artifact.

- open only if A14-C1 leaves a diagnosed catalog-feature normalization bucket;
- freeze and hash the catalog phrase fixture before any provider call, with
  predeclared item and character bounds;
- deterministically reject ungrounded, duplicate, out-of-schema, or newly
  invented concepts;
- record validated coverage, invalid rate, repeatability, latency, tokens, and
  cost against a deterministic normalization comparator;
- retain at most offline evidence-generation tooling when its predeclared
  coverage and reliability gates pass; otherwise record No-Go;
- require a separately reviewed deterministic Shadow/Candidate before any
  validated teacher artifact can affect runtime selection.

### A14-S3 - Online LLM Advisor Shadow

Primary behavior change: none.

- call only on one predeclared ambiguity bucket;
- receive only proposal IDs and bounded aggregate evidence, never raw feature
  phrases or offline-teacher output;
- record proposal legality, deterministic agreement, counterfactual regret,
  latency, tokens, cost, and fallback;
- do not alter state, questions, or recommendations.

### A14-C3 - Guarded LLM Candidate or No-Go

Primary behavior change: attribute choice inside the reviewed bucket.

- enable only if Shadow proves a semantic-quality advantage over the
  deterministic selector;
- require zero invalid decisions and exact deterministic fallback;
- record No-Go when the advantage does not survive fixed folds or cost/reliability
  gates.
- do not treat A14-S3T success as a gate for this Candidate; only the online
  A14-S3 advisor Shadow can open A14-C3.

### A14-C4 - Ask/Stop Candidate

Primary behavior change: stopping before exhaustion.

- open only after selection is stable;
- keep separate from attribute, LLM, profile, query, or retrieval changes;
- report official metrics and the separately declared real-UX question cost;
- expect No-Go unless it preserves future useful-information opportunities.

Feature phrasing and future profile priors remain separate follow-ups. Profile
weight stays `0.0` until an independent ablation proves value.

## Required Diagnostics

Runtime, target-free diagnostics:

- policy version and mode;
- ask/stop action and closed reason code;
- selected and baseline attributes;
- eligible attributes;
- per-attribute evidence status and comparability family;
- selected cascade layer and fallback reason;
- degraded/relaxation status;
- policy decision latency;
- optional advisor trigger, result status, fallback, latency, and token usage.

Offline-only diagnostics:

- questions per session and ask/stop reason counts;
- attribute selection distribution and transition matrix;
- productive-answer rate and answer-to-new-active-evidence rate;
- no-preference and unproductive reply rate;
- repeated, ineligible, known-attribute, and final-turn violations;
- next-turn Candidate stability/coverage change;
- offline best legal question and selected-action regret;
- target rank/hit changes for diagnosis only;
- gained/lost sessions and scenario/fold metrics;
- optional advisor call, validity, timeout, fallback, latency, token, and cost
  distributions.

Question Policy classification remains deterministic triage, not proof that
every miss would be fixed by selecting another question.

## Keep and Revert Gates

Evidence-only slices:

- exact recommendation and ask-trace parity;
- zero response/schema/leakage violations;
- every signal has a source, owner, lifecycle, range, and missing-data status;
- deterministic fallback is complete;
- incremental latency and memory are recorded.

Behavior-changing deterministic slices:

- HitRate@10 does not decline overall;
- TechnicalScore is non-regressing in at least three of four fixed folds;
- no material scenario regression is hidden by aggregate gain;
- gained/lost sessions and changed action buckets have a common mechanism;
- repeated/no-preference/final-turn violations remain zero;
- productive-answer and unproductive-reply diagnostics support the proposed
  mechanism;
- unsupported evidence always takes the declared legacy fallback.

LLM Candidate adds:

- one predeclared trigger class and at most one call per eligible turn;
- zero accepted invalid proposals;
- exact deterministic behavior on no-key, timeout, provider, schema, and
  validation failure;
- bounded call rate, p95 latency, tokens, cost, and fallback rate with numeric
  gates declared before the run;
- improvement over the deterministic comparator, not merely over the old
  priority list;
- no simultaneous A13 or B10b model activation.

Run no behavior-changing slice on Full-200 or the exposed holdout.

## Expected File Ownership

Likely A-owned files after explicit implementation approval:

- `starter/core/question_policy.py`;
- `starter/core/clarification.py` as a compatibility wrapper or legacy adapter;
- `starter/core/decision_evidence.py`, deepened into or consumed by the Module;
- `starter/agent.py` wiring only;
- focused Question Policy, Agent, state, response-guard, audit, and leakage
  tests;
- new experiment/evidence files under the established `docs/a14_*` convention.

Do not change `starter/contracts.py`, B retrievers/rankers, the evaluator,
public labels, catalog, or submission package in A14-0/C1 unless a separately
approved blocker proves a real need.

## Verification and Handoff

Every A14 implementation slice reports:

```text
Branch and commit:
A14 slice and primary behavior:
Failure class:
Comparator and policy version:
Files changed:
Focused/full tests:
Development folds and scenarios:
Question diagnostics:
LLM trigger/cost/fallback diagnostics, if applicable:
Keep/revert decision:
Shared-contract impact:
Known risks:
Next smallest step:
```

Focused and full test commands remain in the A-side workstream. Ordinary
behavior selection uses only Development-160 and the four fixed folds.
