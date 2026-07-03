# HighLevel Location ID Checklist

Use this checklist to collect the four missing HighLevel location IDs, add them to your local `.env`, validate each token/location pair, then run discovery and the all-shows audit.

This process is read-only. Do not change HighLevel, Google Calendar, Gmail, appointments, events, attendees, or emails.

## Safety Rules

- Do not paste HighLevel private integration tokens into chat, docs, screenshots, or commits.
- Keep `.env` local. Never commit `.env`.
- Location IDs are not tokens, but keep them in `.env` so every show's HighLevel configuration stays in one place.
- Validate one show at a time.
- If auth fails, stop discovery for that show until the token/location pairing is fixed.

## Show Mapping

| Show key | HighLevel sub-account/location to open | Paste location ID into `.env` |
| --- | --- | --- |
| `cherry-willow` | Cherry Willow / Apparel with Purpose | `HIGHLEVEL_LOCATION_ID_CHERRY_WILLOW=` |
| `david-daily` | David Daily / The David Daily Show | `HIGHLEVEL_LOCATION_ID_DAVID_DAILY=` |
| `beyond-the-cart` | Beyond the Cart / OmniRocket LLC / Beyond the Cart | `HIGHLEVEL_LOCATION_ID_BEYOND_THE_CART=` |
| `deconstructing-data` | BDEX / Deconstructing Data | `HIGHLEVEL_LOCATION_ID_DECONSTRUCTING_DATA=` |

## How To Find Each Location ID

Repeat these steps for each of the four sub-accounts above.

1. Log into HighLevel with an account that can access the target sub-account.
2. Use the account/location switcher to enter the exact sub-account listed in the table.
3. Confirm you are inside the correct client/show before copying anything.
4. Open the sub-account settings.
5. Look for the location ID in one of these places:
   - Settings > Business Profile, often shown as `Location ID`.
   - Settings > Company/Business Info, if your HighLevel UI uses that label.
   - The browser URL while inside the sub-account, usually after a `/location/` path segment.
6. Copy only the location ID value.
7. Paste it into `reveting/.env` after the matching key.
8. Save `.env`.

Example shape only:

```env
HIGHLEVEL_LOCATION_ID_CHERRY_WILLOW=abc123example
```

Do not add quotes, spaces, or comments after the value.

## `.env` Checklist

Update these four values in `reveting/.env`:

```env
HIGHLEVEL_LOCATION_ID_CHERRY_WILLOW=
HIGHLEVEL_LOCATION_ID_DAVID_DAILY=
HIGHLEVEL_LOCATION_ID_BEYOND_THE_CART=
HIGHLEVEL_LOCATION_ID_DECONSTRUCTING_DATA=
```

Leave the existing `HIGHLEVEL_TOKEN_*` values unchanged.

## Validate Auth

Run these from the `reveting` project directory after the IDs are added:

```bash
python3 scripts/show-launch.py --test-highlevel-auth --show-key cherry-willow
python3 scripts/show-launch.py --test-highlevel-auth --show-key david-daily
python3 scripts/show-launch.py --test-highlevel-auth --show-key beyond-the-cart
python3 scripts/show-launch.py --test-highlevel-auth --show-key deconstructing-data
```

Expected success:

- The command reports a working HighLevel endpoint.
- The status code is successful.
- No token value is printed.

## If A Token/Location Pair Fails

Print or record the failed show key, then check these items before continuing:

| Failed show | Check |
| --- | --- |
| `cherry-willow` | Confirm `HIGHLEVEL_TOKEN_CHERRY_WILLOW` and `HIGHLEVEL_LOCATION_ID_CHERRY_WILLOW` both belong to Cherry Willow / Apparel with Purpose. |
| `david-daily` | Confirm `HIGHLEVEL_TOKEN_DAVID_DAILY` and `HIGHLEVEL_LOCATION_ID_DAVID_DAILY` both belong to David Daily / The David Daily Show. |
| `beyond-the-cart` | Confirm `HIGHLEVEL_TOKEN_BEYOND_THE_CART` and `HIGHLEVEL_LOCATION_ID_BEYOND_THE_CART` both belong to Beyond the Cart / OmniRocket LLC / Beyond the Cart. |
| `deconstructing-data` | Confirm `HIGHLEVEL_TOKEN_DECONSTRUCTING_DATA` and `HIGHLEVEL_LOCATION_ID_DECONSTRUCTING_DATA` both belong to BDEX / Deconstructing Data. |

Common fixes:

- The location ID was copied from the wrong sub-account.
- The private integration token was created in a different sub-account than the location ID.
- The token scopes do not include the read access needed for contacts, calendars, forms, custom fields, or appointments.
- The `.env` value has quotes, spaces, or an accidental trailing character.
- The command was run from the wrong project directory.

Do not run discovery for a show until its auth test succeeds.

## Run Discovery

After auth succeeds for a show, run discovery for that show:

```bash
python3 scripts/show-launch.py --discover-highlevel --show-key cherry-willow
python3 scripts/show-launch.py --discover-highlevel --show-key david-daily
python3 scripts/show-launch.py --discover-highlevel --show-key beyond-the-cart
python3 scripts/show-launch.py --discover-highlevel --show-key deconstructing-data
```

Expected files per show:

- `data/discovery/{show_key}_appointments.json`
- `data/discovery/{show_key}_forms.json`
- `data/discovery/{show_key}_form_fields.json`
- `data/discovery/{show_key}_form_submissions.json`
- `data/discovery/{show_key}_custom_field_map.json`

## Run The All-Shows Audit

After discovery succeeds for the four shows, run:

```bash
python3 scripts/operations-audit.py --show-key all --calendar-events data/calendar/ww_reveting_events.json
```

Expected outputs:

- `data/audit/operations_audit_report.md`
- `data/audit/operations_audit_report.json`
- `data/audit/operations_audit_issues.csv`
- `data/audit/operations_manager_dashboard.html`

## Operator Run Sheet

- [ ] Add `HIGHLEVEL_LOCATION_ID_CHERRY_WILLOW` to `.env`.
- [ ] Add `HIGHLEVEL_LOCATION_ID_DAVID_DAILY` to `.env`.
- [ ] Add `HIGHLEVEL_LOCATION_ID_BEYOND_THE_CART` to `.env`.
- [ ] Add `HIGHLEVEL_LOCATION_ID_DECONSTRUCTING_DATA` to `.env`.
- [ ] Validate auth for `cherry-willow`.
- [ ] Validate auth for `david-daily`.
- [ ] Validate auth for `beyond-the-cart`.
- [ ] Validate auth for `deconstructing-data`.
- [ ] Run discovery for `cherry-willow`.
- [ ] Run discovery for `david-daily`.
- [ ] Run discovery for `beyond-the-cart`.
- [ ] Run discovery for `deconstructing-data`.
- [ ] Run the all-shows audit.
