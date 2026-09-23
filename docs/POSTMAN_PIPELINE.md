# Deterministic Postman Intake Pipeline

`postman_pipeline.py` orchestrates the deterministic Postman intake flow before any LLM reasoning.

It runs these stages in order:

1. normalize collection/environment;
2. validate normalized model;
3. discover scenario candidates;
4. validate candidate model;
5. optionally prepare one minimal design context;
6. optionally require execution readiness.

The pipeline writes a small manifest with SHA-256 hashes of the source collection/environment and the status of each stage.

## Discovery only

```bash
poetry run python scripts/postman_pipeline.py \
  --collection path/to/collection.json \
  --environment path/to/environment.json \
  --workspace work/postman/example
```

## Prepare one design context

```bash
poetry run python scripts/postman_pipeline.py \
  --collection path/to/collection.json \
  --environment path/to/environment.json \
  --candidate-id example-read-read-only \
  --workspace work/postman/example
```

## Require execution readiness

Add `--require-execution-ready`. The pipeline must fail when the selected context contains unresolved variables, unsupported features, missing resource correlations, or static-resource strategies that still require review.

## LLM boundary

aXet Code should consume `design-context.json`, not the raw Postman collection, unless diagnosing parser defects. This keeps context small and makes deterministic evidence the source of truth.
