---
name: reveting-ghl-workflows
version: 1.0.0
author: Go Technology Solutions
license: MIT
tags:
  - ghl
  - go-high-level
  - automation
  - crm
  - livestream
  - content-engine
  - b2b-marketing
frameworks:
  - Jessie Lizak Reveting Methodology
  - Go High Level Official Documentation
  - HubSpot Academy CRM Automation
related_skills:
  - reveting-show-setup
  - reveting-email-flows
  - reveting-calendar-flows
  - reveting-streamyard-flows
---

# Reveting GHL Workflows

Automate the Jessie Lizak Reveting™ guest lifecycle inside Go High Level. This skill
defines the full pipeline architecture, contact schema, workflow maps, reporting
dashboard, and quality checks required to run a B2B livestream show on autopilot.

## When to Use

- Building or auditing a Reveting-powered GHL account
- Configuring guest pipelines, audience pipelines, or show-day automations
- Standardising tags, custom fields, and workflow triggers across environments
- Reporting on show pipeline health, conversion rates, and automation performance

## Pipeline Architecture

### Guest Pipeline (6 stages)

| Stage | Name | Description |
|-------|------|-------------|
| 1 | **Prospect** | Identified potential guest; no outreach yet. |
| 2 | **Outreach Sent** | Initial contact email/social message delivered. |
| 3 | **Shortlisted** | Guest responded positively; pre-qualification in progress. |
| 4 | **Confirmed** | Guest accepted; calendar invite, pre-interview, and assets sent. |
| 5 | **Recorded** | Episode recorded; post-production and distribution underway. |
| 6 | **Past Guest** | Episode published; guest moved to alumni / future outreach pool. |

### Audience Pipeline (3 stages)

| Stage | Name | Description |
|-------|------|-------------|
| 1 | **Show Subscriber** | Opted in to show notifications (email or SMS list). |
| 2 | **Engaged Viewer** | Opened/watched show content; interacted with CTAs. |
| 3 | **CSQL** | Customer Sales Qualified Lead — meet qualification criteria for sales handoff. |

## Contact Schema

### Standard Tags (5)

| Tag | Purpose |
|-----|---------|
| `reveting-prospect` | Any potential guest at any pipeline stage |
| `reveting-current-guest` | Active confirmed/shortlisted guest in current cycle |
| `reveting-past-guest` | Alumni of a previous episode |
| `reveting-audience-subscriber` | Opted-in viewer |
| `reveting-csql` | Sales-qualified lead from audience |

### Custom Fields (6)

| Field | Type | Purpose |
|-------|------|---------|
| Guest Pipeline Stage | Dropdown | Current stage in 6-stage guest pipeline |
| Audience Pipeline Stage | Dropdown | Current stage in 3-stage audience pipeline |
| Episode Date | Date | Scheduled recording / air date |
| Guest Source | Text | How the guest was identified (e.g. LinkedIn, referral) |
| CSQL Qualified Date | Date | Date the contact met CSQL criteria |
| Show Segment(s) | Multi-select | Topic segments the guest is relevant for |

## Workflow Maps

### 1. Guest Confirmation Workflow  *(8 steps + unenrollment)*

**Trigger:** Tag `reveting-shortlisted` added.

1. **Pre-Qualification Form** — Send intake form (Calendly / GHL form).
2. **Decision Check** — If form completed within 48 h, proceed; else send reminder.
3. **Qualification Gate** — If guest meets criteria → tag `reveting-confirmed`; else → tag `reveting-declined`, exit.
4. **Calendar Invite** — Send calendar booking link for recording slot.
5. **Pre-Interview Package** — Email show guide, bio questionnaire, headshot request, tech checklist.
6. **Reminder Sequence** — 48 h, 24 h, 2 h before recording; SMS + email.
7. **Confirmation Stamped** — Update custom field `Guest Pipeline Stage = Confirmed`.
8. **Production Notification** — Alert host + production team via internal notification (email / Slack).

**Unenrollment:** At any confirmed or later stage, if the guest cancels or no-shows,
remove all active sequences, tag `reveting-cancelled`, and trigger the Cancellation Recovery
workflow after 7 days.

---

### 2. Show-Day Reminder Workflow  *(4 steps — targets host & production)*

**Trigger:** Epoch-based scheduled trigger 1 hour before recording start time.

1. **Host Alert** — Send host the guest bio, talking points, and pre-interview summary.
2. **Production Checklist** — Remind production team: Streamyard scene preset, recording backup, mic check.
3. **Countdown Notification** — 15-minute warning to all parties.
4. **Join Link Distribution** — Send guest and co-hosts the final Streamyard guest link.

---

### 3. Post-Show Sequence

**Trigger:** Tag `reveting-recorded` added (or `Episode Date` field set + 1 day wait).

1. **Thank You** — Email guest within 24 h of recording with "episode in production" notice.
2. **Promo Assets Delivery** — When episode is published, send guest shareable graphics + link.
3. **Audience Notification** — Broadcast new episode to `reveting-audience-subscriber` tagged contacts.
4. **Guest Alumni Move** — Tag `reveting-past-guest`, remove `reveting-confirmed`, update pipeline stage.
5. **Episode Survey** — 7-day post-publish feedback request (guest experience survey).
6. **Re-Engagement** — After 30 days, move guest to Nurture segment for future outreach.

---

### 4. Audience Capture Workflow

**Trigger:** Form submission, link click, or webhook from livestream platform.

1. **Opt-In Confirmation** — Immediate double opt-in email with show details and next episode date.
2. **Tagging** — Apply `reveting-audience-subscriber` tag; set `Audience Pipeline Stage = Show Subscriber`.
3. **Welcome Sequence** — 3-email welcome series introducing the show, past episodes, and CTAs.
4. **Engagement Tracking** — On email open + link click → tag `reveting-engaged-viewer`, update pipeline stage.
5. **Lead Scoring** — Accumulate engagement score; when threshold met → tag `reveting-csql`, set CSQL date, notify sales.

## Reporting Dashboard Spec

| Metric | Source | Frequency |
|--------|--------|-----------|
| Guests per Pipeline Stage | Pipeline stage field | Real-time |
| Outreach → Confirmed Rate | Workflow conversion | Weekly |
| Avg Time per Pipeline Stage | Date diff between stage changes | Monthly |
| Audience Subscriber Growth | Tag count delta | Weekly |
| CSQL Conversion Rate | CSQL tag / subscriber count | Monthly |
| Show-Day No-Show Rate | `reveting-cancelled` / confirmed | Per episode |
| Email Open / Click Rates (per workflow) | GHL email reporting | Weekly |
| Top Guest Sources | Custom field aggregation | Monthly |

## Quality Check

Before activating any workflow in production, verify:

- [ ] All triggers match the correct tag additions or field changes.
- [ ] Unenrollment rules are present on every sequence (no orphaned emails).
- [ ] No two workflows fire on the same trigger without conditional branching.
- [ ] Custom field API names match exactly what the skill specifies.
- [ ] Tags are created in GHL before workflows reference them.
- [ ] Test contacts have traversed every pipeline stage end-to-end.
- [ ] Internal notifications (Slack / email) use correct recipient addresses.
- [ ] Calendar booking links point to the correct calendar / event type.
- [ ] All personalisation tokens (`{{contact.first_name}}`, etc.) are valid.
- [ ] Reporting dashboard filters align with pipeline stages and tag names.

## References

- [Framework Notes](references/framework-notes.md) — sources, citations, agent routing table
- [Output Template](templates/output-template.md) — deliverable shell for implementation projects
