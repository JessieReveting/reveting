# Reveting GHL Workflows — Deliverable Shell

> **Project:** [Show Name / Client Name]
> **Prepared by:** [Author / Agency]
> **Date:** [YYYY-MM-DD]
> **Version:** 1.0

---

## 1. Guest Pipeline Stages

Define the 6-stage pipeline in GHL Custom Field `Guest Pipeline Stage` (Dropdown).

| # | Stage | Tag(s) Applied | Entry Criteria | Exit Criteria |
|---|-------|----------------|----------------|---------------|
| 1 | **Prospect** | `reveting-prospect` | Identified as potential guest | Outreach message sent |
| 2 | **Outreach Sent** | *(no new tag)* | Initial message delivered | Positive response received |
| 3 | **Shortlisted** | `reveting-pre-qualified` | Guest responded positively | Passes qualification form |
| 4 | **Confirmed** | `reveting-current-guest` | Qualified + calendar booked | Recording completed |
| 5 | **Recorded** | `reveting-recorded` | Episode recorded | Episode published + guest nurtured |
| 6 | **Past Guest** | `reveting-past-guest` | Episode published + 30-day nurture | — |

### Action Items

- [ ] Create custom field `Guest Pipeline Stage` (Dropdown)
- [ ] Create all tags listed above
- [ ] Create Smart List "Active Guests" filtering on stages 2–4
- [ ] Create Smart List "Past Guests" filtering on stage 6

---

## 2. Audience Pipeline Stages

Define the 3-stage pipeline in GHL Custom Field `Audience Pipeline Stage` (Dropdown).

| # | Stage | Tag(s) Applied | Entry Criteria | Exit Criteria |
|--- |-------|----------------|----------------|---------------|
| 1 | **Show Subscriber** | `reveting-audience-subscriber` | Opted in to show notifications | Opens/watches content |
| 2 | **Engaged Viewer** | `reveting-engaged-viewer` | Opened or clicked show content | Meets CSQL qualification criteria |
| 3 | **CSQL** | `reveting-csql` | Meets lead qualification criteria | Sales handoff completed |

### Action Items

- [ ] Create custom field `Audience Pipeline Stage` (Dropdown)
- [ ] Create all tags listed above
- [ ] Create Smart List "CSQL Ready" filtering on `reveting-csql` tagged
- [ ] Define CSQL qualification criteria with sales team

---

## 3. Contact Tags

| Tag Name | Category | When Applied |
|----------|----------|-------------|
| `reveting-prospect` | Pipeline | Contact identified as potential guest |
| `reveting-current-guest` | Pipeline | Guest confirmed for upcoming episode |
| `reveting-past-guest` | Pipeline | Guest completed episode + post-show sequence |
| `reveting-audience-subscriber` | Audience | Contact opted in to view the show |
| `reveting-csql` | Audience | Contact qualified as sales-ready lead |

### Action Items

- [ ] Create all 5 tags in GHL
- [ ] Verify no duplicate or conflicting tags exist
- [ ] Document tag naming convention in team wiki

---

## 4. Custom Fields

| Field Name | Field Type | Options / Format | Purpose |
|------------|-----------|------------------|---------|
| Guest Pipeline Stage | Dropdown | Prospect, Outreach Sent, Shortlisted, Confirmed, Recorded, Past Guest | Guest lifecycle tracking |
| Audience Pipeline Stage | Dropdown | Show Subscriber, Engaged Viewer, CSQL | Audience lifecycle tracking |
| Episode Date | Date | ISO 8601 | Scheduled recording / air date |
| Guest Source | Single-line Text | Free text | Track guest origin channel |
| CSQL Qualified Date | Date | ISO 8601 | Date lead met CSQL criteria |
| Show Segment(s) | Multi-select | [Define show topics] | Segment relevance tagging |

### Action Items

- [ ] Create all 6 custom fields in GHL
- [ ] Populate `Show Segment` options based on show format
- [ ] Add fields to contact detail card for visibility

---

## 5. Workflow Maps

### 5.1 Guest Confirmation Workflow

**Trigger:** Tag `reveting-shortlisted` added

| Step | Action | Wait / Condition | Notes |
|------|--------|-----------------|-------|
| 1 | Send Pre-Qualification Form | Wait 48 h for response | GHL form or Calendly link |
| 2 | Decision: Form completed? | If no → send reminder | Add 24 h wait, then final reminder |
| 3 | Qualification Gate | Guest meets criteria? | Yes → tag `reveting-confirmed`; No → tag `reveting-declined`, exit |
| 4 | Send Calendar Booking Link | Wait until booked | Connect to GHL calendar |
| 5 | Send Pre-Interview Package | Immediate after booking | Email with guide, bio form, tech checklist |
| 6a | Reminder — 48 h before recording | Wait / date-based trigger | SMS + Email |
| 6b | Reminder — 24 h before recording | Wait / date-based trigger | SMS + Email |
| 6c | Reminder — 2 h before recording | Wait / date-based trigger | SMS + Email |
| 7 | Update Pipeline Stage | Custom field = Confirmed | Set field value |
| 8 | Notify Host & Production | Internal email / Slack | Alert all parties |

**Unenrollment Conditions:**
- Guest cancels → remove all sequences, tag `reveting-cancelled`
- Guest no-show → after recording window passes, tag `reveting-cancelled`
- Cancellation Recovery → 7-day delay, then re-engagement email

---

### 5.2 Show-Day Reminder Workflow

**Trigger:** Scheduled 1 hour before recording start time

| Step | Action | Timing | Recipients |
|------|--------|--------|------------|
| 1 | Send host bio + talking points | T-1 h | Show host |
| 2 | Production checklist reminder | T-1 h | Production team |
| 3 | 15-minute countdown | T-15 min | Host + production |
| 4 | Distribute guest join link | T-10 min | Guest + co-hosts |

---

### 5.3 Post-Show Sequence

**Trigger:** Tag `reveting-recorded` added + 1 day wait

| Step | Action | Timing | Notes |
|------|--------|--------|-------|
| 1 | Thank You / In Production notice | Immediately | Send within 24 h of recording |
| 2 | Promo Assets Delivery | When episode goes live | Shareable graphics + link |
| 3 | Audience Broadcast | Same as Step 2 | Broadcast to `reveting-audience-subscriber` |
| 4 | Move to Past Guest | Same as Step 2 | Tag `reveting-past-guest`, remove `reveting-confirmed` |
| 5 | Episode Survey | +7 days post-publish | Guest experience feedback |
| 6 | Re-Engagement | +30 days post-publish | Move to Nurture segment |

---

### 5.4 Audience Capture Workflow

**Trigger:** Form submission / link click / webhook from livestream platform

| Step | Action | Timing | Notes |
|------|--------|--------|-------|
| 1 | Double Opt-In Confirmation | Immediate | Next episode date + show details |
| 2 | Tag & Stage Update | Immediate | Tag `reveting-audience-subscriber`, stage = Show Subscriber |
| 3 | Welcome Email Sequence | Start immediately | 3-email series (intro, best episodes, CTA) |
| 4 | Engagement Tracking | Ongoing | Open/click → tag `reveting-engaged-viewer` |
| 5 | Lead Scoring | When threshold met | Tag `reveting-csql`, set CSQL date, notify sales |

---

## 6. Reporting Dashboard

### 6.1 Pipeline Health

| Metric | Filter / Calculation | Target | Current |
|--------|---------------------|--------|---------|
| Total Prospects | `reveting-prospect` tag count | — | — |
| Outreach → Confirmed Rate | `reveting-current-guest` / `reveting-prospect` | ≥ 20% | — |
| Avg Days: Prospect → Confirmed | Date field diff | ≤ 30 days | — |
| Show-Day No-Show Rate | `reveting-cancelled` / `reveting-current-guest` | ≤ 5% | — |

### 6.2 Audience Metrics

| Metric | Filter / Calculation | Target | Current |
|--------|---------------------|--------|---------|
| Subscriber Count | `reveting-audience-subscriber` tag count | — | — |
| New Subscribers (weekly) | Delta week over week | ≥ 50 / week | — |
| Engaged Viewer Rate | `reveting-engaged-viewer` / subscriber count | ≥ 30% | — |
| CSQL Conversion Rate | `reveting-csql` / subscriber count | ≥ 2% | — |

### 6.3 Automation Performance

| Metric | Source | Reporting Frequency |
|--------|--------|-------------------|
| Email Open Rate (per workflow) | GHL email reporting | Weekly |
| Email Click Rate (per workflow) | GHL email reporting | Weekly |
| Workflow Completion Rate | Goal step reached vs. enrolled | Monthly |
| Top Guest Sources | `Guest Source` field aggregation | Monthly |

---

## 7. Quality Checklist

Complete this checklist before going live with each workflow.

- [ ] **Triggers Verified** — All triggers match expected tag additions or field changes.
- [ ] **Unenrollment Rules Present** — No contact can get stuck in an active sequence.
- [ ] **No Trigger Conflicts** — No two workflows fire on the same trigger without conditional branching.
- [ ] **Custom Field Names Match** — API names match skill specification exactly.
- [ ] **Tags Pre-Exist** — All tags are created before workflows reference them.
- [ ] **End-to-End Test Passed** — Test contacts have traversed every pipeline stage.
- [ ] **Internal Notifications Configured** — Correct Slack channels / email addresses for internal alerts.
- [ ] **Calendar Links Verified** — Booking links point to the correct calendar / event type.
- [ ] **Personalisation Tokens Valid** — All merge tokens resolve correctly in test emails.
- [ ] **Reporting Filters Aligned** — Dashboard filters match current pipeline stage names and tag names.

---

## 8. Appendix

### Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | [YYYY-MM-DD] | [Author] | Initial draft |

### Notes

[Free-text space for project-specific notes, open questions, and decisions.]
