#!/usr/bin/env python3
"""
Show Launch Automation — Main Orchestrator
Takes a GHL appointment record and generates all show assets.

Usage:
  python3 scripts/show-launch.py --input appointment.json --dry-run
  python3 scripts/show-launch.py --input appointment.json --execute
  python3 scripts/show-launch.py --ghl-pull --dry-run
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────
GHL_API_BASE = "https://services.leadconnectorhq.com"
GHL_TOKEN = os.environ.get("GHL_TOKEN", "[REDACTED_SECRET]")
GHL_LOCATION_ID = os.environ.get("GHL_LOCATION_ID", "fcO3237HZyeXNe9O8")

REPO_ROOT = Path(__file__).parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "shows.json"
EXAMPLES_DIR = REPO_ROOT / "examples"

# ── GHL API ──────────────────────────────────────────────────
def ghl_headers():
    return {
        "Authorization": f"Bearer {GHL_TOKEN}",
        "Content-Type": "application/json",
        "Version": "2021-07-28",
    }

def ghl_get(path, params=None):
    url = f"{GHL_API_BASE}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url += f"?{qs}"
    req = urllib.request.Request(url, headers=ghl_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ⚠️ GHL API error {e.code}: {body[:300]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ⚠️ Request failed: {e}", file=sys.stderr)
        return None

def pull_appointments(start_date=None, end_date=None):
    """Pull appointments from GHL calendar."""
    if not start_date:
        start_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00.000Z")
    if not end_date:
        end_date = (datetime.now(timezone.utc) + timedelta(days=90)).strftime("%Y-%m-%dT23:59:59.999Z")

    print(f"\n📋 Pulling appointments from GHL...")
    print(f"   Range: {start_date[:10]} → {end_date[:10]}")

    data = ghl_get("/calendars/events", {
        "locationId": GHL_LOCATION_ID,
        "startTime": start_date,
        "endTime": end_date,
    })

    if not data:
        print("  ❌ Failed to fetch appointments")
        return []

    events = data.get("events", []) if isinstance(data, dict) else data
    print(f"  ✅ Found {len(events)} appointment(s)")
    return events

# ── Appointment Parser ───────────────────────────────────────
def parse_appointment(raw):
    """Parse a raw GHL event into a standardized appointment dict."""
    # Handle both raw GHL API format and our example JSON format
    if "appointment" in raw:
        raw = raw["appointment"]

    guest = raw.get("guest", raw.get("contact", {}))
    start = raw.get("start_time", raw.get("startTime", ""))
    end = raw.get("end_time", raw.get("endTime", ""))

    # Parse topics
    topics = raw.get("topics", [])
    if not topics:
        description = raw.get("description", raw.get("calendar_description", ""))
        for line in description.split("\n"):
            if line.strip().startswith(("1.", "2.", "3.", "•", "-")):
                topics.append(line.strip().lstrip("123.•- "))
    if not topics:
        topics = ["Topic 1", "Topic 2", "Topic 3"]

    first_name = guest.get("first_name", guest.get("firstName", ""))
    last_name = guest.get("last_name", guest.get("lastName", ""))

    return {
        "guest_name": f"{first_name} {last_name}".strip() or raw.get("event_name", "Guest"),
        "guest_first_name": first_name,
        "guest_last_name": last_name,
        "guest_email": guest.get("email", ""),
        "guest_phone": guest.get("phone", ""),
        "guest_linkedin": guest.get("linkedin_url", guest.get("linkedinUrl", "")),
        "show_name": raw.get("show_name", raw.get("calendar", "The David Daily Show")),
        "episode_title": raw.get("episode_title", raw.get("title", "").replace("The David Daily Show with ", "").strip()),
        "date": raw.get("date", start[:10] if start else ""),
        "start_time": start,
        "end_time": end,
        "topics": topics[:3],
        "status": raw.get("status", "confirmed"),
        "location": raw.get("location", "StreamYard URL TBD"),
        "description": raw.get("description", ""),
    }

# ── Asset Generators ─────────────────────────────────────────
def generate_banner_thumbnail(appointment, output_dir):
    """Generate a LinkedIn event banner using Pillow (no Canva needed)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  ⚠️ Pillow not installed. Run: pip3 install Pillow")
        return None

    show_name = appointment.get("show_name", "The David Daily Show")
    guest_name = appointment.get("guest_name", "Guest")
    episode_title = appointment.get("episode_title", "")
    date_str = appointment.get("date", "")
    topics = appointment.get("topics", [])

    # LinkedIn event banner: 1920×1080
    img = Image.new("RGB", (1920, 1080), color=(13, 27, 62))
    draw = ImageDraw.Draw(img)

    # Gold accent bar at top
    draw.rectangle([0, 0, 1920, 8], fill=(245, 166, 35))

    # Gold accent bar at bottom
    draw.rectangle([0, 1072, 1920, 1080], fill=(245, 166, 35))

    # Try to load fonts, fall back to default
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
        name_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        topic_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except (OSError, IOError):
        title_font = ImageFont.load_default()
        name_font = ImageFont.load_default()
        topic_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Show name (top area)
    draw.text((100, 60), show_name.upper(), fill=(245, 166, 35), font=title_font)

    # Episode title
    draw.text((100, 200), episode_title, fill=(255, 255, 255), font=name_font)

    # Guest name
    draw.text((100, 320), f"with {guest_name}", fill=(245, 166, 35), font=name_font)

    # Date
    draw.text((100, 440), date_str, fill=(138, 155, 181), font=small_font)

    # Topics
    y = 520
    for i, topic in enumerate(topics):
        draw.text((120, y + i * 55), f"• {topic}", fill=(245, 255, 255), font=topic_font)

    # Brand mark (bottom right)
    draw.text((1500, 980), "gotech.ai", fill=(138, 155, 181), font=small_font)

    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "banner.png"
    img.save(str(output_path), "PNG")
    print(f"  ✅ Banner saved: {output_path}")
    return str(output_path)

def generate_ical_event(appointment, output_dir):
    """Generate a .ics calendar event."""
    try:
        from icalendar import Calendar, Event, vText, vDatetime
    except ImportError:
        print("  ⚠️ icalendar not installed. Run: pip3 install icalendar")
        return None

    cal = Calendar()
    cal.add("prodid", "-//Go Technology Solutions//Show Launch//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    event = Event()
    event.add("summary", f"{appointment['show_name']} with {appointment['guest_name']}")
    event.add("description", (
        f"Episode: {appointment.get('episode_title', '')}\n"
        f"Guest: {appointment['guest_name']}\n"
        f"Topics: {', '.join(appointment.get('topics', []))}\n\n"
        f"Logistics: Login 15 min early. Go live at {appointment.get('start_time', '')} ET"
    ))
    event.add("location", vText("StreamYard URL TBD"))
    event.add("status", "CONFIRMED")

    # Parse date/time
    date_str = appointment.get("date", "")
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            event.add("dtstart", dt.replace(hour=10, minute=45))
            event.add("dtend", dt.replace(hour=12, minute=0))
        except ValueError:
            pass

    event["uid"] = f"{appointment.get('guest_last_name', 'guest').lower()}-{date_str}@reveting.com"
    cal.add_component(event)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "episode.ics"
    with open(output_path, "wb") as f:
        f.write(cal.to_ical())
    print(f"  ✅ Calendar event saved: {output_path}")
    return str(output_path)

def generate_email_sequence(appointment, output_dir):
    """Generate all email templates with variables filled."""
    emails = {}

    # Guest Outreach Touch 1
    emails["outreach-1"] = (
        f"Subject: {appointment['guest_first_name']}, quick question about {appointment['topics'][0] if appointment.get('topics') else 'your expertise'}\n\n"
        f"Hi {appointment['guest_first_name']},\n\n"
        f"I host {appointment['show_name']} — a weekly LinkedIn Live where technology leaders share practical frameworks.\n\n"
        f"30-minute conversation, 3-5 talking points you control, and I'll send you 3 clips afterward.\n\n"
        f"Interested? Here's the booking link: [BOOKING_FORM_LINK]\n\n"
        f"David Goecke\nFounder, Go Technology Solutions"
    )

    # Confirmation
    emails["confirmation"] = (
        f"Subject: You're confirmed for {appointment['show_name']} — here's what's next\n\n"
        f"Hi {appointment['guest_first_name']},\n\n"
        f"You're confirmed for {appointment['show_name']} on {appointment.get('date', '')} at {appointment.get('start_time', '')} ET.\n\n"
        f"Prep checklist:\n"
        f"✓ StreamYard link: [STREAMYARD_GUEST_LINK]\n"
        f"✓ Browser: Chrome or Firefox\n"
        f"✓ Equipment: Headset, 720p+ webcam\n\n"
        f"David Goecke"
    )

    # Pre-show T-7
    emails["preshow-1"] = (
        f"Subject: Pre-show briefing for your {appointment['show_name']} episode\n\n"
        f"Hi {appointment['guest_first_name']},\n\n"
        f"Your episode is in 7 days — {appointment.get('date', '')} at {appointment.get('start_time', '')} ET.\n\n"
        f"Book your 15-minute briefing: [BRIEFING_CALL_LINK]\n\n"
        f"David Goecke"
    )

    # Pre-show T-3
    topics_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(appointment.get("topics", [])))
    emails["preshow-2"] = (
        f"Subject: 3 days to your {appointment['show_name']} episode — quick read\n\n"
        f"Hi {appointment['guest_first_name']},\n\n"
        f"Your episode is in 3 days.\n\n"
        f"YOUR EPISODE\n"
        f"Title: {appointment.get('episode_title', '')}\n"
        f"Date: {appointment.get('date', '')} at {appointment.get('start_time', '')} ET\n"
        f"StreamYard: [STREAMYARD_GUEST_LINK]\n\n"
        f"TOPICS:\n{topics_list}\n\n"
        f"David Goecke"
    )

    # Post-show clip delivery
    emails["postshow-clips"] = (
        f"Subject: Your 3 clips from {appointment['show_name']} — ready to post\n\n"
        f"Hi {appointment['guest_first_name']},\n\n"
        f"Your 3 clips are ready!\n\n"
        f"CLIP 1: [CLIP_1_LINK]\n"
        f"CLIP 2: [CLIP_2_LINK]\n"
        f"CLIP 3: [CLIP_3_LINK]\n\n"
        f"TAG: @DavidGoecke | @gotechai\n\n"
        f"David Goecke"
    )

    # Save all emails
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in emails.items():
        path = output_dir / f"{name}.md"
        path.write_text(content)
        print(f"  ✅ Email saved: {path}")

    return emails

# ── Main Pipeline ────────────────────────────────────────────
def launch_show(appointment, dry_run=True):
    """Run the full show launch pipeline."""
    guest_name = appointment.get("guest_name", "Guest")
    show_name = appointment.get("show_name", "The David Daily Show")
    date_str = appointment.get("date", "unknown")

    print(f"\n{'='*60}")
    print(f"  SHOW LAUNCH: {show_name}")
    print(f"  Guest: {guest_name}")
    print(f"  Date: {date_str}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"{'='*60}")

    safe_name = guest_name.lower().replace(" ", "-")
    output_dir = REPO_ROOT / "assets" / safe_name

    if dry_run:
        print(f"\n  📋 Would generate:")
        print(f"     • Banner image → {output_dir}/banner.png")
        print(f"     • Calendar event → {output_dir}/episode.ics")
        print(f"     • Email sequence → {output_dir}/emails/ (5 emails)")
        print(f"     • PPTX deck → {output_dir}/episode.pptx")
        print(f"\n  ℹ️  Run with --execute to actually generate assets")
        return

    # Step 1: Banner
    print(f"\n  🎨 Generating banner...")
    generate_banner_thumbnail(appointment, output_dir)

    # Step 2: Calendar event
    print(f"\n  📅 Generating calendar event...")
    generate_ical_event(appointment, output_dir)

    # Step 3: Email sequence
    print(f"\n  📧 Generating email sequence...")
    generate_email_sequence(appointment, output_dir / "emails")

    # Step 4: PPTX
    print(f"\n  📊 Generating PPTX deck...")
    print(f"     Run: python3 presentations/reveting-show-flow.py --guest \"{guest_name}\"")

    print(f"\n  ✅ All assets generated in: {output_dir}")

# ── CLI ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Show Launch Automation")
    parser.add_argument("--input", "-i", help="Path to GHL appointment JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no changes")
    parser.add_argument("--execute", action="store_true", help="Actually generate assets")
    parser.add_argument("--ghl-pull", action="store_true", help="Pull appointments from GHL API")
    parser.add_argument("--days-ahead", type=int, default=90, help="How many days ahead to pull")
    args = parser.parse_args()

    dry_run = not args.execute

    if args.ghl_pull:
        events = pull_appointments()
        if not events:
            print("  No appointments found.")
            return
        for evt in events:
            appt = parse_appointment(evt)
            launch_show(appt, dry_run=dry_run)
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"  ❌ File not found: {input_path}")
            sys.exit(1)
        with open(input_path) as f:
            data = json.load(f)
        # Handle both raw appointment and wrapped {"appointment": {...}}
        appointment = data.get("appointment", data)
        launch_show(appointment, dry_run=dry_run)
    else:
        # Default: use the Daniel Burrus example
        example_path = EXAMPLES_DIR / "appointments" / "daniel-burrus.json"
        if example_path.exists():
            with open(example_path) as f:
                data = json.load(f)
            appointment = data.get("appointment", data)
            launch_show(appointment, dry_run=dry_run)
        else:
            print("  ❌ No input file specified. Use --input or --ghl-pull")
            sys.exit(1)

if __name__ == "__main__":
    main()
