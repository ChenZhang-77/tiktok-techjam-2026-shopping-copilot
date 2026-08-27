# A9 Should-Ask Gate — Rejected Experiment

## Decision

Reject and revert the A9 runtime gate tested at `30765cd`. The final runtime
was restored by `11cf67f`; AB0 `DecisionEvidence` remains available, but the
Agent continues to use the pre-A9 ask/no-ask behavior.

The tested rule suppressed clarification only when evidence was healthy,
Top-K Jaccard stability was at least `0.8`, and no useful Candidate partition
remained among available attributes. Missing or degraded evidence fell back to
the existing question policy. It used neither the uncalibrated score margin nor
target/evaluator labels, and it did not change the shared A/B contract.

## Development-160 Result

| Metric | AB0 baseline | A9 candidate | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.7625 | 0.7500 | -0.0125 |
| MRR | 0.529812 | 0.527269 | -0.002543 |
| MTTC | 5.35000 | 5.43125 | +0.08125 |
| Efficiency | 0.565000 | 0.556875 | -0.008125 |
| Technical score | 0.653194 | 0.644556 | -0.008638 |

There were no gained sessions and two lost sessions: `public_0097` and
`public_0098`. Browsing scenario score fell `0.011172`; Buying fell `0.010422`.
Boundary and Intent Override were unchanged. This reproducible regression is
sufficient to reject the candidate before fold evaluation.

## Evidence Boundary

The hash-bound evaluator reports do not contain turn-level `ask_attribute` or
clarification-reason traces. Therefore this retained decision makes no exact
claim about total-question or no-value-question deltas. Any renewed A9
experiment must first retain a hash-bound turn audit before using those measures
in its keep/revert decision.

## Why the Hypothesis Failed Here

The local evaluator scores recommendations before generating the next customer
reply, so asking does not delay a hit on the current turn. After a miss, a real
question can reveal another target preference; `ask_attribute=None` instead
produces a generic request to ask a specific attribute. The gate therefore
cannot improve the current ranking and can remove information needed by later
turns. This is an evaluator-mechanism conclusion, not a claim that unnecessary
questions have no real product UX cost.

## Route Consequence

Proceed to **A10a Candidate Question Value**: improve which useful question is
asked while preserving recommendations and the existing ask opportunity. A
future A9 variant would be a new experiment requiring both a hash-bound turn
audit and the existing technical keep gate. Holdout and Full-200 remain
untouched.

Machine-readable evidence is in `docs/a9_should_ask_evidence.json`; the rejected
clean report is in `docs/a9_reports/development_stability_080.json`.
