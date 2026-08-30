# Semantic Duplicate Audit Prompt Contract V1

Compare every freshly generated current message with the exposed legacy message
texts for semantic near-duplication only. Do not receive legacy labels,
Candidate/comparator output, targets, scenarios, evaluator data, future turns,
or recommendations. Return full fresh-item coverage and only pairs that express
materially the same boundary case despite wording differences.

This audit cannot create, edit, select, or label a fresh item. Any reported pair
is rejected before Candidate scoring and remains accounted for in the duplicate
report.
