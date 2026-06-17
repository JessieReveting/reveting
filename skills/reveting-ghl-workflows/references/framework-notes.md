# Framework Notes

## Authoritative Sources

### 1. Jessica (Jessie) Lizak — Reveting™

- **Core Thesis:** Treat every audience member like a guest and every guest like an audience member. Systematic, repeatable guest lifecycles compound into a content engine.
- **Key Principles:**
  -Guest-first pipeline: qualify before you book, confirm before you record, nurture after you publish.
  - Content repurposing: every episode generates clips, quotes, and derivative assets.
  - Sales alignment: audience behavioural data → lead scoring → SQL handoff.
- **Primary Assets:**
  - _Reveting_ — downloadable playbook
  - _The Ultimate Guide to Podcast Guesting_ (course)
  - _Reveting Accelerator_ (coaching program)
- **Attribution:** Jessica Lizak / https://jessicalizak.com

### 2. Go High Level (GHL) — Official Documentation

- **Platform:** CRM, marketing automation, funnels, calendars, reputation management, SaaS mode.
- **Relevant Features:**
  - Workflows (trigger-based automations, conditional paths, wait steps, goals)
  - Custom Fields & Custom Values (contact schema)
  - Tags & Smart Lists (segmentation)
  - Calendar / Appointment Scheduling (booking, reminders)
  - Email & Campaign Builder (broadcasts, sequences)
  - Reputation & Review Management (post-show surveys)
  - API & Webhooks (platform integrations — Streamyard Zapier, etc.)
  - Snapshots (account templates for replication)
- **Docs URL:** https://help.gohighlevel.com

### 3. HubSpot Academy — CRM Automation Curriculum

- **Relevant Courses:**
  - _CRM Setup & Data Management_ — contact properties, lifecycle stages, lead scoring
  - _Marketing Automation Workflows_ — enrollment, branching, goals, suppression lists
  - _Reporting & Analytics_ — pipeline dashboards, conversion metrics
  - _Sales & Marketing Alignment_ — lead handoff, qualification criteria
- **Key Takeaways for GHL Migration:** HubSpot lifecycle stages map directly to Reveting pipeline stages; HubSpot workflow patterns translate to GHL workflow builder with equivalent trigger/condition/wait logic.
- **Docs URL:** https://academy.hubspot.com

## Mapping Philosophy

| Concept | Jessie Lizak Reveting | GHL Implementation | HubSpot Parallel |
|---------|----------------------|--------------------|-----------------|
| Guest lifecycle | Qualify → Book → Record → Repurpose | Tag + custom field pipeline | Lifecycle stage |
| Audience lifecycle | Subscribe → Engage → Buy | Tag + custom field pipeline | Lifecycle stage |
| Lead scoring | Implicit in engagement signals | Custom field + workflow logic | HubSpot lead score |
| Automation | Systematic outreach/reminders | Workflow builder (trigger/action) | Marketing workflows |
| Reporting | Pipeline health & conversion | GHL dashboards + reporting | Custom reports |

## Agent Routing Table

Use this table to delegate sub-tasks to the correct specialist agent:

| Skill / Agent | Domain | When to Route |
|---------------|--------|---------------|
| `reveting-show-setup` | Show configuration, guest research, outreach templates | Setting up a new show; researching prospects; drafting outreach |
| `reveting-email-flows` | Email sequence design, copywriting, deliverability | Building or editing welcome sequences, reminder emails, nurture flows |
| `reveting-calendar-flows` | Booking page setup, reminder logic, calendar sync | Configuring booking links, calendar reminders, schedule sync |
| `reveting-streamyard-flows` | Streamyard scenes, recording workflows, OBS/Streamyard config | Setting up show-day tech, scene templates, recording triggers |
| `ghl-api` (platform API) | GHL API calls, webhook handling, custom integrations | Custom API integrations, external platform connects |
| `browser` tool | GHL UI screenshots, visual verification | Visual QA of workflow builder, dashboard verification |
| `terminal` tool | Data export, file ops, scripting | Bulk contact import, script-based analysis |

---

## Citation Index

| # | Source | Topic | URL |
|---|--------|-------|-----|
| 1 | Jessie Lizak — _Reveting_ | Guest pipeline methodology, audience-as-guest philosophy | https://jessicalizak.com |
| 2 | Go High Level — Help Center | Workflows, tags, custom fields, calendars | https://help.gohighlevel.com |
| 3 | HubSpot Academy — CRM Automation | Lifecycle stages, workflow design, reporting | https://academy.hubspot.com |
