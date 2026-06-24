#!/usr/bin/env python3
"""
GoTech Solutions — Weekly Digest Generator
Generates a weekly digest email with business metrics, leads, clients, content, and tasks.

Usage:
  python3 daily-digest.py                    # Print digest to stdout
  python3 daily-digest.py --send             # Send digest via email
  python3 daily-digest.py --send --to boss@example.com
  python3 daily-digest.py --week 2026-06-19  # For a specific week

Data Sources:
  - data/cash.json      — Cash balance and transactions
  - data/leads.json     — Sales pipeline leads
  - data/clients.json   — Active clients
  - data/content_calendar.json — Content schedule
  - data/tasks.json     — Tasks and action items
  - data/metrics.json   — Historical metrics snapshots
"""

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# === CONFIG ===
STARTUP_DIR = Path("/Users/davidgo/Documents/GoTechSolutions/startup")
DATA_DIR = STARTUP_DIR / "data"
SCRIPTS_DIR = STARTUP_DIR / "scripts"

CASH_FILE = DATA_DIR / "cash.json"
LEADS_FILE = DATA_DIR / "leads.json"
CLIENTS_FILE = DATA_DIR / "clients.json"
CONTENT_FILE = DATA_DIR / "content_calendar.json"
TASKS_FILE = DATA_DIR / "tasks.json"
METRICS_FILE = DATA_DIR / "metrics.json"

DIGEST_RECIPIENT = os.environ.get("GMAIL_USER", "bizrunner@gmail.com")

# === LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("daily-digest")


# === DATA LOADING ===
def load_json(path: Path, default: Any = None) -> Any:
    """Load a JSON file, returning default if not found."""
    if default is None:
        default = {}
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


# === DIGEST SECTIONS ===
def get_week_boundaries(week_of: Optional[str] = None) -> tuple:
    """Get the Monday and Sunday for the target week."""
    if week_of:
        # Parse the date and find the Monday of that week
        target = datetime.date.fromisoformat(week_of)
        monday = target - datetime.timedelta(days=target.weekday())
    else:
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)
    return monday, sunday


def section_cash(monday: datetime.date, sunday: datetime.date) -> str:
    """Generate the cash position section."""
    cash = load_json(CASH_FILE, {"balance": 0, "transactions": [], "starting_balance": 500, "start_date": "2026-06-24"})

    balance = cash.get("balance", 0)
    starting = cash.get("starting_balance", 500)
    target = 1_000_000
    progress = (balance / target) * 100 if target > 0 else 0

    # This week's transactions
    week_tx = [
        t for t in cash.get("transactions", [])
        if monday.isoformat() <= t.get("date", "")[:10] <= sunday.isoformat()
    ]
    week_revenue = sum(t["amount"] for t in week_tx if t["amount"] > 0)
    week_expenses = sum(abs(t["amount"]) for t in week_tx if t["amount"] < 0)
    net_flow = week_revenue - week_expenses

    # Calculate daily rate
    all_tx = cash.get("transactions", [])
    recent_positive = [t for t in all_tx if t["amount"] > 0][-30:]
    daily_rate = sum(t["amount"] for t in recent_positive) / 30 if recent_positive else 0
    days_to_1m = (target - balance) / daily_rate if daily_rate > 0 else None

    lines = [
        "## 💰 Cash Position",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Current Balance | **${balance:,.2f}** |",
        f"| Starting Balance | ${starting:,.2f} ({cash.get('start_date', 'N/A')}) |",
        f"| Net Change (since start) | ${balance - starting:+,.2f} |",
        f"| Target | ${target:,.0f} |",
        f"| Progress | {progress:.4f}% |",
        f"",
        f"### This Week ({monday.isoformat()} to {sunday.isoformat()})",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Revenue | ${week_revenue:+,.2f} |",
        f"| Expenses | ${week_expenses:+,.2f} |",
        f"| Net Cash Flow | ${net_flow:+,.2f} |",
        f"| Transactions | {len(week_tx)} |",
        f"",
    ]

    if days_to_1m is not None:
        est_months = days_to_1m / 30
        lines.append(f"**At current rate (${daily_rate:,.0f}/day): {days_to_1m:.0f} days ({est_months:.1f} months) to $1M**")
    else:
        lines.append("**No revenue data yet — start closing deals to calculate runway to $1M!**")

    lines.append("")

    # Recent transactions
    if week_tx:
        lines.append("### Recent Transactions")
        lines.append("")
        lines.append("| Date | Amount | Note | Balance |")
        lines.append("|------|--------|------|---------|")
        for tx in sorted(week_tx, key=lambda x: x.get("date", "")):
            date_str = tx.get("date", "")[:10]
            amount = tx.get("amount", 0)
            note = tx.get("note", "")
            bal = tx.get("balance", 0)
            lines.append(f"| {date_str} | ${amount:+,.2f} | {note} | ${bal:,.2f} |")
        lines.append("")

    return "\n".join(lines)


def section_leads(monday: datetime.date, sunday: datetime.date) -> str:
    """Generate the leads section."""
    leads_data = load_json(LEADS_FILE, {"leads": [], "stats": {"total": 0, "by_source": {}}})
    leads = leads_data.get("leads", [])

    # This week's new leads
    week_leads = [
        l for l in leads
        if monday.isoformat() <= (l.get("created_at", "")[:10] or "") <= sunday.isoformat()
    ]

    # Pipeline breakdown
    stages: Dict[str, list] = {}
    for l in leads:
        stage = l.get("stage", "unknown")
        if stage not in stages:
            stages[stage] = []
        stages[stage].append(l)

    total_pipeline_value = sum(
        l.get("estimated_value", 0) for l in leads
        if l.get("stage") not in ("won", "lost")
    )

    lines = [
        "## 🎯 Leads & Pipeline",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| New This Week | **{len(week_leads)}** |",
        f"| Total Pipeline | {len(leads)} |",
        f"| Pipeline Value | ${total_pipeline_value:,.2f} |",
        f"| Sources | {', '.join(f'{k}: {v}' for k, v in leads_data.get('stats', {}).get('by_source', {}).items()) or 'N/A'} |",
        f"",
    ]

    # Stage breakdown
    if stages:
        lines.append("### By Stage")
        lines.append("")
        lines.append("| Stage | Count | Total Value |")
        lines.append("|-------|-------|-------------|")
        for stage, items in sorted(stages.items()):
            value = sum(l.get("estimated_value", 0) for l in items)
            lines.append(f"| {stage} | {len(items)} | ${value:,.2f} |")
        lines.append("")

    # New leads detail
    if week_leads:
        lines.append("### New This Week")
        lines.append("")
        for l in sorted(week_leads, key=lambda x: x.get("score", 0), reverse=True):
            score = l.get("score", 0)
            name = l.get("name", "Unknown")
            source = l.get("source", "unknown")
            interest = l.get("interest", "")
            value = l.get("estimated_value", 0)
            emoji = "🔥" if score >= 80 else "⭐" if score >= 60 else "📌"
            lines.append(f"- {emoji} [{score}] **{name}** ({source}) — {interest} | ${value:,.2f}")
        lines.append("")

    return "\n".join(lines)


def section_clients(monday: datetime.date, sunday: datetime.date) -> str:
    """Generate the active clients section."""
    clients_data = load_json(CLIENTS_FILE, {"clients": [], "total_mrr": 0})
    clients = clients_data.get("clients", [])

    active = [c for c in clients if c.get("status") == "active"]
    churned = [c for c in clients if c.get("status") == "churned"]
    total_mrr = clients_data.get("total_mrr", 0)
    total_arr = total_mrr * 12

    # New this week
    new_this_week = [
        c for c in clients
        if monday.isoformat() <= (c.get("start_date", "") or "") <= sunday.isoformat()
    ]

    lines = [
        "## 👥 Clients",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Active Clients | **{len(active)}** |",
        f"| New This Week | {len(new_this_week)} |",
        f"| Churned | {len(churned)} |",
        f"| MRR | **${total_mrr:,.2f}/mo** |",
        f"| ARR | ${total_arr:,.2f}/yr |",
        f"",
    ]

    if active:
        lines.append("### Active Clients")
        lines.append("")
        lines.append("| Company | Service | Plan | Monthly Value | Start Date |")
        lines.append("|---------|---------|------|---------------|------------|")
        for c in sorted(active, key=lambda x: x.get("monthly_value", 0), reverse=True):
            company = c.get("company", "Unknown")
            service = c.get("service", "")
            plan = c.get("plan", "")
            value = c.get("monthly_value", 0)
            start = c.get("start_date", "")
            lines.append(f"| {company} | {service} | {plan} | ${value:,.2f} | {start} |")
        lines.append("")

    if new_this_week:
        lines.append("### New This Week 🎉")
        lines.append("")
        for c in new_this_week:
            lines.append(f"- **{c.get('company', 'Unknown')}** — {c.get('service', '')} ({c.get('plan', '')}) | ${c.get('monthly_value', 0):,.2f}/mo")
        lines.append("")

    return "\n".join(lines)


def section_content(monday: datetime.date, sunday: datetime.date) -> str:
    """Generate the content published section."""
    content = load_json(CONTENT_FILE, {"week_of": "", "items": []})
    items = content.get("items", [])

    # This week's content
    week_items = [
        item for item in items
        if monday.isoformat() <= (item.get("date", "")[:10] or "") <= sunday.isoformat()
    ]

    published = [i for i in week_items if i.get("status") == "published"]
    planned = [i for i in week_items if i.get("status") == "planned"]
    in_progress = [i for i in week_items if i.get("status") in ("in_progress", "editing")]

    lines = [
        "## 📹 Content Published",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Published This Week | **{len(published)}** |",
        f"| In Progress | {len(in_progress)} |",
        f"| Planned | {len(planned)} |",
        f"| Week Of | {content.get('week_of', 'N/A')} |",
        f"",
    ]

    if published:
        lines.append("### Published")
        lines.append("")
        for item in published:
            title = item.get("title", "Untitled")
            ctype = item.get("type", "unknown")
            platforms = ", ".join(item.get("platforms", []))
            lines.append(f"- ✅ **{title}** ({ctype}) — {platforms}")
        lines.append("")

    if in_progress:
        lines.append("### In Progress")
        lines.append("")
        for item in in_progress:
            title = item.get("title", "Untitled")
            lines.append(f"- 🔄 {title}")
        lines.append("")

    if planned:
        lines.append("### Coming Up")
        lines.append("")
        for item in planned[:5]:
            title = item.get("title", "Untitled")
            date = item.get("date", "")[:10]
            lines.append(f"- 📅 {date}: {title}")
        lines.append("")

    return "\n".join(lines)


def section_tasks(monday: datetime.date, sunday: datetime.date) -> str:
    """Generate the upcoming tasks section."""
    tasks = load_json(TASKS_FILE, {"tasks": []})

    if isinstance(tasks, dict):
        task_list = tasks.get("tasks", [])
    elif isinstance(tasks, list):
        task_list = tasks
    else:
        task_list = []

    # Categorize tasks
    overdue = []
    due_this_week = []
    upcoming = []
    completed = []

    today = datetime.date.today()
    for task in task_list:
        status = task.get("status", "")
        due_str = task.get("due_date", "")

        if status in ("done", "completed"):
            completed.append(task)
        elif due_str and due_str < today.isoformat():
            overdue.append(task)
        elif due_str and monday.isoformat() <= due_str <= sunday.isoformat():
            due_this_week.append(task)
        else:
            upcoming.append(task)

    lines = [
        "## ✅ Upcoming Tasks",
        "",
        f"| Category | Count |",
        f"|----------|-------|",
        f"| 🔴 Overdue | {len(overdue)} |",
        f"| 🟡 Due This Week | {len(due_this_week)} |",
        f"| 🔵 Upcoming | {len(upcoming)} |",
        f"| ✅ Completed | {len(completed)} |",
        f"",
    ]

    if overdue:
        lines.append("### 🔴 Overdue")
        lines.append("")
        for t in overdue:
            title = t.get("title", "Untitled")
            due = t.get("due_date", "")
            priority = t.get("priority", "normal")
            emoji = "🚨" if priority == "high" else "⚠️"
            lines.append(f"- {emoji} **{title}** (due: {due})")
        lines.append("")

    if due_this_week:
        lines.append("### 🟡 Due This Week")
        lines.append("")
        for t in sorted(due_this_week, key=lambda x: x.get("due_date", "")):
            title = t.get("title", "Untitled")
            due = t.get("due_date", "")
            assignee = t.get("assignee", "")
            lines.append(f"- 📌 **{title}** — {due} {f'({assignee})' if assignee else ''}")
        lines.append("")

    if upcoming:
        lines.append("### 🔵 Upcoming")
        lines.append("")
        for t in sorted(upcoming, key=lambda x: x.get("due_date", "z"))[:5]:
            title = t.get("title", "Untitled")
            due = t.get("due_date", "TBD")
            lines.append(f"- 📋 {title} — {due}")
        lines.append("")

    return "\n".join(lines)


# === FULL DIGEST ===
def generate_digest(week_of: Optional[str] = None) -> str:
    """Generate the full weekly digest as markdown."""
    monday, sunday = get_week_boundaries(week_of)
    today = datetime.date.today()

    header = f"""# 🚀 GoTech Weekly Digest

**Week of {monday.isoformat()} to {sunday.isoformat()}**
*Generated: {today.isoformat()}*

---
"""

    sections = [
        header,
        section_cash(monday, sunday),
        "---",
        "",
        section_leads(monday, sunday),
        "---",
        "",
        section_clients(monday, sunday),
        "---",
        "",
        section_content(monday, sunday),
        "---",
        "",
        section_tasks(monday, sunday),
        "---",
        "",
        "## 🎯 Top Priorities This Week",
        "",
        "1. **Follow up on qualified leads** — Check in with proposal-stage leads",
        "2. **Convert pipeline to clients** — Push deals across the finish line",
        "3. **Post content consistently** — 21 shorts + 7 long-form this week",
        "4. **Update cash forecast** — Reflect new revenue/expenses",
        "5. **Review overdue tasks** — Clear blockers and re-prioritize",
        "",
        "---",
        "*Generated by GoTech Solutions — Daily Digest Script*",
    ]

    return "\n".join(sections)


# === SEND DIGEST ===
def send_digest(digest_md: str, to_addr: str, from_account: str = "gmail") -> bool:
    """Send the digest as an email."""
    # Convert markdown to a simple HTML email
    html_body = markdown_to_html(digest_md)
    subject = f"GoTech Weekly Digest — {datetime.date.today().isoformat()}"

    # Use email-sender.py if available
    sender_script = SCRIPTS_DIR / "email-sender.py"
    if sender_script.exists():
        cmd = [
            sys.executable, str(sender_script),
            "--to", to_addr,
            "--subject", subject,
            "--body", digest_md,
            "--from", from_account,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Digest sent to {to_addr}")
            return True
        else:
            logger.error(f"email-sender.py failed: {result.stderr}")
            return False

    # Fallback: direct SMTP
    logger.info("email-sender.py not found, sending via direct SMTP...")
    import smtplib
    import ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    gmail_user = os.environ.get("GMAIL_USER", "bizrunner@gmail.com")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_password:
        logger.error("GMAIL_APP_PASSWORD not set. Cannot send email.")
        return False

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_user, gmail_password)

            msg = MIMEMultipart("alternative")
            msg["From"] = gmail_user
            msg["To"] = to_addr
            msg["Subject"] = subject
            msg.attach(MIMEText(digest_md, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            server.sendmail(gmail_user, [to_addr], msg.as_string())
            logger.info(f"Digest sent to {to_addr} via direct SMTP")
            return True
    except Exception as e:
        logger.error(f"Failed to send digest: {e}")
        return False


def markdown_to_html(md: str) -> str:
    """Simple markdown to HTML conversion for email."""
    import re

    lines = md.split("\n")
    html_parts = []
    in_table = False
    in_code = False

    for line in stripped:
        stripped = line.strip()

        # Code blocks
        if stripped.startswith("```"):
            if in_code:
                html_parts.append("</code></pre>")
                in_code = False
            else:
                lang = stripped[3:].strip()
                html_parts.append(f'<pre><code class="{lang}">' if lang else "<pre><code>")
                in_code = True
            continue

        if in_code:
            html_parts.append(line.replace("<", "&lt;").replace(">", "&gt;"))
            continue

        # Skip empty lines
        if not stripped:
            html_parts.append("")
            continue

        # Horizontal rule
        if stripped == "---":
            html_parts.append("<hr/>")
            continue

        # Headers
        if stripped.startswith("# "):
            html_parts.append(f"<h1>{stripped[2:]}</h1>")
            continue
        elif stripped.startswith("## "):
            html_parts.append(f"<h2>{stripped[3:]}</h2>")
            continue
        elif stripped.startswith("### "):
            html_parts.append(f"<h3>{stripped[4:]}</h3>")
            continue
        elif stripped.startswith("#### "):
            html_parts.append(f"<h4>{stripped[5:]}</h4>")
            continue

        # Table
        if "|" in stripped and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # Skip separator rows
            if not in_table:
                html_parts.append("<table><thead><tr>")
                for c in cells:
                    c = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', c)
                    c = re.sub(r'\*(.*?)\*', r'<em>\1</em>', c)
                    html_parts.append(f"<th>{c}</th>")
                html_parts.append("</tr></thead><tbody>")
                in_table = True
            else:
                html_parts.append("<tr>")
                for c in cells:
                    c = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', c)
                    c = re.sub(r'\*(.*?)\*', r'<em>\1</em>', c)
                    c = re.sub(r'`(.*?)`', r'<code>\1</code>', c)
                    html_parts.append(f"<td>{c}</td>")
                html_parts.append("</tr>")
            continue
        else:
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False

        # List items
        if stripped.startswith("- ") or stripped.startswith("* "):
            text = stripped[2:]
            text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
            text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
            html_parts.append(f"<li>{text}</li>")
            continue

        # Numbered list
        if re.match(r'^\d+\.\s', stripped):
            text = re.sub(r'^\d+\.\s', '', stripped)
            text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
            text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
            html_parts.append(f"<li>{text}</li>")
            continue

        # Paragraph with inline formatting
        text = stripped
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
        html_parts.append(f"<p>{text}</p>")

    if in_table:
        html_parts.append("</tbody></table>")

    body = "\n".join(html_parts)
    return f"""<!DOCTYPE html>
<html>
<head>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 700px; margin: 0 auto; padding: 20px; }}
h1 {{ color: #1a1a2e; border-bottom: 3px solid #e94560; padding-bottom: 10px; }}
h2 {{ color: #16213e; border-bottom: 1px solid #ddd; padding-bottom: 6px; margin-top: 30px; }}
h3 {{ color: #0f3460; margin-top: 20px; }}
table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
th {{ background: #16213e; color: white; }}
tr:nth-child(even) {{ background: #f8f9fa; }}
hr {{ border: none; border-top: 2px solid #e94560; margin: 30px 0; }}
li {{ margin: 4px 0; }}
strong {{ color: #1a1a2e; }}
blockquote {{ border-left: 4px solid #e94560; padding-left: 16px; color: #555; margin: 20px 0; }}
ol, ul {{ padding-left: 24px; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


# === MAIN ===
def main():
    parser = argparse.ArgumentParser(
        description="GoTech Weekly Digest — Generate and send business digests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 daily-digest.py                     # Print digest to stdout
  python3 daily-digest.py --send              # Send to default recipient
  python3 daily-digest.py --send --to boss@example.com
  python3 daily-digest.py --week 2026-06-19   # For a specific week
  python3 daily-digest.py --send --from gmail
        """,
    )

    parser.add_argument(
        "--send",
        action="store_true",
        help="Send the digest via email instead of printing to stdout",
    )
    parser.add_argument(
        "--to",
        help=f"Recipient email (default: {DIGEST_RECIPIENT})",
    )
    parser.add_argument(
        "--from",
        dest="from_account",
        choices=["gmail", "outlook"],
        default="gmail",
        help="Email account to send from (default: gmail)",
    )
    parser.add_argument(
        "--week",
        help="Generate digest for a specific week (YYYY-MM-DD format, any day in the week)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save digest to reports/ directory",
    )

    args = parser.parse_args()

    # Generate digest
    logger.info("Generating weekly digest...")
    digest = generate_digest(args.week)

    if args.save:
        today = datetime.date.today().isoformat()
        reports_dir = STARTUP_DIR / "reports"
        reports_dir.mkdir(exist_ok=True)
        filename = f"weekly-digest-{today}.md"
        filepath = reports_dir / filename
        with open(filepath, "w") as f:
            f.write(digest)
        logger.info(f"Digest saved to {filepath}")

    if args.send:
        recipient = args.to or DIGEST_RECIPIENT
        success = send_digest(digest, recipient, args.from_account)
        if success:
            logger.info(f"Digest sent successfully to {recipient}")
        else:
            logger.error("Failed to send digest")
            sys.exit(1)
    else:
        print(digest)


if __name__ == "__main__":
    main()
