# Domain docs

This repository uses a single-context domain-document layout.

## Before exploring

Read the root `CONTEXT.md` when it exists, then read any ADRs under `docs/adr/`
that relate to the area being changed. If these files do not exist, continue
without creating them pre-emptively; producer skills create them only when a
real vocabulary or architectural decision needs to be recorded.

## Vocabulary

Use the terms defined in `CONTEXT.md` in specs, ticket titles, tests, and code.
If a required concept is missing, first decide whether the proposed term is
unnecessary or whether the glossary genuinely needs to be extended.

## ADR conflicts

Call out any proposal that conflicts with an existing ADR. Do not silently
replace a recorded decision.
