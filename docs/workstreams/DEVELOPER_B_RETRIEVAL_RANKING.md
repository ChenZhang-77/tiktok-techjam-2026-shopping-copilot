# Developer B Workstream - Retrieval / Ranking Plane

## 1. How to use this document

This is the standalone workstream brief for Developer B or a new coding-agent
conversation taking over the Retrieval / Ranking Plane.

This is the current implementation-phase allocation, not a permanent statement
about team members. If ownership changes, update both workstream documents and
the shared handoff status together.

At the start of a new conversation:

1. confirm the current Git branch and working tree,
2. read AGENTS.md completely,
3. read this document,
4. read README.md, docs/competition_specification.md,
   docs/agent_api_contract.json, docs/evaluation_config.json,
   docs/baseline_results.json, starter/agent.py, and
   evaluator/local_evaluator.py,
5. confirm the shared contracts with Developer A before changing them,
6. work on a feature/experiment branch, never directly on main,
7. do not push, merge, or open a PR unless the user explicitly asks.

AGENTS.md and the official participant kit override this document if they
conflict.

## 2. Mission

Developer B owns the 50,000-product side of the system:

    Developer A tells us what the user currently wants
      -> retrieve plausible products from the frozen catalog
      -> preserve target recall in the candidate pool
      -> rank the best candidate as high as possible
      -> report diagnostics and fallbacks to Developer A

The goal is a measurable, modular Retrieval / Ranking Plane with strong recall,
high ranking precision, predictable latency, reproducible caches, and
deterministic fallbacks.

Developer B optimizes primarily for:

- baseline parity before refactoring,
- higher HitRate@10,
- higher MRR without material HitRate loss,
- bounded latency and memory,
- inspectable score/rank provenance,
- robust fallback behavior.

## 3. Primary ownership

### 3.1 Catalog Store

Own catalog loading, normalization, indexing, and reusable product text.

The frozen catalog contains 50,000 unique parent_asin values and is read-only.
Never mutate catalog rows or inject mock ASINs.

Build product evidence across:

- title,
- categories,
- features,
- details,
- store,
- description,
- price only when present and parseable.

Observed data limitations:

- price is empty for about 78.9 percent of products,
- description is empty for about 47.8 percent,
- features is empty for about 10.4 percent,
- explicit details keys such as Color, Brand, Material, Style, and Size are
  sparse.

Consequences:

- never depend on details alone,
- never apply broad price filtering,
- put title/categories/features before long or sparse fields,
- expose catalog-valid ASIN checks to Response Guard,
- keep index/cache construction deterministic.

### 3.2 BM25 lexical retrieval

Preserve the official SQLite FTS5 BM25 baseline before changing behavior.

Required first result:

| Metric | Official baseline |
| --- | ---: |
| HitRate@10 | 0.125 |
| MRR | 0.068034 |
| MTTC | 9.81 |
| TechnicalScore | 0.10671 |

Refactoring must preserve:

- field-aware weighting,
- tokenization behavior,
- deterministic ordering,
- valid parent_asin output,
- response compatibility.

Only after parity:

- benchmark deeper retrieval than final top_k,
- expose route ranks/scores,
- support fusion/reranking candidates,
- measure initialization and query time.

Internal depth such as 80 to 150 is an experiment parameter, not a fixed truth.

### 3.3 Structured evidence

Structured scoring must use cross-field evidence rather than sparse details-only
filters.

Possible attributes:

- category,
- material,
- color,
- size,
- style,
- brand,
- budget,
- feature,
- use_case.

Policy:

- high-confidence, well-covered hard evidence may use a guarded filter,
- lower-confidence or sparse evidence becomes a ranking bonus/penalty,
- a filter that leaves too few candidates must relax,
- fill shortages from the unfiltered ranking,
- preserve which constraint was relaxed in diagnostics.

Developer A owns extraction/state truth. Developer B owns how supplied
constraints affect retrieval and ranking.

Developer A owns when and why per-turn Strategy values change. Developer B owns
the retrieval/fusion mechanics and supplies evidence-backed default values or
safe ranges. Neither side changes route-weight semantics alone.

### 3.4 Dense retrieval

Dense retrieval is a benchmark candidate, not a mandatory architecture choice.

The first lightweight benchmark may use:

    sentence-transformers/all-MiniLM-L6-v2

Alternative small models are allowed when they are available, measurable, and
better suited to product text.

If dense retrieval is implemented:

- define the exact product-text template,
- precompute 50,000 product embeddings,
- cache them locally,
- record model/revision, dimensions, dtype, normalization, and seed,
- verify cache/catalog compatibility,
- compute query embeddings from Developer A's distilled query,
- return Top-N semantic candidates with rank provenance,
- report build time, query time, memory, and cache size,
- fall back cleanly when model/cache loading fails.

Do not regenerate embeddings for every evaluation.
Do not introduce a hosted vector database for this 50,000-item in-memory task.
Do not commit generated embeddings unless explicitly approved and license-safe.

### 3.5 Candidate fusion

Compare lexical, dense, and structured routes on development data.

Weighted Reciprocal Rank Fusion is the first candidate because route raw-score
scales differ:

    fused_score(item) += route_weight / (RRF_K + rank)

Requirements:

- route weights and RRF_K are configuration, not scattered literals,
- deduplicate by parent_asin,
- preserve each route's rank provenance,
- handle a missing/failed route,
- keep an unfused result for ablation,
- tune only on development cross-validation,
- never tune from sealed holdout.

Do not assume RRF wins. A simpler route or calibrated alternative may be kept
when development evidence is stronger and complexity is lower.

### 3.6 Constraint-aware ranking

After recall is adequate:

- score candidate compatibility with active constraints,
- keep hard/soft confidence distinct,
- use current explicit intent above profile evidence,
- avoid double-counting the same field across routes,
- explain score provenance for visual/manual review,
- rerank only a bounded candidate pool.

Primary question:

    Does MRR improve without materially reducing HitRate@10?

### 3.7 Semantic reranking

Run and report at least one reproducible semantic-ranking experiment.

Possible path:

- distilled query/current state from Developer A,
- Top 30 or Top 50 candidates,
- lightweight local cross-encoder or other semantic scorer,
- deterministic fallback to constraint/fusion ordering.

Retain the semantic reranker only if development cross-validation supports it.
If it regresses, costs too much, or is infeasible:

- document the negative result,
- report latency/memory/cost,
- keep the local deterministic fallback,
- do not retain dead complexity for appearance.

An external paid LLM is optional and requires timeout, token accounting, cost
reporting, secret handling, and deterministic fallback.

### 3.8 Performance and cache behavior

Measure:

- catalog/index initialization time,
- per-query route latency,
- fusion/rerank latency,
- end-to-end retrieval/ranking latency,
- embedding/index cache size,
- peak or approximate memory,
- cache hit/miss/rebuild behavior,
- fallback count.

Do not invent a performance target without measurement. Compare each new path
to the current baseline and document the tradeoff.

### 3.9 RetrievalDiagnostics

Return enough information for Developer A's planner and clarification policy:

- route sizes,
- route availability/failure,
- fused size,
- filtered size,
- relaxed constraints,
- lexical/dense top-overlap,
- candidate diversity signals when available,
- route/fusion/rerank latency,
- cache state,
- fallback/degraded mode,
- short human-readable reason.

Diagnostics must never include evaluator-only labels or target information.

## 4. Files owned by this workstream

These are target locations, created only when responsibilities are real:

    starter/retrieval/catalog_store.py
    starter/retrieval/bm25.py
    starter/retrieval/structured.py
    starter/retrieval/dense.py
    starter/retrieval/fusion.py
    starter/retrieval/hybrid.py

    starter/ranking/constraint_scorer.py
    starter/ranking/profile_scorer.py
    starter/ranking/reranker.py

    starter/utils/timing.py
    scripts/build_dense_index.py
    scripts/run_ablation.py
    scripts/inspect_results.py

    tests/test_catalog_store.py
    tests/test_bm25_parity.py
    tests/test_structured.py
    tests/test_fusion.py
    tests/test_dense_fallback.py
    tests/test_reranker_fallback.py
    tests/test_retrieval_smoke.py

Do not create every file up front. Start with BM25 parity and one stable
retriever seam.

## 5. Explicit non-ownership

Developer B does not own:

- user-message state management,
- constraint extraction from conversation text,
- Intent Override state transitions,
- no-preference/asked-attribute tracking,
- Buying/Browsing classification logic,
- clarification-question policy,
- Response Guard policy,
- starter/agent.py orchestration.

Developer B may use fixture SessionState and Strategy objects. Do not implement
a second competing dialogue state machine inside retrieval/ranking files.

## 6. Shared contract with Developer A

### 6.1 Inputs expected from A

At minimum:

- distilled query,
- active constraints with attribute, normalized value, confidence, hard/soft
  status, and source turn,
- Buying/Browsing intent,
- Strategy,
- top_k,
- session/turn identifiers only when needed for diagnostics.

Never request:

- ground_truth,
- target ASIN,
- scenario_type,
- difficulty_bucket,
- intent_card,
- evaluator-only behavior.

### 6.2 Outputs returned to A

Candidate should preserve:

- parent_asin,
- route ranks,
- fusion score,
- constraint score,
- optional semantic-rerank score,
- enough provenance for manual inspection.

Stable seam:

    HybridRetriever.retrieve(query, state, strategy)
        -> candidates, diagnostics

Optional ranking seam:

    Reranker.rank(query, state, candidates, strategy)
        -> ranked_candidates

Developer B must not force Developer A to import retrieval implementation
internals.

### 6.3 Contract-change rule

Before changing a shared type or interface:

1. describe the need and expected caller impact,
2. update or add contract tests,
3. notify Developer A,
4. avoid simultaneous edits to the same shared file,
5. keep the change small and backward-compatible when possible.

## 7. Implementation order

### B0 - Shared baseline and contracts

- Reconfirm official baseline.
- Agree on Candidate, Strategy, and RetrievalDiagnostics.
- Use Python 3.10+.
- Confirm development split; keep holdout sealed.

### B1 - Catalog Store and BM25 parity

- Extract catalog loading/index setup behind a stable seam.
- Preserve baseline behavior.
- Add parity and deterministic-order tests.
- Record initialization and query time.

### B2 - Deeper lexical and structured evidence

- Benchmark deeper BM25 candidate pools.
- Add cross-field structured scoring.
- Add guarded filtering and relaxation.
- Report recall/ranking effects on development.

### B3 - Dense retrieval experiment

- Define product/query text.
- Build reproducible cache.
- Benchmark semantic recall.
- Test missing/corrupt cache fallback.
- Keep or reject based on development cross-validation.

### B4 - Fusion

- Benchmark RRF against single routes.
- Add dedup and route diagnostics.
- Record route overlap and latency.
- Keep the simplest evidence-supported method.

### B5 - Constraint and semantic ranking

- Add constraint-aware scoring.
- Evaluate a bounded semantic reranker.
- Measure MRR, HitRate, latency, memory, and fallback.
- Document negative results as well as positive ones.

### B6 - Integration and hardening

- Integrate Developer A's real Strategy/SessionState.
- Verify Buying/Browsing differences affect execution.
- Verify diagnostics support candidate-aware clarification.
- Run failure, cache, and reproducibility tests.

## 8. Required tests

At minimum:

- catalog loads 50,000 unique valid ASINs,
- frozen catalog is never mutated,
- BM25 refactor reproduces baseline ordering/metrics where expected,
- retrieval depth is configurable,
- structured evidence reads across all intended fields,
- sparse price/details do not empty broad result sets,
- hard-filter zero result relaxes safely,
- route outputs are deterministic,
- fusion handles missing routes and duplicates,
- Candidate provenance survives fusion/ranking,
- dense cache compatibility is checked,
- dense missing/corrupt cache reaches lexical fallback,
- semantic-reranker failure reaches fusion/constraint fallback,
- response contains enough candidates for Developer A to fill top_k,
- diagnostics contain no target/ground-truth data.

Tests must never use target labels as retrieval inputs.

## 9. Evaluation and manual review

Use named development experiments:

    ./scripts/start_experiment.sh bm25-depth-v1
    ./scripts/start_experiment.sh structured-v1
    ./scripts/start_experiment.sh dense-minilm-v1
    ./scripts/start_experiment.sh rrf-v1
    ./scripts/start_experiment.sh semantic-rerank-v1

For each run record:

- hypothesis,
- exact model/configuration,
- code/commit,
- development subset,
- HitRate@10 and MRR,
- scenario diagnostics,
- latency, memory, cache size,
- fallback/error count,
- keep/revert decision.

Use the visualizer to inspect why products rank where they do. Public target
labels may be shown to a human reviewer, but retrieval/ranking code must never
receive them as inputs.

Do not tune from sealed holdout or repeatedly inspect the full 200.

## 10. Handoff to Developer A

Provide:

- stable HybridRetriever and optional Reranker interfaces,
- Candidate and RetrievalDiagnostics definitions,
- fixture outputs for Buying and Browsing Strategies,
- configuration defaults and their experiment evidence,
- cache build/load instructions,
- latency/memory measurements,
- fallback behavior and failure fixtures,
- development ablation results,
- branch and commit SHA used for the handoff.

Developer A should be able to integrate without understanding retrieval
implementation details.

## 11. Definition of done for B

Developer B's workstream is ready for integration when:

- catalog access is deterministic and read-only,
- refactored BM25 preserves the official baseline before enhancements,
- structured evidence uses cross-field data and guarded filters,
- dense retrieval has a reproducible cache and lexical fallback,
- fusion is deterministic, deduplicated, and evidence-supported,
- constraint ranking improves or has a documented negative result,
- a semantic-ranking experiment is reproducible and retained only when useful,
- Candidate provenance and RetrievalDiagnostics are inspectable,
- latency, memory, and cache size are recorded,
- Developer A can integrate through stable seams,
- focused tests pass,
- development metrics and visual traces are recorded,
- no evaluator/data/label leakage exists,
- no changes were committed directly to, merged into, or pushed to main.

## 12. New-conversation status template

At the end of a work session, leave:

    Branch:
    Commit:
    Gate:
    Completed:
    Tests:
    Development metrics:
    Latency/memory/cache:
    Visual traces inspected:
    Shared-contract changes:
    Waiting on Developer A:
    Known risks:
    Next smallest step:
