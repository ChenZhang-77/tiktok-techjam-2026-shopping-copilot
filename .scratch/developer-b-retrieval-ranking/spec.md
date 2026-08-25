Status: ready-for-agent

# Developer B Retrieval / Ranking Plane

## Problem Statement

The Shopping Agent's Control Plane now produces strong conversational state and
strategy decisions, but catalog retrieval and ranking remain embedded in the
Agent. This prevents independent parity testing, route-level diagnostics,
reliable fallbacks, and measured experiments with structured, semantic, fusion,
and reranking approaches. The current development score is strong, so changing
retrieval without a protected seam risks losing proven behavior.

## Solution

Build a modular Retrieval / Ranking Plane behind one stable high-level seam. It
will first reproduce the current lexical and constraint-aware behavior exactly,
then add independently measurable routes and ranking stages only when fixed
Development Set cross-validation supports them. Every optional path will expose
Candidate Provenance, operational diagnostics, bounded resource use, and a
deterministic local fallback. The Control Plane will continue to own dialogue
state, intent routing, clarification, and response guarding.

## User Stories

1. As a shopper, I want recommendations to preserve the current strong behavior while the search internals are modularized, so that engineering changes do not make the experience worse.
2. As a shopper with precise buying constraints, I want catalog evidence from all useful product fields to influence ranking, so that matching products appear in the Top 10.
3. As a shopper who changes intent, I want stale product evidence discarded, so that recommendations follow my current request.
4. As a browsing shopper, I want broad but relevant candidates, so that clarification and later turns can converge without premature filtering.
5. As the Control Plane, I want one stable retrieval interface, so that I do not depend on retrieval implementation details.
6. As the Control Plane, I want route and fallback diagnostics, so that strategy and clarification can react to actual candidate evidence.
7. As a developer, I want catalog loading and indexes to be deterministic and read-only, so that experiments are reproducible and catalog integrity is protected.
8. As a developer, I want lexical parity tests before enhancements, so that regressions are attributable to a specific experiment.
9. As a developer, I want structured filters to relax safely, so that sparse catalog fields never eliminate all useful candidates.
10. As a developer, I want semantic retrieval to use a reproducible local cache, so that evaluation does not depend on a hosted vector database.
11. As a developer, I want every optional model stage to fail back to deterministic local ranking, so that the Shopping Agent remains usable offline.
12. As a developer, I want route ranks and score evidence preserved through fusion and ranking, so that recommendation movement is inspectable.
13. As an experiment owner, I want overall and per-scenario ablations on fixed cross-validation folds, so that retained changes have evidence beyond one aggregate score.
14. As an experiment owner, I want initialization time, query latency, memory, cache size, and fallback counts recorded, so that score gains can be judged against operational cost.
15. As a competition reviewer, I want reproducible semantic-ranking evidence even when the result is negative, so that the architecture reflects measured decisions rather than decorative complexity.
16. As a competition reviewer, I want evaluation-set exposure disclosed accurately, so that reported claims remain defensible.

## Implementation Decisions

- The sole Control Plane integration seam is a Hybrid Retriever operation that accepts the existing Retrieval Request and returns the existing Retrieval Result.
- The Control Plane retains ownership of conversation state, constraint extraction, Buying/Browsing classification, Strategy selection, clarification, and response guarding.
- The Retrieval / Ranking Plane owns catalog access, route execution, structured evidence, filtering and relaxation, candidate fusion, ranking, Candidate Provenance, operational diagnostics, and deterministic fallbacks.
- B0 locks the latest A-side Development Set metrics and contract behavior before retrieval code changes.
- B1 extracts the current catalog and BM25 behavior behind the shared seam with exact ordering and metric parity before enhancements.
- Lexical, structured, and semantic retrieval remain independently observable Routes; no Route is retained merely because it was implemented.
- Structured evidence uses all useful catalog fields and treats sparse attributes as ranking evidence unless confidence and coverage justify guarded filtering.
- Weighted reciprocal-rank fusion is the first fusion candidate because route score scales are not assumed comparable; its weights and constant are experiment configuration.
- Dense retrieval uses a small local model and a reproducible cache when benchmarked; it must not require a hosted vector database or per-evaluation index rebuild.
- Semantic reranking is bounded to a small Candidate Pool and must fall back to the pre-rerank order on failure.
- Profile influence starts disabled and is outside the retained path unless its own Development Set ablation succeeds without overriding explicit current intent.
- Generated embeddings, checkpoints, and large experiment outputs remain uncommitted unless separately approved and license-safe.
- The Exposed Holdout is not used for B-stage selection. One Final Public Run is allowed after configuration freeze and is reported as non-confirmatory.

## Testing Decisions

- Protect behavior at the highest seam with Agent response tests and the official evaluator on the Development Set.
- Test the Hybrid Retriever through its public request/result contract rather than importing internal route implementation details from the Control Plane.
- Require deterministic catalog cardinality, ASIN validity, ordering, deduplication, and read-only behavior.
- Require BM25 parity at candidate-order and Development Set metric levels before B1 is complete.
- Test guarded-filter relaxation, result filling, missing routes, incompatible caches, corrupt caches, semantic-reranker failure, and empty queries as externally visible behavior.
- Preserve the repository's standard-library unittest style and extend existing contract and Agent smoke-test patterns.
- Record overall and per-scenario HitRate@10, MRR, MTTC, Efficiency, and TechnicalScore for every meaningful retained experiment.
- Use fixed folds within the Development Set for feature selection; do not run holdout or full evaluation during ordinary B development.
- Treat exact metric parity as the B0/B1 gate; later features require ablation evidence and no unexplained scenario regression.

## Out of Scope

- Conversation-state management and constraint extraction.
- Buying/Browsing classification and Strategy policy ownership.
- Clarification-question selection and Response Guard policy.
- Mutation of the catalog, evaluator, public labels, split manifest, or scoring logic.
- Public-label or target-ASIN access at Agent runtime.
- Full foundation-model training or fine-tuning.
- Hosted industrial vector databases and production infrastructure.
- Multimodal processing, shopping transactions, and scored-path UI work.
- Repeated holdout or full-set tuning.

## Further Notes

- The independently reproduced A-side Development Set baseline is HitRate@10
  0.7625, MRR 0.522693, MTTC 5.31875, Efficiency 0.568125, and TechnicalScore
  0.651683, with 40 standard-library tests passing.
- Buying and Intent Override currently have the lowest scenario HitRate@10
  (0.71875 and 0.708333), so they are priority diagnostics for B improvements;
  Browsing and Boundary are regression guards.
- The official weak baseline and the current A-side baseline are different
  comparison points. B0/B1 parity is measured against the current A-side
  baseline, while final reports should retain the official weak baseline row.
