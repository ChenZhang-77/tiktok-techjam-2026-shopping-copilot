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

Current blocker: R0. Follow `optimization_roadmap.md` for the complete order.
Two important later guards: do not start A9 using only the current Top-K
candidate text, and do not change `RetrievalRequest` for query components
without the roadmap's coordinated contract step.
