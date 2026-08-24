# Postman Normalized Model v2

Purpose: convert Postman Collection v2.0/v2.1 plus an optional environment into a neutral, deterministic model consumed by downstream Performance Engineering tooling.

Principles:
- Parse deterministically before involving an LLM.
- Never execute Postman JavaScript during parsing.
- Never persist raw secrets into normalized output.
- Preserve variable scope and unresolved references.
- Detect runtime variable producers and consumers.
- Report unsupported features explicitly.
- Treat Postman response-time tests as candidate SLA evidence, never an approved SLA.
- Keep Postman-specific concerns isolated from JMeter generation.

Strict validation fails when unresolved variables or unsupported feature occurrences exist. Non-strict mode reports them as warnings.
