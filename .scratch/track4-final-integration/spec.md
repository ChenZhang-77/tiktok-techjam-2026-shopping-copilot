# Track 4 final integration

Status: ready-for-agent

## Problem Statement

The selected source works locally but is not a self-contained competition delivery.
The teammate visualizer, verified optional F2 reranker and older packaging work
must become one reproducible, truthfully documented submission.

## Solution

Implement the user-approved 24 final delivery rules, preserving the offline default
and official Agent contract, with explicit bounded LLM reranking and visible fallback.
Rules and ADR-0002 remain authoritative for scope; original competition requirements
and the participant contract take precedence over our implementation preferences.

## User Stories

1. As an evaluator, I want one Agent entry so I need not combine branches.
2. As a user, I want a no-key offline default with local model assets.
3. As a user, I want explicit LLM enhancement limited to qualified product reranking.
4. As an evaluator, I want valid recommendations even when the optional API fails.
5. As a reviewer, I want actual execution, usage and fallback evidence, not mode labels alone.
6. As a maintainer, I want limits and no accidental paid requests during tests or setup.
7. As an evaluator, I want a clean-directory package and reproducible setup commands.
8. As a teammate, I want replay evidence tied to the correct source and configuration.
9. As a judge, I want honest architecture, limitations, contributions and comparison evidence.
10. As an owner, I want review gates after every slice and no unauthorized publication.

## Implementation Decisions

- Preserve the official reset/respond envelope and RetrievalRequest/Result seam.
- Use one configuration-aware delivery Agent over the retained Control Plane.
- Extract only frozen F2 runtime behavior, not experiment orchestration or A13/A14.
- Offline never constructs a live provider. Enhancement needs explicit mode,
  credentials and finite limits; failures retain pre-rerank results and are reported.
- Local model assets are setup inputs, never fetched during respond.
- Build the independent bundle from a source allowlist and hash its final bytes.
- Keep evaluator-only evidence in reports/replay, never in runtime inputs/prompts.
- Implementation authorization includes local changes, tests and local commits;
  paid validation, external transfer and publication retain separate authorization.

## Testing Decisions

The accepted seams are Agent.reset/respond (including delivery configuration and
public execution diagnostics), Retriever.retrieve, package build/check commands,
and visualizer read-only API/replay. These directly instantiate approved rules
2, 8-17; do not invent lower-level testing interfaces.
Use synthetic local catalog fixtures and fake external providers; test externally
observable results and failure behavior. Run red/green slices, full unittest,
syntax checks and diff checks. No type checker is configured; use compilation and
contract tests unless the repository gains an explicit checker later.
Compare actual offline default and delivery Agent on fixed Development-160/four
folds. Verify source/package hashes, fresh imports and optional-asset degradation.
Live F2 verification is separately gated and cannot be replaced by mocks.

## Out of Scope

Live chat/HTTP deployment, accounts, model/prompt tuning, A13/A14/profile/B11/B12,
holdout tuning, private evaluation access, publishing secrets or unapproved API calls.

## Further Notes

Starting source: 3b0141633f2df8044fcbde4e9f99794f30778e93.
F2 source: a9e34ae4b125c8103b4f740134d7f1752a97c476.
Local tickets are ordered independently verifiable slices, not blanket permission
for their explicitly gated external actions. Source publication is not submission.
