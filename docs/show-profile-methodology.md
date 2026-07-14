# Show Profile Methodology

## Identification

Unique shows are identified by reconciling spreadsheet titles, tab names, episode-row language, host names, recurring client names, and any matching repository evidence. When a workbook names a client but the episode rows name a distinct show, the show title is derived from the most specific recurring show-facing evidence rather than the client file name alone.

## Status Assignment

`required` is used when the current operating evidence shows the deliverable or step as part of the real workflow, not just a possible future output.

`optional` is used when the evidence shows the item can appear in the workflow but is not consistently required for readiness.

`not_used` is used only when evidence clearly shows the show does not currently use that deliverable or system.

`unknown` is used when evidence is incomplete, indirect, outdated, or not strong enough to support a confident requirement.

## Valid Evidence

Valid evidence includes bounded spreadsheet reads, repository discovery exports, repository manifests, client operating files, show-specific rules, and documented human-reviewed operating exceptions. A single suggestive field name is weaker evidence than a recurring row pattern, structured export, or explicit workflow note.

## Constraint

Generic deliverable assumptions are prohibited because Reveting shows do not share one universal operating model. Some shows are guest-booking shows, some are editorial-first, some are multi-guest, and some do not support newsletters, blogs, or podcast distribution at all.

## Audit Control

Show-specific profiles should be the control layer for future audits and health scoring. Readiness, required assets, excluded categories, and blocked states should be evaluated against each show's own profile rather than a generic livestream checklist.

## Reconciliation

Each `historical-source-map.yaml` identifies where the current profile came from, what fields still need verification, what fields are likely missing, and what blockers prevent stronger coverage. Later reconciliation should start from that map before reopening live spreadsheets or changing the profile.

## Confidence

Confidence should track evidence quality, not optimism. Use high confidence when spreadsheet and repository evidence align, medium when the operating model is mostly clear but incomplete, and low when the show depends on a thin workbook sample, unresolved identity, or missing repository-side history.
