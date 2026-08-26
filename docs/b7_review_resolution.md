# B7 Standards and Spec Review Resolution

Fixed point: `2280bf7` (last Developer A commit before the B workstream).

Reviewed code-behavior commit: `5b66df5`.

## Review outcome

The first two-axis review found two blocking defects and four additional hard or
spec findings: dense warm-cache requests bypassed shared validation; zero-weight
fusion returned an unreported empty result; ticket status lines were not parser
compatible; the expensive reranker had no enforceable timeout; the B5
comparator crossed revisions without an equivalence proof; and the default
structured route was mislabeled as BM25.

All six were corrected and covered by tests. A second review then identified
that a daemon-thread timeout returned promptly but could leave the expensive
calculation running. The reranker was moved into an isolated spawn process that
is terminated and joined on timeout, and the evaluator now closes the process
in a `finally` block. The clean-cache artifact was also regenerated from the
current configuration with `timeout_ms` recorded.

The final parallel Standards/Spec review reported:

- Standards: zero hard violations; one non-blocking Repeated Switches judgment.
- Spec: zero findings.
- Blocking findings: zero.
- Verification: 140 full-suite tests and 39 focused tests passed.

The Repeated Switches judgment is accepted for this freeze: experiment-mode
parsing in the shell and retriever construction/reporting in Python are separate
boundaries, the set of modes is frozen, and a registry refactor immediately
before the Final Public Run would add risk without changing behavior. Record it
as a future maintainability item if another mode is added.

