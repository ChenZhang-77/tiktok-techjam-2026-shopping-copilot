# Shopping Copilot - Current Status

This file is the single source of truth for the current project state. It is
written for a fresh Codex conversation and for the two-person team. Re-check
the Git checkout before relying on any checkout-specific value below.

## Start Here in a New Conversation

Read, in order:

1. `AGENTS.md` for non-negotiable operating rules.
2. This file for the verified current state and next decision.
3. `docs/optimization_roadmap.md` for the project-wide execution order.
4. One workstream document:
   - A: `docs/workstreams/DEVELOPER_A_CONTROL_PLANE.md`
   - B: `docs/workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md`
5. The files named by the selected experiment.

At the beginning of the conversation, report:

```text
Branch:
HEAD:
Working tree clean/dirty:
Selected workstream and experiment:
Files expected to change:
Development-only verification command:
```

Do not implement a backlog item merely because it appears in a roadmap. The
user must still ask for implementation. A planning or review request is
read-only.

## Verified Behavior Checkpoint

Verified on 2026-08-27:

| Item | Value |
| --- | --- |
| Historical branch at verification | `yuqing` |
| Behavior commit | `bddf7d7e8ad7dda6880ae4d8e08d0c4c082e29e2` |
| Local tracking ref | `origin/main` at the same commit when last inspected |
| Full test suite | 148 passed |
| Catalog | 50,000 unique products, local generated file ignored by Git |
| Default runtime | deterministic structured retrieval/ranking |

Branch and remote facts can drift. Re-check them before reporting or changing
the repository. Do not fetch, push, merge, or open a PR unless the user asks.
Documentation-only commits after this checkpoint do not invalidate the metrics;
any runtime behavior change does.

## Verified Development Result

The integrated A+B runtime at `bddf7d7` was independently reproduced on the
fixed Development-160 split with the structured default:

| Metric | Development-160 |
| --- | ---: |
| HitRate@10 | 0.7625 |
| MRR | 0.526989 |
| MTTC | 5.30625 |
| Efficiency | 0.569375 |
| TechnicalScore | 0.653222 |

Scenario diagnostics:

| Scenario | Samples | HitRate@10 | MRR | MTTC | TechnicalScore |
| --- | ---: | ---: | ---: | ---: | ---: |
| Boundary | 8 | 0.875000 | 0.775000 | 5.875000 | 0.772500 |
| Browsing | 64 | 0.812500 | 0.572241 | 4.906250 | 0.699797 |
| Buying | 64 | 0.718750 | 0.459518 | 5.203125 | 0.613168 |
| Intent Override | 24 | 0.708333 | 0.503571 | 6.458333 | 0.596071 |

Observed reliability was zero response exceptions, invalid payloads, reported
fallbacks, and internal fallbacks. The bound artifact is
`docs/b7_pre_freeze_development.json`.

## Historical Final Public Result

The one Full-200 Final Public Run was executed from frozen commit `98d3325`:

| Metric | Full-200 |
| --- | ---: |
| HitRate@10 | 0.765000 |
| MRR | 0.517355 |
| MTTC | 5.375000 |
| Efficiency | 0.562500 |
| TechnicalScore | 0.650207 |

This is a historical, non-confirmatory public snapshot. The 40-session public
holdout had already been exposed by earlier full-set work. Do not tune against,
repeat, or present this result as a sealed validation result. The organizer's
private 800 sessions remain the external generalization test. See:

- `docs/adr/0001-treat-public-holdout-as-exposed.md`
- `docs/b7_final_public_summary.json`
- `docs/b7_final_public_run.json`

Any later behavior change means the Full-200 result no longer describes the new
runtime. Report it as historical and select new work only with Development-160
cross-validation.

## Current Retained Runtime

```text
user message
  -> state/context update
  -> current-turn Buying/Browsing inference
  -> Strategy planning
  -> distilled active-state query
  -> in-memory SQLite FTS5 field-weighted candidate pool
  -> hard/soft cross-field constraint ranking
  -> guarded structured filtering with deterministic relaxation/fill
  -> candidate-aware but still priority-biased clarification
  -> response guard
```

The public seam is:

```text
Agent.respond(session_id, user_message, turn, top_k) -> response dict
HybridRetriever.retrieve(request: RetrievalRequest) -> RetrievalResult
```

The shared contract lives in `starter/contracts.py`. Developer A must not send
evaluator labels. Developer B must not import Agent state implementation
internals.

The current Strategy can express a non-zero Browsing semantic weight, but the
retained default `HybridRetriever` does not execute a semantic route. Treat that
field as requested intent rather than proof of active execution until AB1 makes
requested versus executed route semantics explicit.

## Measured but Disabled Paths

These paths exist for reproducible experiments and failure coverage. They are
not part of the default runtime:

| Path | Decision |
| --- | --- |
| Dense-only MiniLM retrieval | Reject as default; weak recall/ranking |
| Weighted RRF fusion | Reject as default; cross-validation regression |
| Top-30 CrossEncoder semantic rerank | Reject globally; small aggregate gain but MRR and Intent Override regression, high cost |
| Profile ranking | Disabled at weight 0.0; no evidence-backed gain |

Do not claim that the default runtime dynamically combines lexical, dense, and
semantic routes. The defensible story is that the team implemented, measured,
and rejected paths whose tradeoffs were not robust.

## Current Bottlenecks

The next optimization phase starts from diagnosis, not from another model:

1. Intent is re-inferred from the current utterance and can flip too easily
   after a clarification reply.
2. Clarification normally asks `feature` before using candidate partition
   evidence and does not first decide whether a question is needed.
3. Constraint extraction is rule- and vocabulary-limited. Negation scope is a
   known issue: a sentence such as "I do not care about color, but I prefer
   nylon" can mark both color and material as no-preference.
4. `rejected_constraints` crosses the A/B seam but the retained B path does not
   yet use it as a calibrated negative ranking signal.
5. The semantic reranker has useful scenario-specific signals, but global
   enablement damages MRR and Intent Override.
6. The public-facing README, final package, and demo narrative lag the runtime.

## R0 Result

R0 is complete at clean code commit `0b9bc74`. The Development-160 baseline
remained HitRate@10 `0.7625`, MRR `0.526989`, MTTC `5.30625`, and recommended
technical score `0.653222`; R0 changed no runtime behavior.

Of 38 missed sessions, the earliest observed cause was Intent / Strategy
Routing in 25, State / Override in seven, and Extraction in six. Intent /
Strategy Routing was the largest class in every fixed fold. The target entered
the retained lexical pool in 145 of 160 sessions, so the next optimization
should stay on the A-side control plane.
This is deterministic evidence triage, not proof that every downstream failure
would disappear after one upstream behavior change. The durable report is
`docs/r0_development_failure_taxonomy.md`, with turn-level offline evidence in
the adjacent JSON artifact.

## A8 Result

A8 is retained at clean code commit `83a6bcd`. `IntentAssessment` is now a
persistent `SessionState` value with intent, A-owned ordinal confidence,
evidence, source turn, and an explicit transition reason. A diagnostics expose
the complete decision while `Strategy.reason` exposes only the transition;
the A/B request contract is unchanged.

On Development-160, HitRate@10 remains `0.7625`, MRR increases from `0.526989`
to `0.529812`, MTTC changes from `5.30625` to `5.35`, and technical score is
effectively neutral (`0.653222` to `0.653194`). Buying improves in three of four
folds and Browsing does not regress; Intent Override regresses slightly. The
bounded decision and rejected variants are recorded in
`docs/a8_stateful_intent_evidence.md`.

## AB0 Result

AB0 is retained at clean code commit `3988b8b`. The A-side adapter computes
bounded full-pool size, Top-K stability, constraint coverage, attribute
partition, relaxation/degradation, and turn/exhaustion summaries before
clarification. Raw Candidate IDs/text are not serialized, and the shared A/B
contracts are unchanged. Route-local score margin is observable but explicitly
uncalibrated and unusable for A9.

The clean Development-160 metrics and all 160 session outcomes exactly match
A8. A separate 818-turn replay also produced an identical ask/recommendation
trace hash. The original slow scanner was rejected; the retained implementation
observed `41.18 ms` mean response latency and zero failures. Full evidence is in
`docs/ab0_decision_evidence.md`.

## A9 Result

A9 is rejected and reverted. The tested stability/no-partition gate reduced
neither total questions nor MTTC: HitRate fell from `0.7625` to `0.7500`, MTTC
rose from `5.35` to `5.43125`, and technical score fell from `0.653194` to
`0.644556`. Two sessions were lost and none gained. Three bounded conservative
thresholds exactly matched the baseline but improved no keep metric. The final
runtime therefore preserves the pre-A9 question policy. See
`docs/a9_should_ask_evidence.md`.

## Next Decision

The next dependency-ordered module is A10a Candidate Question Value. It should
improve which useful question is asked, not reopen threshold-only suppression.
Score margin remains forbidden as a gate. A11 Extraction and Scope Hardening
remains supported by six primary Extraction misses and stays after the
dependencies specified in the roadmap.

The complete dependency order lives only in `docs/optimization_roadmap.md`.
Immediate blocker to remember: B9 cannot start before AB1 freezes shared route
semantics.

If submission is imminent, skip new behavior work and execute the delivery
track in `docs/demo_and_submission_plan.md`.

## Ownership

| Area | Owner | Non-owner |
| --- | --- | --- |
| Session state, extraction, intent, Strategy timing, clarification, response guard, `starter/agent.py` | Developer A | Developer B |
| Catalog, lexical/structured/dense retrieval, fusion, ranking, cache, retrieval diagnostics | Developer B | Developer A |
| `RetrievalRequest`, `RetrievalResult`, Strategy weight semantics | Shared and coordinated | Neither changes alone |
| Evaluator, public labels, frozen catalog | Official/read-only | Neither modifies |

## Documentation Map

| Document | Purpose |
| --- | --- |
| `README.md` | Public project entry, setup, architecture, results, limitations |
| `AGENTS.md` | Operational contract for coding agents |
| `docs/current_status.md` | Current verified state and next decision |
| `docs/optimization_roadmap.md` | Project-wide optimization sequence and gates |
| `docs/r0_development_failure_taxonomy.md` | Clean Development-160 failure audit and next-experiment evidence |
| `docs/a8_stateful_intent_evidence.md` | Stateful intent keep/reject evidence and tradeoff boundary |
| `docs/ab0_decision_evidence.md` | DecisionEvidence sources, fallbacks, parity, and A9 input boundary |
| `docs/a9_should_ask_evidence.md` | Rejected should-ask gate, evaluator mechanism, and A10a route consequence |
| `docs/ablation_summary.md` | Human-readable keep/reject evidence |
| `docs/workstreams/DEVELOPER_A_CONTROL_PLANE.md` | Standalone A-side route |
| `docs/workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md` | Standalone B-side route |
| `docs/demo_and_submission_plan.md` | Demo, README, Devpost, packaging, rehearsal |
| `CONTEXT.md` | Stable shared vocabulary only |

## Remaining Track 4 Coverage Gaps

- Browsing-specific diverse dense retrieval is implemented only as disabled
  experimental machinery, not retained runtime behavior.
- Semantic reranking is reproducible but globally rejected; conditional use is
  still a hypothesis.
- Profile ranking remains disabled at weight `0.0`; long-term profile value has
  not been demonstrated.
- Candidate-aware clarification exists, but a complete should-ask gate has not
  yet been retained.

These are explicit gaps, not implied capabilities. If an experiment is rejected
again, preserve the measured result and disclose the literal coverage gap.

## Safe Verification Commands

Default runtime tests:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Ordinary Development-160 evaluation:

```bash
.venv/bin/python -m experiments.evaluation_reporting \
  --split development --structured-filter \
  --output /private/tmp/shopping-copilot-development.json
```

Do not run `--split full` or `--split holdout` during optimization.

## End-of-Session Handoff

Every implementation session should leave this concise status in its final
response or an updated workstream section:

```text
Branch and commit:
Experiment ID:
Hypothesis:
Files changed:
Tests:
Development folds/results:
Scenario gains/regressions:
Latency/memory/fallback impact:
Keep/revert decision:
Shared-contract changes:
Known risks:
Next smallest step:
```
