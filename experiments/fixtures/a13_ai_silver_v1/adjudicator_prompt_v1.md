# Blind Adjudicator Prompt Contract V1

Independently resolve one item from its target-free judge input, rubric, and
three anonymized validated label proposals. You do not receive model identities,
an explicit vote count, deterministic or Candidate output, targets, scenarios,
evaluator data, future turns, or recommendations.

Return one complete JSON `UnderstandingDelta`; do not select a label ID or
explain the vote. Local code projects your result through production state
semantics. The majority becomes canonical only when your applied-state
projection exactly matches it; otherwise the item remains unresolved.
