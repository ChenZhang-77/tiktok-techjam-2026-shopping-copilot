# A14 deadline selection pilot

Predeclared 2026-08-31, before viewing Candidate outcomes. LR0 found two
synthetic editor corrections, but no competition gain; retain only the cheap
offline diagnostic and defer A13 runtime/multi-family work for the deadline.
The coordinator's score-first request opens this separate deterministic pilot.

This is a small A14-S1/C1 investigation, not a claim that the full all-legal-
question counterfactual audit or formal S1 gate is complete. One Candidate,
one paired Development run; no parameter sweep. Runtime defaults stay unchanged
unless all keep conditions and a follow-up review pass.

Hypothesis: within already comparable evidence, rank-weighted separation with
no reduction in evidence coverage chooses a more useful question than raw
vocabulary diversity. Reuse QuestionPolicy.decide and existing A14-1 records.
No new catalog interpretation, state/query/retrieval change, LLM, or stop rule.

Frozen selector:

1. Preserve stop, feature-first, degraded/error, and the existing concrete-
   Buying material anchor (active category + color).
2. Examine only the contiguous legacy-eligible priority prefix with available
   bounded-vocabulary evidence, canonical questions and bounded extraction.
   Stop the prefix at the first unsupported attribute; never demote it by
   treating missing evidence as zero. If the baseline is outside the prefix,
   keep it.
3. Among that prefix, require coverage at least the baseline's. Choose maximum
   rank-weighted split, then coverage, with baseline on equal split. Only a
   strictly larger split may replace baseline.

First run legacy-returning Shadow, retaining same-snapshot proposed actions;
then run the opt-in Candidate through the unchanged official evaluator on the
same fixed Development-160. Partition both results using the fixed four folds
(not four independently fitted models). Compare scenario scores, gained/lost
sessions, productive-answer diagnostics, legality, fallback, and timing.

Keep gate: aggregate TechnicalScore strictly improves, HitRate does not fall,
at least three folds do not regress, no scenario loses >0.01 TechnicalScore,
zero response/schema/eligibility violations, and a coherent changed-question
mechanism. If any fails, preserve default and stop this Candidate. A passing
pilot still needs the full S1 counterfactual/productive-answer audit and review
before default activation. No Full/Holdout, evaluator changes or target rules.

## Result

Pending. Expected files: isolated `experiments/a14_deadline_selection.py`,
synthetic seam tests, this evidence record and current navigation. No production
source changes are planned for the pilot.
