#!/usr/bin/env python3
"""
Cash Alert System for GoTechSolutions Startup.

Monitors cash balance and sends macOS notifications when:
- Balance changes (up or down)
- Balance drops below a configurable threshold
- Large changes detected (>$500 by default)

Usage:
    python3 cash-alert.py              # Default: --check
    python3 cash-alert.py --check      # Check balance and alert on changes
    python3 cash-alert.py --test       # Send test notification
    python3 cash-alert.py --threshold 500  # Alert if balance drops below 500
    python3 cash-alert.py --install    # Install as daily cron job
    python3 cash-alert.py --status     # Show current state and last alert
    python3 cash-alert.py --quiet      # Suppress notifications
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path for importing notify
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from notify import notify, notify_critical, notify_success

# --- Configuration ---
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = BASE_DIR / "scripts"
CRON_DIR = BASE_DIR / "cron"

CASH_FILE = DATA_DIR / "cash.json"
STATE_FILE = SCRIPTS_DIR / "cash-alert-state.json"
LOG_FILE = SCRIPTS_DIR / "cash-alert-log.txt"
CRON_FILE = CRON_DIR / "jobs.json"

LARGE_CHANGE_THRESHOLD = 500.0


def log_message(message):
    """Write a timestamped log entry to the log file."""
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}\n"
    
    # Print to stdout
    print(f"[{timestamp[:19]}] {message}")
    
    # Append to log file
    try:
        with open(LOG_FILE, "a") as f:
            f.write(entry)
    except IOError as e:
        print(f"[WARN] Could not write to log file: {e}", file=sys.stderr)


def read_cash_balance():
    """Read current balance from cash.json.
    
    Returns:
        float: Current balance, or None if file not found/invalid
    """
    try:
        with open(CASH_FILE, "r") as f:
            data = json.load(f)
        balance = float(data.get("balance", 0))
        return balance
    except FileNotFoundError:
        log_message("ERROR: cash.json not found at " + str(CASH_FILE))
        return None
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        log_message(f"ERROR: Could not parse cash.json: {e}")
        return None


def read_state():
    """Read the last alert state.
    
    Returns:
        dict: State data with last_balance, last_alert_time, last_change
    """
    default_state = {
        "last_balance": None,
        "last_alert_time": None,
        "last_change": None,
        "alert_count": 0
    }
    
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        return state
    except FileNotFoundError:
        log_message("INFO: No state file found, creating fresh state.")
        return default_state
    except (json.JSONDecodeError, ValueError) as e:
        log_message(f"WARN: Could not parse state file: {e}. Using defaults.")
        return default_state


def save_state(state):
    """Save the alert state to disk.
    
    Args:
        state (dict): State data to persist
    """
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        log_message(f"ERROR: Could not save state: {e}")


def send_notification(title, subtitle, sound="default", quiet=False):
    """Send a notification (or log it in quiet mode).
    
    Args:
        title: Notification title
        subtitle: Notification body text
        sound: macOS notification sound name
        quiet: If True, only log (don't send)
    """
    if quiet:
        log_message(f"[QUIET] Would notify: {title} - {subtitle}")
        return True
    
    return notify(title, subtitle, sound)


def send_critical_notification(title, subtitle, quiet=False):
    """Send a critical notification (or log it in quiet mode)."""
    if quiet:
        log_message(f"[QUIET] Would notify (critical): {title} - {subtitle}")
        return True
    return notify_critical(title, subtitle)


def send_success_notification(title, subtitle, quiet=False):
    """Send a success notification (or log it in quiet mode)."""
    if quiet:
        log_message(f"[QUIET] Would notify (success): {title} - {subtitle}")
        return True
    return notify_success(title, subtitle)


def check_balance(threshold=float("inf"), quiet=False):
    """Check cash balance against stored state and alert on changes.
    
    Args:
        threshold: Alert if balance drops below this value
        quiet: If True, suppress notifications (just log)
    
    Returns:
        dict: Status information about the check
    """
    current_balance = read_cash_balance()
    if current_balance is None:
        log_message("Cannot check balance: unable to read cash.json")
        return {"status": "error", "reason": "cannot_read_balance"}
    
    state = read_state()
    old_balance = state.get("last_balance")
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "status": "ok",
        "current_balance": current_balance,
        "old_balance": old_balance,
        "change": None,
        "alerts_sent": []
    }
    
    # First run - just store the balance
    if old_balance is None:
        log_message(f"First run: setting initial balance to ${current_balance:,.2f}")
        state["last_balance"] = current_balance
        state["last_alert_time"] = now
        save_state(state)
        result["alerts_sent"].append("initial")
        send_notification(
            "💰 Cash Alert Initialized",
            f"Current balance: ${current_balance:,.2f}\nMonitoring for changes.",
            quiet=quiet
        )
        return result
    
    # Calculate change
    change = current_balance - old_balance
    result["change"] = change
    
    if change == 0:
        log_message(f"No change (balance: ${current_balance:,.2f})")
        state["last_alert_time"] = now
        save_state(state)
        result["status"] = "no_change"
        return result
    
    # Balance changed!
    change_pct = (change / old_balance * 100) if old_balance != 0 else 0
    direction = "📈 UP" if change > 0 else "📉 DOWN"
    
    subtitle = (
        f"Old: ${old_balance:,.2f}\n"
        f"New: ${current_balance:,.2f}\n"
        f"Change: {'+${:,.2f}'.format(change) if change > 0 else '-${:,.2f}'.format(abs(change))} ({direction})"
    )
    
    # Determine alert type
    is_large = abs(change) > LARGE_CHANGE_THRESHOLD
    is_below_threshold = current_balance < threshold
    
    if change > 0:
        # Balance went up - success
        title = "💰 Cash Balance Increased!"
        sound = "Glass"
        if is_large:
            title = "💰💰 Large Cash Inflow!"
        send_success_notification(title, subtitle, quiet=quiet)
        result["alerts_sent"].append("increase")
    else:
        # Balance went down - warning/critical
        if is_large:
            title = "🚨 LARGE CASH OUTFLOW DETECTED!"
            send_critical_notification(title, subtitle, quiet=quiet)
            result["alerts_sent"].append("large_decrease")
        elif is_below_threshold:
            title = "⚠️ Cash Below Threshold!"
            send_critical_notification(title, subtitle, quiet=quiet)
            result["alerts_sent"].append("below_threshold")
        else:
            title = "📉 Cash Balance Decreased"
            send_notification(title, subtitle, sound="Basso", quiet=quiet)
            result["alerts_sent"].append("decrease")
    
    # Alert if below threshold (even on increase, notify)
    if is_below_threshold and "below_threshold" not in result["alerts_sent"]:
        alert_subtitle = subtitle + f"\n\n⚠️ Alert: Balance is below ${threshold:,.2f} threshold!"
        send_critical_notification("⚠️ Low Cash Alert", alert_subtitle, quiet=quiet)
        result["alerts_sent"].append("below_threshold")
    
    # Update state
    state["last_balance"] = current_balance
    state["last_alert_time"] = now
    state["last_change"] = change
    state["alert_count"] = state.get("alert_count", 0) + len(result["alerts_sent"])
    save_state(state)
    
    log_message(
        f"Balance changed: ${old_balance:,.2f} → ${current_balance:,.2f} "
        f"({'+' if change > 0 else ''}{change:,.2f}). "
        f"Alerts: {', '.join(result['alerts_sent'])}"
    )
    
    return result


def run_test(quiet=False):
    """Send a test notification to verify the system works."""
    log_message("Sending test notification...")
    
    title = "🧪 Cash Alert Test"
    subtitle = (
        "This is a test notification from the Cash Alert System.\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "If you see this, notifications are working!"
    )
    
    result = send_notification(title, subtitle, quiet=quiet)
    
    if result:
        log_message("Test notification sent successfully.")
    else:
        log_message("ERROR: Test notification failed.")
    
    return result


def install_cron():
    """Install this script as a daily cron job in jobs.json."""
    log_message("Installing cash-alert as daily cron job...")
    
    try:
        with open(CRON_FILE, "r") as f:
            cron_data = json.load(f)
    except FileNotFoundError:
        cron_data = {"jobs": []}
    except json.JSONDecodeError as e:
        log_message(f"ERROR: Could not parse jobs.json: {e}")
        return False
    
    # Check if already installed
    script_path = str(Path(__file__).resolve())
    job_id = "cash-alert-py"
    
    for job in cron_data.get("jobs", []):
        if job.get("id") == job_id:
            log_message(f"Job '{job_id}' already exists. Updating...")
            # Update existing job
            job["name"] = "Cash Alert Check (Python)"
            job["command"] = f"python3 {script_path} --check"
            job["enabled"] = True
            with open(CRON_FILE, "w") as f:
                json.dump(cron_data, f, indent=2)
            log_message("Cron job updated successfully.")
            return True
    
    # Add new job
    new_job = {
        "id": job_id,
        "name": "Cash Alert Check (Python)",
        "schedule": {
            "type": "daily",
            "time": "10:00"
        },
        "command": f"python3 {script_path} --check",
        "enabled": True,
        "last_run": None,
        "last_status": None,
        "next_run": None
    }
    
    cron_data.setdefault("jobs", []).append(new_job)
    
    try:
        with open(CRON_FILE, "w") as f:
            json.dump(cron_data, f, indent=2)
        log_message(f"Cron job '{job_id}' installed successfully.")
        log_message(f"  Schedule: daily at 10:00")
        log_message(f"  Command: {new_job['command']}")
        return True
    except IOError as e:
        log_message(f"ERROR: Could not write jobs.json: {e}")
        return False


def show_status():
    """Display current state and last alert information."""
    print("\n" + "=" * 50)
    print("  Cash Alert System Status")
    print("=" * 50)
    
    # Current balance
    balance = read_cash_balance()
    if balance is not None:
        print(f"  Current Balance:    ${balance:,.2f}")
    else:
        print("  Current Balance:    [unavailable]")
    
    # State
    state = read_state()
    last_balance = state.get("last_balance")
    if last_balance is not None:
        print(f"  Last Recorded:      ${last_balance:,.2f}")
    else:
        print("  Last Recorded:      [none]")
    
    last_alert = state.get("last_alert_time")
    if last_alert:
        print(f"  Last Alert Time:    {last_alert}")
    else:
        print("  Last Alert Time:    [never]")
    
    last_change = state.get("last_change")
    if last_change is not None:
        sign = "+" if last_change > 0 else ""
        print(f"  Last Change:        {sign}${last_change:,.2f}")
    else:
        print("  Last Change:        [none]")
    
    alert_count = state.get("alert_count", 0)
    print(f"  Total Alerts Sent:  {alert_count}")
    
    # Cron status
    try:
        with open(CRON_FILE, "r") as f:
            cron_data = json.load(f)
        for job in cron_data.get("jobs", []):
            if "cash" in job.get("id", "").lower() or "cash" in job.get("name", "").lower():
                enabled = "✅" if job.get("enabled") else "❌"
                print(f"  Cron Job:           {enabled} {job.get('name', 'Unknown')}")
                print(f"    Schedule:         {job.get('schedule', {}).get('type', '?')} "
                      f"{job.get('schedule', {}).get('time', '')}")
                print(f"    Command:          {job.get('command', '?')}")
                break
    except (FileNotFoundError, json.JSONDecodeError):
        print("  Cron Job:           [not installed or jobs.json missing]")
    
    # Log file
    if LOG_FILE.exists():
        size = LOG_FILE.stat().st_size
        print(f"  Log File:           {LOG_FILE} ({size} bytes)")
    else:
        print(f"  Log File:           [not created yet]")
    
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Cash Alert System - Monitor cash balance and get notified of changes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 cash-alert.py                    # Check balance (default action)
  python3 cash-alert.py --check            # Explicitly check balance
  python3 cash-alert.py --check --threshold 500   # Alert if below $500
  python3 cash-alert.py --test             # Send test notification
  python3 cash-alert.py --install          # Install as daily cron job
  python3 cash-alert.py --status           # Show current state
  python3 cash-alert.py --check --quiet    # Check but don't send notifications
        """
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Check cash balance and send alerts on changes"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Alert if balance drops below this amount (e.g., 500)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        default=False,
        help="Send a test notification immediately"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        default=False,
        help="Install as a daily cron job in jobs.json"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        default=False,
        help="Show current state and last alert time"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress notifications (just log to file)"
    )
    
    args = parser.parse_args()
    
    # If no action specified, default to --check
    if not any([args.check, args.test, args.install, args.status]):
        args.check = True
    
    # Ensure directories exist
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    log_message("=" * 40)
    log_message("Cash Alert System started")
    
    if args.test:
        run_test(quiet=args.quiet)
    
    if args.install:
        install_cron()
    
    if args.status:
        show_status()
    
    if args.check:
        threshold = args.threshold if args.threshold is not None else float("inf")
        result = check_balance(threshold=threshold, quiet=args.quiet)
        log_message(f"Check complete: {result['status']}")
    
    log_message("Cash Alert System finished")
    log_message("=" * 40)


if __name__ == "__main__":
    main()
