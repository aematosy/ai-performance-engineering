# Scenario-scoped Performance Test Data

Collection-wide classification is useful for discovery, but CSV files should be
generated for a selected scenario.

Flow:

`data-classification.json`
+
`design-context.json`
→
`scenario-data.json`
→
`test-data.csv`
+
`data-requirements.json`

## Column naming

For a single request, request prefixes are removed when safe:

`booking_createbooking_firstname` → `firstname`

For multi-request scenarios, duplicate semantic field names remain qualified:

`booking_createbooking_firstname`
`booking_updatebooking_firstname`

This avoids collisions while keeping simple scenarios readable.

## Safety

The scenario scope never copies configuration, runtime-correlated variables, or
secrets into the CSV.

Those sections remain metadata only.
