# B Retrieval / Ranking Plane Handoff

## Status and provenance

- Workstream: B0-B7 complete.
- Branch: `patryk/track4-experiments`.
- Last retrieval-behavior commit: `5b66df5`.
- Frozen evaluation commit: `98d3325`.
- Final report: `docs/b7_final_public_run.json`.
- Final report SHA-256: `13ffaa619149e27f068961b66079ed494639e3d1a90645ae8bfa064b46a05b3b`.
- No push, merge, or direct change to `main` was performed by this workstream.

`docs/b7_freeze_manifest.json` is intentionally the immutable pre-run freeze
snapshot and therefore records the final run as pending. Completion and the
bound result are recorded in `docs/b7_final_public_summary.json`.

The frozen runtime default is the deterministic local structured path. Dense,
fusion, and semantic reranking remain reproducible experiments but are disabled
by default.

## Final Public Run

The only B-side Full-200 run was executed from the clean frozen commit
`98d3325` with:

```bash
.venv/bin/python -m experiments.evaluation_reporting \
  --split full --structured-filter \
  --output /private/tmp/b7-final-public.json
```

| Metric | Full-200 result |
| --- | ---: |
| HitRate@10 | 0.765 |
| MRR | 0.517355 |
| MTTC | 5.375 |
| Efficiency | 0.5625 |
| TechnicalScore | 0.650207 |

The run reported zero response exceptions, invalid payloads, or fallbacks. The
40-session public holdout had already been exposed by earlier A-side full runs,
so this is a non-confirmatory public snapshot. It was not followed by tuning,
and B did not run the holdout separately.

## Retained configuration and development evidence

The default pipeline is:

```text
Developer A distilled query and constraints
  -> in-memory SQLite FTS5 field-weighted candidate pool
  -> explicit hard/soft cross-field constraint ranking
  -> guarded structured filtering with deterministic relaxation/fill
  -> Candidate list plus RetrievalDiagnostics
```

On Development-160, the frozen structured route achieved HitRate@10 `0.7625`,
MRR `0.526989`, MTTC `5.30625`, and TechnicalScore `0.653222`. Its mean retrieval
latency was `36.870219 ms`, p95 was `82.687167 ms`, initialization was
`1252.970375 ms`, and process peak RSS was `574144512` bytes.

Key keep/reject decisions:

| Variant | HitRate@10 | MRR | TechnicalScore | Decision |
| --- | ---: | ---: | ---: | --- |
| Official weak BM25 | 0.125 | 0.068034 | 0.106710 | comparison only |
| Pure lexical | 0.71875 | 0.485851 | 0.617005 | reject as default |
| Structured, no guarded filter | 0.7625 | 0.522693 | 0.651683 | ablation base |
| Structured, guarded filter | 0.7625 | 0.526989 | 0.653222 | retain |
| Dense only | 0.3375 | 0.160501 | 0.272650 | reject as default |
| RRF fusion, k=10 | 0.75 | 0.486620 | 0.637611 | reject as default |
| Semantic rerank, top 30 | 0.78125 | 0.484162 | 0.656499 | reject as default |

Semantic reranking improved aggregate HitRate slightly but reduced MRR,
regressed the intent-override fold/scenario evidence, and added substantial
latency and memory. It is kept only as an optional reproducible ablation and
failure fixture.

## Stable integration seam

Developer A calls:

```text
HybridRetriever.retrieve(request: RetrievalRequest) -> RetrievalResult
Agent.respond(session_id, user_message, turn, top_k) -> public response dict
```

`RetrievalRequest` accepts only session/turn identifiers, distilled query,
intent, Strategy, active/rejected/no-preference/asked constraints, and `top_k`.
Recursive validation rejects evaluator labels such as target ASIN,
`scenario_type`, `difficulty_bucket`, or ground truth.

`Candidate` now carries `parent_asin`, score/source, route/rank diagnostics, and
optional evidence text. `RetrievalDiagnostics` exposes route sizes and overlap,
stage latency, structured-filter and relaxation evidence, route failures,
rerank pool size, cache state, ranking pool sizes, and fallback state. These
additions are backward-compatible dataclass fields with defaults.

Ownership remains unchanged: A owns session state, intent and constraint
extraction, Strategy changes, clarification, response guard, and orchestration;
B owns catalog retrieval, structured evidence, fusion/ranking mechanics,
optional semantic scoring, and retrieval diagnostics. Route-weight semantics
must not be changed by either side alone.

## Reproduction and verification

Default runtime and Development-160 verification require no model download:

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m experiments.evaluation_reporting \
  --split development --structured-filter \
  --output results-structured-development.json
```

Optional semantic cache reproduction downloads only the six runtime files for
the pinned `cross-encoder/ms-marco-MiniLM-L2-v2` revision
`1b5cd67b15209f24824c50370e0397743aa9b787`:

```bash
.venv/bin/python scripts/cache_reranker.py --allow-model-download
.venv/bin/python -m experiments.evaluation_reporting \
  --split development --semantic-rerank --rerank-limit 30 \
  --output results-semantic-development.json
```

After caching, loading is local-only. The clean cache contains six runtime
files and occupies `63416932` logical bytes. The semantic pool is capped at 30,
uses batch size 16 and maximum length 256, and has a 5000 ms process-enforced
timeout.

Focused fallback checks:

```bash
.venv/bin/python -m unittest \
  tests.test_dense_fallback \
  tests.test_fusion \
  tests.test_reranker \
  tests.test_agent_smoke
```

Missing/corrupt dense caches, failed fusion routes, invalid semantic scores,
backend errors, and semantic timeouts all return a deterministic local
fallback. A timed-out CrossEncoder worker is terminated and joined; the exact
pre-rerank Candidate order is preserved.

## Risks and next integration checks

- `intent_override` remains the weakest final scenario by TechnicalScore
  (`0.598857`); changing it belongs primarily to A-side policy and must not be
  tuned against this exposed Full-200 result.
- The Full-200 result is not sealed evidence because the public holdout was
  already exposed.
- Optional semantic process memory is not fully represented by parent-process
  `ru_maxrss`; the historical in-process B5 peak was about 1.30 GB.
- Experiment mode selection is repeated between shell parsing and Python
  retriever construction. Review accepted this as non-blocking for the freeze;
  use a registry if another mode is added.
- Profile weighting remains disabled (`profile_weight = 0.0`) because explicit
  current intent takes precedence and session-only profile evidence was not
  strong enough to justify another scoring source.

Developer A's next safe check is contract-level integration against
`HybridRetriever.retrieve`, followed by the existing full test suite. Do not
rerun or tune from Full/Holdout while integrating this frozen B configuration.
