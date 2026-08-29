# Demo and Submission Plan

This document turns the current system into a clear, reproducible competition
story. It is a delivery plan, not evidence that every listed artifact already
exists. Confirm actual files before making submission claims.

## Message to judges

Shopping Copilot is a stateful catalog-grounded agent. It carries forward valid
preferences, handles corrections and no-preference language, and returns
deterministic Top 10 catalog recommendations with non-repeating, currently
priority-biased clarification through a local retrieval/ranking pipeline. A
complete candidate-evidence should-ask gate is planned work, not a retained
capability.

The defensible technical story is:

```text
conversation
  -> active intent and constraint state
  -> distilled retrieval request
  -> structured candidates
  -> gated local dense/RRF for broad Browsing, exact structured fallback
  -> priority-biased clarification selection
  -> response guard and catalog-valid Top 10
```

Do not claim that every turn uses dense retrieval, RRF, or semantic reranking.
B9 runs pinned local dense plus weighted RRF only behind its broad-Browsing
gate; global variants were rejected.

The retained runtime now has literal Browsing-dense execution only for B9's
narrow gate. Do not expand that into a global hybrid claim. CrossEncoder
reranking is measured and globally rejected. DeepSeek B10b-DS1 is implemented
and measured only as an opt-in Browsing Top-10 experiment; it is not the
retained default. A13 A-side semantic understanding is a reviewed plan, not an
implemented capability. Profile ranking remains disabled at weight 0.0.

## Evidence available now

- Retained B9 route commit: `7f520ba`; optional B12 code commit: `82891c8`.
- Current full test suite: `297/297` passing on the A13 planning branch.
- Latest A-side correction checkpoint: HitRate@10 `0.925`, MRR `0.552760`,
  MTTC `4.13125`, TechnicalScore `0.765703`; this is Development-only and does
  not isolate the contribution of each correction.
- Earlier retained A11+B9 checkpoint: HitRate@10 `0.8625`, MRR `0.547329`,
  MTTC `4.66875`, TechnicalScore `0.722074`.
- B9 route: dense/fusion executed 102 times; all four folds non-regressing;
  startup about `3.58 s`, peak RSS about `1.109 GB`.
- B10a: Top-3 and Top-5 anchored CrossEncoder candidates rejected; the default
  remains B9.
- B10b-DS1: opt-in Top-10 experiment improved MRR/TechnicalScore while
  HitRate@10 and MTTC stayed unchanged; DS2 Top-20 was rejected by its
  reliability gate.
- A13: reviewed Shadow-first semantic-understanding plan only; no runtime or
  score claim is allowed until its gates pass.
- B11: not started because the current R0 refresh finds zero retrieval/ranking
  primary misses; do not claim a lexical-recall refinement.
- B12: exploratory and disabled by default; favorable aggregate result, but no
  contemporaneous gate and a gain concentrated in fold 4.
- Historical full-200 run: HitRate@10 `0.765`, MRR `0.517355`, MTTC `5.375`,
  TechnicalScore `0.650207`.

The full-200 run is non-confirmatory because those public sessions have already
been exposed. Say “historical public result,” not “unseen holdout validation.”

## Four-case demo script

Use fixed, preselected public sessions and rehearse within the official time
limit. Choose exact session IDs only after verifying that each visibly
demonstrates its intended behavior.

1. **Straight buying intent** — show a narrow request, current state, the actual
   clarification behavior, and relevant Top 10 results. Claim “no wasted
   question” only after A9 is retained and the chosen case verifies it.
2. **Broad browsing intent** — show how the current clarification changes the
   candidate set. Describe it as “high-value” only after AB0/A9 evidence exists.
3. **Intent override** — show an earlier preference being replaced without
   contaminating the new query.
4. **No-preference / boundary case** — show the system dropping the correct
   constraint while preserving unrelated preferences. Disclose the known
   multi-attribute scope limitation if it is not fixed before recording.

For each case narrate: incoming message, visible active state, decision, query,
Top 10, and one concise diagnostic. Do not narrate the evaluator's target as if
the agent knew it.

## Visualizer safety: two views

The visualizer should clearly separate:

- **Agent View**: only information available to the agent at that turn — user
  history, active constraints, strategy, distilled query, route diagnostics,
  and returned recommendations.
- **Evaluator View**: target ASIN, target rank, hit/miss, first-hit turn, and
  aggregate evaluation metrics.

Evaluator-only fields may help analysis but must be visually labeled and must
never feed agent state, prompts, retrieval, ranking, or route selection. A demo
recording should keep the separation visible so judges cannot mistake analysis
data for online inputs.

Development targets may be used here to select and explain an offline demo
case, but the recording must not imply that target rank or hit/miss was available
to the running Agent.

## README and written submission structure

Keep the public narrative in this order:

1. one-sentence problem and solution;
2. architecture diagram or compact flow;
3. reproducible quickstart;
4. verified metrics with dataset labels;
5. one example dialogue;
6. retained-vs-rejected ablation table;
7. latency, dependencies, and fallback behavior;
8. limitations and next work;
9. factual team contributions.

Avoid marketing claims such as “production ready,” “state of the art,” or
“validated on unseen data” unless new evidence genuinely supports them.

## Video outline

A compact 3–4 minute video can use:

- 0:00–0:25 — shopping problem and Track 4 constraint;
- 0:25–0:55 — architecture and why state matters;
- 0:55–2:35 — two or three strongest live cases;
- 2:35–3:10 — evaluation and ablations;
- 3:10–3:35 — limitations, cost, and next step.

Prefer a deterministic prerecorded fallback for the live demo. Record the exact
commit, command, environment, session IDs, and expected output before filming.

## Submission package target

```text
submission/
  README.md
  agent.py
  requirements.txt
  src/                 # only if imports require it
```

Before packaging, verify:

- a clean environment can import and instantiate `Agent`;
- the official response schema is respected on every turn;
- all ASINs exist in the frozen catalog and are unique per response;
- optional caches/models have documented setup and safe fallback behavior;
- no tests, reports, or scripts depend on absolute developer-machine paths;
- no secrets, `.env` files, credentials, private data, generated embeddings, or
  unnecessary artifacts are included;
- evaluator code and official data are not modified;
- licenses and model/data attribution are present where required.

## Team-contribution rule

List only work that can be supported by commits, documents, experiments, or
tests. Use component-level wording such as dialogue state, retrieval/ranking,
evaluation tooling, visualizer, documentation, or demo. Separate joint design
from individual implementation. Do not infer ownership from filenames alone.

## Questions to rehearse

- Why is dense/RRF restricted to broad Browsing rather than enabled globally?
- How do you prevent stale preferences after an intent change?
- When is a clarifying question worth its MTTC cost?
- How do you handle sparse product metadata?
- What happens when an optional model or cache fails?
- How did you avoid tuning on the exposed public slice?
- What is the largest known failure mode, and what experiment comes next?

## Delivery definition of done

- [ ] Final retained configuration is frozen and recorded.
- [ ] Full tests pass from a clean checkout.
- [ ] Development metrics and ablations are reproducible.
- [ ] Agent View and Evaluator View are visibly separated.
- [ ] Demo sessions are preselected and rehearsed without target leakage.
- [ ] Submission package passes a clean-start smoke test.
- [ ] README, report, video, and live demo use identical metrics and claims.
- [ ] Limitations, costs, dependencies, fallbacks, and contributions are stated.
- [ ] Final archive contains only required, license-safe files.

## Related documents

- `docs/current_status.md` — authoritative current state
- `docs/optimization_roadmap.md` — development order and gates
- `docs/ablation_summary.md` — retained and rejected experiments
- `submission/README.md` — packaging checklist
- `visualizer/README.md` — demo tool usage and information boundaries
