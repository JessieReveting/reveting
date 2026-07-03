# HighLevel Connector

Version 1 responsibilities:

- Authenticate with one location-scoped private integration token per show/sub-account.
- Read HighLevel appointments, forms, form submissions, contacts, calendars, and custom fields.
- Normalize snapshots under `data/discovery/`.

No business rules or audit decisions belong here. Do not use one client's token to access another client's data.

