# Delivery configurations

The standalone entry exports `Agent` from `agent.py` and preserves reset/respond.
It uses `starter.delivery.Agent` internally. Offline is the default; live
performance of the integrated LLM configuration has not been measured.

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
does not enable requests: defaults stop at the boundary. No .env files are loaded
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
paid run. Request timeout is 8 seconds with no retries, not a guarantee
of an 8-second whole-turn deadline.

`diagnostics.delivery` identifies requested mode, per-turn success/fallback/skip,
cumulative attempts/successes/fallbacks, allowance and stop reason. Response usage
contains known per-turn tokens; a failed attempt with unknown usage uses allowance
accounting, not a claim of zero billing. Invalid provider details are redacted.
No successful calls means no successful enhancement validation, even if the Agent
completed every session. Normal gate skips are not API failures.

From the standalone bundle directory, check the evaluator command-line entry:

```bash
python tools/evaluate_offline.py --help
```

This checks CLI availability only; it does not evaluate the Agent or reproduce
benchmark results. Follow the bundled `README.md` for asset preparation and the
official-harness evaluation command. The repository test suite is not included
in the standalone bundle.
