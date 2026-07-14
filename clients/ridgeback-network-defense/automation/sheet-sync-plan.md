# Ridgeback Sheet Sync Plan

## Purpose

Keep the Google Sheet as the execution dashboard while the repository remains the durable planning system.

## Source Ownership

- Strategy, content pillars, and baseline social cadence live in the repo.
- Episode seed metadata lives in per-episode YAML.
- Operators may update links and some statuses in the workbook after production moves forward.

## Sync Strategy

1. Read the manifest and workbook content YAML.
2. Read all episode YAML files.
3. Build deterministic row payloads for the three owned tabs.
4. Preview the row payloads locally.
5. Write only when an operator explicitly opts into a workbook sync.

## Guardrails

- Do not create a new workbook unless direct editing is impossible.
- Do not overwrite operator-entered publishing links unless the sync run explicitly owns those columns.
- Keep client-specific copy in YAML or Markdown, not in `if client == "ridgeback"` branches.
