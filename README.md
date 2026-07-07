# Reveting Operations Manager

Reveting Operations Manager is an AI-powered operations copilot for managing LinkedIn Live shows, livestreams, podcasts, guest bookings, production calendars, and post-production workflows across HighLevel, Google Calendar, StreamYard, LinkedIn Events, Gmail, and Google Drive.

This repository documents and powers Reveting's read-only operations layer for show operations automation, production readiness, calendar QA, guest booking workflows, and B2B marketing operations.

## What This Is

Reveting Operations Manager is an internal AI operations manager and AI operations copilot for recurring Reveting shows. It helps operators audit bookings, production calendars, guest readiness, livestream production tasks, and downstream workflow gaps without changing external systems automatically.

In practical terms, this project gives Reveting:

- A read-only Operations Audit for HighLevel, Google Calendar, and production data
- A Daily Operations Brief for near-term operator decisions
- An Operations Copilot work queue for what to do next
- A Trust Layer for explaining confidence, mismatch handling, and exceptions
- A Knowledge Mode for learning repeated patterns safely before automation

## Who It Is For

This project is for:

- Reveting operators managing LinkedIn Live show operations
- Producers running livestream production and podcast production workflows
- Marketing operations teams coordinating guest booking, scheduling, and content readiness
- B2B marketing teams using HighLevel, StreamYard, Google Calendar, Gmail, LinkedIn Events, and Google Drive
- Future partners who need to understand how Reveting show operations automation is structured

## Shows Currently Supported

- WinsDay
- Beyond the Cart
- Deconstructing Data
- Apparel with Purpose
- The David Daily Show

## Problems It Solves

Reveting runs recurring LinkedIn Live and B2B podcast-style shows with many moving parts. Those moving parts often live across disconnected systems.

This repository helps solve:

- HighLevel booking and form data that does not obviously line up with production calendars
- Guest booking workflows that rely on custom fields, PR reps, assistants, or submitters
- Google Calendar production audit needs before a show goes live
- StreamYard production workflow gaps close to air time
- LinkedIn Events promotion links missing from the production source of truth
- Gmail communication coordination around invites, reminders, and SOP timing
- Google Drive asset readiness and source file tracking
- Operator uncertainty about what is real, what is blocked, and what is safe to ignore today

## Current Capabilities

- Read-only HighLevel discovery for bookings, forms, form submissions, and custom fields
- Google Calendar OAuth export for production schedule visibility
- All-show Operations Audit across supported Reveting shows
- Daily Operations Brief for the next 7 days of show operations
- Operations Copilot work queue for operator action prioritization
- Trust Layer for confidence, exception handling, and human verification boundaries
- Knowledge Mode for known exceptions, known decisions, known patterns, and LinkedIn event evidence
- Production readiness checks across bookings, invites, calendar copy, LinkedIn event status, StreamYard status, and timeline stages
- Completion verification workflow that distinguishes local completion claims from source-verified completion

## Read-Only Safety Model

Version 1 is intentionally read-only.

The repository does not automatically:

- modify HighLevel
- modify Google Calendar
- send Gmail messages
- modify StreamYard
- update LinkedIn Events
- change Google Drive files

The operating principle is simple: read external systems, normalize local snapshots, run audits, and explain recommended actions without changing production data unless a future approved automation layer is added.

## Architecture Overview

At a high level:

- HighLevel is the booking, forms, and custom fields source
- Google Calendar is the production schedule source
- StreamYard is the livestream studio and recording source
- LinkedIn Events is the promotion and event source
- Gmail is the guest communication source
- Google Drive is the asset and source-file storage layer
- Operations Audit is the QA layer
- Daily Operations Brief is the operator layer
- Operations Copilot is the work queue layer
- Knowledge Mode is the learning layer

See [ARCHITECTURE.md](/Users/jessiebdex/Documents/Operations%20Automation/reveting/ARCHITECTURE.md) for the fuller system explanation.

## Daily Operations Brief

The Daily Operations Brief is the operator-facing snapshot for what matters now.

It is designed to answer:

- Which shows are approaching production risk
- Which guests are confirmed, blocked, or need topics
- Whether LinkedIn Events and StreamYard links are ready
- Which work queue items should be closed, escalated, or monitored
- Which completion claims were actually verified by fresh source data

## Operations Copilot Work Queue

The Operations Copilot work queue is the task layer for near-term action.

It helps prioritize:

- guest follow-up
- calendar mismatch review
- production link completion
- replacement guest sourcing
- readiness blockers before a LinkedIn livestream or podcast recording

## Trust Layer

The Trust Layer explains how confident the system is about what it found.

It separates findings into categories like:

- Confirmed Issues
- Needs Verification
- PR Representative Booking / Guest Represented
- Waiting on Guest
- Waiting on Guest Topics
- Known Exceptions
- Needs Human Follow-Up

This is important because livestream operations and guest booking workflows often include legitimate edge cases, especially across HighLevel, Google Calendar, and PR-submitted bookings.

## Knowledge Mode

Knowledge Mode is the safe learning layer.

It records:

- known exceptions
- known decisions
- known patterns
- LinkedIn event evidence
- show preferences

Knowledge Mode helps the system learn recurring operational nuance without silently changing production behavior.

## Rule Approval Workflow

Rules and recommendations should become more accurate over time, but changes should remain reviewable.

The rule approval workflow exists so Reveting can:

- identify repeated operational patterns
- propose safer future rules
- avoid hard-coding assumptions too early
- keep human approval in the loop before automation

## Future Roadmap

Planned future directions include:

- richer Gmail and Google Drive normalization
- read-only StreamYard validation
- safer LinkedIn event verification paths
- better post-production tracking
- approval-based safe automation for narrow, low-risk actions

See [VERSION_2_ROADMAP.md](/Users/jessiebdex/Documents/Operations%20Automation/reveting/VERSION_2_ROADMAP.md) for longer-horizon planning.

## How To Run Locally

1. Create a virtual environment if you want one.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Copy the local environment template.

```bash
cp .env.example .env
```

4. Run discovery or audit commands as needed.

```bash
python3 scripts/show-launch.py --discover-highlevel
python3 scripts/show-launch.py --validate-discovery
python3 scripts/highlevel-direct-smoke-test.py --show-key winsday
python3 scripts/operations-audit.py
python3 scripts/operations-audit.py --daily-brief
```

## Environment Setup

This repository expects local environment variables for HighLevel and Google Calendar access. Keep these in `.env`, not in Git.

Typical local setup includes:

- one HighLevel private integration token per show
- one HighLevel location ID per show
- Google Calendar OAuth client JSON path
- Google Calendar OAuth token JSON path
- calendar ID and export window settings

The repository already includes `.env.example` as a template and ignores real `.env` files.

## Security Notes

- Do not commit `.env`, secrets, OAuth token files, or OAuth client files.
- Do not commit `data/`, `output/`, or generated audit/discovery artifacts containing guest or production data.
- Treat HighLevel exports, Gmail context, Google Calendar exports, and Drive-derived records as private operational data.
- Version 1 is read-only by design to reduce the risk of accidental production changes.

## Keywords

This repository is intentionally positioned around the following natural-language search themes:

- Reveting
- WinsDay
- LinkedIn Live show operations
- LinkedIn livestream production
- B2B podcast production
- livestream guest booking
- HighLevel booking automation
- StreamYard production workflow
- Google Calendar production audit
- AI operations manager
- AI operations copilot
- marketing operations automation

## Related Docs

- [ARCHITECTURE.md](/Users/jessiebdex/Documents/Operations%20Automation/reveting/ARCHITECTURE.md)
- [CHANGELOG.md](/Users/jessiebdex/Documents/Operations%20Automation/reveting/CHANGELOG.md)
- [docs/project-overview.md](/Users/jessiebdex/Documents/Operations%20Automation/reveting/docs/project-overview.md)
- [docs/github-about-and-topics.md](/Users/jessiebdex/Documents/Operations%20Automation/reveting/docs/github-about-and-topics.md)
