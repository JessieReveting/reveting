#!/usr/bin/env python3
"""
Cron Job Manager for GoTech Workflow Engine
Reads job configs from startup/cron/jobs.json
Supports: add, remove, list, run, daemon, run-all
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta

# Paths
BASE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "GoTechSolutions", "startup")
JOBS_FILE = os.path.join(BASE_DIR, "cron", "jobs.json")
LOG_FILE = os.path.join(BASE_DIR, "logs", "cron.log")
WORKFLOW_SCRIPT = os.path.join(BASE_DIR, "workflow.py")

# Ensure directories exist
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
os.makedirs(os.path.dirname(JOBS_FILE), exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("cron-manager")

# Day name to weekday number (Monday=0, Sunday=6)
DAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6
}


def load_jobs():
    """Load jobs from JSON config file."""
    if not os.path.exists(JOBS_FILE):
        logger.warning(f"Jobs file not found at {JOBS_FILE}, creating empty config.")
        return {"jobs": []}
    with open(JOBS_FILE, "r") as f:
        return json.load(f)


def save_jobs(config):
    """Save jobs config to JSON file."""
    with open(JOBS_FILE, "w") as f:
        json.dump(config, f, indent=2)
    logger.info("Jobs config saved.")


def compute_next_run(job, from_time=None):
    """Calculate the next run time for a job based on its schedule."""
    now = from_time or datetime.now()
    schedule = job.get("schedule", {})
    stype = schedule.get("type")

    if stype == "interval":
        minutes = schedule.get("minutes", 60)
        last_run_str = job.get("last_run")
        if last_run_str:
            try:
                last_run = datetime.fromisoformat(last_run_str)
                next_run = last_run + timedelta(minutes=minutes)
                if next_run > now:
                    return next_run
            except (ValueError, TypeError):
                pass
        return now + timedelta(minutes=minutes)

    elif stype == "daily":
        time_str = schedule.get("time", "00:00")
        hour, minute = map(int, time_str.split(":"))
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run

    elif stype == "weekly":
        day_name = schedule.get("day", "monday").lower()
        time_str = schedule.get("time", "00:00")
        target_day = DAY_MAP.get(day_name, 0)
        hour, minute = map(int, time_str.split(":"))

        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = target_day - next_run.weekday()
        if days_ahead < 0 or (days_ahead == 0 and next_run <= now):
            days_ahead += 7
        next_run += timedelta(days=days_ahead)
        return next_run

    return now + timedelta(hours=1)


def run_job(job):
    """Execute a single job as a subprocess."""
    command = job.get("command", "")
    job_id = job.get("id", "unknown")
    job_name = job.get("name", job_id)

    logger.info(f"Running job [{job_id}]: {job_name}")
    logger.info(f"Command: {command}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
            timeout=300  # 5 minute timeout
        )

        end_time = datetime.now().isoformat()
        job["last_run"] = end_time

        if result.returncode == 0:
            job["last_status"] = "success"
            logger.info(f"Job [{job_id}] completed successfully.")
            if result.stdout.strip():
                logger.debug(f"stdout: {result.stdout.strip()}")
        else:
            job["last_status"] = "failed"
            logger.error(f"Job [{job_id}] failed with return code {result.returncode}")
            if result.stderr.strip():
                logger.error(f"stderr: {result.stderr.strip()}")

    except subprocess.TimeoutExpired:
        job["last_run"] = datetime.now().isoformat()
        job["last_status"] = "timeout"
        logger.error(f"Job [{job_id}] timed out after 300 seconds.")
    except Exception as e:
        job["last_run"] = datetime.now().isoformat()
        job["last_status"] = "error"
        logger.error(f"Job [{job_id}] error: {e}")

    # Update next_run
    job["next_run"] = compute_next_run(job).isoformat()
    return job


def cmd_list(args):
    """List all jobs."""
    config = load_jobs()
    jobs = config.get("jobs", [])

    if not jobs:
        print("No jobs configured.")
        return

    print(f"\n{'ID':<20} {'Name':<30} {'Enabled':<8} {'Last Status':<12} {'Last Run':<22} {'Next Run':<22}")
    print("-" * 114)

    for job in jobs:
        job_id = job.get("id", "")
        name = job.get("name", "")
        enabled = "Yes" if job.get("enabled", False) else "No"
        last_status = job.get("last_status", "—") or "—"
        last_run = job.get("last_run", "—") or "—"
        next_run = job.get("next_run", "—") or "—"

        # Truncate timestamps for display
        if last_run != "—" and len(last_run) > 19:
            last_run = last_run[:19]
        if next_run != "—" and len(next_run) > 19:
            next_run = next_run[:19]

        print(f"{job_id:<20} {name:<30} {enabled:<8} {last_status:<12} {last_run:<22} {next_run:<22}")

    print(f"\nTotal: {len(jobs)} jobs")
    print()


def cmd_add(args):
    """Add a new job."""
    config = load_jobs()
    jobs = config.get("jobs", [])

    # Check for duplicate ID
    if any(j.get("id") == args.id for j in jobs):
        print(f"Error: Job with ID '{args.id}' already exists.")
        sys.exit(1)

    # Build schedule
    schedule = {}
    if args.interval:
        schedule = {"type": "interval", "minutes": args.interval}
    elif args.daily:
        schedule = {"type": "daily", "time": args.daily}
    elif args.weekly:
        schedule = {"type": "weekly", "day": args.weekday or "monday", "time": args.weekly}
    else:
        print("Error: Must specify --interval, --daily, or --weekly")
        sys.exit(1)

    new_job = {
        "id": args.id,
        "name": args.name or args.id,
        "schedule": schedule,
        "command": args.command,
        "enabled": True,
        "last_run": None,
        "last_status": None,
        "next_run": None
    }

    new_job["next_run"] = compute_next_run(new_job).isoformat()
    jobs.append(new_job)
    config["jobs"] = jobs
    save_jobs(config)
    print(f"Job '{args.id}' added successfully.")


def cmd_remove(args):
    """Remove a job by ID."""
    config = load_jobs()
    jobs = config.get("jobs", [])

    original_count = len(jobs)
    jobs = [j for j in jobs if j.get("id") != args.id]

    if len(jobs) == original_count:
        print(f"Error: Job '{args.id}' not found.")
        sys.exit(1)

    config["jobs"] = jobs
    save_jobs(config)
    print(f"Job '{args.id}' removed.")


def cmd_run(args):
    """Run a specific job by ID."""
    config = load_jobs()
    jobs = config.get("jobs", [])

    for i, job in enumerate(jobs):
        if job.get("id") == args.id:
            jobs[i] = run_job(job)
            config["jobs"] = jobs
            save_jobs(config)
            return

    print(f"Error: Job '{args.id}' not found.")
    sys.exit(1)


def cmd_run_all(args):
    """Run all enabled jobs."""
    config = load_jobs()
    jobs = config.get("jobs", [])

    enabled_jobs = [j for j in jobs if j.get("enabled", False)]
    if not enabled_jobs:
        print("No enabled jobs to run.")
        return

    print(f"Running {len(enabled_jobs)} enabled jobs...")
    for i, job in enumerate(jobs):
        if job.get("enabled", False):
            jobs[i] = run_job(job)

    config["jobs"] = jobs
    save_jobs(config)
    print("All enabled jobs executed.")


def cmd_toggle(args):
    """Enable or disable a job."""
    config = load_jobs()
    jobs = config.get("jobs", [])

    for i, job in enumerate(jobs):
        if job.get("id") == args.id:
            new_state = not job.get("enabled", False)
            if args.enable is not None:
                new_state = args.enable
            jobs[i]["enabled"] = new_state
            state_str = "enabled" if new_state else "disabled"
            print(f"Job '{args.id}' {state_str}.")
            config["jobs"] = jobs
            save_jobs(config)
            return

    print(f"Error: Job '{args.id}' not found.")
    sys.exit(1)


def cmd_daemon(args):
    """Run as a background daemon, checking every minute for jobs to run."""
    logger.info("Cron manager daemon started.")
    logger.info(f"Jobs file: {JOBS_FILE}")
    logger.info(f"Log file: {LOG_FILE}")

    # Write PID file
    pid_file = os.path.join(BASE_DIR, "cron", "cron-manager.pid")
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, shutting down.")
        try:
            os.remove(pid_file)
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Initialize next_run for all jobs on first start
    config = load_jobs()
    jobs = config.get("jobs", [])
    updated = False
    for job in jobs:
        if job.get("enabled") and job.get("next_run") is None:
            job["next_run"] = compute_next_run(job).isoformat()
            updated = True
    if updated:
        config["jobs"] = jobs
        save_jobs(config)

    check_interval = 60  # seconds

    while True:
        try:
            config = load_jobs()
            jobs = config.get("jobs", [])
            now = datetime.now()
            modified = False

            for i, job in enumerate(jobs):
                if not job.get("enabled", False):
                    continue

                next_run_str = job.get("next_run")
                if not next_run_str:
                    job["next_run"] = compute_next_run(job).isoformat()
                    modified = True
                    continue

                try:
                    next_run = datetime.fromisoformat(next_run_str)
                except (ValueError, TypeError):
                    job["next_run"] = compute_next_run(job).isoformat()
                    modified = True
                    continue

                if now >= next_run:
                    logger.info(f"Job '{job['id']}' is due. Executing...")
                    jobs[i] = run_job(job)
                    modified = True

            if modified:
                config["jobs"] = jobs
                save_jobs(config)

        except Exception as e:
            logger.error(f"Error in daemon loop: {e}")

        time.sleep(check_interval)


def main():
    parser = argparse.ArgumentParser(
        description="GoTech Cron Job Manager - JSON-based scheduler for workflow.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 cron-manager.py --list                    List all jobs
  python3 cron-manager.py --daemon                   Run as background daemon
  python3 cron-manager.py --run-all                  Run all enabled jobs now
  python3 cron-manager.py --run --id metrics-update  Run a specific job
  python3 cron-manager.py --add --id my-job --interval 30 --command "python3 workflow.py --mode my-mode"
  python3 cron-manager.py --add --id my-job --daily 09:00 --command "python3 workflow.py --mode daily"
  python3 cron-manager.py --add --id my-job --weekly monday 08:00 --command "python3 workflow.py --mode weekly"
  python3 cron-manager.py --remove --id my-job       Remove a job
  python3 cron-manager.py --toggle --id my-job       Toggle job enabled/disabled
        """
    )

    parser.add_argument("--daemon", action="store_true", help="Run as background daemon (checks every minute)")
    parser.add_argument("--list", action="store_true", help="List all configured jobs")
    parser.add_argument("--run-all", action="store_true", help="Run all enabled jobs immediately")
    parser.add_argument("--run", action="store_true", help="Run a specific job (requires --id)")
    parser.add_argument("--add", action="store_true", help="Add a new job")
    parser.add_argument("--remove", action="store_true", help="Remove a job")
    parser.add_argument("--toggle", action="store_true", help="Toggle job enabled state")
    parser.add_argument("--id", type=str, help="Job ID")
    parser.add_argument("--name", type=str, help="Job display name")
    parser.add_argument("--command", type=str, help="Command to execute")
    parser.add_argument("--interval", type=int, help="Interval in minutes")
    parser.add_argument("--daily", type=str, help="Daily time (HH:MM)")
    parser.add_argument("--weekly", type=str, help="Weekly time (HH:MM)")
    parser.add_argument("--weekday", type=str, help="Day of week for weekly schedule")
    parser.add_argument("--enable", type=lambda x: x.lower() in ('true', '1', 'yes'), help="Set enabled state")

    args = parser.parse_args()

    if args.daemon:
        cmd_daemon(args)
    elif args.list:
        cmd_list(args)
    elif args.run_all:
        cmd_run_all(args)
    elif args.run:
        if not args.id:
            print("Error: --run requires --id")
            sys.exit(1)
        cmd_run(args)
    elif args.add:
        if not args.id or not args.command:
            print("Error: --add requires --id and --command")
            sys.exit(1)
        cmd_add(args)
    elif args.remove:
        if not args.id:
            print("Error: --remove requires --id")
            sys.exit(1)
        cmd_remove(args)
    elif args.toggle:
        if not args.id:
            print("Error: --toggle requires --id")
            sys.exit(1)
        cmd_toggle(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
