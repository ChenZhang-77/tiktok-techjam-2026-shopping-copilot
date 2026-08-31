# Devpost submission draft

Status: prepared text, not submitted. Devpost is the event's project-submission
platform; it links the description, code and demo. The attached competition PDF
requires public GitHub and public YouTube links. Check the actual event form and
latest organizer instructions before posting; this document does not claim to
know every current form field or deadline.

## Project name and tagline

**Adaptive Shopping Copilot** — Stateful catalog search, offline by default,
with explicitly bounded LLM ranking when needed.

## Inspiration / problem

Shopping requests evolve: a customer may start broad, add a constraint, say an
attribute does not matter, or change intent. Repeating a static keyword search
loses context. We built a Track 4 Agent that preserves current preferences and
returns ranked catalog recommendations with a clarifying question when useful.

## What it does

The headless Agent supports the competition's reset/respond interface and frozen
50,000-product catalog. Buying/Browsing strategy, scoped state, a distilled query,
constraint-aware ranking and guarded filtering form the local default. Broad
Browsing can activate a pinned local MiniLM/RRF route. The optional LLM mode only
reranks eligible existing Top-10 products; it is not an LLM dialogue-understanding
module and does not require a production chat backend.

Offline mode needs no external API or key after local assets are prepared.
Enhancement is an explicit pre-run configuration, not automatic escalation or
mid-session switching. It has call/cost/duration limits, no retries, and visible
pre-rerank fallback for unavailable or invalid provider responses.

## How we built it / tools

Development tools verified in this work: **Codex, Git and the macOS terminal**;
Python unittest for regression checks and the in-app browser for UI verification.
Any additional IDE/notebook tools remain for team confirmation; no VSCode/Colab
usage is assumed.

Python, SQLite FTS5, NumPy, PyTorch, Transformers and Sentence Transformers;
sentence-transformers/all-MiniLM-L6-v2 at a pinned revision. Optional provider:
DeepSeek deepseek-v4-flash with the frozen F2 prompt. Data comes from the official
participant kit, derived from McAuley Lab's Amazon Reviews 2023. A vanilla
HTML/CSS/JavaScript local visualizer shows simulated sessions and clearly labels
evaluator-only annotations. AI coding assistance was used during development;
team members must confirm the final disclosure and named contribution statements.

## Results and what we learned

The independent offline bundle reproduces Development-160 HitRate@10 0.925000,
MRR 0.554521, MTTC 4.131250 and TechnicalScore 0.766231. Its paired traces and
four fixed folds match the retained core, with zero observed fallback. Runtime
and source/input hashes are retained alongside per-session results.

Historical F2 runs improved ranking but not hit rate or conversion turns, and
introduced remote latency and cost. They are recorded historical experiments,
not live verification of the integrated package. The default remains offline.
The frozen offline Full200 public report records 186/200 hits: HR@10 0.930000,
MRR 0.527544, MTTC 4.105000 and TechnicalScore 0.761163, with zero observed
fallback/invalid responses/exceptions across 807 turns and zero external calls.
This is a different population from Dev160, not a before/after improvement claim.

We used Development-160/four folds for selection. The other 40 public sessions
were exposed earlier; neither those nor Full-200 are unseen validation. The
organizer's private evaluation remains the external test. Public conversations
are simulated, so we do not claim measured business impact or real-user uplift.

## Limitations / next steps

Complex language and overrides can fail. Clarification is priority-biased,
not a complete immediate over-generality retrieval-cutoff policy. Long-term
profile ranking/update and self-refining workflow orchestration are not
implemented; bounded fixed strategy selection should not be described as those
capabilities. Dense retrieval is conditional. Same-machine
prepared-asset results do not prove cold-start portability. New real LLM testing
and organizer resource/network eligibility are separate gates. We prioritize
reproducibility and honest fallback over unsupported production-readiness claims.

## Links to fill and verify before submission

- Code: final **main** of the existing repository, plus the exact submitted commit.
  Intended URL: https://github.com/ChenZhang-77/tiktok-techjam-2026-shopping-copilot/tree/main
- Run instructions: main's `submission/README.md`; no branch assembly required.
- Evidence: main's `docs/delivery_reports/`, not another branch's working tree.
- Video: **PENDING — record and upload an actual public YouTube demo.**
- Team names/roles: **PENDING confirmation** of [contribution draft](team_contributions.md).
- Repository public access, final commit, licenses/asset permission and all event
  fields: **PENDING final checks/authorization**. A private link is not sufficient.

Other GitHub branches remain preserved. Submitting only main does not hide those
branches if they are in the same public repository. Do not paste placeholders as
completed links or describe this draft as a finished Devpost submission.
