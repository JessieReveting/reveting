#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube SEO Pusher - The David Daily Show
Pushes SEO-optimized titles, descriptions, and tags to YouTube videos
via the Data API v3.

Usage:
    python youtube-seo-pusher.py --video G2vMcCnz2Cc        # Push single video
    python youtube-seo-pusher.py --all                     # Push all episodes
    python youtube-seo-pusher.py --all --limit 5          # Push first 5
    python youtube-seo-pusher.py --all --dry-run          # Preview changes
    python youtube-seo-pusher.py --status                 # Show push status
    python youtube-seo-pusher.py --check G2vMcCnz2Cc      # Verify title match
    python youtube-seo-pusher.py --check --all           # Check all videos

Requirements:
    pip install google-api-python-client google-auth-httplib2

Environment:
    YOUTUBE_API_KEY - YouTube Data API v3 key (required)
"""

import csv
import json
import os
import re
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_PATH = PROJECT_DIR / "yt_seo_full.json"
LOG_PATH = SCRIPT_DIR / "youtube-push-log.csv"

# YouTube API
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
CHANNEL_ID = "UCy_M6IEmXN4Y7QTZGtBRelw"

# Quota management
DAILY_QUOTA_UNITS = 10_000
UPDATE_COST_UNITS = 50  # Approximate cost per video update (snippet.update)

# Title constraints
MAX_TITLE_LENGTH = 60
HOST_NAME = "David Goecke"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FIELDS = [
    "timestamp",
    "video_id",
    "episode",
    "action",
    "status",
    "old_title",
    "new_title",
    "message",
]


def init_log():
    """Initialize the CSV log file if it doesn't exist."""
    if not LOG_PATH.exists():
        with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            writer.writeheader()


def log_entry(video_id: str, episode: str, action: str, status: str,
              old_title: str = "", new_title: str = "", message: str = ""):
    """Append an entry to the push log."""
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writerow({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "video_id": video_id,
            "episode": episode,
            "action": action,
            "status": status,
            "old_title": old_title,
            "new_title": new_title,
            "message": message,
        })


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def load_episodes() -> list[dict]:
    """Load episode data from yt_seo_full.json."""
    if not DATA_PATH.exists():
        print(f"ERROR: Cannot find episode data at {DATA_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"ERROR: Expected JSON array, got {type(data).__name__}", file=sys.stderr)
        sys.exit(1)

    return data


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    if not url or url.strip() in ("", "N/A", "TBD"):
        return None

    url = url.strip()

    # Direct video ID (11 chars, alphanumeric + _ -)
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url):
        return url

    # Standard watch URL: youtube.com/watch?v=VIDEO_ID
    parsed = urlparse(url)
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]

    # Short URL: youtu.be/VIDEO_ID
    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/")

    # Embed URL: youtube.com/embed/VIDEO_ID
    if parsed.hostname in ("www.youtube.com", "youtube.com"):
        match = re.match(r"^/embed/([a-zA-Z0-9_-]{11})", parsed.path)
        if match:
            return match.group(1)

    return None


def get_video_url(ep: dict) -> str | None:
    """Get the YouTube URL from episode data, trying multiple fields."""
    url = ep.get("url", "")
    return url if url and url.strip() not in ("", "N/A", "TBD") else None


# ---------------------------------------------------------------------------
# YouTube API Client
# ---------------------------------------------------------------------------

def get_youtube_service():
    """Build and return the YouTube API service client."""
    if not YOUTUBE_API_KEY:
        print(
            "ERROR: YOUTUBE_API_KEY environment variable is not set.\n"
            "Set it with: export YOUTUBE_API_KEY='your-api-key-here'",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        print(
            "ERROR: google-api-python-client is not installed.\n"
            "Install it with: pip install google-api-python-client google-auth-httplib2",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        service = build(
            YOUTUBE_API_SERVICE_NAME,
            YOUTUBE_API_VERSION,
            developerKey=YOUTUBE_API_KEY,
        )
        return service
    except Exception as e:
        print(f"ERROR: Failed to build YouTube API service: {e}", file=sys.stderr)
        sys.exit(1)


def validate_api_key(service) -> bool:
    """Quick validation that the API key works by fetching channel info."""
    try:
        from googleapiclient.errors import HttpError
        request = service.channels().list(part="snippet", id=CHANNEL_ID)
        response = request.execute()
        if response.get("items"):
            channel_name = response["items"][0]["snippet"]["title"]
            print(f"API Key valid. Channel: {channel_name}")
            return True
        else:
            print(
                f"WARN: Channel {CHANNEL_ID} not found. The key may be valid but "
                "the channel ID may be wrong.",
                file=sys.stderr,
            )
            return False
    except HttpError as e:
        if e.resp.status == 400:
            print(
                f"ERROR: Invalid API key (HTTP 400). Check YOUTUBE_API_KEY.",
                file=sys.stderr,
            )
        elif e.resp.status == 403:
            error_details = e.content.decode("utf-8", errors="replace")
            if "keyInvalid" in error_details:
                print(
                    "ERROR: API key is invalid or restricted (HTTP 403 - keyInvalid).\n"
                    "Check that your key is a valid YouTube Data API v3 key.",
                    file=sys.stderr,
                )
            elif "quotaExceeded" in error_details or "dailyLimitExceeded" in error_details:
                print(
                    "ERROR: YouTube API quota exceeded (HTTP 403).\n"
                    f"Daily limit: {DAILY_QUOTA_UNITS} units. Try again tomorrow.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"ERROR: Access forbidden (HTTP 403): {error_details}",
                    file=sys.stderr,
                )
        else:
            print(f"ERROR: HTTP {e.resp.status}: {e.content.decode('utf-8', errors='replace')}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"ERROR: Failed to validate API key: {e}", file=sys.stderr)
        return False


def fetch_video_snippet(service, video_id: str) -> dict | None:
    """Fetch the current snippet for a video."""
    from googleapiclient.errors import HttpError

    try:
        request = service.videos().list(part="snippet", id=video_id)
        response = request.execute()
        items = response.get("items", [])
        if not items:
            return None
        return items[0]["snippet"]
    except HttpError as e:
        if e.resp.status == 404:
            raise ValueError(f"Video {video_id} not found (may be deleted or private)")
        raise


def update_video_snippet(service, video_id: str, title: str, description: str,
                         tags: list[str]) -> dict:
    """Update a video's title, description, and tags."""
    from googleapiclient.errors import HttpError

    body = {
        "id": video_id,
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "28",  # Science & Technology
        },
    }

    try:
        request = service.videos().update(part="snippet", body=body)
        response = request.execute()
        return response
    except HttpError as e:
        error_body = e.content.decode("utf-8", errors="replace")
        if e.resp.status == 400:
            raise ValueError(
                f"Bad request updating {video_id} (HTTP 400). "
                f"Possible causes: title too long, invalid tags, or missing fields.\n"
                f"Details: {error_body}"
            )
        elif e.resp.status == 403:
            if "quotaExceeded" in error_body or "dailyLimitExceeded" in error_body:
                raise RuntimeError(
                    f"QUOTA EXCEEDED: YouTube API daily quota ({DAILY_QUOTA_UNITS} units) "
                    f"has been reached. No further updates today."
                )
            elif "forbidden" in error_body.lower():
                raise PermissionError(
                    f"Forbidden (HTTP 403): You don't have permission to update video {video_id}. "
                    f"The video may not belong to your channel.\n"
                    f"Details: {error_body}"
                )
            else:
                raise RuntimeError(f"Forbidden (HTTP 403): {error_body}")
        elif e.resp.status == 404:
            raise ValueError(f"Video {video_id} not found")
        else:
            raise RuntimeError(f"HTTP {e.resp.status}: {error_body}")


# ---------------------------------------------------------------------------
# SEO Validation
# ---------------------------------------------------------------------------

def validate_title(title: str, ep: dict) -> list[str]:
    """Validate title against SEO rules. Returns list of warnings."""
    warnings = []

    if len(title) > MAX_TITLE_LENGTH:
        warnings.append(
            f"Title is {len(title)} chars (max {MAX_TITLE_LENGTH}): '{title}'"
        )

    if HOST_NAME not in title and "David Goecke" not in title:
        warnings.append(f"Title missing host name: '{title}'")

    ep_num = ep.get("ep", "")
    if ep_num and ep_num not in title:
        warnings.append(f"Title missing episode number ({ep_num}): '{title}'")

    return warnings


def validate_description(desc: str) -> list[str]:
    """Validate description against SEO rules. Returns list of warnings."""
    warnings = []

    if len(desc) < 50:
        warnings.append(f"Description too short ({len(desc)} chars, min 50 recommended)")

    if "#" not in desc:
        warnings.append("Description missing hashtags")

    return warnings


def parse_tags(tags_raw: str) -> list[str]:
    """Parse comma-separated tags string into a list."""
    if not tags_raw:
        return []
    return [t.strip() for t in tags_raw.split(",") if t.strip()]


# ---------------------------------------------------------------------------
# Status Tracking
# ---------------------------------------------------------------------------

def get_status(episodes: list[dict], service) -> list[dict]:
    """Check which episodes have been pushed and match YouTube."""
    results = []

    for ep in episodes:
        video_id = extract_video_id(get_video_url(ep))
        if not video_id:
            continue

        seo_title = ep.get("title", "")

        try:
            snippet = fetch_video_snippet(service, video_id)
            if snippet:
                current_title = snippet.get("title", "")
                matches = current_title == seo_title
                results.append({
                    "ep": ep.get("ep", ""),
                    "video_id": video_id,
                    "seo_title": seo_title,
                    "current_title": current_title,
                    "matches": matches,
                    "status": "synced" if matches else "pending",
                })
            else:
                results.append({
                    "ep": ep.get("ep", ""),
                    "video_id": video_id,
                    "seo_title": seo_title,
                    "current_title": "",
                    "matches": False,
                    "status": "not_found",
                })
        except Exception as e:
            results.append({
                "ep": ep.get("ep", ""),
                "video_id": video_id,
                "seo_title": seo_title,
                "current_title": "",
                "matches": False,
                "status": f"error: {e}",
            })

        # Small delay to avoid rate limiting
        time.sleep(0.2)

    return results


def print_status(status_list: list[dict]):
    """Print a formatted status table."""
    print("\n" + "=" * 100)
    print("  YouTube SEO Push Status")
    print("=" * 100)

    synced = sum(1 for s in status_list if s["status"] == "synced")
    pending = sum(1 for s in status_list if s["status"] == "pending")
    errors = sum(1 for s in status_list if s["status"].startswith("error"))
    not_found = sum(1 for s in status_list if s["status"] == "not_found")

    print(f"  Total videos:  {len(status_list)}")
    print(f"  Synced:        {synced}")
    print(f"  Pending:       {pending}")
    print(f"  Not found:     {not_found}")
    print(f"  Errors:        {errors}")
    print("-" * 100)

    # Show pending items
    if pending > 0:
        print("\n  Pending updates:")
        for s in status_list:
            if s["status"] == "pending":
                print(f"    {s['ep']}: {s['video_id']}")
                print(f"      YouTube:  {s['current_title'][:60]}")
                print(f"      SEO:      {s['seo_title'][:60]}")

    print("=" * 100)


# ---------------------------------------------------------------------------
# Quota Estimation
# ---------------------------------------------------------------------------

def estimate_quota(num_videos: int) -> dict:
    """Estimate quota usage for a batch of updates."""
    cost_per_video = UPDATE_COST_UNITS
    total_cost = num_videos * cost_per_video
    remaining = DAILY_QUOTA_UNITS - total_cost
    max_videos_today = DAILY_QUOTA_UNITS // cost_per_video

    return {
        "cost_per_video": cost_per_video,
        "total_cost": total_cost,
        "remaining": remaining,
        "max_videos_today": max_videos_today,
        "within_quota": total_cost <= DAILY_QUOTA_UNITS,
    }


def print_quota_estimate(num_videos: int):
    """Print quota usage estimate."""
    est = estimate_quota(num_videos)

    print(f"\n  Quota Estimate:")
    print(f"    Videos to update:    {num_videos}")
    print(f"    Cost per update:     ~{est['cost_per_video']} units")
    print(f"    Total cost:          ~{est['total_cost']} units")
    print(f"    Daily limit:         {DAILY_QUOTA_UNITS} units")
    print(f"    Remaining after:     ~{est['remaining']} units")
    print(f"    Max updates today:   {est['max_videos_today']} videos")

    if not est["within_quota"]:
        print(f"\n  WARNING: This batch exceeds the daily quota!")
        print(f"  Reduce --limit to {est['max_videos_today']} or fewer.")
    print()


# ---------------------------------------------------------------------------
# Main Actions
# ---------------------------------------------------------------------------

def push_single_video(service, ep: dict, dry_run: bool = False) -> bool:
    """Push SEO updates for a single video. Returns True if successful."""
    video_id = extract_video_id(get_video_url(ep))
    if not video_id:
        ep_num = ep.get("ep", "unknown")
        print(f"  SKIP {ep_num}: No valid YouTube URL")
        log_entry(video_id or "", ep.get("ep", ""), "push", "skipped",
                  message="No valid YouTube URL")
        return False

    seo_title = ep.get("title", "")
    seo_desc_preview = ep.get("desc_preview", "")
    seo_tags_raw = ep.get("tags", "")
    seo_tags = parse_tags(seo_tags_raw)

    ep_num = ep.get("ep", "")

    # Validate
    title_warnings = validate_title(seo_title, ep)
    if title_warnings:
        for w in title_warnings:
            print(f"  WARN {ep_num}: {w}")

    # Build full description (preview + hashtags)
    hashtags = " ".join(f"#{tag.replace(' ', '').replace('-', '')}" for tag in seo_tags[:5])
    full_description = f"{seo_desc_preview}\n\n{hashtags}" if hashtags else seo_desc_preview

    if dry_run:
        print(f"  DRY-RUN {ep_num} [{video_id}]:")
        print(f"    Title: {seo_title}")
        print(f"    Desc:  {full_description[:80]}...")
        print(f"   Tags:  {len(seo_tags)} tags")
        log_entry(video_id, ep_num, "push", "dry-run",
                  new_title=seo_title, message="Dry run - no changes made")
        return True

    # Fetch current state
    try:
        current = fetch_video_snippet(service, video_id)
        if not current:
            print(f"  ERROR {ep_num}: Video {video_id} not found on YouTube")
            log_entry(video_id, ep_num, "push", "error",
                      message="Video not found on YouTube")
            return False

        current_title = current.get("title", "")
        if current_title == seo_title:
            print(f"  OK {ep_num}: Title already matches, skipping")
            log_entry(video_id, ep_num, "push", "skipped",
                      old_title=current_title, new_title=seo_title,
                      message="Already up to date")
            return True

    except Exception as e:
        print(f"  ERROR {ep_num}: Failed to fetch current state: {e}")
        log_entry(video_id, ep_num, "push", "error",
                  message=f"Fetch failed: {e}")
        return False

    # Update
    try:
        update_video_snippet(service, video_id, seo_title, full_description, seo_tags)
        print(f"  OK {ep_num} [{video_id}]: Updated successfully")
        log_entry(video_id, ep_num, "push", "success",
                  old_title=current_title, new_title=seo_title,
                  message="Updated title, description, and tags")
        return True
    except (ValueError, PermissionError, RuntimeError) as e:
        print(f"  ERROR {ep_num}: {e}")
        log_entry(video_id, ep_num, "push", "error",
                  old_title=current.get("title", "") if current else "",
                  new_title=seo_title, message=str(e))
        return False
    except Exception as e:
        print(f"  ERROR {ep_num}: Unexpected error: {e}")
        log_entry(video_id, ep_num, "push", "error",
                  new_title=seo_title, message=f"Unexpected: {e}")
        return False


def push_all(service, episodes: list[dict], limit: int | None = None,
             dry_run: bool = False) -> dict:
    """Push SEO updates for all episodes (or up to limit)."""
    to_push = episodes[:limit] if limit else episodes

    # Filter to episodes with URLs
    valid = [ep for ep in to_push if extract_video_id(get_video_url(ep))]
    skipped = len(to_push) - len(valid)

    if skipped:
        print(f"  Skipping {skipped} episodes without valid URLs")

    print(f"  Pushing {len(valid)} episodes...")
    print_quota_estimate(len(valid))

    if not dry_run:
        est = estimate_quota(len(valid))
        if not est["within_quota"]:
            print("  ABORT: Quota would be exceeded. Use --limit to reduce batch size.")
            return {"success": 0, "failed": 0, "skipped": skipped}

    results = {"success": 0, "failed": 0, "skipped": skipped}

    for i, ep in enumerate(valid):
        ep_num = ep.get("ep", f"#{i+1}")
        print(f"\n[{i+1}/{len(valid)}] Processing {ep_num}...")

        success = push_single_video(service, ep, dry_run=dry_run)
        if success:
            results["success"] += 1
        else:
            results["failed"] += 1

        # Rate limiting: small delay between API calls
        if not dry_run and i < len(valid) - 1:
            time.sleep(1)

    # Summary
    print(f"\n  {'=' * 50}")
    action = "Would update" if dry_run else "Updated"
    print(f"  {action}: {results['success']} videos")
    if results["failed"]:
        print(f"  Failed: {results['failed']} videos")
    if results["skipped"]:
        print(f"  Skipped (no URL): {results['skipped']} videos")
    print(f"  Log: {LOG_PATH}")
    print(f"  {'=' * 50}")

    return results


def check_video(service, ep: dict) -> bool:
    """Check if a single video's title matches the SEO title."""
    video_id = extract_video_id(get_video_url(ep))
    if not video_id:
        print(f"  SKIP {ep.get('ep', '?')}: No valid YouTube URL")
        return False

    seo_title = ep.get("title", "")
    ep_num = ep.get("ep", "?")

    try:
        snippet = fetch_video_snippet(service, video_id)
        if not snippet:
            print(f"  {ep_num} [{video_id}]: NOT FOUND on YouTube")
            return False

        current_title = snippet.get("title", "")
        current_desc = snippet.get("description", "")
        current_tags = snippet.get("tags", [])

        matches = current_title == seo_title
        status = "MATCH" if matches else "MISMATCH"

        print(f"  {ep_num} [{video_id}]: {status}")
        print(f"    YouTube title:  {current_title}")
        print(f"    SEO title:      {seo_title}")

        if not matches:
            # Show diff
            for i, (a, b) in enumerate(zip(current_title, seo_title)):
                if a != b:
                    print(f"    First diff at char {i}: YouTube='{a}' vs SEO='{b}'")
                    break

        # Check description
        seo_desc = ep.get("desc_preview", "")
        if seo_desc and seo_desc not in current_desc:
            print(f"    Description: MISSING SEO content")
        elif seo_desc:
            print(f"    Description: OK")

        # Check tags
        seo_tags = set(parse_tags(ep.get("tags", "")))
        yt_tags = set(current_tags)
        if seo_tags and not seo_tags.issubset(yt_tags):
            missing = seo_tags - yt_tags
            print(f"    Tags: MISSING {len(missing)} tags: {', '.join(list(missing)[:5])}")
        elif seo_tags:
            print(f"    Tags: OK ({len(seo_tags)} present)")

        return matches

    except Exception as e:
        print(f"  {ep_num} [{video_id}]: ERROR - {e}")
        return False


def check_all(service, episodes: list[dict], limit: int | None = None):
    """Check all videos against SEO data."""
    to_check = episodes[:limit] if limit else episodes
    valid = [ep for ep in to_check if extract_video_id(get_video_url(ep))]

    print(f"\n  Checking {len(valid)} videos...")
    print(f"  (This uses ~1 API unit per video for listing)\n")

    matched = 0
    mismatched = 0
    errors = 0

    for i, ep in enumerate(valid):
        ep_num = ep.get("ep", f"#{i+1}")
        print(f"[{i+1}/{len(valid)}] {ep_num}...")

        result = check_video(service, ep)
        if result is True:
            matched += 1
        elif result is False:
            mismatched += 1
        else:
            errors += 1

        # Rate limiting
        if i < len(valid) - 1:
            time.sleep(0.5)

    print(f"\n  {'=' * 50}")
    print(f"  Check complete: {matched} match, {mismatched} mismatch, {errors} errors")
    print(f"  {'=' * 50}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Push SEO updates to YouTube videos via Data API v3.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python youtube-seo-pusher.py --video G2vMcCnz2Cc
  python youtube-seo-pusher.py --video G2vMcCnz2Cc --dry-run
  python youtube-seo-pusher.py --all
  python youtube-seo-pusher.py --all --limit 5
  python youtube-seo-pusher.py --all --dry-run --limit 3
  python youtube-seo-pusher.py --status
  python youtube-seo-pusher.py --check G2vMcCnz2Cc
  python youtube-seo-pusher.py --check --all
  python youtube-seo-pusher.py --all --limit 10

Environment:
  YOUTUBE_API_KEY    YouTube Data API v3 key (required)
""",
    )

    # Target selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--video", "-v", type=str, metavar="ID",
        help="Push/check a single video by YouTube video ID or URL",
    )
    group.add_argument(
        "--all", "-a", action="store_true",
        help="Push/check all episodes from yt_seo_full.json",
    )
    group.add_argument(
        "--status", "-s", action="store_true",
        help="Show which videos have been updated vs pending",
    )

    # Modifiers
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Preview changes without actually updating YouTube",
    )
    parser.add_argument(
        "--limit", "-l", type=int, metavar="N",
        help="Limit number of videos to process",
    )
    parser.add_argument(
        "--check", "-c", action="store_true",
        help="Check mode: verify current YouTube title matches SEO title (use with --video or --all)",
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Only validate titles/descriptions against SEO rules, no API calls",
    )
    parser.add_argument(
        "--data-file", type=Path, default=None,
        help="Override path to yt_seo_full.json",
    )
    parser.add_argument(
        "--skip-api-validate", action="store_true",
        help="Skip initial API key validation (useful for --validate-only)",
    )

    args = parser.parse_args()

    # Banner
    print("\n" + "=" * 60)
    print("  YouTube SEO Pusher - The David Daily Show")
    print("=" * 60)

    # Override data path if provided
    global DATA_PATH
    if args.data_file:
        DATA_PATH = args.data_file

    # Load episodes
    episodes = load_episodes()
    print(f"  Loaded {len(episodes)} episodes from {DATA_PATH.name}")

    # Validate-only mode (no API needed)
    if args.validate_only:
        print("\n  Validating SEO data...")
        issues = 0
        for ep in episodes:
            title = ep.get("title", "")
            desc = ep.get("desc_preview", "")
            ep_num = ep.get("ep", "?")

            warnings = validate_title(title, ep)
            warnings.extend(validate_description(desc))

            if warnings:
                issues += len(warnings)
                for w in warnings:
                    print(f"  WARN {ep_num}: {w}")

        if issues == 0:
            print(f"  All {len(episodes)} episodes pass validation.")
        else:
            print(f"  {issues} warnings found across {len(episodes)} episodes.")
        return

    # Initialize log
    init_log()

    # Build API service
    service = get_youtube_service()

    # Validate API key (unless skipped)
    if not args.skip_api_validate:
        print("\n  Validating API key...")
        if not validate_api_key(service):
            print("\n  API key validation failed. Use --skip-api-validate to override.")
            sys.exit(1)
        print()

    # Execute requested action
    if args.video:
        # Extract video ID
        video_id = extract_video_id(args.video)
        if not video_id:
            print(f"ERROR: Could not extract video ID from: {args.video}", file=sys.stderr)
            sys.exit(1)

        # Find matching episode
        matching_ep = None
        for ep in episodes:
            ep_url = get_video_url(ep)
            if ep_url and extract_video_id(ep_url) == video_id:
                matching_ep = ep
                break

        if not matching_ep:
            print(f"WARNING: Video {video_id} not found in yt_seo_full.json.")
            print("Cannot push SEO data without a matching episode entry.", file=sys.stderr)
            sys.exit(1)

        if args.check:
            check_video(service, matching_ep)
        else:
            push_single_video(service, matching_ep, dry_run=args.dry_run)

    elif args.all:
        if args.check:
            check_all(service, episodes, limit=args.limit)
        else:
            push_all(service, episodes, limit=args.limit, dry_run=args.dry_run)

    elif args.status:
        print("\n  Fetching current status from YouTube...")
        status_list = get_status(episodes, service)
        print_status(status_list)


if __name__ == "__main__":
    main()
