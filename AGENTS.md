# AGENTS.md - TikTok TechJam 2026 Track 4

## 1. Purpose and authority

This repository targets Track 4, Shopping Copilot: AI Conversational Search and
Recommendations.

This file is an operational contract for coding agents and the two-person team.
It records stable constraints, the evidence-based experiment flow, and the
submission gates. It is deliberately not a frozen architecture specification.
Implementation details, model choices, weights, and module boundaries remain
hypotheses until experiments support them.

Before changing code, read:

- README.md
- docs/competition_specification.md
- docs/agent_api_contract.json
- docs/evaluation_config.json
- docs/baseline_results.json
- docs/submission_rules.md
- starter/agent.py
- evaluator/local_evaluator.py

The official participant kit and competition PDF override this file if they
conflict. Never treat public labels or evaluator implementation details as
runtime Agent inputs.

## 2. Competition contract

The evaluator calls:

    reset(session_id, user_profile)
    respond(session_id, user_message, turn, top_k)

respond must return the three required fields below. usage is optional when no
model is used; when present, it must follow the shown shape.

    {
        "message": str,
        "ask_attribute": str | None,
        "recommendations": [{"parent_asin": str}, ...],
        "usage": {
            "prompt_tokens": int,
            "completion_tokens": int,
        },
    }

Hard constraints:

- Maximum 10 turns per session.
- Only the first 10 valid unique parent_asin values are scored.
- The frozen catalog is read-only. Never mutate it or inject mock ASINs.
- Agent behavior must use only reset and respond inputs plus the frozen catalog.
- Do not read ground_truth, scenario_type, difficulty_bucket, intent_card,
  behavior, evaluator internals, or target ASINs at runtime.
- Do not hardcode public-set answers.
- Do not modify evaluator scoring or public labels to improve reported scores.
- The scored path is text-only. Do not add multimodal processing.
- Do not prioritize UI for scoring. A lightweight demo UI is optional, but the
  scored backend/headless path must stand alone.
- Do not build heavy external vector databases, full-model training,
  foundation-model fine-tuning, or production infrastructure.
- Keep all retrieval and ranking lightweight and local/in-memory where practical.
- Keep API keys and private data out of source, logs, artifacts, and commits.

Official metrics:

    Efficiency = clip((11 - MTTC) / 10, 0, 1)

    TechnicalScore =
        0.50 * HitRate@10
        + 0.30 * MRR
        + 0.20 * Efficiency

Official weak BM25 baseline:

| Metric | Value |
| --- | ---: |
| HitRate@10 | 0.125 |
| MRR | 0.068034 |
| MTTC | 9.81 |
| Efficiency | 0.119 |
| TechnicalScore | 0.10671 |

## 3. Verified participant-kit facts

These observations come from the frozen catalog, public set, and evaluator.
They are data-audit facts, not permission to exploit the public simulator.

### 3.1 Dataset integrity

- Catalog: 50,000 rows and 50,000 unique parent_asin values.
- Public set: 200 samples, 200 unique targets, all present in the catalog.
- Scenario mix: 80 Buying, 80 Browsing, 30 Intent Override, 10 Boundary.
- The competition PDF states that public and private evaluation use separate
  users and target products.

The public set confounds scenario and difficulty:

- Buying is always easy.
- Browsing and Boundary are medium.
- Intent Override is hard.

Therefore a per-scenario gain is diagnostic, not proof that routing alone caused
the improvement. Difficulty and initial disclosure differ at the same time.

### 3.2 Catalog coverage

Important observed missingness:

- price is empty for about 78.9 percent of products.
- description is empty for about 47.8 percent.
- features is empty for about 10.4 percent.
- details is usually present, but explicit Color, Brand, Material, Style, and
  Size keys are sparse.

Consequences:

- Never make price or a details-only attribute a broad hard filter.
- Extract evidence across title, categories, features, details, store, and
  description.
- Put title, categories, and features before sparse or long fields in dense text.
- Relax filters when coverage or confidence is low.

### 3.3 Public clarification behavior

In the current public kit, the approximate fraction of sessions where an
attribute can reveal an undisclosed constraint is:

| Attribute | Observed availability |
| --- | ---: |
| category | 0 percent |
| brand | 0 percent |
| budget | 0 percent |
| size | 3.8 to 10 percent |
| use_case | 1.2 to 10 percent |
| style | 6.2 to 13.3 percent |
| material | 63.3 to 80 percent |
| feature | 95 to 97.5 percent |
| other | 100 percent |

Do not hardcode these percentages or optimize only for this simulator. Use them
to reject a known-bad fixed question order. A good policy must remain
candidate-aware and robust to private-session paraphrasing.

### 3.4 User profile limits

The supplied profile is an anonymized weak prior:

- purchase_frequency is constant in the current public set.
- preference_tags are generic and have uneven target-text overlap.
- rating_style and average_prior_rating are not direct product constraints.

Start profile ranking weight at zero. Add profile influence only after a
development cross-validation ablation improves results without overriding
explicit current intent.

The evaluator provides no stable cross-session user identity. Implement
session-level distilled preferences. Do not claim true long-term cross-session
memory unless a separate demo extension implements it and clearly documents
that it is outside the scored contract.

## 4. Track 4 alignment

The solution must visibly address the four pillars in the competition PDF.

### 4.1 Intent routing and hybrid pipeline

- Detect Buying versus Browsing from observable messages and current state.
- Buying should favor precise constraint-aware retrieval.
- Browsing should favor broader semantic recall and useful clarification.
- Route decisions must change actual weights, depth, filters, or ranking.
- Combine lexical, category/structured, and semantic evidence. The exact route
  contributions remain experimental.

### 4.2 Multi-turn scenario evolution

- Accumulate current constraints across turns.
- Detect Intent Override and deactivate stale conflicting intent.
- Track no-preference responses and do not repeat rejected questions.
- Always build queries from current distilled state, never blind full-history
  concatenation.

### 4.3 Dynamic context programming

- Keep raw history for audit.
- Keep active, overridden, rejected, and no-preference state separately.
- Adapt retrieval depth, route contribution, filter strictness, and question
  choice from current evidence and diagnostics.
- Use session-level preference distillation; document the lack of stable
  cross-session identity as a limitation.

### 4.4 Product and efficiency evaluation

- Optimize HitRate@10, MRR, and MTTC together.
- Report overall and per-scenario metrics.
- Report token use, latency, fallback behavior, and reproducibility.
- Demonstrate both normal behavior and at least one failure or degraded path.

Proactive clarification and semantic ranking are part of the core Track 4 story,
not decorative late-stage extras. The project must run and report a reproducible
semantic-ranking experiment. Retain that path only if development
cross-validation supports it; otherwise document the negative result or
infeasibility and keep the explicit local-scoring fallback. An external paid LLM
is not required. A local cross-encoder, embedding model, or other measured
semantic ranker is acceptable.

## 5. Target architecture - an experiment hypothesis

Start with one ShoppingAgent and replaceable internal capabilities:

    User message
      -> state/context update
      -> Buying/Browsing route
      -> strategy selection
      -> lexical / semantic / structured retrieval
      -> evidence-based fusion
      -> constraint-aware semantic ranking
      -> clarification decision
      -> response guard

This is not permission to build every box before measuring one vertical slice.
Keep a component only when it:

- is required by the public API or Track 4 scope,
- improves development cross-validation metrics and later survives the
  one-time sealed holdout check,
- improves robustness or reproducibility,
- or is necessary to demonstrate a PDF pillar clearly.

Prefer a small stable interface over many speculative modules.

Suggested seams:

- SessionState: current intent, history, active constraints, overridden
  constraints, no-preference attributes, asked attributes, prior strategy.
- Strategy: route contributions, depth, filter policy, clarification decision,
  and a human-readable reason.
- Candidate: parent_asin plus score/rank provenance.
- RetrievalDiagnostics: route sizes, overlap, filter relaxation, fallbacks,
  and latency.
- HybridRetriever.retrieve(query, state, strategy).
- Reranker.rank(query, state, candidates, strategy).

Keep starter/agent.py focused on orchestration. Do not freeze exact dataclass
fields or create modules with no real responsibility.

## 6. State and context rules

### 6.1 Constraint handling

Recognize at minimum:

- category
- material
- color
- size
- style
- brand
- budget
- feature
- use_case

Preserve raw phrases and source turns. When classification is uncertain, retain
the phrase as soft feature evidence instead of discarding it.

Distinguish hard constraints from soft preferences. Hard filtering is allowed
only with high confidence and sufficient catalog coverage. If a filter leaves
too few candidates, relax the lowest-confidence constraint and convert it into
a ranking signal.

### 6.2 Intent Override

On clear override language:

1. identify the new value,
2. deactivate conflicting prior values,
3. preserve history for debugging,
4. rebuild the query from active state,
5. discard stale candidate continuity,
6. record the override event.

Never search old and new conflicting values together.

### 6.3 Boundary and no preference

When the user reports no preference:

1. mark the attribute as no-preference,
2. deactivate conflicting soft state when appropriate,
3. do not ask the same attribute again,
4. continue recommending from remaining evidence.

## 7. Retrieval and ranking

### 7.1 Baseline lexical route

Refactor the official SQLite FTS5 BM25 only after baseline parity is protected
by tests and an evaluator result. Preserve field-aware weighting and exact
response behavior until the modular seam is proven.

Retrieve deeper than the final top 10 when testing fusion or reranking. Treat
depth such as 80 to 150 as a benchmark candidate, not a permanent default.

### 7.2 Structured evidence

Structured scoring must combine evidence across all useful catalog fields.
Details-only SQL-style filtering is insufficient because explicit structured
keys and price are sparse.

Use:

- guarded filtering for high-confidence, well-covered hard constraints,
- ranking bonuses for lower-confidence or sparsely represented evidence,
- fallback filling from an unfiltered ranking when fewer than top_k remain.

### 7.3 Dense retrieval

Dense retrieval is a candidate path, not a foregone architecture decision.
sentence-transformers/all-MiniLM-L6-v2 may be the first lightweight benchmark,
but it must compete with lexical and structured baselines.

If enabled:

- precompute and cache catalog embeddings,
- build text with high-signal fields first,
- report model name, dimensions, cache size, build time, and query latency,
- fail safely to lexical plus structured retrieval,
- avoid external vector databases unless local measurement proves a need.

### 7.4 Fusion

Weighted Reciprocal Rank Fusion is the first fusion candidate because route
score scales differ. RRF_K and route weights are experiment parameters, not
truths.

Tune parameters only on the development subset. Never inspect the holdout after
every parameter change. Preserve an unfused route result for ablation.

### 7.5 Semantic and constraint ranking

Separate retrieval recall from ranking precision.

Recommended evidence order:

1. deterministic constraint-aware ranking,
2. dense similarity if already available,
3. lightweight local semantic reranker on a small candidate pool,
4. external LLM only when measured gain justifies latency, cost, and failure
   risk.

Never rerank the entire 50,000-item catalog. If reranking fails, return the
pre-rerank order.

### 7.6 Profile personalization

PROFILE_WEIGHT starts at 0.00.

Profile evidence may be added only as a small soft signal after a development
cross-validation ablation. Explicit current user instructions always dominate
historical or aggregate tags.

## 8. Clarification policy

Clarification does not replace recommendation. Unless no candidates exist,
return the current best valid recommendations and optionally ask one useful
question in the same response.

### 8.1 Required first policy

Do not use the old fixed orders category/budget/size/material/feature or
use_case/style/feature/material.

Use this evidence-based order:

1. choose feature or material when the current candidate pool shows that the
   attribute can partition plausible candidates,
2. choose color, style, size, use_case, brand, budget, or category only when
   current state and candidate evidence make the question informative,
3. use other when no typed attribute is clearly informative,
4. never repeat a no-preference or exhausted attribute.

The policy must not hardcode public sample IDs, target values, or the observed
availability table.

### 8.2 Over-generality

Treat proactive guidance as P1:

- detect an overloaded or low-confidence candidate pool,
- stop adding weak retrieval branches when they only add noise,
- select a question that meaningfully partitions the pool,
- still return safe current top candidates for early-hit opportunity,
- record why clarification was chosen.

Simple entropy, value diversity, or expected candidate reduction is sufficient.
Do not build an LLM reflection agent.

## 9. Failure handling and response guard

Required fallbacks:

| Failure | Fallback |
| --- | --- |
| Dense model/cache unavailable | BM25 plus structured scoring |
| Semantic reranker error | Fusion or lexical ordering |
| Optional LLM timeout | Deterministic parser/ranker |
| Parser uncertain | Preserve raw phrase as soft feature |
| Hard filter empties pool | Relax filter |
| Fewer than top_k candidates | Fill from unfiltered ranking |
| Duplicate or invalid ASIN | Drop while preserving order |
| Invalid ask_attribute | None or safe allowed fallback |
| Expensive stage risks timeout | Skip it and record fallback |

Before returning, validate:

- message is a string,
- ask_attribute is allowed or None,
- recommendations is a list,
- ASINs exist in the frozen catalog,
- ASINs are unique and ordered,
- at most top_k are returned,
- when usage is present, its values are non-negative integers.

Agent.respond should not leak an exception when a safe fallback exists.

## 10. Testing

Minimum tests:

- state accumulates constraints without duplicates,
- provenance is preserved,
- Intent Override deactivates stale intent,
- distilled query excludes overridden values,
- no-preference attributes are not asked again,
- clarification does not suppress valid recommendations,
- fusion is deterministic and deduplicated,
- missing routes are handled,
- empty hard filters recover candidates,
- response guard removes invalid/duplicate ASINs and fills safely,
- Agent reset and multi-turn respond always satisfy the public schema,
- dense/reranker/optional-LLM failures reach deterministic fallbacks.

Test logic must never depend on ground_truth.

## 11. Evaluation protocol

### 11.1 Baseline gate

Before feature work:

1. reproduce docs/baseline_results.json,
2. save the exact output and environment,
3. preserve evaluator and public data unchanged,
4. ensure refactoring maintains baseline parity.

### 11.2 Public-set overfitting control

Create one deterministic, scenario-stratified split:

- development: 160 sessions
  - 64 Buying
  - 64 Browsing
  - 24 Intent Override
  - 8 Boundary
- holdout: 40 sessions
  - 16 Buying
  - 16 Browsing
  - 6 Intent Override
  - 2 Boundary

Generate the split once before experiments. Within each scenario, sort samples
by SHA256 of the UTF-8 string techjam-2026-public-split-v1, a NUL separator, and
sample_id; allocate the first required count to holdout and the rest to
development. Check in the script and a sample-ID-only manifest so every agent
reproduces the same split without copying labels into Agent inputs.

Rules:

- Tune models, weights, depths, and heuristics only on development.
- Use fixed cross-validation folds inside development for feature selection.
- Open holdout exactly once, after architecture and parameters are frozen.
- Do not keep, revert, or retune a feature based on holdout results.
- Do not move samples between subsets after seeing results.
- Do not expose either subset's labels to Agent runtime.
- Treat small per-scenario holdout counts as directional, especially Boundary.
- After the one-time holdout check, run the full official 200 for final public
  reporting. Do not tune further from either result.
- Repeated runs are for stochastic stability or latency, not repeated tuning on
  the same labels.

Any post-holdout correctness change invalidates the confirmatory status and must
be disclosed. The fixed holdout remains sealed during ordinary development.

### 11.3 Experiment records

Each experiment must record:

- commit SHA and dirty/clean state,
- dataset subset and sample count,
- configuration and model identifiers,
- overall HitRate@10, MRR, MTTC, Efficiency, and TechnicalScore,
- per-scenario metrics,
- token use and latency when relevant,
- fallback/error counts,
- hypothesis, result, and keep/revert decision.

One additional hit changes overall HitRate by 0.005. Do not present a tiny
public-set delta as strong evidence without robustness, ablation, and
development cross-validation support.

Every feature must answer:

- What improved?
- Which scenario changed?
- What regressed?
- What did it cost?
- Did the gain survive development cross-validation?

## 12. Implementation gates

### Gate 0 - Baseline and experiment protocol

- Official baseline reproduced.
- Development/holdout split frozen.
- Result recording works.
- No evaluator or data mutation.

### Gate 1 - Stateful lexical vertical slice

- Existing BM25 remains valid.
- State accumulation works.
- Override and no-preference behavior work.
- Distilled queries exclude stale intent.
- Data-aware clarification returns recommendations plus a useful question.
- Unit tests and development evaluation pass.

### Gate 2 - Hybrid recall

- Structured scoring uses cross-field evidence.
- Dense retrieval is benchmarked, not assumed.
- Fusion and fallbacks are deterministic.
- Primary target is development cross-validation HitRate@10 improvement.

### Gate 3 - Ranking and semantic evidence

- Constraint-aware ranking is measured.
- At least one semantic-ranking candidate is evaluated reproducibly and retained
  only if development cross-validation supports it; negative results and the
  explicit local-scoring fallback are documented.
- Profile influence remains off unless its own ablation passes.
- Primary target is MRR improvement without material HitRate loss.

### Gate 4 - Adaptive orchestration

- Buying/Browsing route changes execution.
- Over-generality triggers useful proactive guidance.
- Candidate repetition and diagnostics affect strategy.
- Override rebuilds state and retrieval.
- Primary target is lower MTTC / higher Efficiency without recall regression.

### Gate 5 - Freeze, harden, and submit

- Architecture and parameters frozen.
- Fixed holdout opened exactly once without subsequent tuning.
- Full 200-session official evaluation run for final reporting.
- Tests, clean-start setup, fallbacks, and ablations pass.
- PDF deliverables and judging evidence complete.

## 13. Collaboration

The two-person team assigns ownership per experiment rather than permanently
binding people to modules. Agree on public interfaces before parallel work.
Avoid simultaneous edits to starter/agent.py or shared contracts.

Useful collaboration seams:

    HybridRetriever.retrieve(query, state, strategy)
        -> candidates, diagnostics

    Reranker.rank(query, state, candidates, strategy)
        -> ranked_candidates

Use retrieval stubs and state/strategy fixtures so work can proceed
independently. Coordinate shared-contract changes before merging. Follow gates
in order; the team owns the day-by-day schedule and must reserve time for
freeze, ablation, documentation, rehearsal, and packaging.

## 14. Git rules

- Work only on feature/experiment branches.
- Never commit directly to main.
- Never merge to main or push a branch unless the user explicitly asks.
- Keep main at the cloned baseline until an experiment is approved.
- Make small, tested commits.
- Do not combine architecture refactoring and metric tuning in one large commit.
- Do not format or modify unrelated files.
- Do not commit catalog files, embeddings, checkpoints, results containing
  private data, API keys, or local environment files.

## 15. Reproducibility and official deliverables

### 15.1 Repository documentation

The final README must include:

- project overview and Track 4 problem framing,
- setup and installation,
- exact reproduction steps,
- architecture and model choices,
- tools, APIs, libraries, datasets, and assets,
- dense/cache build process if used,
- initialization and evaluation time,
- token usage and external API cost,
- deterministic fallbacks,
- limitations and future improvements,
- team member contributions.

### 15.2 Submission package

Before submission, verify:

- Devpost has a clear written project description.
- The submitted GitHub repository is public.
- The public repository contains runnable, well-structured code and README.
- A short end-to-end demo video is public on YouTube and linked from Devpost.
- The demo may show API/headless usage; UI is not required.
- The video and repository do not include unauthorized trademarks,
  copyrighted content, secrets, or private evaluation data.

### 15.3 Judging alignment

Do not optimize only the local TechnicalScore. Prepare evidence for:

| Criterion | Weight | Required evidence |
| --- | ---: | --- |
| Technical Execution | 35 percent | reliable run, architecture, metrics, fallbacks |
| Innovation and Problem Insight | 20 percent | sharp problem choice and non-trivial rationale |
| Impact and Relevance | 20 percent | concrete shopping/user value |
| Feasibility and Practicality | 15 percent | latency, cost, resource use, reproducibility |
| Presentation and Communication | 10 percent | coherent demo and defensible explanation |

The ablation table should include the official baseline, each retained vertical
slice, overall metrics, and per-scenario diagnostics.

## 16. Agent execution rules

When implementing:

1. inspect the current repository and branch before writing,
2. preserve the public Agent interface,
3. implement the smallest testable vertical slice,
4. keep optional dependencies behind deterministic fallbacks,
5. run focused tests after each change,
6. evaluate on development after meaningful milestones,
7. keep holdout sealed until the one-time Gate 5 check,
8. report metric deltas and costs,
9. diagnose scenario regressions before retaining a feature,
10. avoid sweeping unrelated refactors,
11. prefer clear code and measurable behavior over frameworks,
12. do not start later gates while earlier gates are unstable.

## 17. Definition of done

The project is submission-ready only when:

- the official evaluator runs end-to-end,
- the public API contract is respected,
- the catalog and evaluator remain unchanged,
- no label, target, simulator, or private-data leakage exists,
- all 200 public sessions complete without unhandled Agent crashes,
- recommendations are validated and usage is validated when present,
- active state handles accumulation, override, and no-preference correctly,
- Buying/Browsing routing changes real behavior,
- proactive clarification is useful and non-repetitive,
- hybrid/semantic paths have deterministic fallbacks,
- retained features survive development ablation/cross-validation, and the
  frozen final configuration is reported once on holdout,
- full-set metrics and per-scenario diagnostics are recorded,
- setup and results are reproducible,
- limitations and session-only profile scope are explicit,
- README, Devpost, public GitHub, public YouTube demo, disclosures, and team
  contributions satisfy the official deliverables,
- the architecture and tradeoffs can be explained without framework buzzwords.

## Agent skills

### Issue tracker

Engineering specs and tickets are tracked as local Markdown under `.scratch/`.
See `docs/agents/issue-tracker.md`.

### Triage labels

The repository uses the default canonical triage-role names. See
`docs/agents/triage-labels.md`.

### Domain docs

The repository uses a single-context domain-document layout. See
`docs/agents/domain.md`.
