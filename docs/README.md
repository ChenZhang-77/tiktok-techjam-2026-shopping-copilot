# Documentation Map

Use this page to choose the right document without reconstructing project state
from old reports.

## Start here

1. [Current status](current_status.md) — verified current behavior, metrics and gaps.
2. [Final release plan](final_release_plan.md) — Plan One/Two and all freeze decisions.
3. [Release comparison](release_comparison.md) — same-protocol branch selection and review.
4. [Branch inventory](branch_inventory.md) — historical sources and recovery points.
5. [Release roadmap](optimization_roadmap.md) — delivery order, not an experiment queue.
6. [Project structure](project_structure.md) — stable file placement and evidence rules.
7. [Operating contract](../AGENTS.md) — safety, ownership and evaluation boundaries.

Older A13/A14 design and experiment documents below remain useful references.
They do not authorize resuming frozen work or override current status.

## Workstream execution

- `workstreams/DEVELOPER_A_CONTROL_PLANE.md` — A-side dialogue/state route
- `workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md` — B-side retrieval/ranking route
- `a_control_plane_handoff.md` — compatibility pointer for old A-side links
- `b_retrieval_ranking_handoff.md` — compatibility pointer for old B-side links

## Delivery

- `final_readiness.md` — completed local checks, archive identity and remaining external gates
- `final_delivery_execution.md` — six-step execution and automatic review log
- `devpost_draft.md` — main-only code link and honest submission text
- `demo_recording_script.md` — rehearsed simulated cases and recording script
- `team_contributions.md` — commit-supported draft pending team confirmation
- `delivery_reports/README.md` — independent package and historical F2 evidence
- `demo_and_submission_plan.md` — demo, report, video, packaging, and claim rules
- `../submission/README.md` — final-package staging checklist
- `../visualizer/README.md` — visual debugging and Agent/Evaluator view boundary

## Contracts and evaluation

- `competition_specification.md` — normalized Track 4 requirements
- `agent_api_contract.json` — agent interface contract
- `evaluation_config.json` — evaluator configuration
- `development_folds_v1.json` — deterministic Development folds
- `adr/0001-treat-public-holdout-as-exposed.md` — public-data decision record

## Current experiment evidence

- `r0_development_failure_taxonomy.md` — canonical Development miss diagnosis
- `a8_stateful_intent_evidence.md` — retained persistent intent assessment
- `ab0_decision_evidence.md` — complete A-side decision-evidence inventory
- `a9_should_ask_evidence.md` — rejected should-ask candidate
- `a10a_question_value_evidence.md` — rejected question-value candidate
- `a10b_query_plan_evidence.md` — retained A-internal QueryPlan boundary
- `a11_extraction_scope_evidence.md` — retained bounded A11 behavior, folds,
  rejected expansions, and AB1 handoff
- `ab1_route_semantics_evidence.md` — retained shared route diagnostics
- `b8_rejected_constraint_evidence.md` — tested and reverted B8 candidate;
  zero Development rejection coverage
- `b9_conditional_dense_evidence.md` — retained broad-Browsing dense/RRF gate,
  exact fallback, four-fold result, and operational cost
- `b10a_constraint_rerank_evidence.md` — rejected Top-3/Top-5 learned rerankers
- `b11_prerequisite_evidence.md` — reason lexical-recall work was not started
- `b12_adaptive_depth_evidence.md` — exploratory adaptive depth, default off

Each recent experiment normally has a matching machine-readable
`*_evidence.json` and raw `*_reports/` directory. These paths are deliberately
stable because tests and evidence hashes bind them together.

## Historical evidence

Files named `b0_*` through `b7_*` and directories such as `b2_reports/` through
`b5_reports/` are experiment evidence. They do not override
`current_status.md`, and an implemented route is not necessarily enabled.

Completed planning tickets that remain useful for provenance live under
`archive/tickets/`. They are historical inputs, not the current backlog.

## Repository structure

Read `project_structure.md` before adding or moving a directory. In particular,
do not cosmetically relocate hash-bound JSON or raw reports without updating
every reference, test, and reproducibility record.

When ending a coding session, update only the documents whose truth changed and
leave a concise handoff using the template in the active workstream document.
