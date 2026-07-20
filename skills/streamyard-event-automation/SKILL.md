---
name: streamyard-event-automation
description: Process Reveting client-show bookings across multiple GoHighLevel accounts into one master Google Sheet, the ww@reveting.com Google Calendar, and StreamYard broadcasts. Use when asked to run, audit, resume, or configure the GHL-to-calendar-to-sheet-to-StreamYard pipeline for Beyond the Cart, The David Daily Show, Ridgeback Network Defense shows, WinsDay, Apparel with Purpose, or Deconstructing Data.
---

# StreamYard Event Automation

Operate one idempotent production pipeline across Reveting's customer show accounts. Treat GHL as the booking source, the master sheet as the cross-system ledger, `ww@reveting.com` as the production calendar, and StreamYard as the broadcast system.

## Load configuration

Read [references/account-routing.md](references/account-routing.md) before configuring or running a batch. Route by GHL location plus calendar/form identifiers; never route only by host name.

Use the browser-control skill for GHL and StreamYard when no approved API or connector is available. Use connected Google Calendar and Google Sheets tools for their respective records.

## Run the pipeline

1. Open every enabled GHL account in the routing table.
2. Read active bookings created or changed since the prior successful cursor.
3. Normalize each booking into one episode record. Preserve the GHL location ID, calendar ID, appointment ID, contact ID, form submission ID, guest data, timezone, raw topics, and original payload.
4. Match the show using the configured location and calendar/form identifiers. Stop and flag ambiguous or unmapped bookings.
5. Build the idempotency key as `ghl_location_id + appointment_id`. Search the master sheet before creating anything.
6. Show the proposed create/update batch and source gaps to the user. Require approval before external writes.
7. Upsert the master-sheet row first and mark its state `Approved for production`.
8. Create or update the `ww@reveting.com` Google Calendar event in Eastern Time. Include the guest, production team, pre-show block, approved title/topics, and the master-row identifier.
9. Create the StreamYard broadcast through the browser's `Create → Live stream` flow. Use the approved episode title, date, go-live time, and per-show destinations.
10. Copy the StreamYard studio URL and broadcast metadata back to both the calendar event and the same master-sheet row.
11. Re-read the sheet, calendar, and StreamYard result. Mark the row `Production setup complete` only when identifiers and URLs reconcile.
12. Save a per-account cursor only after the batch verifies successfully.

## Apply content and timing rules

- Keep GHL raw topics as evidence; never publish them directly.
- Require approved, edited topics before publishing guest-facing calendar or StreamYard content.
- Use Eastern Time on the production calendar and retain the guest's original timezone separately.
- Reserve the configured pre-show period, normally 15 minutes.
- Use the corrected episode number and show-specific CTA from the master record.
- Treat Ridgeback's two shows as separate show routes even when they share a GHL location or StreamYard account.

## Handle destinations

- Default new broadcasts to LinkedIn, YouTube, Facebook, and Twitter/X when those destinations are enabled for the show.
- Use per-show destination overrides from the Config tab; do not infer them from a prior broadcast.
- Before creating a broadcast, verify each destination is connected and authorized.
- If any required destination is disconnected or expiring, stop that broadcast, flag `Destination reconnect required`, and continue preparing non-destructive drafts for the rest of the batch.
- Never silently omit a requested destination.

## Maintain the master sheet

Keep one episode per row. At minimum, write:

- show key, client, host, lifecycle state, and Reveting episode number
- GHL location/calendar/appointment/contact/form IDs
- guest name, email, phone, LinkedIn URL, timezone, and raw submission
- approved title, edited topics, CTA, pre-show time, and go-live time
- Google Calendar event ID and URL
- StreamYard studio URL and selected destinations
- source timestamps, review notes, error state, and last successful pipeline step

Never create a second row when the idempotency key already exists. Update only fields supported by newer source evidence.

## Recovery rules

- Resume from the last successful step recorded in the row.
- If the sheet exists but the calendar does not, create only the calendar and downstream steps.
- If the calendar exists but StreamYard does not, reuse the calendar event and create only the broadcast.
- If StreamYard exists, never recreate it solely because the calendar or sheet lacks its URL; verify and write back the existing URL.
- Route cancellations and reschedules to human review before changing calendar invitations or broadcasts.

## Completion check

- Confirm every enabled GHL account was scanned.
- Confirm every processed booking has exactly one master row.
- Confirm calendar date/time, title, attendees, and studio URL match the row.
- Confirm StreamYard title, date/time, and selected destinations match the row.
- Report skipped accounts, ambiguous routing, disconnected destinations, and any pending user approval.
