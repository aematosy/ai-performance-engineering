# Natural Design Command Contract

Public entrypoint:

scripts/natural_performance_design.sh

For a cURL supplied by the user, invoke one Shell command only.

The command must be a single physical line.

Required structured arguments:

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

heredoc
stdin
WriteFile
multiline shell construction
Markdown fences inside Shell
positional argument guessing
input discovery
--help
manual retries

An existing file may be used only when the user explicitly supplied its path, via --input.
