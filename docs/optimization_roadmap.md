# Shopping Copilot — Release Roadmap

## Current objective

Deliver [Plan One / optional Plan Two](final_release_plan.md), not another open-ended
optimization cycle. The selected main source is Chen `0bd3375` → remote
`yuqing`; local `llm` → remote `llm` retains the verified optional reranker.
[Current status](current_status.md) owns metrics and [branch inventory](branch_inventory.md)
owns freeze/recovery details.

## Execution order

1. **Select and verify source — complete:** same fixed Development-160 population,
   hashes, B9 parameters and synthetic prewarm; compare original P0 and Chen,
   record all four folds/scenarios and gained/lost sessions.
2. **Organize release:** freeze unfinished experiments, reconcile README/status/
   navigation/workstreams, run full tests and independent Standards/Spec review.
3. **Publish source:** fast-forward only to authorized `llm` and `yuqing`.
   Recheck remote heads immediately before push; stop on divergence; verify
   remote SHAs afterward. Do not update `main`.
4. **Next delivery step, not claimed complete here:** regenerate an independent
   Plan One package from the selected source. Reuse P0 packaging ideas only after
   updating its copied runtime, provenance and claims. Test clean-start imports,
   valid responses, required local model assets and missing-asset fallback.
5. **Optional Plan Two packaging:** separately wire the exact F2 reranking recipe
   with explicit mode selection, budgets and no-key/error fallback. Do not enable
   A13 or A14 selectors along with it. Confirm host/network/API eligibility.
6. **Final artifacts:** factual contributions, licenses/attribution, report,
   demo/video and required submission metadata; rehearse the actual package.

Publishing a source branch does not mark steps 4–6 complete.

## Frozen optimization backlog

Do not automatically resume A13 AI-silver, valid-34 repair, semantic Candidate,
A14 counterfactual/selector work, A12 profile, B11 recall, B12 depth, or new model
sweeps. See the freeze table and reopening gates in
[final release plan](final_release_plan.md). Their old design documents are
historical specifications, not the active queue.

The previous detailed A/B dependency map remains recoverable through
[the recorded pre-release commits](branch_inventory.md). Retained and rejected
behavior decisions still live in [ablation summary](ablation_summary.md) and
the original hash-bound experiment records; do not move those records.

## Non-negotiable evaluation and ownership rules

- Fixed Development-160 and its four folds only; no Full-200/holdout tuning.
- Never pass target/ground-truth/scenario/future-turn evidence into runtime.
- Preserve official evaluator, catalog and shared A/B contracts.
- No parameter or prompt tuning hidden in a release comparison.
- Any later behavior experiment needs one primary variable, a predeclared
  keep/revert gate, session/scenario/fold evidence and latency/fallback accounting.
- Developer A owns state and questions; B owns retrieval/ranking. No unilateral
  contract or route-weight changes. Full rules: `../AGENTS.md`.
