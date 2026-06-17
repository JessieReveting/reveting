# Reveting Show Variables — Full Reference

## Production System Overview

- **Production system:** app.reveting.com
- **Calendar:** ww@reveting.com
- **Questions:** WhatsApp Jessie
- **Source:** Jessie Lizak (Reveting) production SOP and Go High Level platform documentation

---

## TIER 1 — Show Constants

> *Set once at show launch. Stored in show's Google Drive root folder.*

### Show Identity

| Variable | Definition | Example |
|----------|-----------|---------|
| `[SHOW_NAME]` | Full public show name | The David Daily |
| `[SHOW_EMAIL]` | Production team inbox | tdd@gotech.ai |
| `[CALENDAR_ACCOUNT]` | Google Calendar used as source of truth | ww@reveting.com |
| `[SHOW_TIMEZONE]` | Broadcast timezone for all calendar events | Eastern Time (USA) |
| `[SHOW_DAY_OF_WEEK]` | Recurring show day | Wednesday |
| `[SHOW_RECURRING_TIME_ET]` | Recurring go-live time in ET | 12:00 PM ET |
| `[PRESHOW_DURATION_MIN]` | Minutes before go-live for tech check | 15 |
| `[SHOW_DURATION_MIN]` | Max reserved time for show | 60 |

### Team

| Variable | Definition | Example |
|----------|-----------|---------|
| `[HOST_NAME]` | On-camera host name | David Goecke |
| `[HOST_LINKEDIN_URL]` | Host LinkedIn profile URL | linkedin.com/in/davidgoecke |
| `[PRODUCER_NAME]` | Behind-the-scenes producer | Jessie Lizak |
| `[PRODUCTION_ASSISTANT_NAME]` | PA who sends emails + manages calendar | |
| `[SIGNATURE_BLOCK]` | Full email signature block (name, title, links) | |

### Channel Stack

> *Pull from Total Deliverables Document every time. Never guess.*

| Variable | Value (Yes/No) |
|----------|----------------|
| `[STREAM_TO_LINKEDIN]` | |
| `[STREAM_TO_YOUTUBE]` | |
| `[STREAM_TO_FACEBOOK]` | |
| `[STREAM_TO_TWITCH]` | |
| `[STREAM_TO_INSTAGRAM]` | **Note:** events cannot be pre-posted on IG — link to channel only |
| `[LINKEDIN_PAGE_OR_PROFILE]` | Page or Personal Profile |
| `[LINKEDIN_CHANNEL_OWNER]` | Name of person/page the LinkedIn Live streams from |

### Podcast & Replay Links

| Variable | Definition |
|----------|-----------|
| `[SPOTIFY_SHOW_LINK]` | Spotify show page (not individual episode) |
| `[APPLE_PODCASTS_SHOW_LINK]` | Apple Podcasts show page |
| `[YOUTUBE_CHANNEL_LINK]` | YouTube channel for this show |
| `[SHOW_WEBSITE_LINK]` | Show website or landing page |
| `[PAST_EPISODES_LINK]` | Best link for guests to hear past episodes before their appearance |

### Booking & Docs

| Variable | Definition |
|----------|-----------|
| `[BOOKING_FORM_LINK]` | Public-facing guest booking calendar link |
| `[TOTAL_DELIVERABLES_DOC]` | Master Sheet — channel stack, outline links, show structure |
| `[CLIENT_OUTLINE_LINK]` | Show-specific episode outline Google Doc |
| `[GOOGLE_DRIVE_ROOT_FOLDER]` | Root Google Drive folder for all show assets |
| `[STREAMYARD_ACCOUNT_URL]` | StreamYard account base URL for this show |
| `[LINKEDIN_INVITE_WALKTHROUGH_URL]` | Video walkthrough for how guests send LinkedIn event invites |

### Guest Qualification Rules

| Variable | Value |
|----------|-------|
| `[MIN_LINKEDIN_FOLLOWERS]` | **5,000+ preferred.** 1,000–4,999: confirm with Production + Marketing Lead. Below 1,000: no-go unless no other option. |
| `[SHOW_CONTENT_PILLARS]` | Comma-separated topic categories that align with client messaging |
| `[ESCALATION_CONTACT]` | Jessie via WhatsApp |
| `[FALLBACK_SHOW_LINKS]` | Up to 3 other client shows to redirect "not a fit" guests |

---

## TIER 2 — Episode Variables

> *Set per episode. Complete before any email is sent.*

### Guest Info

| Variable | Source |
|----------|--------|
| `[GUEST_FIRST_NAME]` | Booking form |
| `[GUEST_LAST_NAME]` | Booking form |
| `[GUEST_TITLE]` | Booking form |
| `[GUEST_COMPANY]` | Booking form |
| `[GUEST_EMAIL]` | Booking form |
| `[GUEST_PHONE]` | Booking form |
| `[GUEST_LINKEDIN_URL]` | Booking form |
| `[GUEST_LINKEDIN_FOLLOWERS]` | Manual LinkedIn check — used for fit gate |
| `[GUEST_PR_CONTACT_NAME]` | Booking form (if submitted) |
| `[GUEST_PR_CONTACT_EMAIL]` | Booking form (if submitted) |
| `[GUEST_TIMEZONE]` | Booking form → selected timezone field |

### Episode Details

| Variable | Source / Rule |
|----------|---------------|
| `[EPISODE_NUMBER]` | Assigned by Production + Marketing Lead |
| `[EPISODE_DATE]` | e.g. Wednesday, June 18, 2026 |
| `[EPISODE_TITLE]` | **Created by production team — NEVER raw guest submission** |
| `[TOPIC_1]` | Edited by production team. 3–7 words. Aligned to show strategy. |
| `[TOPIC_2]` | Edited by production team. 3–7 words. |
| `[TOPIC_3]` | Edited by production team. 3–7 words. |
| `[TOPIC_4]` | Edited by production team. 3–7 words. (optional) |
| `[GURU_OF_THE_WEEK]` | LinkedIn URL submitted by guest |
| `[SEGMENT_TITLE]` | For podcast platform metadata |

### Show Timing (all three time zones, every episode)

| Variable | Calculation |
|----------|-------------|
| `[PRESHOW_TIME_ET]` | Go-live time minus 15 min, Eastern |
| `[PRESHOW_TIME_CT]` | Go-live time minus 15 min, Central |
| `[PRESHOW_TIME_PT]` | Go-live time minus 15 min, Pacific |
| `[GOLIVE_TIME_ET]` | Confirmed from calendar |
| `[GOLIVE_TIME_CT]` | ET minus 1 hour |
| `[GOLIVE_TIME_PT]` | ET minus 3 hours |

### Episode Links

| Variable | Ready? |
|----------|--------|
| `[STREAMYARD_GUEST_LINK]` | ☐ |
| `[LINKEDIN_EVENT_URL]` | ☐ |
| `[YOUTUBE_EVENT_URL]` | ☐ |
| `[FACEBOOK_EVENT_URL]` | ☐ |
| `[TWITCH_EVENT_URL]` | ☐ |
| `[INSTAGRAM_CHANNEL_URL]` | ☐ |
| `[EPISODE_DRIVE_FOLDER]` | ☐ |
| `[EPISODE_SCRIPT_LINK]` | ☐ |

### Post-Production Assets

| Variable | SLA | Sent? |
|----------|-----|-------|
| `[AI_CLIPS_DRIVE_LINK]` | Within 1h of show end | ☐ |
| `[FULL_RECORDING_LINK]` | Within 1h of show end | ☐ |
| `[TRANSCRIPT_LINK]` | Within 1h of show end | ☐ |
| `[HUMAN_EDITED_CLIPS_LINK]` | Max 36h after show | ☐ |
| `[SPOTIFY_EPISODE_LINK]` | After podcast upload | ☐ |
| `[APPLE_EPISODE_LINK]` | After podcast upload | ☐ |

---

## EMAIL TRIGGER CHECKLIST

### Email 1 — T-14 Activation (or immediate if < 14 days)

**Required variables:**
- `[SIGNATURE_BLOCK]`, `[GUEST_FIRST_NAME]`, `[SHOW_NAME]`
- `[EPISODE_DATE]`, `[GOLIVE_TIME_ET/CT/PT]`
- `[PAST_EPISODES_LINK]`, `[LINKEDIN_CHANNEL_OWNER]`

### Email 2 — Event Published (most variable-heavy)

**Required variables:**
- All of Email 1, plus:
- `[EPISODE_TITLE]`, `[TOPIC_1–4]`
- `[STREAMYARD_GUEST_LINK]`
- `[LINKEDIN_EVENT_URL]`, `[SHOW_WEBSITE_LINK]`
- `[HOST_NAME]`, `[HOST_LINKEDIN_URL]`

### Email 3 — T-7 Days

**Required variables:**
- `[GUEST_FIRST_NAME]`, `[SHOW_NAME]`
- `[EPISODE_DATE]`, `[GOLIVE_TIME_ET/CT/PT]`
- `[BOOKING_FORM_LINK]` (for briefing call)

### Email 4 — Day Before

**Required variables:**
- `[GUEST_FIRST_NAME]`, `[SHOW_NAME]`
- `[STREAMYARD_GUEST_LINK]`
- `[GOLIVE_TIME_ET/CT/PT]`
- `[EPISODE_TITLE]`

### Email 5 — Morning Of (2–4 hours before)

**Required variables:**
- `[GUEST_FIRST_NAME]`, `[SHOW_NAME]`
- `[STREAMYARD_GUEST_LINK]`
- `[GOLIVE_TIME_ET/CT/PT]`

### Email 6 — Post-Show (within 1 hour)

**Required variables:**
- `[GUEST_FIRST_NAME]`, `[SHOW_NAME]`
- `[EPISODE_TITLE]`, `[EPISODE_DATE]`
- `[FULL_RECORDING_LINK]` (if available)

### Email 7 — Clip Delivery (24–36 hours)

**Required variables:**
- `[GUEST_FIRST_NAME]`, `[SHOW_NAME]`
- `[HUMAN_EDITED_CLIPS_LINK]` or `[AI_CLIPS_DRIVE_LINK]`
- `[GUEST_LINKEDIN_URL]`, `[HOST_LINKEDIN_URL]`
- `[SPOTIFY_EPISODE_LINK]`, `[APPLE_EPISODE_LINK]`

---

## CALENDAR DESCRIPTION TEMPLATES

### Stage 1 — New Booking (set immediately)

```
[SHOW_NAME] with [GUEST_FIRST_NAME] [GUEST_LAST_NAME]

StreamYard link: TBD — will be sent via email

Thank you for submitting your topics. We will format them to fit the show
and email them shortly.

LOGISTICS
• Login 15 minutes early: [PRESHOW_TIME_ET] ET / [PRESHOW_TIME_CT] CT / [PRESHOW_TIME_PT] PT
• Go live: [GOLIVE_TIME_ET] ET / [GOLIVE_TIME_CT] CT / [GOLIVE_TIME_PT] PT
• Duration: 60 minutes
• Use Chrome or Firefox

QUESTIONS? Reply to this email or WhatsApp [PRODUCER_NAME].
```

### Stage 2 — Event Published (updated when promoted)

```
[SHOW_NAME] Ep. [EPISODE_NUMBER]: [EPISODE_TITLE]
with [GUEST_FIRST_NAME] [GUEST_LAST_NAME], [GUEST_TITLE] at [GUEST_COMPANY]

TOPICS:
1. [TOPIC_1]
2. [TOPIC_2]
3. [TOPIC_3]

STREAM: [LINKEDIN_EVENT_URL]
REPLAY: [YOUTUBE_EVENT_URL]
PODCAST: [SPOTIFY_SHOW_LINK]

Join live on LinkedIn or catch the replay on YouTube.
```
