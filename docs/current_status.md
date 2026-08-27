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

## Verified Checkout Snapshot

Verified on 2026-08-27:

| Item | Value |
| --- | --- |
| Branch | `yuqing` |
| HEAD | `bddf7d7e8ad7dda6880ae4d8e08d0c4c082e29e2` |
| Local tracking ref | `origin/main` at the same commit when last inspected |
| Full test suite | 148 passed |
| Catalog | 50,000 unique products, local generated file ignored by Git |
| Default runtime | deterministic structured retrieval/ranking |

Branch and remote facts can drift. Re-check them before reporting or changing
the repository. Do not fetch, push, merge, or open a PR unless the user asks.

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

## Next Decision

The next technical action is R0 in `docs/optimization_roadmap.md`: classify
Development-160 failures into recall, ranking, state, dialogue, and extraction
causes. The first behavior experiment after that should normally be A8,
stateful intent persistence. B-side conditional semantic work is blocked on a
stable A-side intent signal.

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
| `docs/ablation_summary.md` | Human-readable keep/reject evidence |
| `docs/workstreams/DEVELOPER_A_CONTROL_PLANE.md` | Standalone A-side route |
| `docs/workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md` | Standalone B-side route |
| `docs/demo_and_submission_plan.md` | Demo, README, Devpost, packaging, rehearsal |
| `CONTEXT.md` | Stable shared vocabulary only |

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
