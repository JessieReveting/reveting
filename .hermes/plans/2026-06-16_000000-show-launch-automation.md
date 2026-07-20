# Show Launch Automation — Focused Plan

> **For Hermes:** Execute this plan task-by-task.

**Goal:** Build a system that takes a GHL appointment record as input and automatically creates ALL the assets and accounts needed to launch a show episode — LinkedIn event banner, StreamYard broadcast, multi-platform distribution, and SOP execution.

**Single input:** GHL appointment record (JSON export or API pull)
**Single trigger:** New booking appears in GHL "Confirmed" pipeline stage

**Architecture:**
1. Python script pulls appointment from GHL API
2. Creates Canva banner (guest photo + show branding) via Autofill API
3. Creates StreamYard broadcast with LinkedIn Live destination
4. Creates destination accounts/channels (YouTube, X, Facebook, Twitch, Kick)
5. Generates all SOP assets (emails, calendar descriptions, PPTX)
6. Logs everything to a show dashboard spreadsheet

**Tech Stack:** Python 3, Canva Connect API (OAuth), StreamYard API (if available), GHL REST API, Google Sheets API (for guest list)

---

## Current State

### What exists
- `golivestream/` — 3 of 5 skills complete (show-setup, email-flows, ghl-workflows)
- Calendar-flows and streamyard-flows skills need to be written
- PPTX generator not created yet
- No Canva integration
- No StreamYard API integration
- GHL token: load `HIGHLEVEL_TOKEN_WINSDAY` from the local `.env`; never paste the token into tracked files.
- GHL Location ID: `fcO3237HZyeXNe9O8`

### Input Data (appointment record example)
```json
{
  "guest_name": "Daniel Burrus",
  "guest_email": "jennifer@burrus.com",
  "guest_phone": "+12623670949",
  "linkedin_url": "https://www.linkedin.com/in/danielburrus/",
  "topics": [
    "Capital allocation using Hard Trends",
    "Using AI to amplify human judgment",
    "Preparing for quantum and exponential shifts"
  ],
  "show_name": "The David Daily Show",
  "episode_title": "Betting on Certainty, Not Assumptions",
  "date": "2026-06-18",
  "start_time": "11:00 AM ET",
  "preshow_time": "10:45 AM ET",
  "duration_min": 60,
  "producer_signature": "..."
}
```

---

## Step-by-Step Plan

### Task 1: Complete missing skill files

**Objective:** Write calendar-flows and streamyard-flows skills (the 2 subagents didn't finish).

**Files to create:**

1. `skills/reveting-calendar-flows/SKILL.md` — Full skill with frontmatter, 6-phase process (slot architecture, booking page, reminder sequence, no-show recovery), platform comparison, benchmarks, quality checklist.

2. `skills/reveting-calendar-flows/references/framework-notes.md`

3. `skills/reveting-calendar-flows/templates/output-template.md`** — Deliverable with all config fields

4. `skills/reveting-calendar-flows/scripts/check-output.py` — Checks: booking, reminder, guest, slot, calendar, no-show

5. `skills/reveting-streamyard-flows/SKILL.md` — Full skill with frontmatter, 6 phases (brand kit, scenes, overlays, guest invite, multi-destination, run-of-show), naming convention, quality checklist.

6. `skills/reveting-streamyard-flows/references/framework-notes.md`

7. `skills/reveting-streamyard-flows/templates/output-template.md` — Deliverable with scene library, SOP, run-of-show

8. `skills/reveting-streamyard-flows/scripts/check-output.py` — Checks: scene, guest, brand, recording, linkedin, run-of-show

**Verification:**
```bash
for skill in reveting-calendar-flows reveting-streamyard-flows; do
  test -f skills/$skill/SKILL.md && echo "OK: $skill" || echo "MISSING: $skill"
  test -f skills/$skill/scripts/check-output.py && echo "OK: $skill scripts" || echo "MISSING"
done
```

---

### Task 2: Write PPTX generator script

**Objective:** Create the 13-slide show production deck generator.

**File:** `presentations/reveting-show-flow.py`

**Content:** Python script using `python-pptx` (already installed — used for ICP prospect deck). Generates 13 slides:

1. Title — Show name + "End-to-End Production Flow"
2. Overview flow map — 4-column lane diagram
3. Tier 1 Show Setup — 6 variable groups
4. Guest Booking & Fit Gate
5. T-14 Activation & Calendar Stage 1
6. Email 1 (Event Published)
7. Pre-Show Email Cadence
8. Calendar Stage 2 & StreamYard Prep
9. Live Show Run-of-Show (45-min template)
10. GHL Pipeline
11. Post-Show Sequence
12. Skill Map — how the 5 skills connect
13. Summary / Next Steps + QR code to this repo

Brand colors: NAVY=#0D1B3E, GOLD=#F5A623, GREEN=#1EA56B, RED=#D93B3B

**Verification:**
```bash
pip3 install python-pptx 2>/dev/null
python3 presentations/reveting-show-flow.py
test -f presentations/Reveting-Show-Flow.pptx && echo "PPTX created OK"
```

---

### Task 3: Create the guest list Google Sheet structure + show config

**Objective:** Create the Google Sheet template that feeds Canva and the whole pipeline.

**Files to create:**

1. `config/shows.json` — All show configurations:
```json
{
  "shows": {
    "the-david-daily-show": {
      "name": "The David Daily Show",
      "host": "David Goecke",
      "host_linkedin": "https://www.linkedin.com/in/davidgoecke/",
      "timezone": "America/New_York",
      "day_of_week": "Thursday",
      "stream_time_et": "11:00 AM",
      "preshow_time_et": "10:45 AM",
      "duration_min": 60,
      "producer_email": "${PRODUCER_EMAIL}",
      "signature_block": "—\nDavid Goecke\nFounder, Go Technology Solutions\ngotech.ai",
      "primary_color": "#0D1B3E",
      "accent_color": "#F5A623",
      "channels": {
        "linkedin": "https://www.linkedin.com/company/gotechai/",
        "youtube": "https://youtube.com/@gotechai",
        "facebook": "",
        "twitter": "",
        "twitch": "",
        "kick": ""
      },
      "podcast_links": {
        "spotify": "",
        "apple": "",
        "youtube": ""
      },
      "min_linked_in_followers": 5000,
      "content_pillars": "AI, Technology, Business Strategy, Leadership",
      "fallback_show_links": []
    }
  }
}
```

2. `scripts/guest-list-template.csv` — Template for the Google Sheet with columns:
   - Show Name, Episode Number, Episode Title, Guest First Name, Guest Last Name, Guest Email, Guest Phone, Guest LinkedIn, Guest Topics (3), Episode Date, Start Time, Status, Banner Created, LinkedIn Event Created, StreamYard Created, Email 1 Sent, Email 2 Sent, Email 3 Sent, Email 4 Sent

---

### Task 4: Build the show launch script

**Objective:** Create `scripts/show-launch.py` — the main orchestration script.

**File:** `scripts/show-launch.py`

**What it does (in order):**

1. **Input:** Takes GHL appointment JSON (from API or file)
2. **Step 1 — Pull guest data from GHL:**
   - Use GHL API to pull contact details + custom fields
   - Get LinkedIn profile photo URL (if available in GHL custom fields)
   - Use the token at runtime: `Authorization: Bearer ${HIGHLEVEL_TOKEN_WINSDAY}`

3. **Step 2 — Create Canva banner:**
   - Upload guest LinkedIn photo to Canva as asset
   - Trigger Autofill on the show's brand template
   - Data fields: `{SHOW_NAME}`, `{EPISODE_TITLE}`, `{GUEST_NAME}`, `{DATE}`, `{TIME}`, `{GUEST_PHOTO}`, `{TOPIC_1}`, `{TOPIC_2}`, `{TOPIC_3}`
   - Export as PNG (LinkedIn event banner size: 1920×1080)
   - Save to `assets/{show}/{episode}/banner.png`

   **NOTE:** Canva Connect API requires Enterprise org + OAuth. If you don't have Enterprise, alternative is:
   - Use `python-pptx` or `Pillow` to generate the banner programmatically (no Canva needed)
   - Guest photo + show branding + text overlay = LinkedIn banner
   - This is actually faster and doesn't need Canva credentials

4. **Step 3 — Create LinkedIn Live event:**
   - This requires LinkedIn API access (OAuth 2.0 with `w_member_social` scope)
   - Alternative: Create manually using the banner image, or use a LinkedIn-facing approach
   - For now: Generate the event description text and save it, flag as "needs manual LinkedIn event creation"

5. **Step 4 — Set up multi-platform destinations:**
   - YouTube: Create live broadcast via YouTube Live Streaming API
   - This also needs OAuth. For now: generate the planned destinations list

6. **Step 5 — Generate email sequence:**
   - Use the email templates from the skills
   - Fill in all variables from the appointment data
   - Generate SendGrid/Mailgun-ready JSON for automation
   - Save to `assets/{show}/{episode}/emails/`

7. **Step 6 — Generate calendar event (.ics):**
   - Create the calendar invite with logistics
   - Two versions: guest version (StreamYard link TBD) and team version (full details)

8. **Step 7 — Generate PPTX for the episode:**
   - Use the reveting-show-flow.py generator
   - Customize with episode-specific data

9. **Step 8 — Log everything to Google Sheet:**
   - Append a row to the guest list sheet with all generated assets

**CLI interface:**
```bash
python3 scripts/show-launch.py --input appointment.json --dry-run
python3 scripts/show-launch.py --input appointment.json --execute
python3 scripts/show-launch.py --ghl-pull  # Pull directly from GHL API
```

**Verification:**
```bash
# Dry run with the Daniel Burrus appointment
python3 scripts/show-launch.py --input examples/appointments/daniel-burrus.json --dry-run
# Should print all planned actions without creating anything

# Check generated assets
ls -la assets/the-david-daily-show/ep-001/
# Should show: banner.png, emails/*.md, calendar/*.ics, episode.pptx
```

---

### Task 5: Create sample appointment JSON + examples

**Objective:** Create the example files for testing.

**Files to create:**

1. `examples/appointments/daniel-burrus.json` — The Daniel Burrus appointment (from the data you just gave me)

2. `examples/emails/` — 8 sample email files:
   - `tds-guest-outreach-1.md` through `-3.md` (3-touch sequence)
   - `tds-confirmation.md`
   - `tds-preshow-1.md` and `-2.md`
   - `tds-postshow-1.md` through `-3.md`
   - `tds-weekly-nurture.md`

3. `examples/ical-events/` — 4 sample .ics files:
   - `tds-episode.ics` — The David Daily Show recording session
   - `tds-preshow-briefing.ics` — 15-min briefing call
   - `tds-multi-host.ics` — Multi-host coordination
   - `tds-post-production.ics` — Post-production handoff

4. `examples/banner-spec.md` — Specification document for the banner template (dimensions, fields, brand guidelines)

---

### Task 6: Write README.md

**Objective:** Document the entire repo.

**Content:**
- What this repo does (show launch automation)
- The 5 skills explained
- Quick start: one command to launch a show from an appointment
- Input format (GHL appointment JSON)
- Output assets (banner, emails, calendar, PPTX, StreamYard)
- Canva integration setup (if Enterprise)
- GHL API setup (token + location)
- Google Calendar sync setup
- File structure
- How to add a new show

---

## Files Summary

| # | File | Action | Task |
|---|------|--------|------|
| 1 | `skills/reveting-calendar-flows/SKILL.md` | Create | 1 |
| 2 | `skills/reveting-calendar-flows/references/framework-notes.md` | Create | 1 |
| 3 | `skills/reveting-calendar-flows/templates/output-template.md` | Create | 1 |
| 4 | `skills/reveting-calendar-flows/scripts/check-output.py` | Create | 1 |
| 5 | `skills/reveting-streamyard-flows/SKILL.md` | Create | 1 |
| 6 | `skills/reveting-streamyard-flows/references/framework-notes.md` | Create | 1 |
| 7 | `skills/reveting-streamyard-flows/templates/output-template.md` | Create | 1 |
| 8 | `skills/reveting-streamyard-flows/scripts/check-output.py` | Create | 1 |
| 9 | `presentations/reveting-show-flow.py` | Create | 2 |
| 10 | `config/shows.json` | Create | 3 |
| 11 | `scripts/guest-list-template.csv` | Create | 3 |
| 12 | `scripts/show-launch.py` | Create | 4 |
| 13 | `examples/appointments/daniel-burrus.json` | Create | 5 |
| 14-21 | `examples/emails/*.md` (8 files) | Create | 5 |
| 22-25 | `examples/ical-events/*.ics` (4 files) | Create | 5 |
| 26 | `examples/banner-spec.md` | Create | 5 |
| 27 | `README.md` | Create | 6 |

**Total: 27 new files**

---

## Dependencies & Prerequisites

### APIs needed (in priority order)
1. **GHL REST API** — Already have token. Used to pull appointment data.
2. **Google Calendar API** — For calendar sync. Needs OAuth setup (google-workspace skill).
3. **Canva Connect API** — For banner generation. Needs Enterprise org + OAuth.
   - **Fallback if no Canva Enterprise:** Use Pillow/python-pptx to generate banners locally. No API needed.
4. **LinkedIn API** — For event creation. Needs OAuth with `w_member_social`.
   - **Fallback:** Generate event description text, create manually.
5. **YouTube Live Streaming API** — For broadcast creation. Needs OAuth.
   - **Fallback:** Generate broadcast config, create manually.
6. **StreamYard** — No public API exists. Broadcast creation is manual.
   - **Fallback:** Generate the run-of-show and scene config, create manually.

### Python packages needed
```
python-pptx      # PPTX generation (already installed)
icalendar        # .ics file generation
Pillow           # Image manipulation (banner generation without Canva)
requests         # HTTP calls (already available)
```

---

## Risks & Open Questions

1. **Canva Enterprise requirement** — The Autofill API requires Canva Enterprise. If you don't have it, we use Pillow for local banner generation instead. Less flexible but zero dependency.

2. **LinkedIn API access** — LinkedIn's API for Live event creation is restricted. May need manual event creation step.

3. **StreamYard has no public API** — Broadcast creation and multi-destination setup is always manual. We can generate the config but not execute.

4. **YouTube Live API** — Requires channel verification and OAuth. May need manual broadcast creation.

5. **Guest LinkedIn photo** — GHL may not have the photo URL. May need to scrape LinkedIn or ask guest to provide.

6. **GitHub auth** — `gh` CLI keeps timing out. User needs to provide a PAT or create repo manually.

---

## Execution Order

```
Task 1 (missing skills)  ──┐
Task 2 (PPTX generator)  ──┤
Task 3 (config + sheet)   ──┼── Can all run in parallel
Task 5 (examples)         ──┘
    │
    ▼
Task 4 (show-launch.py)  ── Depends on all above
    │
    ▼
Task 6 (README)           ── Last, references everything
```

---

## Verification Checklist (end of plan)

- [ ] All 5 skills have SKILL.md + supporting files
- [ ] `python3 presentations/reveting-show-flow.py` generates PPTX
- [ ] `python3 scripts/show-launch.py --input examples/appointments/daniel-burrus.json --dry-run` shows planned actions
- [ ] `python3 scripts/show-launch.py --input examples/appointments/daniel-burrus.json --execute` creates all assets
- [ ] Banner image generated at correct dimensions (1920×1080)
- [ ] All 8 email templates generated with correct variables filled
- [ ] .ics calendar event opens correctly in Google Calendar
- [ ] PPTX opens correctly with show-specific data
- [ ] README explains the full workflow
