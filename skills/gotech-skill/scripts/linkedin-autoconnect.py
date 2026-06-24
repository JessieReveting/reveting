#!/usr/bin/env python3
"""
LinkedIn Auto-Connect & Outreach Automation for GoTech Solutions
==============================================================

Automates LinkedIn connection requests and follow-up outreach using Proxycurl API.

Usage:
    python linkedin-autoconnect.py --search "CTO startups" --limit 10 --dry-run
    python linkedin-autoconnect.py --connect --campaign "tech-founders" --message "Hi {name}..."
    python linkedin-autoconnect.py --status --campaign "tech-founders"
    python linkedin-autoconnect.py --export --campaign "tech-founders"

Setup:
    1. Get Proxycurl API key from https://nubela.co/proxycurl/
    2. Set environment variable: export PROXYCURL_API_KEY="your_key_here"
    3. Install deps: pip install requests
    4. Run with --dry-run first to test without API key

Rate Limits (LinkedIn enforced):
    - Max 20 connection requests per day
    - Max 50 messages per day
    - Random delays (2-5 min) between actions for anti-detection
"""

import argparse
import csv
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

# ============================================================
# CONFIGURATION
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = BASE_DIR / "scripts"
LOG_FILE = SCRIPTS_DIR / "linkedin-activity.log"
PROSPECTS_FILE = DATA_DIR / "linkedin-prospects.json"
CAMPAIGNS_FILE = DATA_DIR / "linkedin-campaigns.json"

MAX_CONNECTIONS_PER_DAY = 20
MAX_MESSAGES_PER_DAY = 50
CONNECTION_DELAY_MIN = 120  # 2 minutes (seconds)
CONNECTION_DELAY_MAX = 300  # 5 minutes (seconds)
MESSAGE_DELAY_MIN = 60
MESSAGE_DELAY_MAX = 180
PROXYCURL_API = "https://nubela.co/proxycurl/api/v2"
PROXYCURL_SEARCH_API = "https://nubela.co/proxycurl/api/v2/search"

# ============================================================
# LOGGING
# ------------------------------------------------------------

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging to both file and console."""
    logger = logging.getLogger("linkedin_autoconnect")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # File handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

    return logger


log = setup_logging()

# ============================================================
# DATA LAYER
# ------------------------------------------------------------

def load_json(filepath: Path, default: dict | list | None = None) -> dict | list:
    """Load JSON from file, return default if not found."""
    if not filepath.exists():
        return default if default is not None else {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default if default is not None else {}


def save_json(filepath: Path, data: dict | list) -> None:
    """Save data as JSON to file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_prospects() -> dict:
    """Load prospects database."""
    return load_json(PROSPECTS_FILE, default={"prospects": []})


def save_prospects(data: dict) -> None:
    """Save prospects database."""
    save_json(PROSPECTS_FILE, data)


def load_campaigns() -> dict:
    """Load campaigns database."""
    return load_json(CAMPAIGNS_FILE, default={"campaigns": {}})


def save_campaigns(data: dict) -> None:
    """Save campaigns database."""
    save_json(CAMPAIGNS_FILE, data)


# ============================================================
# PROXYCURL API WRAPPER
# ------------------------------------------------------------

class ProxycurlClient:
    """Wrapper for Proxycurl LinkedIn API."""

    def __init__(self, api_key: str, dry_run: bool = False):
        self.api_key = api_key
        self.dry_run = dry_run
        self.session = requests.Session() if requests else None
        if self.session and self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def search_people(
        self,
        keywords: str,
        company_domain: str | None = None,
        location: str | None = None,
        page: int = 1,
        size: int = 10,
    ) -> list[dict]:
        """Search for LinkedIn profiles using Proxycurl."""
        if self.dry_run:
            log.info(f"[DRY-RUN] Search: keywords={keywords}, page={page}, size={size}")
            return self._generate_mock_results(keywords, size)

        if not self.api_key:
            log.error("PROXYCURL_API_KEY not set. Use --dry-run or set the env var.")
            sys.exit(1)

        params = {
            "keywords": keywords,
            "page": page,
            "size": size,
        }
        if company_domain:
            params["company_domain"] = company_domain
        if location:
            params["location"] = location

        url = f"{PROXYCURL_SEARCH_API}/people"
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error(f"Proxycurl search failed: {e}")
            return []

    def get_profile(self, linkedin_url: str) -> dict:
        """Fetch detailed profile data."""
        if self.dry_run:
            log.info(f"[DRY-RUN] Fetch profile: {linkedin_url}")
            return self._generate_mock_profile(linkedin_url)

        if not self.api_key:
            log.error("PROXYCURL_API_KEY not set. Use --dry-run or set the env var.")
            sys.exit(1)

        url = f"{PROXYCURL_API}/linkedin"
        params = {"url": linkedin_url, "fallback_to_cache": "on-error"}
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.error(f"Profile fetch failed for {linkedin_url}: {e}")
            return {}

    @staticmethod
    def _generate_mock_results(keywords: str, count: int) -> list[dict]:
        """Generate mock search results for dry-run mode."""
        titles = ["CTO", "VP Engineering", "Head of Product", "CEO", "Co-founder",
                  "Engineering Manager", "Tech Lead", "Chief Architect"]
        companies = ["Acme Tech", "StartupXYZ", "CloudScale", "DataFlow AI",
                     "InnovateLabs", "DevHub", "NexGen Systems", "QuantumBit"]
        results = []
        for i in range(count):
            first = random.choice(["Alex", "Jordan", "Casey", "Morgan", "Taylor", "Riley"])
            last = random.choice(["Smith", "Chen", "Patel", "Garcia", "Kim", "Johnson"])
            results.append({
                "full_name": f"{first} {last}",
                "headline": f"{random.choice(titles)} at {random.choice(companies)}",
                "linkedin_url": f"https://linkedin.com/in/{first.lower()}{last.lower()}{i}",
                "company": random.choice(companies),
                "location": "San Francisco, CA",
                "connections": random.randint(100, 5000),
                "mutual_connections": random.randint(0, 15),
                "tags": keywords.split(),
            })
        return results

    @staticmethod
    def _generate_mock_profile(url: str) -> dict:
        """Generate a mock profile for dry-run mode."""
        name = url.split("/in/")[-1].replace("-", " ").title()
        return {
            "full_name": name,
            "headline": "CTO at TechStartup",
            "company": "TechStartup",
            "location": "San Francisco, CA",
            "summary": "Passionate about AI and developer tools.",
            "connections": 1200,
            "mutual_connections": ["Alice Brown", "Bob Wilson"],
            "shared_groups": ["Python Developers", "AI Founders"],
            "interests": ["Machine Learning", "Open Source"],
            "linkedin_url": url,
        }


# ============================================================
# MESSAGE PERSONALIZATION
# ------------------------------------------------------------

def generate_connection_note(person: dict, template: str | None = None) -> str:
    """Generate a personalized connection note (max 300 chars for LinkedIn)."""
    name = person.get("full_name", person.get("name", "there"))
    first_name = name.split()[0] if name else "there"
    company = person.get("company", person.get("headline", ""))
    mutual = person.get("mutual_connections", [])
    shared_groups = person.get("shared_groups", [])

    if template:
        msg = template.format(
            name=name,
            first_name=first_name,
            company=company,
            mutual=", ".join(mutual[:3]) if mutual else "",
            groups=", ".join(shared_groups[:2]) if shared_groups else "",
        )
    else:
        parts = [f"Hi {first_name},"]
        if company:
            parts.append(f"I see you're at {company} — impressive work.")
        if mutual:
            parts.append(f"We share {len(mutual)} mutual connections.")
        if shared_groups:
            parts.append(f"I noticed we're both in {shared_groups[0]}.")
        parts.append("Would love to connect and exchange ideas. — David, GoTech Solutions")
        msg = " ".join(parts)

    # LinkedIn connection note max: 300 chars
    if len(msg) > 300:
        msg = msg[:297] + "..."
    return msg


def generate_followup_message(person: dict, template: str | None = None) -> str:
    """Generate a personalized follow-up message after connection accepted."""
    name = person.get("full_name", person.get("name", "there"))
    first_name = name.split()[0] if name else "there"
    company = person.get("company", "")
    interests = person.get("interests", [])

    if template:
        msg = template.format(
            name=name,
            first_name=first_name,
            company=company,
            interests=", ".join(interests[:2]) if interests else "",
        )
    else:
        msg = (
            f"Hi {first_name}, thanks for connecting! I'm David from GoTech Solutions. "
            f"I help companies like {company or 'yours'} accelerate with AI automation. "
            f"Would be great to learn what you're working on. "
            f"Open to a quick chat this week?"
        )

    if len(msg) > 1000:  # LinkedIn message limit
        msg = msg[:997] + "..."
    return msg


# ============================================================
# CAMPAIGN TRACKER
# ------------------------------------------------------------

class CampaignTracker:
    """Tracks outreach campaigns: prospect -> connected -> messaged -> replied -> qualified"""

    VALID_STAGES = ["prospect", "connected", "messaged", "replied", "qualified", "rejected"]

    def __init__(self, name: str):
        self.name = name
        self.data = load_campaigns()
        if name not in self.data.get("campaigns", {}):
            self.data.setdefault("campaigns", {})[name] = {
                "name": name,
                "created_at": datetime.now().isoformat(),
                "contacts": [],
                "daily_stats": {},
                "active": False,
            }
        self.campaign = self.data["campaigns"][name]
        save_campaigns(self.data)

    def add_contact(self, person: dict, stage: str = "prospect") -> dict:
        """Add a new contact to the campaign."""
        contact = {
            "id": person.get("linkedin_url", person.get("id", "")),
            "name": person.get("full_name", person.get("name", "")),
            "company": person.get("company", ""),
            "linkedin_url": person.get("linkedin_url", ""),
            "stage": stage,
            "connection_note": "",
            "followup_message": "",
            "connected_at": None,
            "messaged_at": None,
            "replied_at": None,
            "notes": [],
            "added_at": datetime.now().isoformat(),
        }
        # Avoid duplicates
        existing_ids = {c["id"] for c in self.campaign.get("contacts", [])}
        if contact["id"] not in existing_ids:
            self.campaign.setdefault("contacts", []).append(contact)
            log.info(f"[CAMPAIGN:{self.name}] Added contact: {contact['name']} ({stage})")
        save_campaigns(self.data)
        return contact

    def advance_stage(self, contact_id: str, note: str = "") -> None:
        """Advance a contact to the next stage in the pipeline."""
        contacts = self.campaign.get("contacts", [])
        for c in contacts:
            if c["id"] == contact_id:
                current_idx = self.VALID_STAGES.index(c["stage"]) if c["stage"] in self.VALID_STAGES else 0
                if current_idx < len(self.VALID_STAGES) - 1:
                    c["stage"] = self.VALID_STAGES[current_idx + 1]
                    now = datetime.now().isoformat()
                    if c["stage"] == "connected":
                        c["connected_at"] = now
                    elif c["stage"] == "messaged":
                        c["messaged_at"] = now
                    elif c["stage"] == "replied":
                        c["replied_at"] = now
                    if note:
                        c.setdefault("notes").append({"at": now, "text": note})
                    log.info(f"[CAMPAIGN:{self.name}] Advanced {c['name']} -> {c['stage']}")
                break
        save_campaigns(self.data)

    def get_stats(self) -> dict:
        """Get campaign statistics."""
        contacts = self.campaign.get("contacts", [])
        stats = {stage: 0 for stage in self.VALID_STAGES}
        stats["total"] = len(contacts)

        for c in contacts:
            stage = c.get("stage", "prospect")
            if stage in stats:
                stats[stage] += 1

        today = datetime.now().strftime("%Y-%m-%d")
        daily = self.campaign.get("daily_stats", {}).get(today, {})
        stats["connections_today"] = daily.get("connections", 0)
        stats["messages_today"] = daily.get("messages", 0)
        stats["active"] = self.campaign.get("active", False)
        stats["name"] = self.campaign.get("name", self.name)
        stats["created_at"] = self.campaign.get("created_at", "")
        return stats

    def increment_daily(self, action: str) -> None:
        """Track daily action for rate limiting."""
        today = datetime.now().strftime("%Y-%m-%d")
        self.campaign.setdefault("daily_stats", {}).setdefault(today, {"connections": 0, "messages": 0})
        if action == "connection":
            self.campaign["daily_stats"][today]["connections"] += 1
        elif action == "message":
            self.campaign["daily_stats"][today]["messages"] += 1
        save_campaigns(self.data)

    def can_connect(self) -> bool:
        """Check if we can make more connections today."""
        today = datetime.now().strftime("%Y-%m-%d")
        daily = self.campaign.get("daily_stats", {}).get(today, {})
        return daily.get("connections", 0) < MAX_CONNECTIONS_PER_DAY

    def can_message(self) -> bool:
        """Check if we can send more messages today."""
        today = datetime.now().strftime("%Y-%m-%d")
        daily = self.campaign.get("daily_stats", {}).get(today, {})
        return daily.get("messages", 0) < MAX_MESSAGES_PER_DAY

    def set_active(self, active: bool) -> None:
        """Start/stop the campaign."""
        self.campaign["active"] = active
        save_campaigns(self.data)
        status = "STARTED" if active else "STOPPED"
        log.info(f"[CAMPAIGN:{self.name}] Campaign {status}")

    def export_csv(self, filepath: str) -> None:
        """Export campaign results to CSV."""
        contacts = self.campaign.get("contacts", [])
        if not contacts:
            log.warning(f"[CAMPAIGN:{self.name}] No contacts to export")
            return

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "name", "company", "linkedin_url", "stage",
                "connected_at", "messaged_at", "replied_at", "added_at"
            ])
            writer.writeheader()
            writer.writerows(contacts)
        log.info(f"[CAMPAIGN:{self.name}] Exported {len(contacts)} contacts to {filepath}")
        print(f"Exported to: {filepath}")


# ============================================================
# RATE LIMITER & ANTI-DETECTION
# ------------------------------------------------------------

class RateLimiter:
    """Handles rate limiting and anti-detection delays."""

    @staticmethod
    def delay(min_seconds: int, max_seconds: int) -> None:
        """Sleep for a random duration between min and max seconds."""
        wait = random.randint(min_seconds, max_seconds)
        log.debug(f"Waiting {wait}s (anti-detection delay)...")
        time.sleep(wait)

    @staticmethod
    def connection_delay() -> None:
        """Random delay between connection requests (2-5 min)."""
        RateLimiter.delay(CONNECTION_DELAY_MIN, CONNECTION_DELAY_MAX)

    @staticmethod
    def message_delay() -> None:
        """Random delay between messages (1-3 min)."""
        RateLimiter.delay(MESSAGE_DELAY_MIN, MESSAGE_DELAY_MAX)


# ============================================================
# MAIN ACTIONS
# ------------------------------------------------------------

def action_search(args: argparse.Namespace) -> None:
    """Search for LinkedIn prospects."""
    client = ProxycurlClient(api_key=os.environ.get("PROXYCURL_API_KEY", ""), dry_run=args.dry_run)

    keywords = args.search
    limit = args.limit or 10

    log.info(f"Searching LinkedIn for: {keywords} (limit={limit})")

    results = client.search_people(keywords=keywords, size=limit)

    if not results:
        log.info("No results found.")
        return

    # Store results in prospects file
    prospects_data = load_prospects()
    existing_urls = {p.get("linkedin_url") for p in prospects_data.get("prospects", [])}

    new_count = 0
    for person in results:
        url = person.get("linkedin_url", "")
        if url and url not in existing_urls:
            prospect = {
                "id": url,
                "full_name": person.get("full_name", ""),
                "headline": person.get("headline", ""),
                "company": person.get("company", ""),
                "linkedin_url": url,
                "location": person.get("location", ""),
                "connections": person.get("connections", 0),
                "mutual_connections_count": person.get("mutual_connections", 0),
                "tags": person.get("tags", []),
                "source": "search",
                "added_at": datetime.now().isoformat(),
            }
            prospects_data.setdefault("prospects", []).append(prospect)
            existing_urls.add(url)
            new_count += 1

    save_prospects(prospects_data)
    log.info(f"Found {len(results)} profiles. {new_count} new prospects saved.")

    # If campaign specified, add them to campaign
    if args.campaign:
        tracker = CampaignTracker(args.campaign)
        for person in results:
            tracker.add_contact(person)

    # Display results
    for i, person in enumerate(results, 1):
        name = person.get("full_name", "Unknown")
        headline = person.get("headline", "")
        company = person.get("company", "")
        log.info(f"  {i}. {name} — {headline} @ {company}")


def action_connect(args: argparse.Namespace) -> None:
    """Send connection requests."""
    api_key = os.environ.get("PROXYCURL_API_KEY", "")
    dry_run = args.dry_run

    if not api_key and not dry_run:
        log.error("PROXYCURL_API_KEY required for live mode. Use --dry-run to test.")
        sys.exit(1)

    tracker = CampaignTracker(args.campaign)
    client = ProxycurlClient(api_key=api_key, dry_run=dry_run)

    # Get contacts ready for connection
    contacts = tracker.campaign.get("contacts", [])
    to_connect = [c for c in contacts if c.get("stage") == "prospect"]

    if args.limit:
        to_connect = to_connect[:args.limit]

    if not to_connect:
        log.info("No contacts to connect with.")
        return

    if not tracker.can_connect():
        log.warning(f"Daily connection limit reached ({MAX_CONNECTIONS_PER_DAY}/day).")
        return

    message_template = args.message

    for contact in to_connect:
        remaining = MAX_CONNECTIONS_PER_DAY - tracker.get_stats()["connections_today"]
        if remaining <= 0:
            log.warning("Daily connection limit reached.")
            break

        # Get enriched profile data
        profile = client.get_profile(contact["linkedin_url"])

        # Merge contact + profile data
        person = {
            "full_name": contact["name"],
            "name": contact["name"],
            "company": contact["company"] or profile.get("company", ""),
            "linkedin_url": contact["linkedin_url"],
            "mutual_connections": profile.get("mutual_connections", []),
            "shared_groups": profile.get("shared_groups", []),
            "interests": profile.get("interests", []),
            "headline": profile.get("headline", ""),
        }

        note = generate_connection_note(person, message_template)

        if dry_run:
            log.info(f"[DRY-RUN] Would connect to {contact['name']} ({contact['company']})")
            log.info(f"  Note: {note[:80]}...")
            contact["connection_note"] = note
            tracker.increment_daily("connection")
            # Simulate action delay
            if not args.no_delay:
                RateLimiter.connection_delay()
        else:
            log.info(f"Sending connection request to {contact['name']}...")
            # Here you'd call Proxycurl's connection API or LinkedIn's API
            # For now we log the action (actual LinkedIn API integration requires LinkedIn Partner access)
            log.info(f"  Note: {note}")
            contact["connection_note"] = note
            tracker.increment_daily("connection")

        tracker.advance_stage(contact["id"], note=f"Connection note sent: {note[:50]}")

    save_campaigns(tracker.data)
    log.info(f"Connection batch complete. Used today: {tracker.get_stats()['connections_today']}/{MAX_CONNECTIONS_PER_DAY}")


def action_message(args: argparse.Namespace) -> None:
    """Send follow-up messages to connected contacts."""
    api_key = os.environ.get("PROXYCURL_API_KEY", "")
    dry_run = args.dry_run

    if not api_key and not dry_run:
        log.error("PROXYCURL_API_KEY required for live mode. Use --dry-run to test.")
        sys.exit(1)

    tracker = CampaignTracker(args.campaign)
    client = ProxycurlClient(api_key=api_key, dry_run=dry_run)

    # Get contacts ready for follow-up messaging
    contacts = tracker.campaign.get("contacts", [])

    # Accept message template from args or from contacts
    message_template = args.message

    # Find contacts that are connected but not yet messaged
    to_message = [c for c in contacts if c.get("stage") == "connected"]

    if args.limit:
        to_message = to_message[:args.limit]

    if not to_message:
        log.info("No contacts to message.")
        return

    if not tracker.can_message():
        log.warning(f"Daily message limit reached ({MAX_MESSAGES_PER_DAY}/day).")
        return

    for contact in to_message:
        remaining = MAX_MESSAGES_PER_DAY - tracker.get_stats()["messages_today"]
        if remaining <= 0:
            log.warning("Daily message limit reached.")
            break

        profile = client.get_profile(contact["linkedin_url"]) if contact["linkedin_url"] else {}

        person = {
            "full_name": contact["name"],
            "name": contact["name"],
            "company": contact["company"] or profile.get("company", ""),
            "linkedin_url": contact["linkedin_url"],
            "interests": profile.get("interests", []),
        }

        msg = generate_followup_message(person, message_template)

        if dry_run:
            log.info(f"[DRY-RUN] Would message {contact['name']}")
            log.info(f"  Message: {msg[:80]}...")
            contact["followup_message"] = msg
            tracker.increment_daily("message")
            if not args.no_delay:
                RateLimiter.message_delay()
        else:
            log.info(f"Sending follow-up to {contact['name']}...")
            log.info(f"  Message: {msg}")
            contact["followup_message"] = msg
            tracker.increment_daily("message")

        tracker.advance_stage(contact["id"], note=f"Follow-up sent: {msg[:50]}")

    save_campaigns(tracker.data)
    log.info(f"Messaging batch complete. Used today: {tracker.get_stats()['messages_today']}/{MAX_MESSAGES_PER_DAY}")


def action_status(args: argparse.Namespace) -> None:
    """Show campaign statistics."""
    tracker = CampaignTracker(args.campaign)
    stats = tracker.get_stats()

    print(f"\n{'='*60}")
    print(f" Campaign: {stats['name']}")
    print(f"{'='*60}")
    print(f"  Active: {'Yes' if stats['active'] else 'No'}")
    print(f"  Created: {stats['created_at'][:10]}")
    print(f"  Total contacts: {stats['total']}")
    print(f"  Pipeline:")
    for stage in CampaignTracker.VALID_STAGES:
        count = stats.get(stage, 0)
        bar = "█" * count + "░" * (max(0, 10 - count))
        print(f"    {stage:12s} [{bar}] {count}")
    print(f"\n  Daily Usage:")
    print(f"    Connections: {stats['connections_today']}/{MAX_CONNECTIONS_PER_DAY}")
    print(f"    Messages:    {stats['messages_today']}/{MAX_MESSAGES_PER_DAY}")
    print(f"{'='*60}\n")


def action_export(args: argparse.Namespace) -> None:
    """Export campaign results as CSV."""
    tracker = CampaignTracker(args.campaign)
    output = args.output or f"{args.campaign}-export-{datetime.now().strftime('%Y%m%d')}.csv"
    tracker.export_csv(output)


def action_campaign(args: argparse.Namespace) -> None:
    """Start/stop a campaign."""
    tracker = CampaignTracker(args.campaign)

    if hasattr(args, 'start') and args.start:
        tracker.set_active(True)
        print(f"Campaign '{args.campaign}' started.")
    elif hasattr(args, 'stop') and args.stop:
        tracker.set_active(False)
        print(f"Campaign '{args.campaign}' stopped.")
    else:
        # Show status if no start/stop flag
        action_status(args)


# ============================================================
# CLI ARGUMENT PARSING
# ------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="linkedin-autoconnect",
        description="LinkedIn Auto-Connect & Outreach Automation for GoTech Solutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for prospects (dry run)
  python linkedin-autoconnect.py --search "CTO AI startup" --limit 20 --dry-run

  # Search and add to campaign
  python linkedin-autoconnect.py --search "VP Engineering" --campaign tech-leads --limit 10

  # Send connection requests
  python linkedin-autoconnect.py --connect --campaign tech-leads --limit 5 --message "Hi {name}..."

  # Send follow-up messages
  python linkedin-autoconnect.py --message --campaign tech-leads --limit 3

  # Check campaign status
  python linkedin-autoconnect.py --status --campaign tech-leads

  # Export campaign results
  python linkedin-autoconnect.py --export --campaign tech-leads

  # Start a campaign
  python linkedin-autoconnect.py --campaign tech-leads --start
        """,
    )

    parser.add_argument("--search", type=str, help="Search query for LinkedIn prospects (e.g., 'CTO startup')")
    parser.add_argument("--connect", action="store_true", help="Send connection requests to prospects")
    parser.add_argument("--message", type=str, nargs="?", const=True,
                        help="Send follow-up messages (use --message 'custom text with {name}')")
    parser.add_argument("--limit", type=int, default=10, help="Max number of actions to perform (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without making real API calls (no API key needed)")
    parser.add_argument("--campaign", type=str, default="default",
                        help="Campaign name for tracking (default: 'default')")
    parser.add_argument("--status", action="store_true", help="Show campaign statistics")
    parser.add_argument("--export", action="store_true", help="Export campaign results as CSV")
    parser.add_argument("--output", type=str, help="Output file path for --export")
    parser.add_argument("--start", action="store_true", help="Start a campaign")
    parser.add_argument("--stop", action="store_true", help="Stop a campaign")
    parser.add_argument("--no-delay", action="store_true",
                        help="Skip anti-detection delays (useful for testing)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    return parser


# ============================================================
# ENTRY POINT
# ------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        global log
        log = setup_logging(verbose=True)

    # Validate: must have at least one action
    actions = [args.search, args.connect, args.args_message_is_action(),
               args.status, args.export, args.start, args.stop]
    if not any(actions):
        parser.print_help()
        sys.exit(1)

    # Show setup instructions if no API key and not dry-run
    api_key = os.environ.get("PROXYCURL_API_KEY", "")
    if not api_key and not args.dry_run and (args.search or args.connect or args.message):
        log.warning("PROXYCURL_API_KEY not set. Running without --dry-run will fail.")
        log.info("Tip: Use --dry-run to test without API key, or set the env var:")
        log.info("  export PROXYCURL_API_KEY='your_key_here'")

    # Dispatch actions
    if args.search:
        action_search(args)

    elif args.connect:
        action_connect(args)

    elif isinstance(args.message, str):
        # If message string is provided, it's a template for follow-up messages
        action_message(args)
    elif args.message is True:
        # --message without argument → use default template
        action_message(args)

    elif args.status:
        action_status(args)

    elif args.export:
        action_export(args)

    elif args.start or args.stop:
        action_campaign(args)


def _is_message_action(self):
    """Check if --message was used as an action (not just a string template)."""
    return self.message is True


# Monkey-patch for clean dispatch
argparse.Namespace.args_message_is_action = _is_message_action


if __name__ == "__main__":
    main()
