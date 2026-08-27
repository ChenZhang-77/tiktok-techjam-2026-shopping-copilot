# Documentation Map

Use this page to choose the right document without reconstructing project state
from old reports.

## Start here

1. `../AGENTS.md` — operating rules for Codex and contributors
2. `current_status.md` — authoritative current checkpoint, evidence, and risks
3. `optimization_roadmap.md` — dependency-ordered whole-project route
4. `ablation_summary.md` — what was retained, rejected, and why

`../AGENTS.md` is the sole authority for the R0 failure taxonomy and the
offline-target/runtime boundary. `optimization_roadmap.md` is the sole authority
for dependency order. Workstream and experiment documents must reference those
definitions instead of creating local variants.

## Workstream execution

- `workstreams/DEVELOPER_A_CONTROL_PLANE.md` — A-side dialogue/state route
- `workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md` — B-side retrieval/ranking route
- `a_control_plane_handoff.md` — compatibility pointer for old A-side links
- `b_retrieval_ranking_handoff.md` — compatibility pointer for old B-side links

## Delivery

- `demo_and_submission_plan.md` — demo, report, video, packaging, and claim rules
- `../submission/README.md` — final-package staging checklist
- `../visualizer/README.md` — visual debugging and Agent/Evaluator view boundary

## Contracts and evaluation

- `competition_specification.md` — normalized Track 4 requirements
- `agent_api_contract.json` — agent interface contract
- `evaluation_config.json` — evaluator configuration
- `development_folds_v1.json` — deterministic Development folds
- `adr/0001-treat-public-holdout-as-exposed.md` — public-data decision record

## Historical evidence

Files named `b0_*` through `b7_*` and directories such as `b2_reports/` through
`b5_reports/` are experiment evidence. They do not override
`current_status.md`, and an implemented route is not necessarily enabled.

When ending a coding session, update only the documents whose truth changed and
leave a concise handoff using the template in the active workstream document.
