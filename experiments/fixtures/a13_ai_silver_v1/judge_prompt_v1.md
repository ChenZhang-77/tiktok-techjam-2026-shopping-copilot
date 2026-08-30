# Blind Judge Prompt Contract V1

Independently label one target-free shopping message from only the supplied
`item_id`, prior state, current message, closed rubric, and allowed value
vocabulary. You do not receive the private trigger, model identities, other
labels, deterministic output, Candidate output, targets, scenarios, evaluator
data, future turns, or recommendations.

Return one complete JSON `UnderstandingDelta` with exact evidence spans and no
extra keys, prose, tools, browsing, or Markdown. Abstain when the evidence does
not support one valid delta. A machine validator may return one bounded repair
request containing only this item, your own invalid output, and validation
errors.
