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
bounded A11 runtime reached Development score `0.721420` with all four folds
positive. Do not repeat the obsolete “B not integrated”, “40 tests”, or
pre-A11 status from the historical handoff.

AB1 is complete. B8 was tested and reverted because Development-160 had zero
rejection-turn coverage; B9 is the next B-owned module after B8 review. Do not
change `RetrievalRequest` for query components without shared A/B evidence and
compatibility tests. A12 remains separately deferred.
