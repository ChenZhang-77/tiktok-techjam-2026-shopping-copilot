# Delivery configurations

The integration entry is `starter.delivery.Agent`; it preserves reset/respond.
This is a locally tested integration, not a new live F2 verification or final submission.

| Variable | Default | Meaning |
| --- | --- | --- |
| SHOPPING_MODE | offline | offline or llm; read at Agent construction |
| SHOPPING_CATALOG | data/catalog.jsonl | Prepared read-only catalog |
| SHOPPING_DENSE_CACHE | embeddings/minilm-l6-v2-v1 | Prepared vector cache |
| SHOPPING_MODEL_CACHE | models/huggingface/hub | Prepared local model cache |
| SHOPPING_MAX_CALLS | 0 | Global attempted-call allowance per Agent instance |
| SHOPPING_MAX_USD | 0 | Estimated USD allowance per Agent instance |
| SHOPPING_MAX_SECONDS | 0 | Elapsed allowance since first eligible rank request |
| DEEPSEEK_API_KEY | absent | Read only in explicitly selected llm configuration |

Positive call, cost and duration limits are required for live calls. Mode alone
does not authorize a bill: defaults stop at the boundary. No .env files are loaded
automatically and setup/tests must not initiate provider calls. Do not put secrets
in shell history, recorded commands or tracked files.

Offline uses the retained conditional local B9 route and never constructs a live
provider. Missing optional dense assets are separately observable degradation, not
reproduction of full B9 metrics. Missing catalog is a setup failure.

LLM mode wraps the retained retriever with frozen F2 constraint-preserving Top-10
reranking. Only qualified Browsing requests run it. The exact frozen request/model/
prompt and allowance logic comes from `llm@a9e34ae`, with no experiment imports.
Its inherited cost assumptions are conservative experiment allowances, not verified
current provider prices or an invoice; review pricing and funding before any new
authorized paid run. Request timeout is 8 seconds with no retries, not a guarantee
of an 8-second whole-turn deadline. Check organizer limits before final selection.

`diagnostics.delivery` identifies requested mode, per-turn success/fallback/skip,
cumulative attempts/successes/fallbacks, allowance and stop reason. Response usage
contains known per-turn tokens; a failed attempt with unknown usage uses allowance
accounting, not a claim of zero billing. Invalid provider details are redacted.
No successful calls means no successful enhancement validation, even if the Agent
completed every session. Normal gate skips are not API failures.

Offline verification: `python -m unittest tests.test_delivery_agent -q`.
Use synthetic external providers in tests; new live tests need explicit transfer
and budget authorization. See [the approved rules](final_delivery_rules.md).
