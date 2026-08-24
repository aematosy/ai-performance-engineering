# Execution Authorization v1.1

Execution authorization now synchronizes both authoritative YAML state and the
companion human-readable Markdown.

## Transaction

The authorization command:

1. validates design/workload approval;
2. validates explicit human identity;
3. creates plan and Markdown pre-authorization backups;
4. writes YAML authorization state atomically;
5. synchronizes canonical Markdown status lines;
6. never executes JMeter.

Canonical Markdown lines are:

```text
**Status:** `APPROVED`
**Workload Status:** `APPROVED`
**Authorization Status:** `AUTHORIZED`
**Authorized By:** `<human>`
**Authorized At:** `<timestamp>`
```

The synchronization is idempotent and removes obsolete status aliases such as
`Execution Authorization: PENDING`.

Because YAML authorization changes the plan SHA-256, JMX + metadata must be
regenerated after authorization/resynchronization.
