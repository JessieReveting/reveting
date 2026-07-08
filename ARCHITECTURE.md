# Reveting Operations Manager Architecture

Reveting Operations Manager is a read-only AI operations manager and AI operations copilot for LinkedIn Live production, podcast production operations, livestream operations, guest booking workflows, calendar QA, and show operations automation.

The system is designed to help Reveting understand what is booked, what is scheduled, what is missing, what is risky, and what a human operator should do next without changing production systems automatically.

Not every show begins from the same source of truth. Some shows are booking-driven, while others are editorial-first and start from approved research and an episode brief.

## Core System Map

### External System Roles

- HighLevel = booking, forms, contacts, and custom fields source
- Google Calendar = production schedule source
- StreamYard = livestream studio and recording source
- LinkedIn Events = promotion and event source
- Gmail = guest communication source
- Google Drive = asset and source file storage

### Internal System Roles

- Operations Audit = QA layer
- Daily Operations Brief = operator layer
- Operations Copilot = work queue layer
- Knowledge Mode = learning layer

## Why The Architecture Matters

Reveting show operations span multiple systems that each represent a different part of reality:

- HighLevel knows what was booked
- Google Calendar knows what is on the production calendar
- StreamYard knows what live room or recording environment exists
- LinkedIn Events knows what promotion event exists
- Gmail carries reminder and coordination context
- Google Drive holds working assets and source files

The architecture keeps those roles explicit so the system can compare them without blurring source-of-truth boundaries.

For editorial-first shows such as Breach of Protocol, the first source of truth is the approved story package and episode brief rather than HighLevel booking records.

## Layer 1: Discovery

Discovery reads external systems and writes normalized local snapshots.

Discovery should:

- authenticate safely
- read source data
- normalize it into a predictable shape
- write local artifacts for audit use

Discovery must not:

- make production decisions
- suppress issues
- send messages
- modify source systems

Current and planned snapshot roots include:

- `data/discovery/`
- `data/calendar/`
- `data/gmail/`
- `data/drive/`
- `data/streamyard/`

## Layer 2: Operations Audit

Operations Audit is the QA layer.

It compares normalized snapshots only and produces:

- issues
- severity
- evidence
- confidence
- recommended human action
- production health context

The audit should answer questions like:

- Does a HighLevel booking have a valid production calendar event?
- Does the calendar title reflect the real guest?
- Is the LinkedIn event ready?
- Is the StreamYard link ready?
- Is the show blocked by guest topics, confirmation, or production assets?
- Is this a true mismatch or a known exception?

The audit must remain read-only.

## Layer 3: Daily Operations Brief

The Daily Operations Brief is the operator layer.

It turns audit outputs into a short operational readout for the near-term show window. It helps a human operator understand:

- what is urgent today
- what is blocked
- what is safe to ignore today
- what work queue items are active
- what completion claims were actually verified

This is the “what should Jessie care about right now?” layer.

## Layer 4: Operations Copilot

The Operations Copilot is the work queue layer.

It translates audit findings into operator-facing tasks such as:

- finalize production links
- resolve calendar and HighLevel mismatches
- follow up for topics
- confirm guest status
- source a replacement guest

This layer is not an automation engine. It is a prioritization and coordination layer for human operators.

## Layer 5: Trust Layer

The Trust Layer explains confidence and boundaries.

Instead of flattening everything into “right” or “wrong,” it classifies operational findings into buckets such as:

- Confirmed Issues
- Needs Verification
- PR Representative Booking / Guest Represented
- Waiting on Guest
- Waiting on Guest Topics
- Known Exceptions
- Needs Human Follow-Up

This matters because Reveting operations often include:

- PR representatives booking on behalf of guests
- manually corrected production calendars
- replacement guests
- human-confirmed exceptions
- valid LinkedIn events that are missing from the calendar description

## Layer 6: Knowledge Mode

Knowledge Mode is the learning layer.

It stores approved or observed operational context in local configuration such as:

- known exceptions
- known decisions
- known patterns
- LinkedIn event evidence
- show preferences

Knowledge Mode exists so the system can learn from repeated operations work without silently changing logic or hiding uncertainty.

## Source-Of-Truth Boundaries

The current model is intentionally explicit:

- HighLevel is the best source for bookings, form submissions, submitters, and custom fields
- Google Calendar is the best source for scheduled production events
- StreamYard is the best source for live-room and recording readiness
- LinkedIn Events is the best source for promotion-event existence
- Gmail is the best source for communication history
- Google Drive is the best source for files and assets

There is one important workflow exception:

- Editorial-first shows can use an approved story, episode brief, and production-asset package as the primary source of truth before any guest-booking system is involved

The audit layer exists precisely because these sources do not always agree.

## Connector Boundary

Connectors isolate external systems.

A connector may:

- authenticate
- read source data
- normalize records
- write local snapshots

A connector must not:

- contain business rules
- determine operator priority
- send communications without an approved future automation layer

Connector folders include:

- `connectors/highlevel/`
- `connectors/google_calendar/`
- `connectors/gmail/`
- `connectors/google_drive/`
- `connectors/streamyard/`

## Rules Engine

Rules live in configuration rather than being scattered through code.

Current rule areas include:

- attendees and invite expectations
- calendar title and description checks
- production timeline expectations
- guest, PR, assistant, and alternate invite handling
- LinkedIn event and StreamYard readiness expectations
- production health scoring

Rules can also express workflow family differences, such as:

- guest-booking-first shows
- editorial-first shows
- recurring-host defaults
- story approval gates
- approval-gated production asset generation

This supports safer iteration and clearer review over time.

## Completion Verification

The architecture now includes a completion verification step for local operator claims.

That means the system can distinguish:

- Jessie marked a task done locally
- the fresh read-only audit verified it in source data

This prevents local completion notes from being treated as true production completion unless HighLevel, Google Calendar, or other relevant source evidence confirms them.

## Read-Only Safety Model

Version 1 is intentionally read-only.

The system should not directly:

- change HighLevel
- edit Google Calendar
- send Gmail messages
- edit StreamYard
- create or change LinkedIn Events
- update Google Drive assets

Any future automation must be narrow, approval-based, auditable, and clearly separated from discovery, audit, and reporting.

## Long-Term Direction

The long-term goal is not generic automation. It is safe operations assistance for Reveting’s recurring shows.

That means improving:

- LinkedIn Live show operations
- B2B podcast production operations
- livestream guest booking
- production readiness
- calendar QA
- operator clarity
- safe automation readiness

See [VERSION_2_ROADMAP.md](/Users/jessiebdex/Documents/Operations%20Automation/reveting/VERSION_2_ROADMAP.md) for the future roadmap.
