# B-side Handoff Compatibility Pointer

This filename is retained so old links do not break. The earlier build/freeze
handoff is historical evidence and must not be used as the next optimization
plan.

For a new B-side Codex conversation, read:

1. `../AGENTS.md`
2. `current_status.md`
3. `optimization_roadmap.md`
4. `workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md`
5. `ablation_summary.md`

Current reality: the retained default is structured retrieval/ranking plus
bounded A11 extraction and B9 local dense/RRF only for a typed broad-Browsing
gate. Global dense/RRF and CrossEncoder remain rejected ablations; an actual
LLM ranker is absent. Any new route must follow the gates in the current B-side
workstream rather than widening B9 implicitly.

AB1 is complete. B8 was reverted after Development-160 supplied zero rejection
turns. B9 is retained at `7f520ba`: only Browsing changed, all four folds were
non-regressing, and its material startup/memory cost is recorded in
`b9_conditional_dense_evidence.md`. B10a Top-3 and Top-5 candidates were then
rejected for MRR and TechnicalScore regressions; the B9 default remains exact.
See `b10a_constraint_rerank_evidence.md`. B10b is not justified without new R0
evidence; B11/B12 remain prerequisite-gated.
