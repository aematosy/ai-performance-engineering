# Performance Test Plan Contract

The canonical design must preserve:

- scenario;
- target;
- environment;
- authentication;
- workload;
- SLA;
- data requirements;
- transactions;
- correlations;
- expected HTTP contract;
- observability gaps;
- risks;
- approval state.

Executable generation requires an explicit HTTP response contract.

Do not silently default to HTTP 200.

Do not infer HTTP 201 merely because the method is POST.

If the contract is unknown, keep it unresolved until discovered or confirmed.
