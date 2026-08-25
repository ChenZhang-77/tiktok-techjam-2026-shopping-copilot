# Submission Notes

The official submission should contain:

- one Python agent entry file exporting `Agent`
- any local helper modules
- setup instructions
- a short report describing method, model choice, cost, latency, limitations, and team contributions

Recommended final layout:

```text
submission/
  agent.py
  requirements.txt
  README.md
  src/
```

Before final packaging:

- Do not modify `evaluator/` for reported scores.
- Do not include private evaluation data.
- Do not include API keys, `.env`, tokens, or credentials.
- Disclose any external model/API dependency.
- Provide an offline fallback if possible.
- Confirm the agent returns valid `message`, `ask_attribute`, `recommendations`, and `usage`.
