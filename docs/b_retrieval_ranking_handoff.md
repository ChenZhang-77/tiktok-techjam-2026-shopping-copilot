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

Current reality: the retained default is lexical retrieval plus structured
scoring. Dense retrieval, RRF, and global semantic reranking remain documented
ablations and are disabled by default. Any new route must follow the gates in
the current B-side workstream rather than enabling old experiments globally.

Current blocker: R0. Follow `optimization_roadmap.md` for the complete order and
the B workstream for B-local gates. B9 remains Browsing-first for literal Track
4 alignment; stable Buying is a separate secondary hypothesis.
