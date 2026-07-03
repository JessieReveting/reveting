# Reveting Show Operations Tool

Internal tooling for Reveting show operations, including read-only discovery, Google Calendar exports, operations audits, and production health reporting.

Version 1 is read-only. Do not enable automation until explicitly approved.

See [ARCHITECTURE.md](/Users/jessiebdex/Documents/Operations%20Automation/reveting/ARCHITECTURE.md) for the long-term platform architecture and [VERSION_2_ROADMAP.md](/Users/jessiebdex/Documents/Operations%20Automation/reveting/VERSION_2_ROADMAP.md) for future work that must not begin without approval.

## Setup

1. Create a local virtual environment if you want one:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Create a local `.env` file in the project root and add the HighLevel tokens:

```bash
cp .env.example .env
```

Required variables:

```env
HIGHLEVEL_TRANSPORT=direct
HIGHLEVEL_RELAY_BASE_URL=
HIGHLEVEL_RELAY_SHARED_SECRET=

HIGHLEVEL_TOKEN_CHERRY_WILLOW=
HIGHLEVEL_LOCATION_ID_CHERRY_WILLOW=
HIGHLEVEL_TOKEN_DAVID_DAILY=
HIGHLEVEL_LOCATION_ID_DAVID_DAILY=
HIGHLEVEL_TOKEN_BEYOND_THE_CART=
HIGHLEVEL_LOCATION_ID_BEYOND_THE_CART=
HIGHLEVEL_TOKEN_DECONSTRUCTING_DATA=
HIGHLEVEL_LOCATION_ID_DECONSTRUCTING_DATA=
HIGHLEVEL_TOKEN_WINSDAY=
HIGHLEVEL_LOCATION_ID_WINSDAY=

GOOGLE_CALENDAR_ID=ww@reveting.com
GOOGLE_CALENDAR_AUTH_MODE=oauth
GOOGLE_CALENDAR_OAUTH_CLIENT_JSON=secrets/google-calendar-oauth-client.json
GOOGLE_CALENDAR_OAUTH_TOKEN_JSON=secrets/google-calendar-token.json
GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON=
GOOGLE_CALENDAR_DELEGATED_USER=
GOOGLE_CALENDAR_EXPORT_DAYS_AHEAD=180
```

`scripts/show-launch.py` and `scripts/highlevel-direct-smoke-test.py` automatically load `.env` from the project root before validating tokens. Existing system environment variables are preserved and take precedence over values in `.env`.

## Supported HighLevel Pattern

The primary supported pattern is direct, location-scoped API access with one private integration token per show/sub-account.

- Base URL: `https://services.leadconnectorhq.com`
- Version header: `2021-04-15`
- Auth style: `Authorization: Bearer <pit-...>`
- Working documented auth check: `POST /contacts/search`
- Required request body for our sub-account tokens: `{"locationId":"...","pageLimit":1}`

This matches HighLevel's official Contacts API docs and works for the WinsDay private integration token when the token and location ID belong to the same sub-account.

If you explicitly want to force relay mode from a deployed server, set:

```env
HIGHLEVEL_TRANSPORT=relay
```

For direct mode, each show should have both:

- `HIGHLEVEL_TOKEN_*`
- `HIGHLEVEL_LOCATION_ID_*`

Required location IDs:

```env
HIGHLEVEL_LOCATION_ID_CHERRY_WILLOW=
HIGHLEVEL_LOCATION_ID_DAVID_DAILY=
HIGHLEVEL_LOCATION_ID_BEYOND_THE_CART=
HIGHLEVEL_LOCATION_ID_DECONSTRUCTING_DATA=
HIGHLEVEL_LOCATION_ID_WINSDAY=
```

The script does not assume a private token can use agency-wide location search endpoints.

## Minimal Direct Smoke Test

Use this standalone test to validate one private integration token against one documented HighLevel endpoint from a clean local environment:

```bash
python3 scripts/highlevel-direct-smoke-test.py --show-key winsday
```

Expected success shape:

- endpoint: `https://services.leadconnectorhq.com/contacts/search`
- method: `POST`
- status: `200`

The script never prints the token and redacts known secrets from errors.

## Relay Setup

Install the relay dependencies in your deployed environment:

```bash
pip install -r requirements-server.txt
```

Run the relay:

```bash
uvicorn server.highlevel_relay:APP --host 0.0.0.0 --port 8000
```

Then point the desktop tool at it:

```env
HIGHLEVEL_TRANSPORT=relay
HIGHLEVEL_RELAY_BASE_URL=https://your-relay-host
HIGHLEVEL_RELAY_SHARED_SECRET=your-shared-secret
```

Relay mode is optional. Keep it as a fallback if a deployed environment is ever needed for network-policy reasons.

## Test HighLevel Auth

Use this to verify the documented location-scoped HighLevel endpoint from the main orchestration script:

```bash
python3 scripts/show-launch.py --test-highlevel-auth --show-key winsday
```

The auth test uses `POST /contacts/search` with the configured `HIGHLEVEL_LOCATION_ID_*` for that show.

## Run Discovery

This will load `.env` automatically and run HighLevel discovery for the WinsDay sub-account without manually exporting tokens:

```bash
python3 scripts/show-launch.py --discover-highlevel --show-key winsday
```

Run all configured shows after all five `HIGHLEVEL_LOCATION_ID_*` values are present:

```bash
python3 scripts/show-launch.py --discover-highlevel
```

Discovery writes these per-show read-only artifacts:

- `data/discovery/{show_key}_appointments.json`
- `data/discovery/{show_key}_forms.json`
- `data/discovery/{show_key}_form_fields.json`
- `data/discovery/{show_key}_form_submissions.json`
- `data/discovery/{show_key}_custom_field_map.json`
- `data/discovery/{show_key}_episodes.json`

Appointment discovery keeps appointments, contacts, and form submissions separate. For shows like WinsDay that can have two guests per episode, `*_episodes.json` groups records by episode date/time while preserving each guest and each form submission independently.

### Discovery Calendar Selection

HighLevel bookings are treated as the source of truth, so discovery now validates the booking calendar before writing appointment artifacts.

For each show, discovery:

- Loads all calendars in that HighLevel location.
- Checks whether the configured `calendar_id_hint` exists.
- Checks whether the configured `calendar_name_hint` matches an available calendar.
- Finds the configured booking form, when available.
- Probes appointment counts for all calendars in the location.
- Prefers calendars associated with the show's booking form.
- Ranks candidate calendars by config match, form association, active status, and appointment count.
- Writes confidence, warnings, configuration mismatches, and alternate calendars considered into discovery metadata.

Calendar hints live in:

```bash
scripts/show-launch.py
```

Update the matching show entry if HighLevel creates a replacement booking calendar or if a stale calendar starts returning 0 appointments:

```python
"calendar_name_hint": "Exact HighLevel calendar name",
"calendar_id_hint": "ExactHighLevelCalendarId",
```

Discovery confidence means:

- `High`: the selected calendar has strong evidence, usually a config/form match plus appointment data.
- `Medium`: the selected calendar is plausible, but appointment data or configuration evidence is incomplete.
- `Low`: discovery could not prove the selected calendar is the booking source of truth.

Open the discovery health dashboard after discovery:

```bash
open data/discovery/discovery_health.html
```

The dashboard shows selected calendars, IDs, appointment counts, form counts, contact sample counts, confidence, warnings, and configuration mismatches for all shows.

### Validate Discovery

Use validation when a show has 0 appointments, a stale calendar hint, or unclear discovery confidence:

```bash
python3 scripts/show-launch.py --validate-discovery
```

Limit validation to one show:

```bash
python3 scripts/show-launch.py --validate-discovery --show-key beyond-the-cart
```

Validation checks:

- Token valid.
- Location valid.
- Calendar exists.
- Calendar ID matches config.
- Booking form found.
- Appointment endpoint returning data.
- Discovery confidence.

If a check fails, the command prints the failed show, the reason, and the exact configuration area to review. It does not modify HighLevel or Google Calendar.

## Run Operations Audit

Discovery is Version 1. Do not expand discovery unless a missing field blocks audit or operations work.

The read-only operations audit compares HighLevel Discovery V1 artifacts against the `ww@reveting.com` Google Calendar. It does not change Google Calendar, HighLevel, or email.

Audit rules and health scoring live in:

```bash
config/operations_rules.json
```

Rules are configuration, not source-code decisions. Use this file for pre-show offsets, required attendees, required description sections, SOP assets, required custom fields, and production health deductions.

The same rules file also controls audit trust behavior:

- `guest_lifecycle_rules` defines canceled, rescheduled, replaced, and otherwise non-actionable booking statuses.
- `suppression_rules.known_exceptions` and `suppression_rules.suppressed_issues` let operators suppress a specific issue by show, episode date, guest, issue code, reason, and expiration date.
- `issue_operational_impacts` explains why each issue matters in the HTML evidence panels.

First, export Google Calendar event data for `ww@reveting.com` to:

```bash
data/calendar/ww_reveting_events.json
```

### Option A: Direct API Export With OAuth

Recommended for a local Mac. This uses Google's OAuth Desktop app flow, opens a browser the first time you run it, saves a read-only token under `secrets/`, and exports directly to `data/calendar/ww_reveting_events.json` after that. It does not modify Google Calendar.

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a Google Cloud project for Reveting internal tooling.
3. Enable the [Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com) for that project.
4. If prompted, configure the OAuth consent screen:
   - User type: `Internal` if Reveting uses Google Workspace and that option is available, otherwise `External`.
   - App name: `Reveting Operations Audit`.
   - User support email: your Google account.
   - Developer contact email: your Google account.
   - Publishing status can stay in testing for local use.
   - Add your Google account as a test user if the app is external/testing.
5. Create credentials:
   - Credential type: `OAuth client ID`.
   - Application type: `Desktop app`.
   - Name: `Reveting Operations Audit Local`.
6. Download the OAuth client JSON.
7. Create the local secrets directory:

```bash
mkdir -p secrets
```

8. Save the downloaded file as:

```bash
secrets/google-calendar-oauth-client.json
```

The `secrets/` directory is ignored by git. Do not commit the OAuth client JSON or the generated token file.

Local `.env`:

```env
GOOGLE_CALENDAR_ID=ww@reveting.com
GOOGLE_CALENDAR_AUTH_MODE=oauth
GOOGLE_CALENDAR_OAUTH_CLIENT_JSON=secrets/google-calendar-oauth-client.json
GOOGLE_CALENDAR_OAUTH_TOKEN_JSON=secrets/google-calendar-token.json
GOOGLE_CALENDAR_EXPORT_DAYS_AHEAD=180
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the export:

```bash
python3 scripts/export-google-calendar.py
```

The first run opens your browser and asks for Google Calendar read-only consent. After approval, the script saves `secrets/google-calendar-token.json` locally and future exports run without manually copying/pasting event JSON.

Use a bounded audit window when testing:

```bash
python3 scripts/export-google-calendar.py \
  --time-min 2026-06-30T00:00:00-04:00 \
  --time-max 2026-09-28T23:59:59-04:00
```

The export includes normalized fields for event ID, calendar ID, title/summary, start/end, attendees, attendee emails, organizer, creator, description, location, meeting/conference link, and the raw event payload.

### Option B: Direct API Export With A Service Account

Use this only if a Workspace admin prefers service-account access. OAuth Desktop is simpler for local Mac setup.

Required Google credential:

- Enable the Google Calendar API in the Google Cloud project.
- Create a service account JSON key and keep it out of git, for example `secrets/google-calendar-service-account.json`.
- Share the `ww@reveting.com` calendar with the service account email with `See all event details`, or configure Google Workspace domain-wide delegation.
- Required OAuth scope: `https://www.googleapis.com/auth/calendar.readonly`.
- If using domain-wide delegation, set `GOOGLE_CALENDAR_DELEGATED_USER=ww@reveting.com`.

Local `.env`:

```env
GOOGLE_CALENDAR_ID=ww@reveting.com
GOOGLE_CALENDAR_AUTH_MODE=service-account
GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON=secrets/google-calendar-service-account.json
GOOGLE_CALENDAR_DELEGATED_USER=
GOOGLE_CALENDAR_EXPORT_DAYS_AHEAD=180
```

Run:

```bash
python3 scripts/export-google-calendar.py
```

The export includes normalized fields for event ID, calendar ID, title/summary, start/end, attendees, attendee emails, organizer, creator, description, location, meeting/conference link, and the raw event payload.

### Option C: Manual API Export

Use this for the first test if creating credentials is slower.

1. Open Google Calendar API `Events: list` in Google's API Explorer.
2. Use calendar ID `ww@reveting.com`.
3. Set `timeMin` and `timeMax` for the audit window, for example `2026-06-30T00:00:00-04:00` to `2026-09-28T23:59:59-04:00`.
4. Set `singleEvents=true`, `orderBy=startTime`, and `maxResults=2500`.
5. Authorize with `https://www.googleapis.com/auth/calendar.readonly`.
6. Save the JSON response to `data/calendar/manual_google_calendar_events_raw.json`.
7. Normalize it:

```bash
python3 scripts/export-google-calendar.py \
  --input data/calendar/manual_google_calendar_events_raw.json \
  --output data/calendar/ww_reveting_events.json \
  --time-min 2026-06-30T00:00:00-04:00 \
  --time-max 2026-09-28T23:59:59-04:00
```

Google Calendar's UI export creates ICS files, which are not enough for this audit because they can omit full attendee, organizer, creator, and raw event payload details.

The audit input can also use Google Calendar API shape:

```json
{"items": []}
```

or connector/export shape:

```json
{"events": []}
```

Use full event details whenever possible. Attendees are required for the auditor to verify guest, PR, and assistant invite status.

Then run:

```bash
python3 scripts/operations-audit.py
```

Limit to one show:

```bash
python3 scripts/operations-audit.py --show-key winsday
```

Run the Operations Manager audit for every configured show:

```bash
python3 scripts/operations-audit.py --show-key all --calendar-events data/calendar/ww_reveting_events.json
```

The audit writes:

- `data/audit/operations_audit_report.md`
- `data/audit/operations_audit_report.html`
- `data/audit/operations_audit_report.json`
- `data/audit/operations_audit_issues.csv`
- `data/audit/operations_dashboard.json`
- `data/audit/operations_manager_dashboard.json`
- `data/audit/operations_manager_dashboard.html`

The audit checks whether a calendar event exists, whether the SOP pre-show/live time matches, whether title and guests match, whether guest and PR emails are invited, whether assistant emails appear, whether required operations attendees are invited, whether required form fields are present in the description, whether configured SOP/production assets are present, whether duplicates exist, and whether bookings/calendar events are orphaned.

Each issue includes severity, reason, evidence, confidence, recommended action, and a human-readable explanation.

The Operations Manager dashboard is the primary operator landing page. It consumes normalized audit JSON only and does not call HighLevel, Google Calendar, Gmail, Google Drive, or any other external system directly. It summarizes overall production health, per-show health, upcoming episodes, recent episodes, episode production status, SOP checklists, operational timelines, prioritized recommendations, suppressed issues, future autofix classification, and trend versus a previous audit snapshot if one exists.

Production readiness timing is configured in `config/production_timeline_rules.json`. That file controls production stages, stage thresholds, checklist due rules, timeline steps, and stage-aware severity escalation. Override the default with:

```bash
python3 scripts/operations-audit.py --production-timeline-rules config/production_timeline_rules.json
```

By default the audit expects Google Calendar events to start 15 minutes before the HighLevel booking time because the calendar should reserve the pre-show window. Override with:

```bash
python3 scripts/operations-audit.py --preshow-minutes 15 --time-tolerance-minutes 10
```

## Connectors

Connectors live under `connectors/` and isolate external systems. A connector may authenticate, read, normalize, and write JSON snapshots. It must not contain business logic, audit decisions, recommendations, or automation.

Current connector folders:

- `connectors/highlevel/`
- `connectors/google_calendar/`
- `connectors/gmail/`
- `connectors/google_drive/`
- `connectors/streamyard/`

## Webhooks

HighLevel officially documents appointment webhook events that fit this project's scheduling workflow:

- `AppointmentCreate`
- `AppointmentUpdate`
- `AppointmentDelete`

For our use case, `AppointmentDelete` is the closest documented equivalent to an appointment cancellation event.

I did not find a documented form-submitted webhook event in HighLevel's webhook catalog or sitemap. Until HighLevel documents one, the safest design is:

- event-driven for appointment lifecycle changes
- direct API reads for form/contact enrichment only when an appointment event arrives

This avoids continuous polling while still keeping form-dependent show operations accurate.
