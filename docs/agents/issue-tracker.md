# Issue tracker: Local Markdown

This repository stores engineering specs and implementation tickets as Markdown
files under `.scratch/`. GitHub Issues are not used by the engineering skills
unless this document is changed explicitly.

## Conventions

- Give each feature a directory: `.scratch/<feature-slug>/`.
- Store its spec at `.scratch/<feature-slug>/spec.md`.
- Store one implementation ticket per file at
  `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`.
- Never combine multiple implementation tickets into one issue file.
- Record triage state in a `Status:` line near the top of each issue.
- Append discussion under a `## Comments` heading at the bottom of the issue.

When a skill says to publish to the issue tracker, create or update the relevant
file under `.scratch/<feature-slug>/`. When a skill says to fetch a ticket, read
the referenced local issue file.
