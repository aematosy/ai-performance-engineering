# Natural Execution Contract

Public entrypoint:

`scripts/natural_performance_execute.sh`

Internal approval, authorization, preparation, validation and engine dispatch
are implementation details.

Gemini must not orchestrate them manually.

The flow must be resumable and idempotent.

Supported engines:

- JMeter
- Locust

Once selected, the engine cannot silently change.

Real load requires exact:

`RUN`

After RUN, execute the validated bundle and return deterministic evidence.

Do not perform manual retries or CLI discovery.

Do not call internal workflow operations directly.
