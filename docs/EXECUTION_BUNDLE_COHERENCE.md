# Execution Bundle Coherence v1.1

This revision aligns scenario identity resolution with the real project test-plan
contract.

The current canonical scenario identity is:

```yaml
metadata:
  name: create-post-demo
```

The validator still accepts earlier compatible shapes for backward
compatibility, but new regression coverage explicitly tests `metadata.name`.

## Why this matters

The previous validator tests used a synthetic shape:

```yaml
scenario:
  name: create-post-demo
```

while the actual project plan uses `metadata.name`.

The result was:

`unit tests PASS + real artifact FAIL`

v1.1 adds a regression test for the real plan structure.

## Bundle rules

- Plan scenario must match JMX metadata scenario.
- Design-context candidate must match data-requirements candidate.
- When strict Postman binding is requested, the plan must explicitly bind to
  the candidate.
- Valid artifacts from unrelated scenarios must never be combined for
  execution.
