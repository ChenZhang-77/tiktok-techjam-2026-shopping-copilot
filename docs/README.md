# Documentation Map

Use this page to choose the right document without reconstructing project state
from old reports.

## Start here

For the latest requested order (2026-08-31), start with
[B10b-F1 full product reranking](b10b_full_rerank_test.md) and its
[bound results](b10b_full_rerank_result.json): the authorized full pass completed
412 real API requests and improved score on all four folds, but two sessions
have trace differences and the strict parity gate fails. No default switch or
repeat pass. The subsequent [A13-F1 semantic test](a13_semantic_score_test.md)
and [bound result](a13_semantic_score_result.json) are complete: 67 real calls,
60 valid proposals, below the 95% gate. No Candidate was run and no semantic
score benefit is claimed. Next recommendation: resolve paired-retrieval
timing differences in B10b-F1 before another paid reranking comparison.
Earlier deadline evidence remains in [A13 lightweight review](a13_light_review.md)
and [A14 default-route selection pilot](a14_deadline_selection.md).
The older multi-family A13 reference pipeline is deferred, not a prerequisite
for completing the deadline pilot. Neither synthetic review agreement nor an
opt-in experiment implies retained runtime improvement.

1. `../AGENTS.md` — operating rules for Codex and contributors
2. `current_status.md` — authoritative current checkpoint, evidence, and risks
3. `human_optimization_recap_zh.md` — plain-language Chinese timeline from
   A1/B1, metric explanations, decisions, and current interpretation
4. `optimization_roadmap.md` — dependency-ordered whole-project route
5. `question_policy_optimization_plan.md` — authoritative A14 Question Policy
   Module, evidence, alternatives, LLM role, and experiment gates
6. `project_structure.md` — directory responsibilities and file-placement rules
7. `ablation_summary.md` — what was retained, rejected, and why
8. `../DeepSeek_LLM接入实验方案.md` — authoritative A13 semantic-understanding
   plan, review gates, branch boundary, and relationship to B-side DS1
9. `a13_ai_silver_protocol.md` — deferred no-human A13 reference protocol,
   applied-state comparator, KPI hierarchy, contamination controls, and
   separate reference-builder/Candidate provider gates

`../AGENTS.md` is the sole authority for the R0 failure taxonomy and the
offline-target/runtime boundary. `optimization_roadmap.md` is the sole authority
for dependency order. Workstream and experiment documents must reference those
definitions instead of creating local variants.

## Workstream execution

- `workstreams/DEVELOPER_A_CONTROL_PLANE.md` — A-side dialogue/state route
- `workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md` — B-side retrieval/ranking route
- `question_policy_optimization_plan.md` — selected A14 deep-Module design;
  planning/parity work may precede the A13 decision, but Candidate behavior
  remains a separate experiment
- `../DeepSeek_LLM接入实验方案.md` — selected A13 feature plan; A13-1 is
  rejected/reverted and A13-S0 has offline-only Shadow plumbing, not provider
  behavior
- `a13_ai_silver_protocol.md` — deferred no-human reference route; AS0 core
  contracts passed, exact roles and execution runner still pending, and no current
  provider authorization
- `a_control_plane_handoff.md` — compatibility pointer for old A-side links
- `b_retrieval_ranking_handoff.md` — compatibility pointer for old B-side links

## Delivery

- `demo_and_submission_plan.md` — demo, report, video, packaging, and claim rules
- `../A13_annotation_pack_v1.zip` — deterministic legacy offline A13 annotation
  bundle; its exposed items are development diagnostics, not semantic-gate data
- `../submission/README.md` — final-package staging checklist
- `../visualizer/README.md` — visual debugging and Agent/Evaluator view boundary

## Contracts and evaluation

- `competition_specification.md` — normalized Track 4 requirements
- `agent_api_contract.json` — agent interface contract
- `evaluation_config.json` — evaluator configuration
- `development_folds_v1.json` — deterministic Development folds
- `adr/0001-treat-public-holdout-as-exposed.md` — public-data decision record

## Current experiment evidence

- [a13_semantic_score_test.md](a13_semantic_score_test.md) and
  [a13_semantic_score_result.json](a13_semantic_score_result.json) — real
  baseline/Shadow comparison; rejected by validity gate before Candidate
- [a13_light_review.md](a13_light_review.md) — completed 24-call synthetic
  Flash/Pro editor diagnostic; retained offline only, not a score claim
- [a14_deadline_selection.md](a14_deadline_selection.md) — twice-reproduced
  default-route score pilot, fold-2 risk, explicit not-default decision
- [a14_deadline_selection_result.json](a14_deadline_selection_result.json) —
  recomputable sessions/folds and changed-question evidence for that pilot

- `r0_development_failure_taxonomy.md` — canonical Development miss diagnosis
- `a13_0_baseline_evidence.md` — current 0.925 comparator, hashes, fixed folds,
  and refreshed target-free taxonomy
- `a13_0_reports/` — hash-bound raw Development, four-fold, and refreshed
  taxonomy reports used by the A13-0 evidence test
- `a13_1_state_override_evidence.md` — rejected-and-reverted deterministic
  State / Override candidate and restored Shadow comparator
- `a13_1_reports/` — hash-bound candidate/revert Development, fold, and
  taxonomy reports used by the A13-1 evidence test
- `a13_s0_offline_evidence.md` — retained types/fake/validator/gate/fallback
  foundation and exact behavior parity before any provider work
- `a13_s0_reports/` — hash-bound disabled/no-key/fake Development parity reports
- `a13_ai_silver_protocol.md` — planned AS0-AS1F-AS1J-AS2 reference-building protocol;
  AS0 core contracts are implemented, but exact roles, runner and AI-silver remain pending
- `a13_as0_offline_tooling_evidence.md` — hash-bound AS0 comparator, Candidate
  config, schema, contamination, role-preflight, consensus, and KPI tooling;
  blocks AS1F until exact roles and the execution/repair/provenance runner pass
- `a13_annotation_intake_review.md` — validation/provenance audit of the first
  two returned annotation files, valid-34 AI review artifacts, offline
  deterministic failure breakdown, repair IDs, and their L1 historical boundary
- `a14_0_question_policy_evidence.md` — retained deep Question Policy Module,
  exact 649-turn legacy parity, bounded audit, latency, and next gate
- `a14_0_reports/` — hash-bound legacy/current turn traces, Development result,
  and four fixed-fold reports used by the A14-0 evidence test
- `a14_1_attribute_evidence.md` — retained ten-attribute source/status matrix,
  exact legacy parity, bounded latency, and the A13-dependent stop gate
- `a14_1_reports/` — hash-bound full per-turn evidence, derived coverage
  summary, Development, and four-fold reports used by the A14-1 evidence test
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
