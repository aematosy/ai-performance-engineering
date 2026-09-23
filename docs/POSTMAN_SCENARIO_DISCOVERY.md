# Postman Scenario Discovery

`discover_postman_scenarios.py` consumes the normalized Postman v2 model and
produces deterministic scenario candidates before any LLM reasoning.

Candidate types:

- `AUTH`
- `HEALTH`
- `READ_ONLY`
- `WRITE`
- `DEPENDENCY_FLOW`
- `E2E_CANDIDATE`

The discovery layer does not invent missing correlations. When a create
operation exists but downstream operations still target static identifiers, the
E2E candidate is marked `requires_correlation: true`.

The output is advisory discovery, not approval. aXet Code or a human may choose
which candidate should become a Performance Test Plan, but the candidate model
must pass deterministic validation first.
