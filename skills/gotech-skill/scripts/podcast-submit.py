#!/usr/bin/env python3
"""
podcast-submit.py - Podcast Submission Automation Script

Reads podcast metadata, generates/validates RSS feed, and creates submission
checklists for major podcast platforms (Spotify, Apple, Google, etc.).

Usage:
    python3 podcast-submit.py --validate          Validate RSS feed
    python3 podcast-submit.py --submit-checklist  Generate submission checklist
    python3 podcast-submit.py --generate-rss      Generate RSS feed from config
    python3 podcast-submit.py --status            Show submission history/status
    python3 podcast-submit.py --all               Run all operations
"""

import json
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring, parse
import urllib.request
import urllib.error
import argparse

# === Configuration ===
BASE_DIR = Path("/Users/davidgo/Documents/GoTechSolutions/startup")
DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = BASE_DIR / "scripts"
CONFIG_PATH = DATA_DIR / "podcast-config.json"
HISTORY_PATH = DATA_DIR / "submission-history.json"
RSS_OUTPUT_PATH = BASE_DIR / "podcast-rss.xml"

PLATFORMS = {
    "spotify": {
        "name": "Spotify for Podcasters",
        "url": "https://podcasters.spotify.com/",
        "submit_url": "https://podcasters.spotify.com/dash/submit",
        "requirements": [
            "RSS feed with valid audio enclosures",
            "Cover art: JPG/PNG, 3000x3000px recommended",
            "Title and description required",
            "At least one episode published",
            "Valid email in itunes:owner",
        ],
        "notes": "Login with Spotify account. Submit RSS feed URL. Verify ownership of feed.",
    },
    "apple": {
        "name": "Apple Podcasts Connect",
        "url": "https://podcasters.apple.com/",
        "submit_url": "https://podcasters.apple.com/my-podcasts/new",
        "requirements": [
            "RSS feed must be publicly accessible",
            "Cover art: JPG/PNG, 3000x3000px, RGB color space",
            "Title, author, description required",
            "Category must be valid Apple category",
            "At least one episode with audio enclosure",
        ],
        "notes": "Requires Apple ID. Submit via podcasters.apple.com. May take 1-5 days for approval.",
    },
    "google": {
        "name": "Google Podcasts Manager",
        "url": "https://podcastsmanager.google.com/",
        "submit_url": "https://podcastsmanager.google.com/add-feed",
        "requirements": [
            "RSS feed with valid audio enclosures",
            "Cover art referenced in feed",
            "Feed must be publicly accessible",
            "Google account required",
        ],
        "notes": "Add RSS feed URL. Google may re-cache feed periodically.",
    },
    "amazon": {
        "name": "Amazon Music / Audible",
        "url": "https://www.amazon.com/podcasts",
        "submit_url": "https://podcastpublisher.amazon.com/",
        "requirements": [
            "RSS feed with audio enclosures",
            "Cover art present",
            "Valid podcast metadata",
            "At least one episode",
        ],
        "notes": "Submit via Amazon Podcast Publisher portal (Amazon account required).",
    },
    "iheartradio": {
        "name": "iHeartRadio",
        "url": "https://www.iheart.com/podcast/",
        "submit_url": "https://podcaster.iheart.com/submission",
        "requirements": [
            "RSS feed available",
            "Cover art present",
            "Active episodes",
            "Station may require direct contact for setup",
        ],
        "notes": "May require reaching out to iHeartRadio directly for onboarding.",
    },
    "pandora": {
        "name": "Pandora",
        "url": "https://www.pandora.com/podcast/",
        "submit_url": "https://www.pandora.com/podcast/submit",
        "requirements": [
            "RSS feed with audio enclosures",
            "Cover art",
            "Complete podcast info",
        ],
        "notes": "Submit through Pandora's partner portal (formerly Art19).",
    },
    "stitcher": {
        "name": "Stitcher",
        "url": "https://www.stitcher.com/",
        "submit_url": "https://partners.stitcher.com/",
        "requirements": [
            "RSS feed accessible",
            "Audio enclosures present",
            "Podcast metadata complete",
        ],
        "notes": "Stitcher was integrated into SiriusXM/Music Stitcher. May redirect to partner portal.",
    },
}


def load_config():
    """Load podcast configuration from JSON file."""
    if not CONFIG_PATH.exists():
        print(f"ERROR: Config file not found at {CONFIG_PATH}")
        print("Run this script with the config file in place.")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    """Save podcast configuration back to JSON file."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"[✓] Config saved to {CONFIG_PATH}")


def load_history():
    """Load submission history."""
    if not HISTORY_PATH.exists():
        default_history = {"platforms": {}, "last_updated": None}
        save_history(default_history)
        return default_history
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history):
    """Save submission history."""
    history["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"[✓] History saved to {HISTORY_PATH}")


def generate_rss(config):
    """Generate RSS feed from podcast configuration."""
    rss = Element("rss", version="2.0")
    rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

    channel = SubElement(rss, "channel")

    # Basic channel metadata
    SubElement(channel, "title").text = config["title"]
    SubElement(channel, "description").text = config["description"]
    SubElement(channel, "link").text = config["website"]
    SubElement(channel, "language").text = config.get("language", "en-us")
    SubElement(channel, "copyright").text = config.get("copyright", "")
    SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    # Atom link (self-referencing)
    atom_link = SubElement(channel, "atom:link")
    atom_link.set("href", config.get("rss_url", str(RSS_OUTPUT_URL)))
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    # iTunes channel metadata
    itunes_author = SubElement(channel, "itunes:author")
    itunes_author.text = config["author"]

    itunes_owner = SubElement(channel, "itunes:owner")
    SubElement(itunes_owner, "itunes:name").text = config["author"]
    SubElement(itunes_owner, "itunes:email").text = config["email"]

    itunes_summary = SubElement(channel, "itunes:summary")
    itunes_summary.text = config["description"]

    itunes_explicit = SubElement(channel, "itunes:explicit")
    itunes_explicit.text = "yes" if config.get("explicit", False) else "no"

    # Category
    categories = config.get("category", "Religion & Spirituality / Business").split(" / ")
    if len(categories) >= 1:
        cat_text = categories[0].strip()
        sub_cat_text = categories[1].strip() if len(categories) > 1 else None
        itunes_cat = SubElement(channel, "itunes:category")
        itunes_cat.set("text", cat_text)
        if sub_cat_text:
            itunes_subcat = SubElement(itunes_cat, "itunes:category")
            itunes_subcat.set("text", sub_cat_text)

    # Image
    if config.get("image_url") and not config["image_url"].startswith("PLACEHOLDER"):
        itunes_image = SubElement(channel, "itunes:image")
        itunes_image.set("href", config["image_url"])
    else:
        print("[!] Warning: No album art URL set. Add image to podcast-config.json")

    # Episodes
    episodes = config.get("episodes", [])
    if not episodes:
        print("[!] Warning: No episodes defined in config.")

    for ep in episodes:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = ep["title"]
        SubElement(item, "description").text = ep["description"]
        SubElement(item, "guid", isPermaLink="false").text = ep.get(
            "guid", hashlib.md5(ep["title"].encode()).hexdigest()
        )
        SubElement(item, "pubDate").text = ep.get(
            "pub_date", datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        )

        # iTunes episode metadata
        if "episode_number" in ep:
            itunes_ep = SubElement(item, "itunes:episode")
            itunes_ep.text = str(ep["episode_number"])
        if "season_number" in ep:
            itunes_season = SubElement(item, "itunes:season")
            itunes_season.text = str(ep["season_number"])
        if "duration" in ep:
            itunes_duration = SubElement(item, "itunes:duration")
            itunes_duration.text = str(ep["duration"])

        itunes_explicit_ep = SubElement(item, "itunes:explicit")
        itunes_explicit_ep.text = "yes" if config.get("explicit", False) else "no"

        # Enclosure (audio file)
        enclosure = SubElement(item, "enclosure")
        enclosure.set("url", ep.get("audio_url", ""))
        enclosure.set("type", "audio/mpeg")
        enclosure.set("length", str(ep.get("file_size", "0")))

    # Write RSS to file
    xml_string = tostring(rss, encoding="unicode")
    declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    full_xml = declaration + xml_string

    with open(RSS_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(full_xml)

    print(f"[✓] RSS feed written to {RSS_OUTPUT_PATH}")
    return True


def validate_rss_feed():
    """Validate the RSS feed against Spotify/Apple requirements."""
    print("\n" + "=" * 60)
    print("RSS FEED VALIDATION")
    print("=" * 60)

    issues = []
    warnings = []
    passed = []

    # Check if RSS file exists
    if not RSS_OUTPUT_PATH.exists():
        issues.append(f"RSS feed not found at {RSS_OUTPUT_PATH}. Run --generate-rss first.")
        print("\n[ISSUES FOUND]")
        for issue in issues:
            print(f"  ✗ {issue}")
        return False

    # Parse RSS
    try:
        tree = parse(RSS_OUTPUT_PATH)
        root = tree.getroot()
        channel = root.find("channel")
        if channel is None:
            issues.append("No <channel> element found in RSS feed.")
            print("\n[ISSUES FOUND]")
            for issue in issues:
                print(f"  � {issue}")
            return False
    except Exception as e:
        issues.append(f"Failed to parse XML: {e}")
        print("\n[ISSUES FOUND]")
        for issue in issues:
            print(f"  ✗ {issue}")
        return False

    # Validate required elements
    required_elements = {
        "title": None,
        "description": None,
        "link": None,
        "language": None,
        "copyright": None,
    }

    for elem_name in required_elements:
        elem = channel.find(elem_name)
        if elem is not None:
            if elem.text and elem.text.strip():
                required_elements[elem_name] = True
                passed.append(f"Required element <{elem_name}> present and valid")
            else:
                issues.append(f"Required element <{elem_name}> is empty")
        else:
            warnings.append(f"Recommended element <{elem_name}> missing")

    # Validate iTunes namespace elements
    itunes_elements = ["author", "owner", "summary", "explicit", "category", "image"]
    for itunes_elem in itunes_elements:
        elem = channel.find(f"itunes:{itunes_elem}")
        if elem is not None:
            passed.append(f"iTunes element <itunes:{itunes_elem}> present")
        else:
            warnings.append(f"iTunes element <itunes:{itunes_elem}> missing (recommended for Spotify/Apple)")

    # Check email in itunes:owner
    owner = channel.find("itunes:owner")
    if owner is not None:
        email_elem = owner.find("itunes:email")
        if email_elem is not None and email_elem.text:
            passed.append(f"Owner email present: {email_elem.text}")
        else:
            issues.append("Owner email missing (required by Spotify/Apple)")

    # Validate episodes
    items = channel.findall("item")
    if not items:
        issues.append("No episodes found. At least 1 episode required by all platforms.")
    else:
        passed.append(f"Found {len(items)} episode(s)")

        for i, item in enumerate(items, 1):
            title = item.find("title")
            if title is None or not title.text:
                issues.append(f"Episode {i}: Missing title")
            else:
                passed.append(f"Episode {i}: Title OK - {title.text[:50]}")

            enclosure = item.find("enclosure")
            if enclosure is None:
                issues.append(f"Episode {i}: Missing audio enclosure")
            else:
                enc_url = enclosure.get("url", "")
                enc_type = enclosure.get("type", "")
                if not enc_url:
                    issues.append(f"Episode {i}: Empty enclosure URL")
                elif enc_url.startswith("PLACEHOLDER") or "your-cdn" in enc_url:
                    warnings.append(f"Episode {i}: Audio URL is placeholder - replace with real URL")
                else:
                    passed.append(f"Episode {i}: Audio enclosure URL present")

                if not enc_type:
                    warnings.append(f"Episode {i}: Enclosure type not specified, defaulting to audio/mpeg")
                elif "audio" in enc_type:
                    passed.append(f"Episode {i}: Enclosure type valid: {enc_type}")
                else:
                    issues.append(f"Episode {i}: Enclosure type '{enc_type}' is not audio")

    # Print results
    if warnings:
        print("\n[WARNINGS]")
        for w in warnings:
            print(f"  ⚠ {w}")

    if passed:
        print("\n[PASSED]")
        for p in passed:
            print(f"  ✓ {p}")

    if issues:
        print("\n[ISSUES FOUND]")
        for issue in issues:
            print(f"  ✗ {issue}")
        print(f"\n✗ Validation FAILED: {len(issues)} issue(s) found.")
        return False
    else:
        print(f"\n✓ Validation PASSED: All checks passed with {len(warnings)} warning(s).")
        return True


def check_rss_accessibility():
    """Check if the RSS feed URL is accessible (if hosted online)."""
    print("\n" + "=" * 60)
    print("RSS FEED ACCESSIBILITY CHECK")
    print("=" * 60)

    config = load_config()
    rss_url = config.get("rss_url", "")

    if not rss_url or rss_url.startswith("PLACEHOLDER") or "your-domain" in rss_url:
        print(f"[!] RSS URL not configured: {rss_url}")
        print("    Update 'rss_url' in podcast-config.json with your hosted feed URL.")
        print("    Local validation is still possible.")
        return "not_configured"

    print(f"Checking: {rss_url}")
    try:
        req = urllib.request.Request(rss_url, method="GET")
        req.add_header("User-Agent", "PodcastBot/1.0")
        response = urllib.request.urlopen(req, timeout=15)
        content_type = response.headers.get("Content-Type", "")

        if response.status == 200:
            if "xml" in content_type or "rss" in content_type or "text" in content_type:
                print(f"[✓] RSS feed accessible (HTTP 200, Content-Type: {content_type})")
                return True
            else:
                print(f"[!] HTTP 200 but unexpected Content-Type: {content_type}")
                return True
        else:
            print(f"[✗] HTTP {response.status}")
            return False
    except urllib.error.HTTPError as e:
        print(f"[✗] HTTP Error {e.code}: {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"[✗] URL Error: {e.reason}")
        return False
    except Exception as e:
        print(f"[�] Error: {e}")
        return False


def generate_submit_checklist():
    """Generate a submission checklist for all platforms."""
    print("\n" + "=" * 60)
    print("PODCAST SUBMISSION CHECKLIST")
    print("=" * 60)

    config = load_config()
    history = load_history()
    rss_ok = RSS_OUTPUT_PATH.exists()

    print(f"\nPodcast: {config['title']}")
    print(f"Config: {CONFIG_PATH}")
    print(f"RSS Feed: {'Generated ✓' if rss_ok else 'Not Generated ✗'}")
    print(f"Hosted RSS URL: {config.get('rss_url', 'Not configured')}")
    print()

    for platform_id, platform in PLATFORMS.items():
        print(f"\n{'─' * 50}")
        print(f"📻 {platform['name']}")
        print(f"{'─' * 50}")
        print(f"   Platform URL: {platform['url']}")
        print(f"   Submit at: {platform['submit_url']}")

        # Check submission history
        platform_history = history.get("platforms", {}).get(platform_id, {})
        status = platform_history.get("status", "not_submitted")
        submitted_date = platform_history.get("submitted_date", None)

        status_icons = {
            "not_submitted": "[ ]",
            "submitted": "[>]",
            "approved": "[OK]",
            "rejected": "[XX]",
            "pending": "[~]",
            "needs_update": "[!]",
        }
        icon = status_icons.get(status, "[?]")
        print(f"   Status: {icon} {status.replace('_', ' ').title()}")
        if submitted_date:
            print(f"   Last submitted: {submitted_date}")

        print(f"\n   Requirements:")
        for req in platform["requirements"]:
            print(f"     • {req}")

        print(f"\n   Notes: {platform['notes']}")

        # Action items
        print(f"\n   Action Items:")
        if not rss_ok:
            print(f"     → Generate RSS feed first: python3 podcast-submit.py --generate-rss")
        if not config.get("rss_url") or "PLACEHOLDER" in config.get("rss_url", ""):
            print(f"     → Host RSS feed and update rss_url in config")
        if not config.get("image_url") or "PLACEHOLDER" in config.get("image_url", ""):
            print(f"     → Create and upload album art (3000x3000px recommended)")
        if platform_id in ["apple"] and status == "not_submitted":
            print(f"     → Ensure Apple ID is ready")
        if platform_id == "spotify" and status == "not_submitted":
            print(f"     → Ensure Spotify account is ready")

    print(f"\n{'=' * 60}")
    print("GENERAL SUBMISSION STEPS")
    print("=" * 60)
    print("""1. [ ] Finalize your podcast artwork (3000x3000 JPG or PNG, RGB)
2. [ ] Upload your audio files to a hosting service (e.g., Libsyn, Anchor, Podbean, AWS S3)
3. [ ] Update audio URLs in podcast-config.json with real URLs
4. [ ] Update image URL in podcast-config.json with real album art URL
5. [ ] Host your RSS feed and update rss_url in config
6. [x] Validate RSS:  python3 podcast-submit.py --validate
7. [x] Check accessibility: python3 podcast-submit.py --check-access
8. [ ] Submit to each platform using links above
9. [ ] Update submission status: python3 podcast-submit.py --mark-submitted <platform>""")


def mark_submitted(platform_id, status="submitted"):
    """Mark a platform as submitted."""
    if platform_id not in PLATFORMS:
        print(f"[ERROR] Unknown platform: {platform_id}")
        print(f"Available: {', '.join(PLATFORMS.keys())}")
        return

    history = load_history()
    history["platforms"][platform_id] = {
        "name": PLATFORMS[platform_id]["name"],
        "status": status,
        "submitted_date": datetime.now(timezone.utc).isoformat(),
    }
    save_history(history)
    print(f"[✓] {PLATFORMS[platform_id]['name']} marked as: {status}")


def show_status():
    """Display submission history and status."""
    print("\n" + "=" * 60)
    print("SUBMISSION STATUS OVERVIEW")
    print("=" * 60)

    config = load_config()
    history = load_history()

    print(f"\nPodcast: {config['title']}")
    print(f"RSS Feed Generated: {'Yes ✓' if RSS_OUTPUT_PATH.exists() else 'No ✗'}")
    print(f"RSS URL: {config.get('rss_url', 'Not configured')}")
    print(f"Episodes: {len(config.get('episodes', []))}")
    print(f"Last Updated: {history.get('last_updated', 'Never')}")

    print(f"\n{'Platform':<30} {'Status':<15} {'Last Submitted':<25}")
    print("─" * 70)

    for platform_id, platform in PLATFORMS.items():
        platform_history = history.get("platforms", {}).get(platform_id, {})
        status = platform_history.get("status", "not_submitted")
        submitted = platform_history.get("submitted_date", "─")
        print(f"{platform['name']:<30} {status.replace('_', ' ').title():<15} {submitted:<25}")

    # Summary
    total = len(PLATFORMS)
    submitted_count = sum(
        1 for p in history.get("platforms", {}).values()
        if p.get("status") in ["submitted", "approved", "pending"]
    )
    approved_count = sum(
        1 for p in history.get("platforms", {}).values()
        if p.get("status") == "approved"
    )

    print(f"\n{'─' * 70}")
    print(f"Progress: {submitted_count}/{total} submitted, {approved_count}/{total} approved")


def generate_sample_episodes():
    """Generate sample episodes for testing if config has none."""
    return [
        {
            "title": "Episode 1: Introduction",
            "description": "Welcome to The David Daily Show! In this first episode, I introduce myself and share what this podcast will be about — faith, entrepreneurship, and building something meaningful every single day.",
            "episode_number": 1,
            "season_number": 1,
            "duration": "00:05:30",
            "audio_url": "PLACEHOLDER_URL_TO_HOSTED_AUDIO_EP001.mp3",
            "pub_date": "Wed, 24 Jun 2026 08:00:00 GMT",
            "file_size": 5283840,
            "guid": "ep-001-introduction-2026",
        },
        {
            "title": "Episode 2: Faith in Business",
            "description": "How do you integrate your faith into your business decisions today? We discuss practical ways to lead with integrity, serve your customers, and build a company that reflects your values.",
            "episode_number": 2,
            "season_number": 1,
            "duration": "00:08:45",
            "audio_url": "PLACEHOLDER_URL_TO_HOSTED_AUDIO_EP002.mp3",
            "pub_date": "Thu Jun 2026 08:00:00 GMT",
            "file_size": 8401920,
            "guid": "ep-002-faith-business-2026",
        },
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Podcast Submission Automation for The David Daily Show",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 podcast-submit.py --generate-rss       Generate RSS feed from config
  python3 podcast-submit.py --validate           Validate RSS against requirements
  python3 podcast-submit.py --submit-checklist   Show submission checklist
  python3 podcast-submit.py --status             View submission history
  python3 podcast-submit.py --mark-submitted spotify  Mark Spotify as submitted
  python3 podcast-submit.py --all                Run all checks
        """,
    )

    parser.add_argument(
        "--generate-rss",
        action="store_true",
        help="Generate RSS feed from podcast-config.json",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate RSS feed against Spotify/Apple requirements",
    )
    parser.add_argument(
        "--submit-checklist",
        action="store_true",
        help="Generate submission checklist with platform links",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show submission history and status",
    )
    parser.add_argument(
        "--check-access",
        action="store_true",
        help="Check if RSS feed URL is accessible online",
    )
    parser.add_argument(
        "--mark-submitted",
        metavar="PLATFORM",
        help="Mark a platform as submitted (e.g., spotify, apple, google)",
    )
    parser.add_argument(
        "--add-sample-episodes",
        action="store_true",
        help="Add sample episodes to config for testing",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all operations: generate RSS, validate, check accessibility, show checklist",
    )

    args = parser.parse_args()

    # Default action if no arguments provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    if args.all:
        args.generate_rss = True
        args.validate = True
        args.check_access = True
        args.submit_checklist = True
        args.status = True

    # Ensure config exists
    if not CONFIG_PATH.exists():
        if args.generate_rss or args.all:
            print(f"Config missing at {CONFIG_PATH}. Creating sample config...")
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            sample_config = {
                "title": "The David Daily Show",
                "description": (
                    "The David Daily Show is where faith meets business. Every day, host David Goecke "
                    "brings you short, encouraging episodes designed to help entrepreneurs and believers "
                    "grow in their calling. From spiritual insights to practical business strategies, this "
                    "podcast is your daily dose of motivation to build something that matters."
                ),
                "author": "David Goecke",
                "email": "bizrunner@gmail.com",
                "website": "https://www.youtube.com/@DavidGoecke",
                "category": "Religion & Spirituality / Business",
                "subcategory": "Entrepreneurship",
                "explicit": False,
                "language": "en-us",
                "copyright": "© 2026 David Goecke",
                "image_url": "PLACEHOLDER_URL_TO_3000x3000_ARTWORK.jpg",
                "rss_url": "PLACEHOLDER_URL_TO_HOSTED_RSS_FEED.xml",
                "episodes": generate_sample_episodes(),
            }
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(sample_config, f, indent=2, ensure_ascii=False)
            print(f"[✓] Sample config created at {CONFIG_PATH}")
        else:
            print(f"ERROR: Config not found. Run with --generate-rss or --all to create one.")
            sys.exit(1)

    # Execute requested actions
    if args.generate_rss:
        print("\n" + "=" * 60)
        print("GENERATING RSS FEED")
        print("=" * 60)
        config = load_config()
        generate_rss(config)

    if args.validate:
        validate_rss_feed()

    if args.check_access:
        check_rss_accessibility()

    if args.submit_checklist:
        generate_submit_checklist()

    if args.status:
        show_status()

    if args.mark_submitted:
        mark_submitted(args.mark_submitted)

    if args.add_sample_episodes:
        config = load_config()
        config["episodes"] = generate_sample_episodes()
        save_config(config)
        print("[✓] Sample episodes added to config.")


if __name__ == "__main__":
    main()
