# A10b Internal QueryPlan — Retained Evidence

## Decision

Retain the A-owned `QueryPlan` at clean code commit `a6446e9`. It separates
category, hard, soft, semantic, residual, and excluded evidence, then renders
the same single `RetrievalRequest.query` string expected by B. No shared schema,
question policy, intent transition, or state ownership changed.

Rejected and overridden values are visible in the A diagnostic plan but never
rendered as positive terms. Exact values are deduplicated across positive roles.
When structured extraction does not capture the whole current message, the
remaining text is retained as a residual role so A10b does not pretend that A11
extraction is already complete.

## Query Roles

| Role | Source | Rendering rule |
| --- | --- | --- |
| category | active category constraints | positive first |
| hard | other active hard constraints | positive after category |
| soft | other active soft constraints | positive after hard |
| semantic | active feature/use-case constraints | positive after soft |
| residual | current-turn text after exact active/excluded phrase removal | positive last |
| excluded | rejected and overridden inactive values | diagnostic only; never positive |

The complete field producer/type/lifecycle/fallback inventory is in
`docs/a10b_query_plan_evidence.json`. `build_distilled_query` remains a
compatibility wrapper; Agent orchestration uses `build_query_plan` directly and
stores the rendered string in the existing `previous_distilled_query` field.

## Development-160 Result

The clean candidate exactly matches the AB0/A8 baseline on all overall metrics,
all scenario metrics, and every one of the 160 session outcomes:

| Metric | Value | Delta |
| --- | ---: | ---: |
| HitRate@10 | 0.7625 | 0 |
| MRR | 0.529812 | 0 |
| MTTC | 5.35 | 0 |
| Efficiency | 0.565 | 0 |
| Technical score | 0.653194 | 0 |

The session outcome records—including first-hit turn and best rank—share hash
`63a8dd1a958c1a26652d6ae4870dc462735fe6b37dba73e9288b0a3ad8c40849`.
Because all fixed folds are subsets of these identical records, separate fold
runs would reproduce the same fold metrics and were not rerun. Holdout and
Full-200 were not run.

## Conservative Boundary

An early probe that discarded the residual demonstrated that current extraction
does not yet capture all useful title/feature language. A second probe showed
that removing apparently conversational tokens can change OR+BM25 ordering.
Those probes are design evidence only, not hash-bound quantitative claims. The
retained renderer therefore removes only exact consumed and explicitly excluded
values. Broader residual parsing belongs to A11 and must earn its own metrics.

## Next Step

Proceed to **A11 Extraction and Scope Hardening**. Use `QueryPlan` diagnostics
to verify that new extraction moves evidence from residual into the correct
role without reintroducing rejected/overridden values. A10c remains blocked
unless a measured B experiment needs typed query components and AB1 coordinates
the shared contract.
