# Ridgeback Workbook Dashboard Contract

This file captures the operational contract for the live Ridgeback workbook so future sync scripts can update it safely without reverse-engineering the sheet each time.

## Workbook Role

The Google Sheet stays operator-friendly.

- The workbook is the day-to-day production dashboard.
- The repository is the durable source of truth for strategy, templates, process, and automation.
- Sync automation should push approved, structured data into the workbook without forcing nontechnical teammates into Git.

## Current Tabs

### Event Details

Use this tab for episode-level schedule and publishing readiness.

- Preserve historical episode rows.
- Store recording dates as real Sheets dates.
- Keep `Published` as a boolean.
- Leave future publishing links blank until they exist.
- Use `pending` only for guest placeholders when an operator needs a visible reminder.

The live workbook now includes these planned episodes:

| Episode | Recording Date | Working Title | Published |
| --- | --- | --- | --- |
| 56 | 2026-07-17 | The Cost of Moving Second \| Breach of Protocol Episode 56 | `FALSE` |
| 57 | 2026-07-24 | When Trust Becomes the Attack Surface \| Breach of Protocol Episode 57 | `FALSE` |
| 58 | 2026-07-31 | The Window Between Discovery and Damage \| Breach of Protocol Episode 58 | `FALSE` |
| 59 | 2026-08-07 | When Security Metrics Reward the Wrong Behavior \| Breach of Protocol Episode 59 | `FALSE` |
| 60 | 2026-08-14 | Resilience Before the Breach Becomes Recovery \| Breach of Protocol Episode 60 | `FALSE` |
| 61 | 2026-08-21 | What Boards Need to Hear Before the Incident \| Breach of Protocol Episode 61 | `FALSE` |
| 62 | 2026-08-28 | Ransomware as an Operating Model \| Breach of Protocol Episode 62 | `FALSE` |
| 63 | 2026-09-04 | Cloud Concentration and the Cost of Shared Failure \| Breach of Protocol Episode 63 | `FALSE` |
| 64 | 2026-09-11 | What Automation Should Decide and What Humans Must Own \| Breach of Protocol Episode 64 | `FALSE` |
| 65 | 2026-09-18 | Security Architecture for Adversaries Who Adapt \| Breach of Protocol Episode 65 | `FALSE` |
| 66 | 2026-09-25 | Third-Party Risk After the Questionnaire \| Breach of Protocol Episode 66 | `FALSE` |
| 67 | 2026-10-02 | When Identity Becomes Infrastructure \| Breach of Protocol Episode 67 | `FALSE` |
| 68 | 2026-10-09 | The Economics of Friction in Cyber Defense \| Breach of Protocol Episode 68 | `FALSE` |
| 69 | 2026-10-16 | Critical Infrastructure and Cascading Cyber Risk \| Breach of Protocol Episode 69 | `FALSE` |
| 70 | 2026-10-23 | How Fast Is Fast Enough in Vulnerability Defense? \| Breach of Protocol Episode 70 | `FALSE` |
| 71 | 2026-10-30 | Incident Ready Is Not Strategically Ready \| Breach of Protocol Episode 71 | `FALSE` |
| 72 | 2026-11-06 | Machine-Speed Conflict and the Human Decisions That Matter \| Breach of Protocol Episode 72 | `FALSE` |
| 73 | 2026-11-13 | Active Defense Without Operational Chaos \| Breach of Protocol Episode 73 | `FALSE` |
| 74 | 2026-11-20 | How to Read a Threat Week Without Chasing Headlines \| Breach of Protocol Episode 74 | `FALSE` |
| 75 | 2026-11-27 | Trust Boundaries in a Platform-Dependent World \| Breach of Protocol Episode 75 | `FALSE` |
| 76 | 2026-12-04 | Designing Security Programs for Adversaries, Not Auditors \| Breach of Protocol Episode 76 | `FALSE` |
| 77 | 2026-12-11 | What Comes After Perimeter Thinking \| Breach of Protocol Episode 77 | `FALSE` |

### Ridgeback

Use this tab for strategy reference that informs briefs, event copy, social drafts, and repurposing decisions.

The tab should always answer:

- What Ridgeback stands for
- Why the strategy matters now
- Who the audience is
- What content pillars exist
- How voice and CTAs should behave

### Social Schedule

Use this tab as the weekly publishing board for Breach of Protocol.

The tab should include:

- A durable weekly cadence
- One row per planned publishing slot
- Owner and asset requirements
- Draft, approval, and repurposing statuses
- A reminder that Wednesday event promotion should be theme-led, not headline-led

## Sync Boundaries

Future sync automation should follow these rules:

1. Update the existing workbook in place instead of creating replacement files.
2. Treat strategy, episodes, and workflow docs in this repo as the editable source material.
3. Preserve operator-entered links and status updates unless the sync step explicitly owns those fields.
4. Keep Ridgeback-specific content in data files and Markdown, not in one-off script branches.
5. Make every sync action previewable before external writes happen.
