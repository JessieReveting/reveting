#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDSS Export CSV - The David Daily Show
Exports episode data from local JSON cache to clean CSV for spreadsheet import.

Usage:
    python tdss-export-csv.py                    # Export CSV to stdout
    python tdss-export-csv.py > episodes.csv     # Export to file
    python tdss-export-csv.py --json             # Output as JSON instead
    python tdss-export-csv.py --stats            # Print summary statistics
    python tdss-export-csv.py --filter "AI"      # Filter episodes by keyword in tags/topic
    python tdss-export-csv.py --with-guests      # Only episodes with named guests

Data source: yt_seo_full.json (local cache synced from Google Sheets via TDDS)
"""

import json
import sys
import csv
import argparse
import os
from pathlib import Path
from collections import Counter
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "startup" / "yt_seo_full.json"
DATA_PATH_ALT = Path(__file__).resolve().parent.parent / "yt_seo_full.json"
GOOGLE_CREDS = Path.home() / ".hermes" / "auth" / "google_sheets_credentials.json"
GOOGLE_SERVICE_ACCOUNT = Path.home() / ".hermes" / "auth" / "google-service-account.json"

# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def load_episodes() -> list[dict]:
    """Load episode data from the local JSON cache."""
    path = DATA_PATH if DATA_PATH.exists() else DATA_PATH_ALT
    if not path.exists():
        print(f"ERROR: Cannot find yt_seo_full.json at {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"ERROR: Expected JSON array, got {type(data).__name__}", file=sys.stderr)
        sys.exit(1)

    return data


def _normalize_episode(ep: dict) -> dict:
    """Normalize a single episode record for export."""
    return {
        "episode": ep.get("ep", "").strip(),
        "title": ep.get("topic", ep.get("title", "")).strip()
        if not ep.get("topic", "").strip().startswith("The David Daily Show - Episode")
        else ep.get("topic", "").strip(),
        "guest": ep.get("guest") or "",
        "youtube_url": ep.get("url", "").strip()
        if ep.get("url", "").strip() != "N/A"
        else "",
        "tags": ep.get("tags", "").strip(),
    }


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------

def export_csv(episodes: list[dict], output=None):
    """Export episodes as CSV to stdout or given output stream."""
    writer = csv.DictWriter(
        output or sys.stdout,
        fieldnames=["episode", "title", "guest", "youtube_url", "tags"],
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for ep in episodes:
        writer.writerow(_normalize_episode(ep))


def export_json(episodes: list[dict]):
    """Export episodes as pretty-printed JSON to stdout."""
    normalized = [_normalize_episode(ep) for ep in episodes]
    json.dump(normalized, sys.stdout, indent=2, ensure_ascii=False)
    print()  # trailing newline


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def print_stats(episodes: list[dict]):
    """Print summary statistics about the episode library."""
    total = len(episodes)
    with_guests = sum(1 for ep in episodes if ep.get("guest"))
    without_guests = total - with_guests
    with_urls = sum(
        1 for ep in episodes
        if ep.get("url", "").strip() not in ("", "N/A")
    )

    # Tag frequency
    all_tags = []
    for ep in episodes:
        raw = ep.get("tags", "")
        all_tags.extend(t.strip().lower() for t in raw.split(",") if t.strip())
    tag_counts = Counter(all_tags)

    # Guest list
    guests = sorted(set(ep["guest"] for ep in episodes if ep.get("guest")))

    print("=" * 60)
    print("  TDSS Episode Library Statistics")
    print("=" * 60)
    print(f"  Total episodes:        {total}")
    print(f"  With named guests:     {with_guests}")
    print(f"  Host-only episodes:    {without_guests}")
    print(f"  With YouTube URL:      {with_urls}")
    print(f"  Unique guests:         {len(guests)}")
    print()
    print("  Top 15 Tags:")
    for tag, count in tag_counts.most_common(15):
        print(f"    {tag:<35} {count:>3}x")
    print()
    print("  Guest Roster:")
    for g in guests:
        count = sum(1 for ep in episodes if ep.get("guest") == g)
        print(f"    - {g} ({count} episode{'s' if count > 1 else ''})")
    print()
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_episodes(episodes: list[dict], keyword: str) -> list[dict]:
    """Filter episodes where keyword appears in topic, tags, or guest."""
    kw = keyword.lower()
    return [
        ep for ep in episodes
        if kw in ep.get("topic", "").lower()
        or kw in ep.get("tags", "").lower()
        or kw in (ep.get("guest") or "").lower()
    ]


def filter_with_guests(episodes: list[dict]) -> list[dict]:
    """Return only episodes that have a named guest."""
    return [ep for ep in episodes if ep.get("guest")]


# ---------------------------------------------------------------------------
# Optional: Google Sheets Live Sync
# ---------------------------------------------------------------------------

def try_google_sheets_sync(spreadsheet_id: str = None, range_name: str = "Sheet1"):
    """
    Attempt to read live data from Google Sheets API.
    This is optional — falls back gracefully if credentials or library unavailable.

    To use this feature:
      pip install google-api-python-client google-auth-httplib2

    Then call with the spreadsheet ID from your TDDS Google Sheet URL.
    """
    creds_path = (
        GOOGLE_SERVICE_ACCOUNT
        if GOOGLE_SERVICE_ACCOUNT.exists()
        else GOOGLE_CREDS
    )
    if not creds_path.exists():
        print(f"INFO: No Google credentials at {creds_path}", file=sys.stderr)
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("INFO: google-api-python-client not installed. Using local JSON.", file=sys.stderr)
        return None

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    credentials = service_account.Credentials.from_service_account_file(
        str(creds_path), scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=credentials)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    rows = result.get("values", [])

    if not rows:
        print("WARN: No data returned from Google Sheets", file=sys.stderr)
        return None

    # Assume first row is headers
    headers = [h.strip().lower() for h in rows[0]]
    episodes = []
    for row in rows[1:]:
        record = dict(zip(headers, row))
        episodes.append(record)

    print(f"Synced {len(episodes)} rows from Google Sheets", file=sys.stderr)
    return episodes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export TDSS episode data to CSV for spreadsheet import.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python tdss-export-csv.py > tdds_episodes.csv
  python tdss-export-csv.py --filter "quantum" --filter "AI"
  python tdss-export-csv.py --with-guests
  python tdss-export-csv.py --stats
  python tdss-export-csv.py --json | jq '.[0]'
""",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON instead of CSV",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print summary statistics and exit",
    )
    parser.add_argument(
        "--filter", "-f", action="append", default=[],
        help="Filter episodes by keyword (repeatable, OR logic)",
    )
    parser.add_argument(
        "--with-guests", action="store_true",
        help="Only export episodes with a named guest",
    )
    parser.add_argument(
        "--data-file", type=Path, default=None,
        help="Override path to yt_seo_full.json",
    )

    args = parser.parse_args()

    # Override data path if provided
    global DATA_PATH_ALT
    if args.data_file:
        DATA_PATH_ALT = args.data_file

    episodes = load_episodes()

    # Apply filters
    if args.with_guests:
        episodes = filter_with_guests(episodes)

    for kw in args.filter:
        episodes = filter_episodes(episodes, kw)

    if not episodes:
        print("No episodes match the given filters.", file=sys.stderr)
        sys.exit(0)

    # Output
    if args.stats:
        print_stats(episodes)
    elif args.json:
        export_json(episodes)
    else:
        export_csv(episodes)


if __name__ == "__main__":
    main()
