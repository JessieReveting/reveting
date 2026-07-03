# Reveting SOP Memory

This is the local project memory distilled from the two SOP PDFs Jessie supplied on 2026-06-25:

- `Livestream Guest Booking to Pre and Post-Production Email SOP.pdf` - 13 pages
- `Calendar Description Updates for Reveting Events SOP.pdf` - 12 pages

The full extracted text is kept locally under `docs/sops/source-text/` and ignored from Git. Use this summary and the QC checklist for repo/process work unless Jessie says to stop.

## Operating Principles

- `ww@reveting.com` is the single source of truth for Reveting livestream and podcast events.
- Production Assistant owns daily booking monitoring, calendar accuracy, descriptions, correct show naming, and preservation of the original guest submission.
- Before touching a calendar event, confirm show timezone, channel stack, client outline link, standard duration, and pre-show timing from the Total Deliverables Document.
- Never guess the channel stack or platform links.
- Never email raw submitted guest topics and never add raw submitted guest topics directly to the calendar.
- Format topics to fit the specific show strategy before guest-facing use.
- All event timing must include the pre-show time and go-live time, with ET/CT/PT where guest-facing copy requires it.
- When in doubt, WhatsApp Jessie.

## Booking Intake Flow

1. Check `app.reveting.com` daily for new bookings and watch booking notification emails.
2. Use Calendars > Appointment List View and Contacts sorted by Last Activity because automations are not always reliable.
3. Review guest submission for topic alignment, LinkedIn URL, follower count, credibility, required posting fields, and any show-specific fields such as guru of the week.
4. Decide only two things: whether the guest is a fit and whether enough information exists to move forward.
5. If the guest is not a fit, send the Not a Fit email, optionally include better-aligned show links, and do not create/promote the event.
6. If the guest is a fit but info is missing, request the missing details and do not publish/promote until complete.
7. If the guest is a fit and info is complete, proceed with event creation, social posting, and the guest email cadence.

## Guest Fit Gate

- 5,000+ LinkedIn followers is preferred.
- 1,000-4,999 followers requires Production + Marketing Lead confirmation that the guest is credible and aligned.
- Below 1,000 followers is a no-go unless there is no other viable option.
- If Production + Marketing Lead is unsure, escalate to higher management.

## Calendar Description Stages

### Stage 1 - New Booking

Use immediately after booking or when manually creating a missing `ww@reveting.com` event.

Required:

- Event name: `[SHOW NAME] with [GUEST NAME]`
- Location: StreamYard URL TBD
- Note that topics will be formatted and emailed later.
- Promotion expectation: LinkedIn event URL will be shared, guest/team should invite LinkedIn connections, and guest may need to accept a speaker role.
- Channel stack placeholder based on Total Deliverables Document.
- Logistics: log in 15 minutes early and showtime.
- Support email: `ea@reveting.com`
- Original guest submission preserved at the bottom.

If the booking is missing from `ww@reveting.com`, notify management and manually create the calendar invite with the correct guest, client, and team members.

### Stage 2 - Published Event

Use after Production + Marketing Lead posts events and finalizes topics/title in the Total Deliverables Document and client outline.

Required:

- Event name remains `[SHOW NAME] with [GUEST NAME]`.
- Show name, guest name, date, pre-show time, livestream time.
- StreamYard login URL.
- Guest name and LinkedIn URL.
- Final episode title.
- Edited/finalized topics.
- Script/client outline link where applicable.
- Promo links for each active platform.
- LinkedIn direct invite instructions and walkthrough link.
- Reminder that LinkedIn allows 1,000 invites per week.
- Stream-to-your-audience instructions and credential reminder.
- Original guest submission preserved at the bottom.

## Guest Email Cadence

Use the SOP cadence for booked guests:

1. T-14 activation email, mandatory 10-14 days before show or immediately if booked inside 14 days.
2. Published-event email when LinkedIn/Facebook/YouTube/Twitch links are live.
3. One-week email 5-7 days before the livestream.
4. Day-before email.
5. Day-of email, morning of or 2-4 hours before pre-show.
6. Post-show email within 1 hour or less with AI clips, full recording, transcript, and organized Drive link.
7. Final post-production email 24-36 hours after show, not exceeding 36 hours.

Every guest-facing email after event publication should include clear timing, StreamYard or event links when available, and LinkedIn invite encouragement.

## Post-Production Requirements

- Email 5 is time-sensitive and should land while the conversation is fresh.
- Include AI clip, full episode recording, transcript, and organized file location.
- Human-edited clips have a 24-hour editor turnaround expectation.
- Final post-production email should include replay links, Spotify/Apple podcast links when available, clips/Drive link, light CTA to share/tag, and thanks.
- The final post-production email is a KPI reported by the Production Assistant.

## Initial Local Repo QC Notes

- The GitHub repo has all five Reveting skills locally: show setup, email flows, calendar flows, GHL workflows, and StreamYard flows.
- The running Codex session may require restart before all newly installed local skills appear in the active skill list.
- `scripts/show-launch.py` should parse local appointment JSON through `parse_appointment()` before launch.
- `scripts/show-launch.py` must not carry real GHL token defaults in source.
- Email-flow validation should run successfully before process updates are considered ready.
