# Reveting AI Operations Manager Architecture

Version 1 establishes a read-only, auditable operations platform for Reveting livestream and podcast production.

## Mission

The Operations Manager is the central operations platform for Reveting. It should eventually understand every show, guest, booking, calendar event, production task, SOP, asset, and communication required to produce a livestream or podcast.

The system must remain modular, deterministic, explainable, auditable, and read-only until automation is explicitly enabled.

## Layers

### Layer 1: Discovery

Discovery reads external systems and writes normalized JSON snapshots.

Discovery must not make decisions.

Current and future snapshot roots:

- `data/discovery/`
- `data/calendar/`
- `data/gmail/`
- `data/drive/`
- `data/streamyard/`

### Layer 2: Operations Audit

Audit compares normalized snapshots only. It must not call external APIs and must never modify data.

Every issue should include:

- Severity
- Reason
- Evidence
- Confidence
- Recommended action
- Human-readable explanation

### Layer 3: Rules Engine

Rules live in configuration, not source code. Version 1 rules are stored in `config/operations_rules.json`.

Rules may define:

- Required attendees and invite recipients
- Guest, PR, assistant, and alternate invite email checks
- Calendar title and description expectations
- Required Drive, StreamYard, SOP, and production assets
- Required custom form fields
- Pre-show offset and show duration
- Production health scoring

### Layer 4: Automation

Automation is not implemented in Version 1.

Future automation must be approval-based and separated from discovery, audit, and rules.

## Connector Boundary

Connectors isolate external systems. A connector may authenticate, read, normalize, and write JSON snapshots. It must not contain business logic or recommendations.

Connector folders:

- `connectors/highlevel/`
- `connectors/google_calendar/`
- `connectors/gmail/`
- `connectors/google_drive/`
- `connectors/streamyard/`

## Onboarding Model

Future client/show onboarding should require:

- Credentials
- Configuration
- SOP

It should not require Python code changes.

