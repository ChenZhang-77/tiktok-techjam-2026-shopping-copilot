# A-side Handoff Compatibility Pointer

This filename is retained so old links do not break. The earlier build-phase
handoff is archived and must not be used as current project status.

For a new A-side Codex conversation, read:

1. `../AGENTS.md`
2. `current_status.md`
3. `optimization_roadmap.md`
4. `workstreams/DEVELOPER_A_CONTROL_PLANE.md`
5. `ablation_summary.md`

Current reality: A and B are integrated; the stable seam is
`HybridRetriever.retrieve(request: RetrievalRequest) -> RetrievalResult`; the
verified checkpoint recorded in `current_status.md` passed 148 tests. Do not
repeat the obsolete “B not integrated” or “40 tests” status from the historical
handoff.

Current blocking route: R0 -> A8 persistent `IntentAssessment` -> AB0
`DecisionEvidence` availability -> A9 should-ask -> A10a Candidate question
value -> A10b internal `QueryPlan`.
Do not start A9 using only the current Top-K candidate text, and do not change
`RetrievalRequest` for query components without an A10c/AB1 coordination step.
