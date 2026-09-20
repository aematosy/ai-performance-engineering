# Natural Design Request Contract

The only public design command is:

scripts/natural_performance_design_request.sh

Use one non-interactive Shell invocation.

Required request arguments:

--scenario
--method
--url
--header
--body
--users
--ramp-time-seconds
--duration-seconds
--pacing-seconds

Forbidden:

- heredoc
- stdin
- WriteFile
- input discovery
- positional arguments
- --help
- manual retries

The public front door owns cURL materialization, contract probing and validation.
