# Postman E2E Compiler v1

This package closes the missing transformation between Postman scenario
discovery and an executable multi-request JMeter artifact.

The pipeline is:

1. resolve declared Postman script correlations;
2. infer resource lifecycle correlations;
3. compile the selected candidate into a secret-safe executable model;
4. generate scenario-scoped CSV;
5. generate a local-only secrets properties template;
6. generate a multi-request JMX;
7. validate request count, dynamic resource IDs, extractors and data safety.

## Correlation provenance

Declared Postman correlations use:

`source = POSTMAN_SCRIPT`

Inferred CRUD resource correlations use:

`source = INFERRED_RESOURCE_LIFECYCLE`

The Restful Booker E2E resolves:

- `access_token <- Auth/CreateToken :: $.token`
- `booking_id <- Booking/CreateBooking :: $.bookingid`

## Secret handling

Secret-like JSON fields are not written as values to CSV or the executable
model. They become JMeter property references such as:

`${__P(secret_auth_createtoken_password,)}`

The generated secrets template contains blank values only and must remain
local/uncommitted.

## Scope

v1 intentionally supports duration-mode profiles. Iteration-mode execution
remains fail-closed until the controlled runner supports it end-to-end.
