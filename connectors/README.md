# Connectors

Connectors isolate every external system behind a read-only boundary for Version 1.

Each connector may:

- Authenticate
- Read source data
- Normalize source data into JSON snapshots
- Write snapshots under `data/`

Connectors must not contain business logic, audit rules, recommendations, or automation behavior. Discovery collects evidence; the operations audit compares normalized snapshots; future automation must remain approval-based and separate.

Current connector targets:

- `highlevel/`
- `google_calendar/`
- `gmail/`
- `google_drive/`
- `streamyard/`

