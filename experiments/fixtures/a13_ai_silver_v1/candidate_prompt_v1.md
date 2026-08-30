# Candidate Prompt Contract V1

Return one JSON `UnderstandingDelta` proposal for the current customer message
and bounded prior state. Use only the supplied message, prior state,
deterministic evidence, and allowed value vocabulary. Never use a target item,
scenario, recommendation, evaluator result, future turn, fixture trigger, or
another model output.

Every proposed value must be normalized and supported by an exact evidence span
from the current message. Return the complete closed schema with no extra keys.
Use `abstain=true` with all other fields empty when evidence is insufficient or
conflicting. Do not mutate state, call tools, browse, explain, or wrap JSON in
Markdown.
