# Account routing

Use this table as the initial Reveting routing configuration. Store operational URLs, browser profiles, and destination selections in the master Google Sheet `Config` tab; do not hardcode credentials in the skill.

| Show key | Client / owner | GHL location ID | GHL calendar ID | Calendar name | Status |
|---|---|---|---|---|---|
| `beyond-the-cart` | Kyle Hamar / Beyond the Cart | `la5Jw9fi0OrOVGbdJc47` | `SgvRnzc0z5hw1t71I3TL` | Beyond The Cart Podcast | Enabled |
| `david-daily` | David Goecke / The David Daily Show | `fcO3237HO2HZyeXNe9O8` | `tfyAt3M4UCqJwOKpSBry` | The David Daily Show | Enabled |
| `winsday` | Jessie Lizak / Reveting | `SnoTN8sz1XVpiYQCpG79` | `Pc2uJPYPLs8UT0LIfF5k` | WinsDay Livestream & Podcast | Enabled |
| `cherry-willow` | Matt F. / Cherry Willow | `HdJ1p9IKlwJIBCKfxkX7` | `Dyx2Z4FZH1QrIyUrMHIz` | Cherry Willow's apparel with Purpose | Enabled |
| `deconstructing-data` | David F. / BDEX | `X5W015TYFZwWNhtG79Cb` | `xQf69sfGMyYK9PXapHq6` | Deconstructing Data Live Broadcast and Podcast | Enabled |
| `breach-of-protocol` | Scott / Ridgeback Network Defense | Configure in sheet | Configure in sheet | Breach of Protocol | Editorial workflow; GHL may not be required |
| `ridgeback-show-2` | Scott / Ridgeback Network Defense | Configure in sheet | Configure in sheet | Exact show name required | Disabled until identified |

## Config-tab fields

Create one row per show route with:

- `enabled`
- `show_key`
- `client_name`
- `owner_name`
- `ghl_browser_url`
- `ghl_location_id`
- `ghl_calendar_id`
- `ghl_calendar_name`
- `google_calendar_id` (default `ww@reveting.com`)
- `streamyard_account_url`
- `destination_linkedin`
- `destination_youtube`
- `destination_facebook`
- `destination_twitter_x`
- `destination_twitch`
- `preshow_minutes`
- `last_successful_cursor`

## Routing precedence

1. Match exact GHL location ID and calendar ID.
2. If the calendar ID is unavailable, match exact location ID and configured form ID.
3. Use calendar name or host only as a review clue, never as the sole automatic route.
4. Quarantine a booking when zero or multiple routes match.

## Known destination alerts

At the time this routing file was created, the StreamYard dashboard reported lost access to Facebook `OmniRocket` and LinkedIn `I Love My Life! Coaching`, plus expiring access for Facebook `David Goecke` and Instagram `davidgoecke`. Re-check live status before every batch; treat this note as historical evidence, not current connection state.
