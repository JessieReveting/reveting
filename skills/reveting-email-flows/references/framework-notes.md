# Framework Notes — Reveting Email Flows

## Framework Index

### 1. Jessie Lizak Reveting

**Source:** Jessie Lizak's Reveting methodology — a framework for turning one-time content appearances into ongoing audience relationships.

**Key Principles Applied:**
- **Revet (re-engage):** Every content appearance should trigger a follow-up sequence, not end with the event.
- **3-Touch Outreach:** Initial contact, value-add follow-up, and a breakup email maximize response rates without being pushy.
- **Clip Repurposing:** Every episode should yield 3+ short-form clips for social distribution.
- **Suppression Hygiene:** Contacts who don't engage after 3 touches should be suppressed and moved to re-engagement pools — protecting sender reputation.

**Application in This Skill:**
- Sequence 1 (Guest Outreach) follows the 3-touch cadence.
- Sequence 5 (Post-Show) implements the revet principle — the episode is the beginning, not the end.
- Suppression logic prevents list fatigue.

---

### 2. Outreach Sales Engagement

**Source:** Outreach.io sales engagement platform methodology — multi-channel, cadence-based prospecting.

**Key Principles Applied:**
- **Cadence-Based Sequencing:** Emails are sent on a fixed schedule with conditional logic (open/click triggers).
- **Breakup Emails:** The final touch uses a "close your file" approach — often the highest-performing email in a sequence.
- **Personalization Tokens:** First name, industry, role, and episode-specific details are used to increase relevance.
- **A/B Subject Lines:** Subject lines should be tested per sequence for optimal open rates.

**Application in This Skill:**
- All sequences use `{{variable}}` tokens for personalization.
- Breakup email (Outreach Email 3) is included as the final touch.
- Cadence timing (Day 0 → 3 → 7) follows Outreach best practices.

---

### 3. HubSpot Academy CRM Automation

**Source:** HubSpot Academy's email automation and CRM certification curriculum.

**Key Principles Applied:**
- **Workflow Triggers:** Sequences are triggered by events (booking, show date, post-show).
- **Smart Lists & Suppression:** Contacts are dynamically added/removed from lists based on engagement.
- **Lead Nurturing:** Ongoing content delivery keeps contacts warm between major touchpoints.
- **Re-engagement Workflows:** Inactive contacts enter a separate re-engagement workflow after a defined period.

**Application in This Skill:**
- Booking confirmation is triggered by calendar booking event.
- Pre-show and post-show sequences are triggered by show date.
- `show-inactive` tag and 60-day re-engagement pool follow HubSpot suppression best practices.
- Monthly nurture email keeps the relationship active.

---

## Agent Routing Table

| Task | Agent/Role | Notes |
|------|-----------|-------|
| Draft new email copy | Content Agent | Use templates from `templates/output-template.md` |
| Configure automation workflows | CRM/Automation Agent | Use HubSpot or GHL workflows |
| Set up suppression lists | CRM/Automation Agent | Apply `show-inactive` tag logic |
| Produce post-show clips | Video/Production Agent | Follow 9:16 MP4 spec (45–90s) |
| Track open rates | Analytics Agent | Monitor benchmarks per sequence |
| Manage guest calendar | Scheduling Agent | Integrate with reveting-calendar-flows |
| Handle guest replies | Engagement Agent | Manual response for personal follow-up |
| UTM tagging | Analytics Agent | All links must be tagged before deployment |
| Quality check | QA Agent | Run `scripts/check-output.py` before deployment |

---

## References

- Jessie Lizak — Reveting methodology
- Outreach.io — Sales engagement cadence best practices
- HubSpot Academy — Email automation & CRM certification
- Go Technology Solutions — GoLiveStream brand guidelines
