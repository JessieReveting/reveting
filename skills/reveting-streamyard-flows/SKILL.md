---
name: reveting-streamyard-flows
description: "StreamYard production flows for Reveting livestream shows — scenes, overlays, guest invites, run-of-show"
version: 1.0.0
author: Go Technology Solutions
license: MIT
category: livestream
tags: [streamyard, livestream, production, linkedin-live, scenes, overlays, b2b-marketing]
frameworks:
  - Jessie Lizak (Reveting) — LinkedIn Live & livestream content engine
  - StreamYard — official platform documentation
related_skills:
  - reveting-show-setup
  - reveting-email-flows
  - reveting-calendar-flows
  - reveting-ghl-workflows
---

# Reveting StreamYard Flows

StreamYard is the browser-based studio powering Reveting-style LinkedIn Live shows. No software install required for guests — they join via a unique browser link.

## When to Use

- Setting up StreamYard for LinkedIn Live
- Building scenes and overlays for a weekly B2B show
- Creating guest invite flows
- Streaming to LinkedIn Live
- Running a 45-minute interview show
- Downloading recordings for podcast and clips

## Step-by-Step Process

### Phase 1: Account and Brand Kit Setup

1. Create StreamYard account at streamyard.com (Basic or Professional tier)
2. Upload brand assets under Brand → Brand Kit:
   - Logo (PNG with transparent background, minimum 400×400px)
   - Primary and accent colors (hex values)
   - Background image or color for full-screen scenes
3. Add social profiles under Destinations:
   - LinkedIn: connect via LinkedIn OAuth; authorize page or profile streaming
   - YouTube (optional): connect via Google OAuth for simulcast
   - Custom RTMP (optional): for website or podcast platform embeds
4. Test connection: create a private broadcast to verify all destinations receive stream

### Phase 2: Scene Library Design

Build a scene library before the first live. **Minimum 6 scenes** for a WinsDay-style show:

| Scene | Purpose | Layout |
|-------|---------|--------|
| **Holding / Countdown** | Pre-show buffer while attendees join | Full-screen graphic + ticker |
| **Host Solo** | Intro, segue, and close | Single camera fullscreen or offset |
| **Host + Guest** | Main interview segments | Side-by-side or 60/40 split |
| **Screen Share** | Demo, chart, or slide reference | Screen left, cameras right |
| **Quote / Highlight** | Pull-quote overlays during conversation | Background + text overlay |
| **End Card** | CTA and next episode date | Static graphic + social handles |

**Naming convention:** `[ShowName]-[SceneName]-v[n]` (e.g., `WinsDay-HostGuest-v2`)

### Phase 3: Overlay and Lower-Third Templates

1. **Lower thirds:** Guest name, title, and company. Use brand colors. Set display duration to **8 seconds**
2. **Show logo bug:** Persistent logo overlay in corner at 30–40% opacity
3. **Ticker / scroll:** Optional bottom-of-frame text for episode topic or CTA
4. **Banner overlays:** Episode number, sponsored by, hashtag
5. Save all overlays to the Brand Kit for instant recall during live

### Phase 4: Guest Invite Workflow

StreamYard guests join via a unique browser link — no app required.

1. Create or open the broadcast for the episode
2. Click **Invite** → copy guest link
3. Send link to guest via email (see `reveting-email-flows` for pre-show briefing template)
4. **Pre-show tech check (15 min before go-live):**
   - Guest opens link in Chrome or Firefox
   - Confirm camera, microphone, and internet connection
   - Verify guest name display
   - Brief guest on scene transitions and chapter marks
5. **Backup plan:** Have guest phone number for audio-only dial-in
6. **Bring on screen:** Click guest tile → "Add to broadcast" when show starts

### Phase 5: Multi-Destination Streaming Setup

1. In the broadcast, click **Go Live** → select all active destinations
2. LinkedIn stream settings:
   - **Title:** Episode name with ICP keyword
   - **Description:** 3-5 sentence summary + guest name + LinkedIn handle
   - **Visibility:** Public
3. YouTube simulcast: Public or Unlisted for replay
4. Click **Go Live** — confirm all destinations receiving

### Phase 6: Live Production Run-of-Show (45-Minute Template)

| Time | Action | Scene |
|------|--------|-------|
| T-5 min | Holding screen live; welcome early arrivals | Holding |
| T-0 | Host intro, episode context, guest intro | Host Solo → Host + Guest |
| T+3 | Guest bio, origin story | Host + Guest |
| T+12 | Chapter 1: Topic deep-dive | Host + Guest |
| T+24 | Chapter 2: Second topic | Host + Guest |
| T+36 | Chapter 3: Final topic + audience Q&A | Host + Guest |
| T+44 | CTA, next episode preview | Host Solo |
| T+45 | End card | End Card |

**Chapter breaks every 8-12 minutes** for clean clipping in post-production.

### Phase 7: Recording and Handoff

1. Download MP4 within 2 hours of show end
2. Create timestamp log (chapter marks)
3. Collect guest assets (headshot, bio, links)
4. Save show notes draft
5. Hand off to post-production team (24-hour SLA on clips)

## Quality Check

- [ ] Brand kit uploaded: logo, colors, background
- [ ] All 6 scenes built and named per convention
- [ ] LinkedIn Live destination connected and tested
- [ ] Guest invite flow tested before first real guest
- [ ] Recording confirmed downloadable
- [ ] Multi-destination streaming tested
- [ ] Run-of-show template saved and shared with team
