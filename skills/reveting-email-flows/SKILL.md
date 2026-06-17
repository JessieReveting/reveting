---
name: reveting-email-flows
version: 1.0.0
author: Go Technology Solutions
license: MIT
tags:
  - email
  - sequences
  - nurture
  - livestream
  - guest-outreach
  - content-engine
  - b2b-marketing
frameworks:
  - Jessie Lizak Reveting
  - Outreach Sales Engagement
  - HubSpot Academy CRM Automation
related_skills:
  - reveting-show-setup
  - reveting-calendar-flows
  - reveting-ghl-workflows
  - reveting-streamyard-flows
---

# Reveting Email Flows

A 6-sequence email system for Go Technology Solutions' GoLiveStream business hub. Covers the full lifecycle from initial guest outreach through ongoing nurture and re-engagement.

## Sequences Overview

| # | Sequence | Emails | Purpose |
|---|----------|--------|---------|
| 1 | Guest Outreach | 3-touch | Convert prospects to booked guests |
| 2 | Booking Confirmation | 1 | Lock in commitment, set expectations |
| 3 | Pre-Show Briefing | 2 | Prepare guest for live appearance |
| 4 | Show Promotion | 2 | Drive viewership for guest's episode |
| 5 | Post-Show | 3 | Deliver value, gather testimonials, repurpose |
| 6 | Ongoing Nurture | Rolling + 60-day re-engagement | Long-term relationship & reactivation |

---

## Sequence 1: Guest Outreach (3-Touch)

**Goal:** Book a prospect as a GoLiveStream guest.
**Cadence:** Day 0 → Day 3 → Day 7
**Suppression:** If no open or click after all 3 touches, apply `show-inactive` tag and move to 60-day re-engagement pool.

### Email 1 — Introduction (Day 0)

**Subject:** {{guest.first_name}}, your expertise deserves a bigger stage
**Preview:** A quick invite to share your story on GoLiveStream

```
Hi {{guest.first_name}},

I'm reaching out because your work in {{guest.industry/role}} caught our attention at Go Technology Solutions.

We run GoLiveStream — a livestream series where we spotlight leaders like you in short, high-energy episodes. No scripts, no fluff — just a real conversation about what you're building and what you've learned.

Would you be open to a 15-minute chat to see if it's a fit?

Best,
{{sender.name}}
{{sender.title}}, Go Technology Solutions
```

### Email 2 — Value Add (Day 3)

**Subject:** Quick idea for your next {{guest.content_format}} appearance
**Preview:** How GoLiveStream amplifies your message

```
Hi {{guest.first_name}},

Just wanted to follow up — I put together a quick thought on how a GoLiveStream appearance could work for you:

- Reach a targeted B2B audience in {{guest.industry}}
- Get a professionally produced episode you can repurpose
- Join a growing community of practitioners and founders

Here's a recent episode for reference: {{episode.link}}

Worth a quick chat?

Best,
{{sender.name}}
```

### Email 3 — Breakup / Last Touch (Day 7)

**Subject:** Should I close your file, {{guest.first_name}}?
**Preview:** Last attempt — easy opt-in or opt-out

```
Hi {{guest.first_name}},

I don't want to clutter your inbox. If the timing isn't right, no hard feelings.

If you're still interested, just reply "yes" and I'll send over the booking link.

Either way, appreciate your time.

Best,
{{sender.name}}
```

**Suppression Logic:**
- If Email 1: no open after 3 days → send Email 2
- If Email 2: no open after 4 days → send Email 3
- If Email 3: no open or click after 7 days → apply `show-inactive` tag in CRM, suppress from outreach, add to 60-day re-engagement sequence

---

## Sequence 2: Booking Confirmation (1 Email)

**Goal:** Confirm the guest's booking and set expectations.
**Trigger:** Guest books a slot via calendar link.

**Subject:** You're booked! Here's everything you need for {{show.date}}
**Preview:** Your GoLiveStream episode details + next steps

```
Hi {{guest.first_name}},

You're officially booked for GoLiveStream! Here are the details:

📅 Date: {{show.date}}
⏰ Time: {{show.time}} ({{show.timezone}})
📍 Format: Live on StreamYard (link below)
⏱️ Duration: {{show.duration}} minutes

Before we go live, I'll send over a quick briefing doc. For now, just save the calendar invite and you're all set.

Looking forward to it!

{{sender.name}}
```

---

## Sequence 3: Pre-Show Briefing (2 Emails)

**Goal:** Prepare the guest so the live episode runs smoothly.

### Email 1 — Briefing Packet (5 days before show)

**Subject:** Your GoLiveStream briefing — {{show.date}} episode
**Preview:** Talking points, tech check, and what to expect

```
Hi {{guest.first_name}},

Your episode is coming up on {{show.date}}! Here's your briefing packet:

🎯 Episode Topic: {{episode.topic}}
📋 Talking Points: {{episode.talking_points}}
⏱️ Run of Show: {{episode.run_of_show}}

Tech Check:
- We use StreamYard (browser-based, no download needed)
- Please use a wired connection if possible
- Test your camera and mic here: {{streamyard.test_link}}

Quick favor: Could you share a headshot and 2-sentence bio for promotion?

Thanks,
{{sender.name}}
```

### Email 2 — Final Reminder (1 day before show)

**Subject:** See you tomorrow! Final details for your GoLiveStream episode
**Preview:** StreamYard link + last-minute tips

```
Hi {{guest.first_name}},

Quick reminder — we go live tomorrow at {{show.time}} {{show.timezone}}.

🔗 StreamYard Link: {{streamyard.link}}
⏱️ Please join 5 minutes early for a sound check

Tips:
- Good lighting (face a window or use a ring light)
- Look at the camera, not the screen
- Have water nearby

See you there!

{{sender.name}}
```

---

## Sequence 4: Show Promotion (2 Emails)

**Goal:** Drive viewership for the guest's episode using their network and yours.

### Email 1 — Promo Kit (Day of show)

**Subject:** You're live TODAY — share the word! 🎥
**Preview:** Pre-made social posts and links to share

```
Hi {{guest.first_name}},

You're on GoLiveStream TODAY at {{show.time}}! Here's your promo kit:

🔗 Watch Link: {{episode.live_link}}
📱 Share on LinkedIn: {{social.linkedin_share}}
🐦 Share on X: {{social.twitter_share}}

Suggested post:
"I'm joining GoLiveStream today to talk about {{episode.topic}}. Tune in at {{show.time}} {{show.timezone}}: {{episode.live_link}}"

Thanks for sharing — let's make this a great one!

{{sender.name}}
```

### Email 2 — Last Call (1 hour before show)

**Subject:** We go live in 1 hour — final share?
**Preview:** One more push for maximum viewership

```
Hi {{guest.first_name}},

One hour to showtime! If you haven't already, now's the perfect time to share with your network.

🔗 {{episode.live_link}}

See you on the stream!

{{sender.name}}
```

---

## Sequence 5: Post-Show (3 Emails)

**Goal:** Deliver value, gather testimonials, and repurpose content.

### Email 1 — Thank You + Replay (Within 24 hours)

**Subject:** You crushed it! Here's your episode replay
**Preview:** Replay link + clip delivery

```
Hi {{guest.first_name}},

Great conversation yesterday! Here's the replay:

🔗 Full Episode: {{episode.replay_link}}

I'll be sending over 3 short clips in the next 48 hours — perfect for social sharing.

Quick ask: Would you mind leaving a brief testimonial? It helps us grow and reach more people like you.

{{testimonial.link}}

Thanks again,
{{sender.name}}
```

### Email 2 — Clip Delivery (48–72 hours after show)

**Subject:** Your 3 clips are ready! 🎬
**Preview:** Download links for social-ready video clips

```
Hi {{guest.first_name}},

Your clips are ready! Here are 3 highlights from your episode:

🎬 Clip 1 — {{clip.1.title}}: {{clip.1.link}}
🎬 Clip 2 — {{clip.2.title}}: {{clip.2.link}}
🎬 Clip 3 — {{clip.3.title}}: {{clip.3.link}}

Clip Specs:
- Format: MP4
- Aspect Ratio: 9:16 (vertical)
- Duration: 45–90 seconds each
- Resolution: 1080x1920

Feel free to share these on LinkedIn, X, Instagram Reels, or TikTok. Tag us @GoTechSolutions!

{{sender.name}}
```

### Email 3 — Repurpose + Stay Connected (7 days after show)

**Subject:** Let's keep the momentum going
**Preview:** Repurposing ideas and next steps

```
Hi {{guest.first_name}},

It's been a week since your episode — hope the clips have been useful!

Here are a few ways to keep the content working for you:

📝 Blog Post: Turn the episode into a blog on your site
🎙️ Podcast: Extract the audio for a podcast episode
📊 Social Carousel: Pull 3 key quotes into a LinkedIn carousel

If you know anyone who'd be a great guest, I'd love an intro.

Talk soon,
{{sender.name}}
```

---

## Sequence 6: Ongoing Nurture + 60-Day Re-Engagement

### Ongoing Nurture (Monthly)

**Subject:** {{guest.first_name}}, here's what's new at GoLiveStream
**Preview:** Monthly update with new episodes and opportunities

```
Hi {{guest.first_name}},

Here's what's been happening on GoLiveStream:

🎥 Latest Episodes:
- {{latest_episode.1.title}}: {{latest_episode.1.link}}
- {{latest_episode.2.title}}: {{latest_episode.2.link}}

📈 Community Update: {{community.stats}}

If you'd like to come back for a follow-up episode or know someone who should be on the show, just hit reply.

Best,
{{sender.name}}
```

### 60-Day Re-Engagement (For `show-inactive` tagged contacts)

**Subject:** We miss you, {{guest.first_name}} — come back to GoLiveStream?
**Preview:** Reactivation invite after 60-day suppression

```
Hi {{guest.first_name}},

It's been a while since we last connected. GoLiveStream has grown a lot — we've featured {{guest_count}} guests and reached {{view_count}} viewers.

We'd love to have you back. If you're interested, just reply and I'll send over the current topics we're covering.

No pressure — just an open door.

Best,
{{sender.name}}
```

**Suppression:** If no open or click on re-engagement email, suppress permanently. Do not re-enter outreach pool.

---

## Open Rate Benchmarks

| Sequence | Email | Target Open Rate | Industry Avg |
|----------|-------|-----------------|--------------|
| Guest Outreach | Email 1 (Intro) | 35–45% | 30% |
| Guest Outreach | Email 2 (Value Add) | 30–40% | 25% |
| Guest Outreach | Email 3 (Breakup) | 40–55% | 45% |
| Booking Confirmation | Confirmation | 60–75% | 65% |
| Pre-Show | Briefing Packet | 50–65% | 55% |
| Pre-Show | Final Reminder | 55–70% | 60% |
| Show Promotion | Promo Kit | 40–55% | 45% |
| Show Promotion | Last Call | 35–50% | 40% |
| Post-Show | Thank You + Replay | 45–60% | 50% |
| Post-Show | Clip Delivery | 40–55% | 45% |
| Post-Show | Repurpose | 30–45% | 35% |
| Nurture | Monthly Update | 25–35% | 28% |
| Re-Engagement | 60-Day | 20–30% | 22% |

---

## Post-Show Clip Delivery Spec

| Spec | Requirement |
|------|-------------|
| Clips per episode | 3 |
| Format | MP4 |
| Aspect Ratio | 9:16 (vertical) |
| Resolution | 1080x1920 |
| Duration | 45–90 seconds each |
| Delivery window | 48–72 hours after live show |
| Platform targets | LinkedIn, X, Instagram Reels, TikTok |

---

## Re-Engagement Suppression Logic

```
IF guest_outreach_email_1 = not opened after 3 days
  → SEND outreach_email_2

IF guest_outreach_email_2 = not opened after 4 days
  → SEND outreach_email_3

IF guest_outreach_email_3 = not opened AND not clicked after 7 days
  → TAG contact as "show-inactive" in CRM
  → SUPPRESS from all outreach sequences
  → ADD to 60-day re-engagement pool

IF re_engagement_email = not opened AND not clicked after 7 days
  → SUPPRESS permanently
  → DO NOT re-enter any sequence
```

---

## Quality Checklist

Before deploying any email sequence, verify:

- [ ] All `{{variables}}` are mapped to CRM fields
- [ ] Subject lines are under 50 characters (mobile-friendly)
- [ ] Preview text is under 90 characters
- [ ] Unsubscribe link is present in all nurture/re-engagement emails
- [ ] Booking confirmation includes calendar invite (.ics attachment)
- [ ] Pre-show emails include StreamYard test link
- [ ] Post-show clip delivery follows 9:16 MP4 spec
- [ ] Suppression logic is active in automation platform
- [ ] `show-inactive` tag is configured in CRM
- [ ] Open rate tracking is enabled per sequence
- [ ] All links are UTM-tagged for analytics
- [ ] Sender name and signature are consistent across all emails
