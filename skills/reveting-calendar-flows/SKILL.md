---
name: reveting-calendar-flows
description: "Calendar and booking flows for Reveting livestream shows — booking pages, reminders, no-show recovery"
version: 1.0.0
author: Go Technology Solutions
license: MIT
category: livestream
tags: [calendar, booking, scheduling, livestream, reminders, no-show, b2b-marketing]
frameworks:
  - Jessie Lizak (Reveting) — LinkedIn Live & livestream content engine
  - Calendly — official scheduling documentation
  - Outreach — Sales Engagement Cadence Design
related_skills:
  - reveting-show-setup
  - reveting-email-flows
  - reveting-ghl-workflows
  - reveting-streamyard-flows
---

# Reveting Calendar Flows

A consistent weekly LinkedIn Live show depends on scheduling discipline. The Reveting WinsDay model uses a **fixed recurring slot** (same day, same time, every week) to build audience habits and streamline production workflows.

## When to Use

- Setting up a guest booking page for a weekly show
- Building Calendly/Cal.com flows for LinkedIn Live guests
- Designing pre-show reminder sequences
- Handling no-shows for weekly live guests
- Protecting a weekly show slot from overbooking
- Configuring GHL Calendar for podcast guest bookings

## Step-by-Step Process

### Phase 1: Show Slot Architecture

1. **Lock the weekly recording slot** before building any booking page:
   - Same day of week (e.g., every Wednesday)
   - Same time (e.g., 12:00 PM ET)
   - Duration: **60 min show + 15 min buffer = 75 min blocked**
   - Recurring block on host calendar

2. **Separate show time from LinkedIn Live broadcast time:**
   - Record with guest: Wednesday 12:00 PM ET
   - Go live on LinkedIn: same time (live-to-tape) or post-production clip release

3. **Buffer days:** Block the day before (final prep) and morning after (download, handoff)

### Phase 2: Guest Booking Page

Create a dedicated booking page for show guests — not a generic calendar link.

#### Required Intake Fields (all platforms)

- First and last name
- Company and title
- Short bio (50 words — for show notes)
- Episode topic / what you want to share (2-3 sentences)
- LinkedIn profile URL
- Headshot upload link or instructions
- "I consent to receive SMS reminders" (checkbox)

#### Platform Comparison

| Feature | Calendly Pro ($12/mo) | Cal.com (Free/Teams) | GHL Calendar (included) |
|---------|----------------------|---------------------|------------------------|
| Custom intake forms | Yes | Yes | Yes |
| CRM webhook | Yes (Zapier for GHL) | Yes (webhooks) | Native GHL |
| SMS reminders | No | No | Yes (with LC Phone) |
| Routing logic | Yes (Pro+) | Partial | No |

**Recommendation:** GHL Calendar for GHL-native teams; Calendly Pro for HubSpot; Cal.com + n8n for budget-conscious.

### Phase 3: Briefing Call Booking

15-minute pre-show briefing call **5-7 days before** recording.

1. Create Event Type: "Pre-Show Briefing — 15 min"
2. Availability: flexible (any business day, excluding show day)
3. Form: minimal — name, episode number auto-populated
4. Purpose: tech check, topic refinement, rapport building
5. Send briefing call invite automatically via GHL workflow 7 days before recording

### Phase 4: Automated Reminder Sequence

**6-touch cadence for show-day reliability:**

| Touch | Timing | Channel | Content |
|-------|--------|---------|---------|
| 1 — Confirmation | Immediate | Email | Confirmation + prep checklist + StreamYard test link |
| 2 — Briefing invite | T-7 days | Email | Calendar link for 15-min pre-show call |
| 3 — Episode reminder | T-3 days | Email | Talking points + logistics |
| 4 — Day before | T-24h | Email + SMS | StreamYard link + all 3 time zones |
| 5 — Show day | T-1h | SMS | "We go live in 1 hour. Here's your StreamYard link." |
| 6 — Tech check | T-15 min | SMS | "Join now for tech check" |

**No-show rate benchmarks:**
- Confirmation email only: 20-30%
- + 24h email: 15-20%
- + SMS: 8-12%
- **6-touch sequence: 3-5%**

### Phase 5: No-Show Recovery Protocol

| Time | Action |
|------|--------|
| T+5 min | SMS: "We're waiting for you. Reply READY or RESCHEDULE." |
| T+10 min | Phone call to guest |
| T+15 min | Email: "We missed you — let's reschedule" |
| Within 4 hours | Warm rebooking email with new slot link |

### Phase 6: Multi-Host Coordination

- Shared calendar owner for all hosts
- Round-robin booking distribution
- 48-hour swap notice protocol
- Shared run-of-show document

## Quality Check

- [ ] Weekly show slot locked as recurring calendar block
- [ ] Guest booking page includes all 6 required intake fields
- [ ] Confirmation email includes prep checklist
- [ ] 6-touch reminder sequence mapped with assigned channel
- [ ] SMS reminders include READY / RESCHEDULE option
- [ ] No-show recovery assigned to a named person
- [ ] CRM sync tested from booking to pipeline
- [ ] Briefing call booking page created and tested
