# Experiments

Use this folder for team experiment notes. Do not commit large generated artifacts.

Recommended note format:

```markdown
# YYYY-MM-DD Experiment Name

## Hypothesis

## Change

## Command

## Public Score

- HitRate@10:
- MRR:
- MTTC:
- TechnicalScore:

## Scenario Breakdown

- Buying:
- Browsing:
- Intent Override:
- Boundary:

## Notes
```

Suggested experiment sequence:

1. `baseline-bm25`: reproduce official score.
2. `stateful-bm25`: use accumulated user messages across turns.
3. `slot-extraction`: extract material/color/size/style/brand/budget/use_case.
4. `metadata-rerank`: combine BM25 with structured field matching.
5. `adaptive-questions`: ask high-value attributes only when the candidate set is broad.
6. `embedding-retrieval`: add local embedding retrieval with an offline index.
7. `hybrid-rerank`: blend BM25, embeddings, metadata, and session state.
