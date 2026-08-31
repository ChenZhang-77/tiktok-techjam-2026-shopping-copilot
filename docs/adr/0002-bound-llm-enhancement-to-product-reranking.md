# Bound optional LLM enhancement to product reranking

## Decision

The Agent defaults to offline execution. An explicit pre-run LLM configuration
adds the retained B10b-F2 reranker only for eligible Browsing turns. It can reorder
the existing Top-10 candidate pool with constraint protection, but cannot add or
remove pool members.

The integration preserves local multi-turn state, query construction and
clarification. It does not add LLM dialogue understanding, profile updates or
recall expansion. This boundary limits external data transfer and the surface
requiring remote-provider validation.

## Failure behavior

- Missing keys, network errors, timeouts, invalid output or exhausted budgets
  preserve the pre-rerank recommendation order with a visible reason.
- A required catalog/setup error is separate from optional-model degradation.
- Requested mode, actual execution, attempts, successes and fallbacks are reported
  separately. Completing a session without any successful provider call does not
  establish successful enhancement validation.
- Normal eligibility skips are not provider failures. Keys or network availability
  never activate LLM mode when offline mode was selected.

## Evidence and scoring configuration

The final public Full200 evidence uses offline mode. Historical F2 paired results
are retained as earlier experiments, not new live measurements of this integrated
package. Any use of the optional mode for official scoring depends on organizer
network/resource rules and fresh validation of ranking quality, latency and cost.

See [configuration](../delivery_configuration.md), the
[technical report](../../submission/REPORT.md) and
[bound evidence](../delivery_reports/README.md).
