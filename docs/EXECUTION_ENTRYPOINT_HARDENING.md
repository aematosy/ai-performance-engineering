# Execution Entry Point Hardening v1.1

The previous patch used a regex that was too strict for a real Make recipe with
shell continuations. v1.1 parses Makefile targets by boundaries instead:

- find `run-demo:`;
- consume until the next Make target;
- replace only that block;
- preserve following targets.

The public flow becomes:

`make authorize-demo AUTHORIZED_BY="Name"`
-> explicit authorization

`make preflight-demo`
-> controlled validation

`make run-demo`
-> controlled `--execute`
-> authorization verification
-> final `RUN` confirmation

No public Makefile route uses `--authorized`.
