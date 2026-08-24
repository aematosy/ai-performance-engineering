# Performance Data Classification v1.1

This revision hardens configuration detection.

A declared Postman variable is classified as `CONFIGURATION` when its name or
value clearly represents environment/system configuration, including values such
as:

- base URL
- host
- protocol
- port
- endpoint
- service or microservice URL
- domain
- tenant / region / namespace

A URL-valued environment variable is therefore not emitted as CSV test data.

The validator also rejects overlap between `TEST_DATA_CANDIDATE` and
`CONFIGURATION`, `RUNTIME_CORRELATED`, or `SECRET`.

The intended invariant is:

`CSV = business test data only`

and never:

`CSV = configuration + runtime values + secrets + business data`.
