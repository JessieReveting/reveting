---
name: reveting-show-setup
description: "Master variable intake for Reveting livestream shows — Tier 1 show constants + Tier 2 episode variables"
version: 1.0.0
author: Go Technology Solutions
license: MIT
category: livestream
tags: [reveting, livestream, show-setup, variables, intake, onboarding]
frameworks:
  - Jessie Lizak (Reveting) — LinkedIn Live & livestream content engine
  - Go High Level — official automation documentation
related_skills:
  - reveting-email-flows
  - reveting-calendar-flows
  - reveting-ghl-workflows
  - reveting-streamyard-flows
---

# Reveting Show Setup — Master Variable Intake

Every Reveting livestream show operates on two tiers of variables:

- **Tier 1 (Show Constants)**: Defined once at launch; rarely changed.
- **Tier 2 (Episode Variables)**: Filled per recording by the Production Assistant.

These variables power all downstream systems:
- All 7 email templates (T-14 activation through post-production)
- Calendar descriptions (new booking + event published)
- GHL guest pipeline and automation workflows
- StreamYard scene setup and guest invite links
- Post-production asset delivery

## When to Use

- "We have a new client show — what do I need to set up?"
- "What variables do I need before I can run the email sequence?"
- "New show onboarding checklist"
- "Set up show constants in app.reveting.com"
- "Production Assistant needs the episode intake for this week's guest"

## Important Rules

1. **Never email a guest their raw submitted topics.** All topics must be edited to fit the show strategy before appearing in any email or calendar description.
2. **The `ww@reveting.com` calendar is the single source of truth.** All events must be set in Eastern Time (USA).
3. **Never guess the channel stack.** Pull from the Total Deliverables Document every time.
4. **Email 5 (immediate post-show) must go out within 1 hour of show end.** Video editors have a 24-hour SLA on clips; Email 6 must not exceed 36 hours after the show.
5. **Guest LinkedIn follower threshold:**
   - 5,000+ preferred
   - 1,000–4,999 requires Production + Marketing Lead confirmation
   - Below 1,000 is a no-go unless no other option exists
6. **When in doubt → WhatsApp Jessie.**

## Step-by-Step Process

### Phase 1: New Show Launch (Tier 1 — Do Once)

Complete every field in the Show Constants section of `templates/output-template.md`:

1. **Show identity**: name, email, calendar account, timezone, day/time, durations
2. **Team**: host, producer, production assistant, signature block
3. **Channel stack**: confirm against Total Deliverables Document — never assume
4. **Podcast & replay links**: Spotify, Apple Podcasts, YouTube channel, show website
5. **Booking & docs**: booking form link, Total Deliverables doc, client outline link, Google Drive root folder, StreamYard account URL, LinkedIn invite walkthrough video URL
6. **Guest qualification rules**: minimum follower count, content pillars, escalation contact, fallback show links for "not a fit" redirects

> Save the completed Tier 1 doc in the show's Google Drive root folder. Share with all team members. This is the reference document for every Production Assistant working on this show.

### Phase 2: New Episode (Tier 2 — Do Per Recording)

When a new booking appears in `app.reveting.com`:

1. Pull guest submission from:
   `Calendars → Appointment List View → click guest → 3 dots → View Details → Form Submission`
2. Complete Tier 2 (Episode Variables) in `templates/output-template.md`
3. **Edit topics** — do not use raw submitted topics. Format to 3–7 words per topic, aligned to show strategy
4. Verify guest LinkedIn followers → fit gate decision
5. If fit: proceed. If not fit: send "Not a Fit" email and stop
6. If info missing: email guest requesting missing info; do not publish event

### Phase 3: Pre-Send Checklist (Before Each Email)

Use the Email Trigger Checklist in `references/reveting-show-variables.md` to confirm every required variable is populated before each email goes out.

> A missing StreamYard link or wrong time zone in Email 3 causes no-shows.

### Phase 4: Calendar Description Updates

Two stages — both documented in `references/reveting-show-variables.md`:

- **Stage 1 (New Booking)**: Set immediately; includes placeholder text while topics are being formatted
- **Stage 2 (Event Published)**: Updated when Production + Marketing Lead posts the event; includes finalized title, topics, and all platform links

## Output Format

Completed show setup document includes:
- Tier 1 (Show Constants, 30+ variables)
- Tier 2 (Episode Variables, 25+ variables per episode)
- Email trigger checklist with required variables per email
- Calendar description checklist with required variables per stage

## Quality Check

- [ ] Tier 1 complete: all show constants filled, no blanks
- [ ] Channel stack confirmed against Total Deliverables Document
- [ ] Guest qualification rules defined and documented
- [ ] Tier 2 complete: all episode variables filled
- [ ] Topics edited to 3–7 words, aligned to show strategy
- [ ] Guest LinkedIn follower count verified
- [ ] Email trigger checklist reviewed
- [ ] Calendar description stages mapped
- [ ] All links tested (booking form, StreamYard, past episodes)

## Next Steps

1. Complete `templates/output-template.md` with your show's Tier 1 constants
2. Share with all team members
3. Use for every new episode booking
4. Validate with `scripts/check-output.py`
