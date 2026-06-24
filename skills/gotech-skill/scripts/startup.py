#!/usr/bin/env python3
"""
startup.py - Go Tech Command Center Aggregator
Pulls real data from all email accounts, calendars, AI tools, cloud storage,
and recent files. Outputs a JSON summary for dashboard consumption.

Usage:
    python3 startup.py              # Full run, outputs JSON to stdout
    python3 startup.py --summary    # Human-readable summary to stdout
    python3 startup.py --json       # JSON output (default)
    python3 startup.py --save       # Save to startup/data/latest.json

Requirements:
    - dcli (Dashlane CLI) installed and authenticated
    - Python 3.10+ stdlib only (no pip packages)
    - macOS (uses system tools like mdfind, diskutil)
"""

import json
import subprocess
import sys
import os
import re
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────

HOME = Path.home()
STARTUP_DIR = HOME / "Documents" / "GoTechSolutions" / "startup"
EXPORTS_DIR = STARTUP_DIR / "exports"
DATA_DIR = STARTUP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DAYS_BACK = 7
MAX_EMAILS_PER_ACCOUNT = 50

# Email accounts configuration
# Provider: "gmail" = Google Workspace, "outlook" = Office 365
EMAIL_ACCOUNTS = [
    {"email": "david@gotech.ai",        "provider": "outlook", "label": "GoTech"},
    {"email": "davidgoecke@outlook.com","provider": "outlook", "label": "Outlook Personal"},
    {"email": "bizrunner@gmail.com",    "provider": "gmail",   "label": "BizRunner"},
    {"email": "david@reveting.com",     "provider": "gmail",   "label": "Reveting"},
    {"email": "ea@reveting.com",        "provider": "gmail",   "label": "Reveting EA"},
    {"email": "ww@reveting.com",        "provider": "gmail",   "label": "Reveting WW"},
    {"email": "david.goecke@grabtv.com","provider": "gmail",   "label": "GrabTV"},
    {"email": "david.goecke@desetinychurch.tv", "provider": "gmail", "label": "Destiny Church"},
]

# Google accounts that have calendar access
GOOGLE_CALENDAR_ACCOUNTS = [
    "bizrunner@gmail.com",
    "david@reveting.com",
    "david.goecke@grabtv.com",
    "david.goecke@desetinychurch.tv",
]

# Cloud storage paths to check
CLOUD_PATHS = {
    "Google Drive": HOME / "Library" / "CloudStorage" / "GoogleDrive",
    "OneDrive": HOME / "Library" / "CloudStorage" / "OneDrive",
    "iCloud": HOME / "Library" / "Mobile Documents" / "com~apple~CloudDocs",
}

# DATA TAXI thumbdrive
DATA_TAXI_NAMES = ["DATA TAXI", "DATA_TAXI ", "DATATAXI"]
REVETING_VIDEO_SOURCE = HOME / "Library" / "CloudStorage" / "GoogleDrive" / "Reveting Shared"

# ─── Helpers ─────────────────────────────────────────────────────────────────

def utcnow():
    return datetime.now(timezone.utc)

def iso_ts(dt=None):
    if dt is None:
        dt = utcnow()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def run(cmd, timeout=30):
    """Run a shell command, return (stdout, stderr, returncode)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1
    except Exception as e:
        return "", str(e), 1

def dashlane_get(login_email):
    """Fetch a password from Dashlane by login email. Returns password or None."""
    # Try by email/login match
    stdout, stderr, rc = run(f'dcli password --login "{login_email}" --output json 2>/dev/null', timeout=15)
    if rc == 0 and stdout:
        try:
            data = json.loads(stdout)
            if isinstance(data, list) and data:
                return data[0].get("password")
            elif isinstance(data, dict):
                return data.get("password")
        except json.JSONDecodeError:
            pass
    # Fallback: try by title
    stdout, stderr, rc = run(f'dcli password "{login_email}" --output json 2>/dev/null', timeout=15)
    if rc == 0 and stdout:
        try:
            data = json.loads(stdout)
            if isinstance(data, list) and data:
                return data[0].get("password")
            elif isinstance(data, dict):
                return data.get("password")
        except json.JSONDecodeError:
            pass
    return None

def dashlane_authenticated():
    """Check if dcli is logged in."""
    stdout, _, rc = run("dcli status 2>/dev/null")
    return rc == 0 and "Logged in: yes" in stdout

# ─── Email Connectors ────────────────────────────────────────────────────────

def connect_gmail_imap(email_addr, password):
    """Connect to Gmail via IMAP with App Password."""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_addr, password)
        return mail
    except Exception as e:
        return None

def connect_outlook_imap(email_addr, password):
    """Connect to Outlook/Office 365 via IMAP with App Password."""
    try:
        mail = imaplib.IMAP4_SSL("outlook.office365.com", 993)
        mail.login(email_addr, password)
        return mail
    except Exception as e:
        return None

def fetch_email_summary(mail, email_addr):
    """Fetch unread count and recent emails from an IMAP connection."""
    result = {
        "email": email_addr,
        "unread": 0,
        "needs_reply": 0,
        "recent": [],
        "last_checked": iso_ts(),
        "error": None,
    }
    try:
        # Get unread count
        mail.select("INBOX")
        _, data = mail.search(None, "UNSEEN")
        unread_ids = data[0].split()
        result["unread"] = len(unread_ids)

        # Get recent emails (last 20 unread or last 20 overall)
        search_criteria = "UNSEEN" if unread_ids else "ALL"
        _, data = mail.search(None, search_criteria)
        ids = data[0].split()
        recent_ids = ids[-MAX_EMAILS_PER_ACCOUNT:]  # last N

        needs_reply = 0
        emails_list = []

        for eid in recent_ids[-20:]:  # detail on last 20
            _, msg_data = mail.fetch(eid, "(RFC822.HEADER)")
            if not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            if isinstance(raw, bytes):
                msg = email.message_from_bytes(raw)
            else:
                continue

            subject = ""
            try:
                decoded = decode_header(msg.get("Subject", ""))
                subject = "".join(
                    p[0].decode(p[1] or "utf-8") if isinstance(p[0], bytes) else p[0]
                    for p in decoded
                )
            except:
                subject = msg.get("Subject", "(no subject)")

            from_addr = msg.get("From", "")
            date_str = msg.get("Date", "")

            # Check if we've replied (look for In-Reply-To or References)
            in_reply_to = msg.get("In-Reply-To", "")
            references = msg.get("References", "")

            emails_list.append({
                "subject": subject[:100],
                "from": from_addr[:80],
                "date": date_str[:40],
            })

            # Simple heuristic: if no In-Reply-To, might need reply
            # This is imperfect but a starting point

        result["recent"] = emails_list
        result["needs_reply"] = needs_reply  # Will improve with Sent folder check

    except Exception as e:
        result["error"] = str(e)[:200]

    return result

def scan_emails():
    """Scan all 8 email accounts. Returns list of results."""
    results = []
    authenticated = dashlane_authenticated()

    if not authenticated:
        # Return placeholder for all accounts
        for acct in EMAIL_ACCOUNTS:
            results.append({
                "email": acct["email"],
                "label": acct["label"],
                "provider": acct["provider"],
                "unread": 0,
                "needs_reply": 0,
                "recent": [],
                "last_checked": iso_ts(),
                "error": "Dashlane not authenticated. Run: dcli configure",
                "status": "auth_required",
            })
        return results

    for acct in EMAIL_ACCOUNTS:
        entry = {
            "email": acct["email"],
            "label": acct["label"],
            "provider": acct["provider"],
            "unread": 0,
            "needs_reply": 0,
            "recent": [],
            "last_checked": iso_ts(),
            "error": None,
            "status": "ok",
        }

        # Get password from Dashlane
        password = dashlane_get(acct["email"])
        if not password:
            entry["error"] = f"No password found in Dashlane for {acct['email']}"
            entry["status"] = "no_credential"
            results.append(entry)
            continue

        # Connect
        if acct["provider"] == "gmail":
            mail = connect_gmail_imap(acct["email"], password)
        elif acct["provider"] == "outlook":
            mail = connect_outlook_imap(acct["email"], password)
        else:
            entry["error"] = f"Unknown provider: {acct['provider']}"
            entry["status"] = "error"
            results.append(entry)
            continue

        if mail is None:
            entry["error"] = "IMAP connection failed"
            entry["status"] = "connection_failed"
            results.append(entry)
            continue

        try:
            summary = fetch_email_summary(mail, acct["email"])
            entry.update(summary)
        except Exception as e:
            entry["error"] = str(e)[:200]
            entry["status"] = "error"
        finally:
            try:
                mail.logout()
            except:
                pass

        results.append(entry)

    return results

# ─── Calendar Connector ──────────────────────────────────────────────────────

def scan_calendars():
    """Scan Google Calendars for today's events.
    Uses gws CLI if available, otherwise returns placeholder.
    """
    events = []
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Try gws CLI first
    stdout, stderr, rc = run(f'gws calendar list --from {today} --to {tomorrow} --json 2>/dev/null', timeout=30)
    if rc == 0 and stdout:
        try:
            events = json.loads(stdout)
            return {"events": events, "source": "gws", "date": today, "error": None}
        except json.JSONDecodeError:
            pass

    # Fallback: check if google_api.py script exists
    gapi = HOME / ".hermes" / "skills" / "productivity" / "google-workspace" / "scripts" / "google_api.py"
    if gapi.exists():
        stdout, stderr, rc = run(f'python3 "{gapi}" calendar list --from {today} --to {tomorrow} 2>/dev/null', timeout=30)
        if rc == 0 and stdout:
            try:
                events = json.loads(stdout)
                return {"events": events, "source": "google_api", "date": today, "error": None}
            except json.JSONDecodeError:
                pass

    return {
        "events": [],
        "source": "none",
        "date": today,
        "error": "No calendar tool available. Install gws or set up Google Workspace OAuth.",
    }

# ─── AI Conversation Readers ─────────────────────────────────────────────────

def scan_ai_conversations():
    """Scan exported AI conversation files from exports directory."""
    ai_data = {
        "chatgpt": {"count": 0, "last_export": None, "recent": []},
        "claude": {"count": 0, "last_export": None, "recent": []},
        "gemini": {"count": 0, "last_export": None, "recent": []},
        "manus": {"count": 0, "last_export": None, "recent": []},
    }

    if not EXPORTS_DIR.exists():
        return ai_data

    for tool in ai_data:
        tool_dir = EXPORTS_DIR / tool
        if not tool_dir.exists():
            continue

        # Find all JSON/TXT/MD files
        files = sorted(tool_dir.glob("**/*"), key=lambda f: f.stat().st_mtime if f.is_file() else 0, reverse=True)
        files = [f for f in files if f.is_file()]

        ai_data[tool]["count"] = len(files)

        if files:
            last_mtime = files[0].stat().st_mtime
            ai_data[tool]["last_export"] = datetime.fromtimestamp(last_mtime, tz=timezone.utc).isoformat()

            # Read titles from recent files
            for f in files[:5]:
                ai_data[tool]["recent"].append({
                    "file": f.name,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
                })

    return ai_data

# ─── Recent Files Scanner ────────────────────────────────────────────────────

def scan_recent_files(hours=24):
    """Find recently modified files across key directories."""
    dirs_to_scan = [
        HOME / "Documents" / "GoTechSolutions",
        HOME / "Documents",
        HOME / "Desktop",
    ]

    cutoff = utcnow() - timedelta(hours=hours)
    files = []

    for d in dirs_to_scan:
        if not d.exists():
            continue
        stdout, _, rc = run(
            f'find "{d}" -maxdepth 3 -type f -mtime -1 ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/Library/*" 2>/dev/null | head -30',
            timeout=15
        )
        if rc == 0 and stdout:
            for line in stdout.splitlines():
                p = Path(line.strip())
                if p.exists():
                    try:
                        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                        if mtime > cutoff:
                            files.append({
                                "name": p.name,
                                "path": str(p),
                                "modified": mtime.isoformat(),
                                "size": p.stat().st_size,
                            })
                    except:
                        pass

    # Sort by modified time, most recent first
    files.sort(key=lambda f: f["modified"], reverse=True)
    return files[:20]

# ─── Cloud Storage Scanner ───────────────────────────────────────────────────

def scan_cloud_storage():
    """Check cloud storage availability and free space."""
    results = {}

    for name, path in CLOUD_PATHS.items():
        entry = {"path": str(path), "mounted": False, "free_space": None, "error": None}

        if path.exists():
            entry["mounted"] = True
            # Get disk usage
            stdout, _, rc = run(f'diskutil info "{path}" 2>/dev/null | grep -E "Free Space|Available Space"', timeout=10)
            if rc == 0 and stdout:
                entry["free_space"] = stdout.strip()
            else:
                # Fallback: use df
                stdout, _, rc = run(f'df -h "{path}" 2>/dev/null | tail -1', timeout=10)
                if rc == 0 and stdout:
                    parts = stdout.split()
                    if len(parts) >= 4:
                        entry["free_space"] = parts[3]
        else:
            entry["error"] = "Path not found"

        results[name] = entry

    return results

# ─── DATA TAXI Scanner ───────────────────────────────────────────────────────

def scan_data_taxi():
    """Check if DATA TAXI thumbdrive is mounted and get sync status."""
    result = {"mounted": False, "path": None, "free_space": None, "last_sync": None, "reveting_files": 0}

    # Check /Volumes for the drive
    volumes = Path("/Volumes")
    if volumes.exists():
        for vol in volumes.iterdir():
            for name in DATA_TAXI_NAMES:
                if vol.name.strip().upper() == name.strip().upper():
                    result["mounted"] = True
                    result["path"] = str(vol)
                    # Get free space
                    stdout, _, rc = run(f'df -h "{vol}" 2>/dev/null | tail -1', timeout=10)
                    if rc == 0 and stdout:
                        parts = stdout.split()
                        if len(parts) >= 4:
                            result["free_space"] = parts[3]
                    # Count Reveting video files
                    stdout, _, rc = run(f'find "{vol}" -type f \\( -name "*.mp4" -o -name "*.mov" -o -name "*.avi" -o -name "*.mkv" \\) 2>/dev/null | wc -l', timeout=15)
                    if rc == 0 and stdout:
                        result["reveting_files"] = int(stdout.strip())
                    break

    return result

# ─── Kanban / Task Scanner ───────────────────────────────────────────────────

def scan_tasks():
    """Read TODO.md and KANBAN.md for current task status."""
    todo_file = STARTUP_DIR / "TODO.md"
    kanban_file = STARTUP_DIR / "KANBAN.md"
    done_file = STARTUP_DIR / "DONE.md"

    tasks = {"todo": [], "in_progress": [], "done": [], "todo_count": 0, "wip_count": 0, "done_count": 0}

    if todo_file.exists():
        content = todo_file.read_text()
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("[ ]"):
                tasks["todo"].append(line[4:].strip().split("|")[0].strip())
            elif line.startswith("[x]"):
                tasks["done"].append(line[4:].strip().split("|")[0].strip())
        tasks["todo_count"] = len(tasks["todo"])
        tasks["done_count"] = len(tasks["done"])

    if kanban_file.exists():
        content = kanban_file.read_text()
        in_wip = False
        for line in content.splitlines():
            if "## IN PROGRESS" in line:
                in_wip = True
                continue
            if "## DONE" in line:
                in_wip = False
                continue
            if in_wip and line.strip().startswith("- [ ]"):
                tasks["in_progress"].append(line.strip()[4:].strip())
        tasks["wip_count"] = len(tasks["in_progress"])

    return tasks

# ─── Main Orchestrator ───────────────────────────────────────────────────────

def run_all():
    """Run all scanners and return complete data."""
    print(f"[{iso_ts()}] Starting Go Tech Command Center scan...", file=sys.stderr)

    data = {
        "generated_at": iso_ts(),
        "emails": [],
        "calendar": {},
        "ai_conversations": {},
        "recent_files": [],
        "cloud_storage": {},
        "data_taxi": {},
        "tasks": {},
        "errors": [],
    }

    # 1. Emails
    print("  Scanning 8 email accounts...", file=sys.stderr)
    try:
        data["emails"] = scan_emails()
    except Exception as e:
        data["errors"].append(f"Email scan failed: {e}")

    # 2. Calendar
    print("  Scanning calendars...", file=sys.stderr)
    try:
        data["calendar"] = scan_calendars()
    except Exception as e:
        data["errors"].append(f"Calendar scan failed: {e}")

    # 3. AI Conversations
    print("  Scanning AI conversation exports...", file=sys.stderr)
    try:
        data["ai_conversations"] = scan_ai_conversations()
    except Exception as e:
        data["errors"].append(f"AI scan failed: {e}")

    # 4. Recent files
    print("  Scanning recent files...", file=sys.stderr)
    try:
        data["recent_files"] = scan_recent_files()
    except Exception as e:
        data["errors"].append(f"Recent files scan failed: {e}")

    # 5. Cloud storage
    print("  Scanning cloud storage...", file=sys.stderr)
    try:
        data["cloud_storage"] = scan_cloud_storage()
    except Exception as e:
        data["errors"].append(f"Cloud storage scan failed: {e}")

    # 6. DATA TAXI
    print("  Checking DATA TAXI...", file=sys.stderr)
    try:
        data["data_taxi"] = scan_data_taxi()
    except Exception as e:
        data["errors"].append(f"DATA TAXI scan failed: {e}")

    # 7. Tasks
    print("  Reading task lists...", file=sys.stderr)
    try:
        data["tasks"] = scan_tasks()
    except Exception as e:
        data["errors"].append(f"Task scan failed: {e}")

    print(f"[{iso_ts()}] Scan complete.", file=sys.stderr)
    return data

def print_summary(data):
    """Print human-readable summary."""
    print(f"\n{'='*60}")
    print(f"  GO TECH COMMAND CENTER")
    print(f"  {data['generated_at']}")
    print(f"{'='*60}")

    # Emails
    total_unread = sum(e.get("unread", 0) for e in data["emails"])
    total_reply = sum(e.get("needs_reply", 0) for e in data["emails"])
    print(f"\n  EMAIL: {total_unread} unread, {total_reply} need reply across {len(data['emails'])} accounts")
    for e in data["emails"]:
        status = e.get("status", "?")
        err = f" [ERROR: {e['error']}]" if e.get("error") else ""
        print(f"    {e['email']:40s} {e.get('unread', 0):3d} unread  {status}{err}")

    # Calendar
    cal = data.get("calendar", {})
    events = cal.get("events", [])
    print(f"\n  CALENDAR: {len(events)} events today")
    for ev in events[:5]:
        if isinstance(ev, dict):
            print(f"    {ev.get('time', '?'):15s} {ev.get('title', '?')}")
        else:
            print(f"    {str(ev)[:60]}")

    # AI
    ai = data.get("ai_conversations", {})
    print(f"\n  AI CONVERSATIONS:")
    for tool, info in ai.items():
        count = info.get("count", 0)
        last = info.get("last_export", "never")
        print(f"    {tool:10s} {count:3d} exports  last: {last}")

    # Recent files
    files = data.get("recent_files", [])
    print(f"\n  RECENT FILES (24h): {len(files)} files")
    for f in files[:10]:
        print(f"    {f['modified'][:16]}  {f['name'][:50]}")

    # Cloud
    cloud = data.get("cloud_storage", {})
    print(f"\n  CLOUD STORAGE:")
    for name, info in cloud.items():
        mounted = "mounted" if info.get("mounted") else "not found"
        free = info.get("free_space", "?")
        print(f"    {name:15s} {mounted:12s} free: {free}")

    # DATA TAXI
    taxi = data.get("data_taxi", {})
    print(f"\n  DATA TAXI: {'MOUNTED' if taxi.get('mounted') else 'NOT DETECTED'}")
    if taxi.get("mounted"):
        print(f"    Path: {taxi.get('path')}")
        print(f"    Free: {taxi.get('free_space')}")
        print(f"    Video files: {taxi.get('reveting_files', 0)}")

    # Tasks
    tasks = data.get("tasks", {})
    print(f"\n  TASKS: {tasks.get('todo_count', 0)} todo, {tasks.get('wip_count', 0)} in progress, {tasks.get('done_count', 0)} done")
    for t in tasks.get("in_progress", []):
        print(f"    IN PROGRESS: {t}")
    for t in tasks.get("todo", [])[:5]:
        print(f"    TODO: {t}")

    # Errors
    if data.get("errors"):
        print(f"\n  ERRORS ({len(data['errors'])}):")
        for err in data["errors"]:
            print(f"    ! {err}")

    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    data = run_all()

    if "--summary" in sys.argv:
        print_summary(data)
    elif "--save" in sys.argv:
        out = DATA_DIR / "latest.json"
        out.write_text(json.dumps(data, indent=2, default=str))
        print(f"Saved to {out}")
        print_summary(data)
    else:
        # Default: JSON to stdout
        print(json.dumps(data, indent=2, default=str))
