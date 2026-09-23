# Performance Test Plan

**Status:** `APPROVED`
**Workload Status:** `APPROVED`
**Authorization Status:** `AUTHORIZED`
**Authorized By:** `Adrian Matos`
**Authorized At:** `2026-09-21T00:30:22.174320-05:00`

Scenario: `booking-e2e`

Execution Authorized: False

## Objective

Validate the selected Postman scenario under a controlled baseline workload.

## Target

https://restful-booker.herokuapp.com:443

## Transactions

- `POST /auth` (Auth/CreateToken)
- `POST /booking` (Booking/CreateBooking)
- `GET /booking` (Booking/GetBooking)
- `GET /booking/${booking_id}` (Booking/GetBookingByID)
- `PUT /booking/${booking_id}` (Booking/UpdateBooking)
- `PATCH /booking/${booking_id}` (Booking/PartialUpdateBooking)
- `DELETE /booking/${booking_id}` (Booking/DeleteBooking)

## Data

- CSV: `/Users/amatosya/perfomance/demo-agent-perf/data/booking-e2e/test-data.csv`
- Secrets template: `/Users/amatosya/perfomance/demo-agent-perf/data/booking-e2e/secrets.properties.template`

## Governance

Design and workload require human approval before execution.
Execution authorization is recorded separately.
