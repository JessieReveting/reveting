# Sheet Sync Plan Template

## Goal

Keep the workbook useful for operators while keeping durable source material in Git.

## Sync Pattern

1. Read the client manifest.
2. Read structured workbook content.
3. Read structured episode records.
4. Build workbook rows deterministically.
5. Preview changes before any write step.
6. Write only the tabs and ranges the sync script owns.

## Ownership Boundary

- Operators own live links and some status fields.
- The repo owns strategy, reusable schedule defaults, and seed episode planning data.
