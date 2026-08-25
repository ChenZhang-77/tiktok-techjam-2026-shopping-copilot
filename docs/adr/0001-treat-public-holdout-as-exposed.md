# Treat the public holdout as exposed

The A-side baseline was evaluated on all 200 public sessions before the
Retrieval / Ranking Plane was implemented, so the designated 40-session holdout
has already influenced project knowledge. We will select and tune B-stage work
only with fixed cross-validation on the 160-session Development Set, will not
inspect holdout or full-set results during development, and will perform one
Final Public Run after configuration freeze while explicitly reporting that it
is not a clean confirmatory holdout; the organizer's Private Evaluation remains
the external generalization test.
