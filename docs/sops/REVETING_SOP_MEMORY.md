# Reveting SOP Memory

This is the local project memory distilled from the two SOP PDFs Jessie supplied on 2026-06-25:

- `Livestream Guest Booking to Pre and Post-Production Email SOP.pdf` - 13 pages
- `Calendar Description Updates for Reveting Events SOP.pdf` - 12 pages

The full extracted text is kept locally under `docs/sops/source-text/` and ignored from Git. Use this summary and the QC checklist for repo/process work unless Jessie says to stop.

## Operating Principles

- `ww@reveting.com` is the single source of truth for Reveting livestream and podcast events.
- Production Assistant owns daily booking monitoring, calendar accuracy, descriptions, correct show naming, and preservation of the original guest submission.
- Distinguish Operations Tasks from Production Tasks.
- Operations Tasks unblock production and should appear before Production Tasks in Operations Copilot queues.
- Production Tasks create or update production assets and should not be generated prematurely when an Operations Task is still open.
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

## Deconstructing Data Script Memory

- Deconstructing Data episodes may have a Google Doc script created before the show.
- The script link changes every episode.
- When a script exists, treat it as a production source of truth for:
- final episode title
- formatted topics
- StreamYard link
- pre-show timing
- live timing
- host intro
- guest intro
- closing language
- production notes
- Do not rely only on the original HighLevel submission if a script exists.
- For Deconstructing Data drafts, look up or request the per-episode script URL first.
- If the script provides title, topics, StreamYard link, or timing, prefer the script over raw submitted HighLevel fields.
- Check for obvious whitespace and punctuation issues before using script copy in guest-facing drafts.

## WinsDay Multi-Guest Memory

- WinsDay is currently the only multi-guest show in active operations.
- WinsDay normally needs two distinct confirmed guests per episode.
- If the same person appears twice in HighLevel for the same WinsDay date/time, do not count that as two guests.
- Deduplicate by email first, then normalized full name, then LinkedIn URL if available.
- If one person fills both slots, classify the episode as `Open Guest Slot / Needs Second Guest`.
- Treat that state as `Blocked - Awaiting Second Guest`.
- Do not generate final LinkedIn event copy, final calendar updates, or Hannah guest emails until the second distinct guest is confirmed, unless Jessie explicitly approves a solo-guest episode.
- While WinsDay is waiting on the second guest, do not require LinkedIn, Facebook, YouTube, or other final destination links yet.

## Breach of Protocol Memory

- Breach of Protocol is a first-class Ridgeback Network Defense show.
- Format: weekly cybersecurity livestream and podcast.
- Schedule: every Friday.
- Pre-show: 2:45 PM ET.
- Live: 3:00 PM ET.
- The current production model is editorial-first, not guest-booking-first.
- The source of truth is Approved News Story -> Episode Brief -> Production Assets.
- Do not require HighLevel guest bookings, booking forms, Hannah guest emails, PR workflows, or guest calendar matching for the default workflow.
- Default recurring hosts are Steven Oliphant, Samuel Kushner, and Thomas Phillips unless explicitly changed.
- There are currently no guests, but guest support should remain possible later without changing the underlying workflow model.
- Candidate story research is an editorial queue only.
- Never auto-select the lead, supporting, optional third, or backup story.
- Final production assets stay approval-gated until story approval.
- Capture the Flag is its own production asset group and should be generated separately from the main run of show.
- The show must emphasize engineering insight over headlines.
- Use weekly cybersecurity news as evidence, but do not turn the public discussion topics into simple article headlines or CVE names.
- The three public discussion topics should usually map to:
- What changed in the threat landscape this week?
- What defensive blind spot does this reveal?
- What should security leaders do differently now?
- Keep the episode strategic, not just reactive.
- Make the discussion valuable to CISOs, CIOs, IT leaders, security engineers, MSPs, and business leaders.
- Keep Ridgeback's Preemptive Security point of view present without making the episode feel like a product pitch.
- Every story should answer:
- Why does this matter?
- What are defenders missing?
- What should security leaders do differently?
- What can organizations apply immediately?
- Default CTA: Schedule a Technical Briefing at https://ridgebacknet.com and position Ridgeback's Preemptive Security approach as the recommended next step.

### Episode 55 Approved Example

- Date: Friday, July 10, 2026
- Live: 3:00 PM ET
- Episode number: 55
- Hosts: Steven Oliphant, Samuel Kushner, Thomas Phillips
- Approved working theme: When trusted systems, AI agents, remote access tools, and enterprise infrastructure become the attack surface.
- Approved SEO title: AI Ransomware, Patch Speed & Hidden Enterprise Risk | Episode 55
- Approved public discussion topics:
- How AI-powered attacks and rapidly exploited vulnerabilities are changing enterprise risk
- The hidden security blind spots created by trusted platforms, remote management tools, and critical infrastructure
- Why reducing attacker time and strengthening defensive readiness matter more than ever
