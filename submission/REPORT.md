# Shopping Copilot technical report

## Method

The Agent maintains active shopping intent, scoped preferences and overrides,
distills a current query, chooses Buying/Browsing strategy, retrieves from an
in-memory SQLite FTS5 catalog index and ranks with guarded structured evidence.
Pinned local MiniLM/RRF is conditional on the retained B9 broad-Browsing gate.
The default requires no external API. Explicit optional F2 semantic reranking
reorders existing Top-10 products with hard/rejected-constraint protection.

## Models and limitations

Local model: sentence-transformers/all-MiniLM-L6-v2, revision
1110a243fdf4706b3f48f1d95db1a4f5529b4d41. Optional external model:
deepseek-v4-flash, frozen F2 prompt and temperature 0; no immutable remote-model
version or output determinism is claimed. Clarification is priority-biased,
long-term profile ranking is disabled, dense routing is conditional, and there
is no active LLM dialogue-understanding module or multimodal input.

## Evidence status, usage and cost

Independent package validation reproduced Development-160 HR .925, MRR .554521,
MTTC 4.13125, TechnicalScore .766231, exact paired core/delivery response traces
and four-fold results, with 649 turns and zero observed fallback. Dense/fusion
executed 101 times. The bound repository report and tested-runtime manifest are
in docs/delivery_reports; these are same-machine, prepared-asset, synthetic-prewarm
measurements, not a fresh dependency install or hidden-set guarantee.
Offline prompt/completion tokens and external API charges are zero; local CPU,
memory and setup costs are not zero. Warm source evaluation is not a cold-start
or other-machine guarantee. In this package comparison the delivery arm had
response p95 47.702 ms, maximum 119.827 ms, and 1.429 s initialization including
synthetic prewarm. The source comparator ran first in the same process, so this
initialization number is not a cold-process guarantee.

Historical llm-branch F2 paired scores were .779043/.779199 with unchanged HR/MTTC;
826 calls had an inherited estimated allowance of USD .69472392, not a current
price quote or invoice. Historical provider p95 was 1.146/1.609 seconds and max
7.318 seconds. These are not live measurements of this integrated package.
New live verification is pending separate authorization. The API has no retries,
8-second request timeout and call/cost/duration stop conditions; unknown usage
is reserved as allowance, not called free. Failure preserves pre-rerank order.

## Contributions and final submission

Team contribution statements, final package latency/memory evidence, public video
and Devpost URLs must be reconciled before publication. This file is an honest
staging report, not a claim that those external submission gates are complete.
