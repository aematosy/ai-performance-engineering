# Natural Design Contract

Public entrypoint:

`scripts/natural_performance_design.sh`

Do not invoke internal workflow operations directly.

Do not inspect `--help`.

Do not execute performance load during design.

When the expected HTTP status is unknown, one single functional request may be
used to observe the response safely.

If the response is successful and unambiguous, propose it as the functional
contract.

Otherwise leave the contract unresolved and request human confirmation.
