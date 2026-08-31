## Inspiration

Shopping intent moves. Search should keep up.

A shopper can begin with a broad idea, discover a new requirement, or change
direction halfway through a conversation. A useful shopping assistant needs to
track what matters now, not simply repeat an earlier keyword query. We built
Adaptive Shopping Copilot around that problem: turning changing preferences
into inspectable, catalog-grounded recommendations.

## What it does

Our Track 4 solution is a stateful search agent over the competition's frozen
50,000-product catalog. It tracks accumulated preferences, handles intent
overrides and no-preference statements, distinguishes Buying from Browsing,
and returns ranked products with structured clarification.

The product has one Agent entry and two explicit configurations. The default
runs locally without external API calls after catalog and model setup. Optional
LLM enhancement reranks eligible existing Top-10 candidates with constraint
protection. It is selected before a run, never activated just because a key is
present. If enhancement is unavailable, the pre-rerank order is preserved and
the fallback reason is reported.

A local visualizer shows simulated conversations, recommendation changes and
execution routes. Evaluation annotations are separate from Agent inputs. The
scored Agent remains headless and does not depend on a hosted chat service.

## How we built it

The pipeline turns current session state into a distilled query, then combines
SQLite FTS5 retrieval, constraint-aware ranking and guarded filtering. Broad
Browsing requests can activate local MiniLM embeddings and reciprocal-rank
fusion; narrow requests retain the structured route. The optional DeepSeek
reranker changes ordering, not candidate membership or dialogue understanding.

We treated the integration boundaries as part of the product: one reset/respond
interface, explicit call/cost/duration budgets, observable failures, and a
standalone source package with checksums and reproducible evaluation commands.
No credentials, catalog data or model weights are shipped in that package.

Our stack is Python, SQLite, NumPy, PyTorch, Hugging Face Transformers and
Sentence Transformers, with HTML/CSS/JavaScript for visualization. We used Git,
Codex, the macOS terminal and Python unittest during development. AI coding
assistance supported implementation, testing, review and documentation; the
team reviewed the resulting code and claims.

Data comes from the official participant kit, derived from McAuley Lab's Amazon
Reviews 2023 Clothing_Shoes_and_Jewelry category. The local model is
sentence-transformers/all-MiniLM-L6-v2 at a pinned revision. The optional API is
DeepSeek with the retained deepseek-v4-flash reranking configuration.

## Challenges and design decisions

Remembering everything is not the same as remembering the right things. We had
to distinguish active requirements from rejected, overridden and explicitly
irrelevant preferences before retrieval. We also had to make the local and
optional remote paths share one contract without confusing requested mode with
what actually executed.

Rather than assume that adding another model would improve the whole system,
we used a fixed development protocol to compare changes and retained a bounded
semantic route. This keeps the default independent of external API availability,
while leaving an explicit enhancement path for further verification.

## Results we can reproduce

After freezing the offline configuration, one full public evaluation placed the
target product in the Top-10 in **186 of 200 simulated sessions**:

| Metric | Frozen offline Full-200 |
| --- | ---: |
| HitRate@10 | 0.930000 |
| MRR | 0.527544 |
| Mean Turns to Conversion | 4.105000 |
| TechnicalScore | 0.761163 |

Across 807 turns, the run recorded zero external API calls, zero invalid
responses, zero response exceptions and zero fallback events. This means no
external API charges for that run, not zero local compute or setup cost.

The independent package also reproduced the fixed Development-160/four-fold
results with exact core/package response parity and TechnicalScore 0.766231.
Automated tests cover the Agent contract, delivery package and visualizer.
We retain per-session results,
configuration, source/input hashes and timing evidence outside Agent runtime.

These are exposed public-data evaluations, not unseen validation or measured
real-user conversion. Development-160 and Full-200 are different populations,
not a before/after comparison. TechnicalScore is the evaluator's metric, not the
overall judging score. Private-set performance is unknown. Verification used a
prepared same-machine environment; a fresh intended-host installation remains
to be checked. Historical LLM experiments are not new live measurements of this
integrated package, and no LLM was used in the final Full-200 run.

## What we learned and what's next

The useful unit of intelligence is not just a better-ranked list: it is the
connection between current intent, retrieval choices and the next question.
Our potential value is a shopping-search component that can be evaluated
locally and inspected turn by turn, with remote-model use under explicit
control. We have not measured business impact or production reliability.

The current system does not implement complete over-generality retrieval
cutoff, long-term profile updating/ranking, or self-refining workflow
orchestration. These are explicit Track 4 coverage gaps, not capabilities we
claim to have finished. Next priorities are cross-machine validation, stronger
clarification and profile handling, and live evaluation of the optional LLM
integration's ranking quality, cost and latency.

## Team and reproducibility

Team: **double zhang**.

ChenZhang-77 contributed context/preference correctness fixes, guarded DeepSeek
handoff and local dialogue visualization. Pat7ryk contributed retrieval/ranking,
evaluation tooling, release integration and the standalone dual-mode package.

[Start with main](https://github.com/ChenZhang-77/tiktok-techjam-2026-shopping-copilot/tree/main).
The `submission/` directory contains the Agent, setup, configuration and technical
report; `docs/delivery_reports/` contains the numerical evidence. Judges do not
need to assemble code from other branches.
