# Recording script — offline default, honest optional enhancement

Status: walkthrough rehearsed locally; no video has been recorded or uploaded by
this task. The [live event page](https://tiktoktechjam2026.devpost.com/), checked
on 2026-08-31, asks for a public **3-minute YouTube video**. Target 2:55–3:00;
this supersedes our earlier 3–4-minute suggestion. Finish and link it before
2026-09-01 12:00 SGT. Track 4 PDF section 4.5 requires a video despite the generic
form's optional-looking field. API/result walkthroughs are accepted.

## Preparation

Record the final main commit and package manifest in the video's description.
Use the same checked-in report as README; do not read screenshots of old branch
scores as current measurements. Prepare catalog/model assets first, then run:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python visualizer/server.py --port 8765
```

Open localhost, select **Current workspace**, interval 0.7 seconds. No API key is
needed; keep shell environments, credentials and private material off camera.
The UI is a local simulator demonstration, not a real customer chat service.
Use no unlicensed music, logos, brands-as-team-marks or third-party video assets.

## Narration and shots

| Approximate time | Shot / narration |
| --- | --- |
| 0:00–0:20 | Hook: “Shopping intent moves. Search should keep up.” Introduce changing preferences and the 50k catalog |
| 0:20–0:40 | Explain state → strategy/query → structured retrieval → gated local dense → optional bounded product rerank → response guard |
| 0:40–1:50 | Show key moments from the four rehearsed cases below; label simulation and any edited/skipped time |
| 1:50–2:10 | Show offline diagnostics and the synthetic no-key contract test, explicitly not a live provider success |
| 2:10–2:35 | Show frozen Full200: 186/200 sessions hit Top-10, no external calls. Label Dev160 separately and historical F2 as historical; no real-user conversion claim |
| 2:35–2:55 | State coverage gaps and next steps; show setup/main entry and approved component credits |

## Rehearsed Development cases

These outcomes were observed on the unchanged delivery runtime with prepared local
assets on 2026-08-31. Rehearse again after final packaging; they are not guarantees
of hidden performance. Scenario and HIT are evaluator labels.

| UI index / sample | What to show | Observed outcome |
| --- | --- | --- |
| 0 / public_0001 | Buying: turn 1 asks feature; structured route, no dense; show turn 2 ranked result | hit turn 2, rank 1 |
| 5 / public_0006 | Browsing: turns 1–3 execute dense/fusion; turn 4 adds polyester and returns to structured route | hit turn 7, rank 1 |
| 2 / public_0003 | Override: turn 3 moves earlier feature entries to overridden/excluded state; the query drops “3 year battery” while retaining the newly expressed water-resistant request and material | hit turn 7, rank 1 |
| 40 / public_0041 | No-preference: turn 2 gives no material preference; no fabricated material constraint; later explicit polyester becomes active | hit turn 7, rank 1 |

Optional limitation shot: index 1 / public_0002 reaches turn 10 without a hit,
despite adding the new leather requirement. Do not claim all overrides succeed
or that every clarification is necessary/optimal.

Buying case 0 and start/stop/expanded diagnostics were verified through the actual
browser. The other traces were rehearsed through the same TraceRunner API; their
final edited video presentation has not been validated yet.

## Safe optional-mode failure demonstration

From the repository root:

```bash
python -m unittest \
  tests.test_delivery_agent.DeliveryAgentTest.test_missing_key_falls_back_without_attempting_network -v
```

Label this **synthetic no-key contract test: zero paid calls**. It verifies that
explicit LLM mode reports fallback and preserves pre-LLM ranking without network.
Do not call it live LLM validation. Actual provider demonstrations require fresh
transfer/budget authorization and must show real success/usage/fallback records.

## Before upload

- Team approves the final script, names/roles and asset permissions.
- Final main/commit and evidence links work from a signed-out browser.
- Video uses the actual current code, marks simulation and any edited time, and
  does not expose targets as Agent inputs or claim historical F2 is a new run.
- Upload an actual public YouTube video and verify public playback; then paste
  its URL into Devpost. Upload/publication requires separate authorization.
