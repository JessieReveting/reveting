# Output Template — Reveting Email Flows

Deliverable shell for all email variants. Copy, customize variables, and deploy.

---

## Guest Outreach Sequence (3 Emails)

### GO-01: Introduction Email

```
Subject: {{guest.first_name}}, your expertise deserves a bigger stage
Preview: A quick invite to share your story on GoLiveStream

Hi {{guest.first_name}},

I'm reaching out because your work in {{guest.industry/role}} caught our attention at Go Technology Solutions.

We run GoLiveStream — a livestream series where we spotlight leaders like you in short, high-energy episodes. No scripts, no fluff — just a real conversation about what you're building and what you've learned.

Would you be open to a 15-minute chat to see if it's a fit?

Best,
{{sender.name}}
{{sender.title}}, Go Technology Solutions
```

### GO-02: Value Add Email

```
Subject: Quick idea for your next {{guest.content_format}} appearance
Preview: How GoLiveStream amplifies your message

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

### GO-03: Breakup / Last Touch Email

```
Subject: Should I close your file, {{guest.first_name}}?
Preview: Last attempt — easy opt-in or opt-out

Hi {{guest.first_name}},

I don't want to clutter your inbox. If the timing isn't right, no hard feelings.

If you're still interested, just reply "yes" and I'll send over the booking link.

Either way, appreciate your time.

Best,
{{sender.name}}
```

---

## Booking Confirmation (1 Email)

### BC-01: Confirmation Email

```
Subject: You're booked! Here's everything you need for {{show.date}}
Preview: Your GoLiveStream episode details + next steps

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

## Pre-Show Briefing (2 Emails)

### PS-01: Briefing Packet Email

```
Subject: Your GoLiveStream briefing — {{show.date}} episode
Preview: Talking points, tech check, and what to expect

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

### PS-02: Final Reminder Email

```
Subject: See you tomorrow! Final details for your GoLiveStream episode
Preview: StreamYard link + last-minute tips

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

## Show Promotion (2 Emails)

### SP-01: Promo Kit Email

```
Subject: You're live TODAY — share the word! 🎥
Preview: Pre-made social posts and links to share

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

### SP-02: Last Call Email

```
Subject: We go live in 1 hour — final share?
Preview: One more push for maximum viewership

Hi {{guest.first_name}},

One hour to showtime! If you haven't already, now's the perfect time to share with your network.

🔗 {{episode.live_link}}

See you on the stream!

{{sender.name}}
```

---

## Post-Show (3 Emails)

### PO-01: Thank You + Replay Email

```
Subject: You crushed it! Here's your episode replay
Preview: Replay link + clip delivery

Hi {{guest.first_name}},

Great conversation yesterday! Here's the replay:

🔗 Full Episode: {{episode.replay_link}}

I'll be sending over 3 short clips in the next 48 hours — perfect for social sharing.

Quick ask: Would you mind leaving a brief testimonial? It helps us grow and reach more people like you.

{{testimonial.link}}

Thanks again,
{{sender.name}}
```

### PO-02: Clip Delivery Email

```
Subject: Your 3 clips are ready! 🎬
Preview: Download links for social-ready video clips

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

### PO-03: Repurpose + Stay Connected Email

```
Subject: Let's keep the momentum going
Preview: Repurposing ideas and next steps

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

## Weekly Episode Announcement

### WA-01: Weekly Announcement Email

```
Subject: New on GoLiveStream: {{episode.title}} with {{guest.name}}
Preview: This week's episode is live — watch now

Hi {{subscriber.first_name}},

This week on GoLiveStream:

🎥 {{episode.title}}
👤 Featuring {{guest.name}}, {{guest.title}} at {{guest.company}}

{{episode.description}}

🔗 Watch Now: {{episode.replay_link}}

Enjoy,
The Go Technology Solutions Team
```

---

## Re-Engagement Sequence

### RE-01: 60-Day Re-Engagement Email

```
Subject: We miss you, {{guest.first_name}} — come back to GoLiveStream?
Preview: Reactivation invite after 60-day suppression

Hi {{guest.first_name}},

It's been a while since we last connected. GoLiveStream has grown a lot — we've featured {{guest_count}} guests and reached {{view_count}} viewers.

We'd love to have you back. If you're interested, just reply and I'll send over the current topics we're covering.

No pressure — just an open door.

Best,
{{sender.name}}
```

---

## Quality Checklist

- [ ] All `{{variables}}` mapped to CRM fields
- [ ] Subject lines under 50 characters
- [ ] Preview text under 90 characters
- [ ] Unsubscribe link in nurture/re-engagement emails
- [ ] Calendar invite attached to confirmation
- [ ] StreamYard test link in pre-show briefing
- [ ] Post-show clips follow 9:16 MP4 spec
- [ ] Suppression logic active in automation platform
- [ ] `show-inactive` tag configured in CRM
- [ ] Open rate tracking enabled per sequence
- [ ] All links UTM-tagged
- [ ] Sender name and signature consistent
- [ ] Run `scripts/check-output.py` before deployment
