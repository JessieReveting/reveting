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
