# Production Playbook

This playbook captures the approved local workflow models that the Reveting Operations Copilot should follow before any external automation is considered.

## Workflow Families

## Operations Tasks vs Production Tasks

- Operations Tasks unblock production.
- Production Tasks create or update production assets.
- Operations Tasks should always surface before Production Tasks in Operations Copilot queues because they unlock downstream work.

### Operations Tasks

- guest sourcing
- waiting for guest confirmation
- waiting for client approval
- waiting for payment
- waiting for script
- waiting for artwork
- waiting for StreamYard destination
- waiting for HighLevel reconciliation

### Production Tasks

- calendar update
- Hannah email
- LinkedIn event
- StreamYard setup
- YouTube description
- newsletter
- post-production emails

### Queue Rule

- Do not generate Production Tasks until prerequisite Operations Tasks are complete or explicitly cleared by Jessie.

### Guest-Booking Shows

These shows begin with bookings, forms, and scheduling context.

- HighLevel is usually the first structured source.
- Google Calendar, StreamYard, LinkedIn Events, Gmail, and Drive are checked against that booking context.
- Guest confirmation, PR representative handling, and Hannah email drafts are part of the workflow.

Examples:

- WinsDay
- Beyond the Cart
- Deconstructing Data
- Apparel with Purpose
- The David Daily Show

### WinsDay Guest Readiness

- WinsDay is currently the only multi-guest guest-booking show.
- WinsDay normally requires two distinct confirmed guests per episode.
- Duplicate HighLevel submissions from the same person do not fill both slots.
- Deduplicate WinsDay guest slots by email first, then normalized full name, then LinkedIn URL.
- If only one distinct guest remains, classify the episode as `Open Guest Slot / Needs Second Guest`.
- Treat that state as `Blocked - Awaiting Second Guest`.
- Do not generate final LinkedIn event copy, final calendar updates, or Hannah emails until the second distinct guest is confirmed, unless Jessie explicitly approves a solo-guest episode.

### Editorial-First Shows

These shows begin with research and story approval, not bookings.

- The first source of truth is editorial.
- Candidate stories may be collected and scored, but story selection stays human-approved.
- Production assets are generated only after an approved story package exists.
- External writes remain approval-gated.

## Breach of Protocol

### Show Facts

- Show: Breach of Protocol
- Client / Brand: Ridgeback Network Defense
- Format: Weekly cybersecurity livestream and podcast
- Workflow type: Research-driven editorial workflow
- Schedule: Every Friday
- Pre-show: 2:45 PM ET
- Live: 3:00 PM ET
- Current episode: Friday, July 10, 2026
- Episode number: 55

### Default Hosts

Unless a human explicitly changes the lineup, use:

- Steven Oliphant
- Samuel Kushner
- Thomas Phillips

### Default Guest Model

- There are currently no guests.
- Do not require HighLevel guest bookings.
- Do not require booking forms.
- Do not require Hannah guest emails.
- Do not require PR representative workflows.
- Do not require guest calendar matching.
- Guest support may be enabled later without changing the editorial-first workflow model.

### Source Of Truth

The production source of truth is:

Approved News Story
↓
Episode Brief
↓
All Production Assets

HighLevel is not the primary source for this show's default workflow.

## Weekly Production Workflow

### Phase 1: Episode Brief

Generate and maintain:

- episode number
- episode date
- hosts
- episode theme
- lead story
- supporting stories
- key takeaways
- Ridgeback CTA

### Phase 2: News Research

Maintain a candidate-story editorial queue with:

- headline
- publication date
- source
- why it matters
- enterprise impact
- CISO/CIO relevance
- engineering relevance
- priority score

Rules:

- This is an editorial queue only.
- Never automatically choose stories.

### Phase 3: Story Selection

Maintain:

- Lead Story
- Supporting Story
- Optional Third Story
- Backup Story

Rules:

- Human approval is required.

### Phase 4: Production Assets

Generate after story approval:

- LinkedIn Event
- LinkedIn Company Post
- Long-form Event Description
- Newsletter
- Topic Banners
- YouTube Title
- YouTube Description
- StreamYard overlays
- StreamYard banners
- Lower thirds
- Producer notes
- CTA graphics

### Phase 5: Capture the Flag

Generate separately:

- Question
- Answer
- Supporting explanation
- Graphic requirements
- Reveal timing

Treat Capture the Flag as its own production asset group.

### Phase 6: Producer Run of Show

Generate:

- Opening
- Introductions
- Lead Story
- Supporting Story
- Engineering Discussion
- Capture the Flag
- Audience Questions
- Closing
- CTA

### Phase 7: Post Production

Generate a checklist for:

- Podcast upload
- Newsletter recap
- Clips
- Transcript
- Blog
- LinkedIn clips
- Production QA
- Standard CTA

## Editorial Rules

- Breach of Protocol is not a news-reading show.
- Every story should answer why it matters.
- Every story should answer what defenders are missing.
- Every story should answer what security leaders should do differently.
- Every story should answer what organizations can apply immediately.
- The show should always emphasize engineering insight over headlines.
- Use weekly cybersecurity news as evidence, but make the public discussion topics thematic, strategic, and repeatable in structure.
- Do not use article headlines, raw story titles, or CVE names as the final public-facing topics.
- The three public discussion topics should usually map to:
- What changed in the threat landscape this week?
- What defensive blind spot does this reveal?
- What should security leaders do differently now?
- Keep the episode strategic rather than reactive.
- Keep Ridgeback's Preemptive Security point of view present without turning the discussion into a product pitch.

## Episode 55 Approved Example

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

## Default CTA

- Schedule a Technical Briefing
- URL: https://ridgebacknet.com
- Position Ridgeback's Preemptive Security approach as the recommended next step.

## Automation Guardrails

Do not automatically:

- select stories
- generate final assets before story approval
- create LinkedIn events
- create StreamYard broadcasts
- send emails
- modify Google Calendar

Everything remains approval-gated until explicit human approval is added for a narrow action.
