#!/usr/bin/env python3
"""
Weekly Accountability Report Generator for GoTechSolutions

Generates a comprehensive weekly accountability report including:
- Revenue tracking vs 60-day plan targets
- Outreach and conversion metrics
- Cash position and MRR growth
- Accountability scoring (0-100)
- Action items for next week
- Integration with 60-day-revenue-plan.md targets

Usage:
    python weekly-accountability.py --week 1
    python weekly-accountability.py --week 1 --save
    python weekly-accountability.py --week 1 --send --save
    python weekly-accountability.py --week 1 --dry-run
    python weekly-accountability.py --init-sample-data
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
TEMPLATES_DIR = BASE_DIR / "templates"
PLAN_FILE = BASE_DIR / "60-day-revenue-plan.md"
EMAIL_SENDER = BASE_DIR / "scripts" / "email-sender.py"

# Plan start date (June 24, 2026 = Day 1)
PLAN_START = date(2026, 6, 24)

# ─── 60-Day Plan Weekly Targets (from plan Section 4) ───────────────────────
# Week number: (monday_date, phase, new_clients, avg_ticket, mrr_added, cum_mrr, cash_in)
PLAN_WEEKLY_TARGETS = {
    1:  {"monday": "2026-06-24", "phase": "Foundation",   "new_clients": 8,  "avg_ticket": 400, "mrr_added": 3200,  "cum_mrr": 3200,   "cash_in": 3200},
    2:  {"monday": "2026-07-01", "phase": "Launch",       "new_clients": 10, "avg_ticket": 450, "mrr_added": 4500,  "cum_mrr": 7700,   "cash_in": 7700},
    3:  {"monday": "2026-07-08", "phase": "Launch",       "new_clients": 12, "avg_ticket": 500, "mrr_added": 6000,  "cum_mrr": 13700,  "cash_in": 13700},
    4:  {"monday": "2026-07-15", "phase": "Scale",       "new_clients": 15, "avg_ticket": 550, "mrr_added": 8250,  "cum_mrr": 21950,  "cash_in": 21950},
    5:  {"monday": "2026-07-22", "phase": "Scale",       "new_clients": 18, "avg_ticket": 600, "mrr_added": 10800, "cum_mrr": 32750,  "cash_in": 32750},
    6:  {"monday": "2026-08-01", "phase": "Accelerate",  "new_clients": 22, "avg_ticket": 650, "mrr_added": 14300, "cum_mrr": 47050,  "cash_in": 47050},
    7:  {"monday": "2026-08-08", "phase": "Accelerate",  "new_clients": 25, "avg_ticket": 700, "mrr_added": 17500, "cum_mrr": 64550,  "cash_in": 64550},
    8:  {"monday": "2026-08-16", "phase": "Sprint",      "new_clients": 22, "avg_ticket": 750, "mrr_added": 16500, "cum_mrr": 81050,  "cash_in": 81050},
    9:  {"monday": "2026-08-24", "phase": "Sprint",      "new_clients": 18, "avg_ticket": 800, "mrr_added": 14400, "cum_mrr": 95450,  "cash_in": 95450},
    10: {"monday": "2026-09-01", "phase": "LAUNCH",      "new_clients": 10, "avg_ticket": 500, "mrr_added": 5000,  "cum_mrr": 100450, "cash_in": 100450},
}

# Funnel conversion targets (from plan Section 9)
FUNNEL_TARGETS = {
    "outreach_to_reply": 0.10,   # 10%
    "reply_to_call": 0.30,      # 30%
    "call_to_proposal": 0.40,   # 40%
    "proposal_to_close": 0.30,  # 30%
}

# Scoring weights
SCORING_WEIGHTS = {
    "outreach_consistency": 0.25,
    "conversion_rate": 0.25,
    "revenue_vs_target": 0.30,
    "pipeline_growth": 0.20,
}

# Burn rate by month (from plan Section 10)
BURN_RATE = {
    "June": 2000,
    "July": 3000,
    "August": 5000,
    "September": 8000,
}


# ─── Utility Functions ───────────────────────────────────────────────────────

def _parse_date(date_str: str) -> datetime | None:
    """Parse a date string in various ISO formats."""
    if not date_str:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
    # Try date-only
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def week_number_from_date(d: date | datetime) -> int:
    """Get ISO week number from a date."""
    if isinstance(d, datetime):
        d = d.date()
    return d.isocalendar()[1]


def get_week_dates(week_number: int, year: int | None = None) -> tuple[datetime, datetime]:
    """Get Monday and Sunday dates for a given ISO week number."""
    if year is None:
        year = datetime.now().year
    # ISO week: Monday is day 1
    monday = datetime.strptime(f"{year}-W{week_number:02d}-1", "%G-W%V-%u")
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_plan_week_for_date(target_date: date) -> int:
    """Determine which plan week a given date falls in (1-10)."""
    delta = (target_date - PLAN_START).days
    if delta < 0:
        return 0  # Before plan start
    week = (delta // 7) + 1
    return min(week, 10)


def format_currency(amount: float) -> str:
    """Format a number as USD currency."""
    if amount >= 1000000:
        return f"${amount:,.0f}"
    return f"${amount:,.2f}"


def format_pct(val: float) -> str:
    """Format a decimal as percentage."""
    return f"{val:.1f}%"


def variance_indicator(actual: float, target: float, lower_is_better: bool = False) -> str:
    """Return colored indicator for variance."""
    if target == 0:
        return "⚪"
    diff = actual - target
    if lower_is_better:
        if diff <= 0:
            return "🟢"
        elif diff <= target * 0.1:
            return "🟡"
        else:
            return "🔴"
    else:
        if diff >= 0:
            return "🟢"
        elif diff >= -target * 0.1:
            return "🟡"
        else:
            return "🔴"


# ─── Data Loading ────────────────────────────────────────────────────────────

def load_json(filepath: Path) -> dict | list:
    """Load a JSON file, returning empty dict if not found."""
    if not filepath.exists():
        return {}
    with open(filepath, "r") as f:
        return json.load(f)


def load_all_data(data_dir: Path) -> dict:
    """Load all data files from the data directory."""
    return {
        "revenue_log": load_json(data_dir / "revenue_log.json"),
        "cash": load_json(data_dir / "cash.json"),
        "leads": load_json(data_dir / "leads.json"),
        "clients": load_json(data_dir / "clients.json"),
        "metrics": load_json(data_dir / "metrics.json"),
        "deals": load_json(data_dir / "deals.json"),
    }


def filter_data_by_week(data: dict, week_number: int, year: int | None = None) -> dict:
    """Filter all data sources to only include entries from the target week."""
    monday, sunday = get_week_dates(week_number, year)
    monday_date = monday.date()
    sunday_date = sunday.date()

    # ── Revenue log ──
    revenue_log = data.get("revenue_log", {})
    revenue_entries = []
    if isinstance(revenue_log, list):
        revenue_entries = revenue_log
    elif isinstance(revenue_log, dict):
        revenue_entries = revenue_log.get("entries", revenue_log.get("transactions", []))

    week_revenue = []
    for entry in revenue_entries:
        if isinstance(entry, dict) and "date" in entry:
            entry_date = _parse_date(entry["date"])
            if entry_date and monday_date <= entry_date.date() <= sunday_date:
                week_revenue.append(entry)

    # ── Leads ──
    leads_data = data.get("leads", {})
    all_leads = leads_data if isinstance(leads_data, list) else leads_data.get("leads", [])
    week_leads = []
    for lead in all_leads:
        if isinstance(lead, dict):
            date_str = lead.get("created_at") or lead.get("date_added") or lead.get("date")
            if date_str:
                lead_date = _parse_date(date_str)
                if lead_date and monday_date <= lead_date.date() <= sunday_date:
                    week_leads.append(lead)

    # ── Deals ──
    deals_data = data.get("deals", {})
    all_deals = deals_data if isinstance(deals_data, list) else deals_data.get("deals", [])
    week_deals = []
    for deal in all_deals:
        if isinstance(deal, dict):
            date_str = deal.get("created_at") or deal.get("date") or deal.get("closed_date")
            if date_str:
                deal_date = _parse_date(date_str)
                if deal_date and monday_date <= deal_date.date() <= sunday_date:
                    week_deals.append(deal)

    # ── Cash (latest position) ──
    cash_data = data.get("cash", {})
    latest_cash = {}
    if isinstance(cash_data, list) and cash_data:
        # Find latest by date
        dated = [c for c in cash_data if "date" in c]
        if dated:
            latest_cash = max(dated, key=lambda x: x.get("date", ""))
        else:
            latest_cash = cash_data[-1]
    elif isinstance(cash_data, dict):
        latest_cash = cash_data

    # ── Metrics (closest snapshot at or before this week) ──
    metrics_data = data.get("metrics", {})
    latest_metrics = {}
    if isinstance(metrics_data, dict) and "snapshots" in metrics_data:
        snapshots = metrics_data["snapshots"]
        for snap in reversed(snapshots):
            snap_date = _parse_date(snap.get("date", ""))
            if snap_date and snap_date.date() <= sunday_date:
                latest_metrics = snap
                break
        if not latest_metrics and snapshots:
            latest_metrics = snapshots[-1]
    elif isinstance(metrics_data, list) and metrics_data:
        latest_metrics = metrics_data[-1]
    elif isinstance(metrics_data, dict):
        latest_metrics = metrics_data

    # ── Clients ──
    clients_data = data.get("clients", {})
    clients_list = clients_data if isinstance(clients_data, list) else clients_data.get("clients", [])

    return {
        "monday": monday,
        "sunday": sunday,
        "week_number": week_number,
        "week_revenue": week_revenue,
        "cash": latest_cash,
        "all_leads": all_leads,
        "week_leads": week_leads,
        "week_deals": week_deals,
        "all_clients": clients_list,
        "metrics": latest_metrics,
        "all_metrics": metrics_data,
    }


# ─── Calculations ────────────────────────────────────────────────────────────

def calc_total_revenue(week_revenue: list[dict]) -> float:
    """Calculate total revenue from week's revenue entries."""
    total = 0.0
    for entry in week_revenue:
        amount = entry.get("amount", entry.get("revenue", entry.get("value", 0)))
        if isinstance(amount, (int, float)):
            total += amount
    return total


def calc_outreach_metrics(week_leads: list[dict], week_deals: list[dict], metrics: dict) -> dict:
    """
    Calculate outreach metrics from week's leads and deals.
    Handles multiple data formats and falls back to metrics.json if available.
    """
    result = {
        "sent": 0,
        "replies": 0,
        "calls": 0,
        "proposals": 0,
        "closes": 0,
    }

    # Count from leads by stage
    for lead in week_leads:
        stage = (lead.get("stage") or lead.get("status") or "new").lower()
        if stage in ("won", "closed", "client", "signed"):
            result["sent"] += 1
            result["replies"] += 1
            result["calls"] += 1
            result["proposals"] += 1
            result["closes"] += 1
        elif stage in ("proposal_sent", "proposal", "sent_proposal"):
            result["sent"] += 1
            result["replies"] += 1
            result["calls"] += 1
            result["proposals"] += 1
        elif stage in ("call_done", "call_completed", "demo_done", "meeting", "call_booked", "call_scheduled"):
            result["sent"] += 1
            result["replies"] += 1
            result["calls"] += 1
        elif stage in ("replied", "responded", "interested", "contacted", "sent", "outreach", "emailed", "messaged"):
            result["sent"] += 1
            result["replies"] += 1
        elif stage in ("new", "lead", ""):
            result["sent"] += 1

    # Also count from deals
    for deal in week_deals:
        stage = (deal.get("stage") or deal.get("status") or "").lower()
        if stage in ("won", "closed"):
            result["closes"] += 1
            result["proposals"] += 1
            result["calls"] += 1
            result["replies"] += 1
            result["sent"] += 1
        elif stage in ("proposal", "sent"):
            result["proposals"] += 1
            result["calls"] += 1
            result["replies"] += 1
            result["sent"] += 1

    # Fallback: if metrics.json has explicit outreach data, use it
    if result["sent"] == 0 and isinstance(metrics, dict):
        for key in result:
            if key in metrics and isinstance(metrics[key], (int, float)):
                result[key] = int(metrics[key])

    return result


def calc_conversion_rates(metrics: dict) -> dict:
    """Calculate conversion rates between funnel stages."""
    sent = metrics["sent"]
    replies = metrics["replies"]
    calls = metrics["calls"]
    closes = metrics["closes"]

    return {
        "outreach_to_reply": replies / sent if sent > 0 else 0.0,
        "reply_to_call": calls / replies if replies > 0 else 0.0,
        "call_to_close": closes / calls if calls > 0 else 0.0,
        "overall_conversion": closes / sent if sent > 0 else 0.0,
    }


def calc_cash_position(cash_data: dict) -> tuple[float, float]:
    """Get current cash position and change from starting/previous."""
    if not cash_data:
        return 0.0, 0.0

    current = cash_data.get("balance", cash_data.get("current", 0))
    starting = cash_data.get("starting_balance", cash_data.get("previous_balance", 0))

    try:
        current = float(current)
        starting = float(starting)
    except (ValueError, TypeError):
        current = 0.0
        starting = 0.0

    return current, current - starting


def calc_mrr(clients_list: list) -> tuple[float, int, int]:
    """
    Calculate Monthly Recurring Revenue from active clients.
    Returns (mrr, active_count, total_count).
    """
    if not isinstance(clients_list, list):
        return 0.0, 0, 0

    mrr = 0.0
    active_count = 0
    total_count = len(clients_list)

    for client in clients_list:
        if isinstance(client, dict):
            status = client.get("status", "active").lower()
            if status in ("active", "signed", "client"):
                monthly = client.get("monthly_value", client.get("mrr", client.get("value", 0)))
                try:
                    mrr += float(monthly)
                    active_count += 1
                except (ValueError, TypeError):
                    continue

    return mrr, active_count, total_count


def calc_pipeline_value(all_leads: list) -> float:
    """Calculate total pipeline value from all leads."""
    total = 0.0
    for lead in all_leads:
        if isinstance(lead, dict):
            val = lead.get("estimated_value", lead.get("value", lead.get("deal_value", 0)))
            try:
                total += float(val)
            except (ValueError, TypeError):
                continue
    return total


def calc_accountability_score(
    outreach_metrics: dict,
    conversion_rates: dict,
    revenue: float,
    plan_targets: dict,
    week_leads_count: int,
) -> tuple[float, dict]:
    """
    Calculate accountability score (0-100) based on weighted components.
    Returns total score and breakdown.
    """
    breakdown = {}

    # 1. Outreach consistency (25%) — did we hit outreach target?
    # Estimate target outreach from plan: new_clients / overall_conversion_rate
    target_outreach = max(plan_targets["new_clients"] / 0.0036, 50)  # min 50/week
    outreach_ratio = min(outreach_metrics["sent"] / target_outreach, 1.5) / 1.5
    breakdown["outreach_consistency"] = round(outreach_ratio * 100, 1)

    # 2. Conversion rate vs target (25%)
    target_ocr = FUNNEL_TARGETS["outreach_to_reply"]
    target_rtc = FUNNEL_TARGETS["reply_to_call"]
    target_ctc = FUNNEL_TARGETS["proposal_to_close"]

    actual_ocr = conversion_rates["outreach_to_reply"]
    actual_rtc = conversion_rates["reply_to_call"]
    actual_ctc = conversion_rates["call_to_close"]

    ocr_score = min(actual_ocr / target_ocr, 1.5) / 1.5 if target_ocr > 0 else 0
    rtc_score = min(actual_rtc / target_rtc, 1.5) / 1.5 if target_rtc > 0 else 0
    ctc_score = min(actual_ctc / target_ctc, 1.5) / 1.5 if target_ctc > 0 else 0

    conversion_combined = ocr_score * 0.4 + rtc_score * 0.3 + ctc_score * 0.3
    breakdown["conversion_rate"] = round(max(0, conversion_combined) * 100, 1)

    # 3. Revenue vs target (30%)
    revenue_ratio = min(revenue / max(plan_targets["mrr_added"], 1), 1.5) / 1.5
    breakdown["revenue_vs_target"] = round(revenue_ratio * 100, 1)

    # 4. Pipeline growth (20%) — new leads vs target
    target_leads = plan_targets.get("new_clients", 5) * 3  # 3x leads-to-clients ratio
    pipeline_ratio = min(week_leads_count / max(target_leads, 1), 1.5) / 1.5
    breakdown["pipeline_growth"] = round(pipeline_ratio * 100, 1)

    # Weighted total
    total = (
        breakdown["outreach_consistency"] * SCORING_WEIGHTS["outreach_consistency"]
        + breakdown["conversion_rate"] * SCORING_WEIGHTS["conversion_rate"]
        + breakdown["revenue_vs_target"] * SCORING_WEIGHTS["revenue_vs_target"]
        + breakdown["pipeline_growth"] * SCORING_WEIGHTS["pipeline_growth"]
    )
    return round(min(total, 100), 1), breakdown


def get_score_label(score: float) -> tuple[str, str]:
    """Get emoji + label for score."""
    if score >= 90:
        return "🟢", "EXCELLENT"
    elif score >= 75:
        return "🟡", "GOOD"
    elif score >= 60:
        return "🟠", "NEEDS IMPROVEMENT"
    else:
        return "🔴", "CRITICAL"


# ─── Plan Targets ────────────────────────────────────────────────────────────

def get_plan_targets(week_number: int) -> dict:
    """Get the plan targets for a given week."""
    if week_number in PLAN_WEEKLY_TARGETS:
        return PLAN_WEEKLY_TARGETS[week_number]
    # Extrapolate for weeks beyond plan
    last = PLAN_WEEKLY_TARGETS[10]
    return {
        "monday": (date(2026, 9, 1) + timedelta(weeks=week_number - 10)).isoformat(),
        "phase": "Growth",
        "new_clients": 10,
        "avg_ticket": 500,
        "mrr_added": 5000,
        "cum_mrr": last["cum_mrr"] + 5000 * (week_number - 10),
        "cash_in": last["cash_in"] + 5000 * (week_number - 10),
    }


def get_cumulative_targets(up_to_week: int) -> dict:
    """Get cumulative targets up to a given week."""
    total_mrr = 0
    total_clients = 0
    total_cash = 0
    for w in range(1, min(up_to_week, 10) + 1):
        t = PLAN_WEEKLY_TARGETS[w]
        total_mrr += t["mrr_added"]
        total_clients += t["new_clients"]
        total_cash += t["cash_in"]
    return {
        "cum_mrr": total_mrr,
        "cum_clients": total_clients,
        "cum_cash": total_cash,
    }


# ─── Report Generation ──────────────────────────────────────────────────────

def generate_report(
    week_data: dict,
    plan_targets: dict,
    cumulative_targets: dict,
    outreach_metrics: dict,
    conversion_rates: dict,
    cash_current: float,
    cash_change: float,
    mrr: float,
    active_clients: int,
    total_clients: int,
    pipeline_value: float,
    score: float,
    score_breakdown: dict,
) -> str:
    """Generate the full markdown report."""
    monday = week_data["monday"]
    sunday = week_data["sunday"]
    week_number = week_data["week_number"]
    total_revenue = calc_total_revenue(week_data["week_revenue"])
    week_leads_count = len(week_data["week_leads"])
    score_emoji, score_label = get_score_label(score)

    # Extract wins and lessons
    wins = []
    lessons = []
    for entry in week_data["week_revenue"]:
        if isinstance(entry, dict):
            if "win" in entry:
                wins.append(entry["win"])
            if "lesson" in entry:
                lessons.append(entry["lesson"])

    # Also check metrics
    metrics = week_data.get("metrics", {})
    if isinstance(metrics, dict):
        wins = wins or metrics.get("wins", [])[:3]
        lessons = lessons or metrics.get("lessons", [])[:3]

    # Pad to 3
    while len(wins) < 3:
        wins.append("—")
    while len(lessons) < 3:
        lessons.append("—")

    # Determine phase
    phase = plan_targets.get("phase", "Growth")

    # Calculate plan comparison
    plan_mrr_added = plan_targets.get("mrr_added", 0)
    plan_new_clients = plan_targets.get("new_clients", 0)
    plan_cash_in = plan_targets.get("cash_in", 0)

    # Cumulative plan targets
    cum_mrr_target = cumulative_targets["cum_mrr"]
    cum_clients_target = cumulative_targets["cum_clients"]

    # Days elapsed
    days_into_plan = (monday.date() - PLAN_START).days
    total_plan_days = 69
    pct_time_elapsed = min(days_into_plan / total_plan_days * 100, 100)

    # ── Build action items ──
    action_items = []
    if outreach_metrics["sent"] < plan_new_clients * 5:
        deficit = plan_new_clients * 5 - outreach_metrics["sent"]
        action_items.append(f"⚡ Send {deficit:.0f} more outreach messages to hit pipeline target")
    if conversion_rates["outreach_to_reply"] < FUNNEL_TARGETS["outreach_to_reply"]:
        action_items.append("📧 A/B test outreach templates — reply rate below 10% target")
    if conversion_rates["reply_to_call"] < FUNNEL_TARGETS["reply_to_call"]:
        action_items.append("📞 Add more value-first follow-ups — reply-to-call rate needs lift")
    if conversion_rates["call_to_close"] < FUNNEL_TARGETS["proposal_to_close"]:
        action_items.append("💰 Practice closing techniques or improve proposal quality")
    if total_revenue < plan_mrr_added * 0.7:
        action_items.append("🚨 Revenue critically behind — focus on closing existing pipeline")
    if week_leads_count < plan_new_clients * 2:
        action_items.append("🔍 Increase lead generation — need more top-of-funnel")
    if not action_items:
        action_items.append("🎯 Maintain momentum — scale what's working")
        action_items.append("📈 Push for 120% of targets to build buffer for sprint phase")

    # ── Next week targets ──
    next_targets = get_plan_targets(week_number + 1)
    next_week_items = [
        f"Send ~{next_targets['new_clients'] * 5} outreach messages",
        f"Book {max(next_targets['new_clients'] // 2, 2)} calls",
        f"Close {next_targets['new_clients']} deals",
        f"Generate {format_currency(next_targets['mrr_added'])} in new MRR",
    ]

    # ── Build report ──
    report = f"""# 📊 Weekly Accountability Report — Week {week_number}

**GoTechSolutions** | **Phase:** {phase}
**Period:** {monday.strftime("%B %d")} – {sunday.strftime("%B %d, %Y")}
**Day {max(days_into_plan, 1)} of {total_plan_days}** ({pct_time_elapsed:.0f}% of plan elapsed)
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

## 🏆 Accountability Score

{score_emoji} **{score}/100** — {score_label}

| Component | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Outreach Consistency | {score_breakdown['outreach_consistency']:.0f}% | 25% | {score_breakdown['outreach_consistency'] * 0.25:.1f} |
| Conversion Rate | {score_breakdown['conversion_rate']:.0f}% | 25% | {score_breakdown['conversion_rate'] * 0.25:.1f} |
| Revenue vs Target | {score_breakdown['revenue_vs_target']:.0f}% | 30% | {score_breakdown['revenue_vs_target'] * 0.30:.1f} |
| Pipeline Growth | {score_breakdown['pipeline_growth']:.0f}% | 20% | {score_breakdown['pipeline_growth'] * 0.20:.1f} |
| **TOTAL** | | | **{score:.1f}** |

---

## 💰 Revenue This Week

| Metric | Actual | Plan | Variance |
|--------|--------|------|----------|
| Revenue (MRR Added) | {format_currency(total_revenue)} | {format_currency(plan_mrr_added)} | {variance_indicator(total_revenue, plan_mrr_added)} {format_currency(total_revenue - plan_mrr_added)} |
| Cumulative MRR | {format_currency(mrr)} | {format_currency(cum_mrr_target)} | {variance_indicator(mrr, cum_mrr_target)} {format_currency(mrr - cum_mrr_target)} |

**Gap to Week {week_number} Target:** {format_currency(max(plan_mrr_added - total_revenue, 0))}
**Gap to Cumulative Target:** {format_currency(max(cum_mrr_target - mrr, 0))}

---

## 📈 Cash Position

| Metric | Value |
|--------|-------|
| Current Cash | {format_currency(cash_current)} |
| Weekly Change | {format_currency(cash_change)} {'📈' if cash_change >= 0 else '📉'} |
| Plan Cash Target (Cumulative) | {format_currency(cumulative_targets['cum_cash'])} |

---

## 👥 Clients

| Metric | Actual | Plan | Variance |
|--------|--------|------|----------|
| Active Clients | {active_clients} | {cum_clients_target} | {variance_indicator(active_clients, cum_clients_target)} {active_clients - cum_clients_target:+d} |
| MRR | {format_currency(mrr)} | {format_currency(cum_mrr_target)} | {variance_indicator(mrr, cum_mrr_target)} |
| Pipeline Value | {format_currency(pipeline_value)} | — | — |

---

## 📊 Outreach & Funnel Metrics

| Metric | Actual | Target | Variance |
|--------|--------|--------|----------|
| Outreach Sent | {outreach_metrics['sent']} | ~{plan_new_clients * 5} | {outreach_metrics['sent'] - plan_new_clients * 5:+d} |
| Replies | {outreach_metrics['replies']} | — | — |
| Calls Booked | {outreach_metrics['calls']} | ~{max(plan_new_clients // 2, 1)} | {outreach_metrics['calls'] - max(plan_new_clients // 2, 1):+d} |
| Proposals Sent | {outreach_metrics['proposals']} | — | — |
| Closes | {outreach_metrics['closes']} | {plan_new_clients} | {variance_indicator(outreach_metrics['closes'], plan_new_clients)} {outreach_metrics['closes'] - plan_new_clients:+d} |

---

## 🔄 Conversion Rates

| Funnel Stage | Actual | Target | Status |
|-------------|--------|--------|--------|
| Outreach → Reply | {format_pct(conversion_rates['outreach_to_reply'])} | {format_pct(FUNNEL_TARGETS['outreach_to_reply'])} | {'✅' if conversion_rates['outreach_to_reply'] >= FUNNEL_TARGETS['outreach_to_reply'] else '❌'} |
| Reply → Call | {format_pct(conversion_rates['reply_to_call'])} | {format_pct(FUNNEL_TARGETS['reply_to_call'])} | {'✅' if conversion_rates['reply_to_call'] >= FUNNEL_TARGETS['reply_to_call'] else '❌'} |
| Call → Close | {format_pct(conversion_rates['call_to_close'])} | {format_pct(FUNNEL_TARGETS['proposal_to_close'])} | {'✅' if conversion_rates['call_to_close'] >= FUNNEL_TARGETS['proposal_to_close'] else '❌'} |
| **Overall** | **{format_pct(conversion_rates['overall_conversion'])}** | **0.36%** | {'✅' if conversion_rates['overall_conversion'] >= 0.0036 else '❌'} |

---

## 🏅 Top 3 Wins of the Week

1. **{wins[0]}**
2. **{wins[1]}**
3. **{wins[2]}**

---

## 📚 Top 3 Lessons Learned

1. **{lessons[0]}**
2. **{lessons[1]}**
3. **{lessons[2]}**

---

## 🎯 Next Week Targets (Week {week_number + 1})

1. {next_week_items[0]}
2. {next_week_items[1]}
3. {next_week_items[2]}
4. {next_week_items[3]}

---

## ⚡ Action Items

"""
    for i, item in enumerate(action_items, 1):
        report += f"{i}. {item}\n"

    report += f"""
---

## 📋 60-Day Plan Progress

| Week | Phase | Plan MRR Added | Plan Cum MRR | Status |
|------|-------|---------------|--------------|--------|
"""

    # Show progress for each week up to current
    running_mrr = 0
    for w in range(1, min(week_number, 10) + 1):
        t = PLAN_WEEKLY_TARGETS[w]
        running_mrr += t["mrr_added"]
        status = "✅" if w < week_number else ("🔵 Current" if w == week_number else "⬜")
        report += f"| {w} | {t['phase']} | {format_currency(t['mrr_added'])} | {format_currency(running_mrr)} | {status} |\n"

    if week_number >= 10:
        report += f"| **TOTAL** | | **{format_currency(100450)}** | | 🎯 |\n"

    report += f"""
---

## 📊 Plan vs Actual Summary

| Metric | Plan (End of W{week_number}) | Actual | Variance |
|--------|-----|--------|----------|
| MRR | {format_currency(cum_mrr_target)} | {format_currency(mrr)} | {variance_indicator(mrr, cum_mrr_target)} {format_currency(mrr - cum_mrr_target)} |
| Clients | {cum_clients_target} | {active_clients} | {variance_indicator(active_clients, cum_clients_target)} {active_clients - cum_clients_target:+d} |
| Revenue This Week | {format_currency(plan_mrr_added)} | {format_currency(total_revenue)} | {variance_indicator(total_revenue, plan_mrr_added)} {format_currency(total_revenue - plan_mrr_added)} |

---

*Report generated by GoTechSolutions Weekly Accountability System*
*Plan reference: 60-day-revenue-plan.md*
*Next review: {sunday.strftime("%B %d, %Y")}*
"""

    return report


# ─── Email & Save Functions ─────────────────────────────────────────────────

def send_report_email(report: str, week_number: int, dry_run: bool = False) -> bool:
    """Send the report via email using email-sender.py."""
    if not EMAIL_SENDER.exists():
        print(f"❌ email-sender.py not found at {EMAIL_SENDER}")
        return False

    subject = f"📊 GoTechSolutions — Weekly Accountability Report W{week_number}"

    # Build command
    cmd = [
        sys.executable, str(EMAIL_SENDER),
        "--to", os.environ.get("REPORT_EMAIL_TO", os.environ.get("GMAIL_USER", "")),
        "--subject", subject,
        "--body", report,
    ]
    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
        if result.returncode == 0:
            print(f"✅ Report emailed successfully")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ Email send failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Failed to run email-sender.py: {e}")
        return False


def save_report(report: str, week_number: int, reports_dir: Path) -> Path:
    """Save the report to the reports directory."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"weekly-accountability-W{week_number:02d}.md"
    filepath = reports_dir / filename
    with open(filepath, "w") as f:
        f.write(report)
    print(f"✅ Report saved to {filepath}")
    return filepath


# ─── Sample Data Generator ──────────────────────────────────────────────────

def create_sample_data(data_dir: Path):
    """Create sample data files for testing."""
    data_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()

    # Revenue log — entries for the current week
    sample_revenue = {
        "entries": [
            {
                "date": (now - timedelta(days=6)).isoformat(),
                "amount": 1200,
                "source": "Client A - Go Live Stream",
                "win": "Closed first Go Live Stream client",
                "service": "go-live",
            },
            {
                "date": (now - timedelta(days=4)).isoformat(),
                "amount": 800,
                "source": "Client B - Communications",
                "win": "Signed Communications package",
                "service": "comms",
            },
            {
                "date": (now - timedelta(days=2)).isoformat(),
                "amount": 1500,
                "source": "Client C - AI Ops",
                "win": "New AI Operations contract",
                "service": "ai-ops",
            },
            {
                "date": (now - timedelta(days=1)).isoformat(),
                "amount": 0,
                "source": "Client D - Discovery call completed",
                "lesson": "Cold outreach works better with personalized subject lines",
            },
        ],
    }

    # Cash position
    sample_cash = {
        "balance": 4500.0,
        "starting_balance": 1000.0,
        "transactions": [
            {"date": (now - timedelta(days=6)).isoformat(), "amount": 1200, "balance": 2200.0, "note": "Client A payment"},
            {"date": (now - timedelta(days=4)).isoformat(), "amount": 800, "balance": 3000.0, "note": "Client B payment"},
            {"date": (now - timedelta(days=2)).isoformat(), "amount": 1500, "balance": 4500.0, "note": "Client C payment"},
        ],
        "start_date": "2026-06-24",
    }

    # Leads
    sample_leads = {
        "leads": [
            {"id": "L001", "name": "Prospect Alpha", "company": "Alpha Inc", "email": "alpha@test.com", "source": "linkedin", "interest": "ai-ops", "estimated_value": 500, "stage": "won", "score": 85, "created_at": (now - timedelta(days=6)).isoformat(), "notes": ["Warm lead from LinkedIn"]},
            {"id": "L002", "name": "Prospect Beta", "company": "Beta LLC", "email": "beta@test.com", "source": "cold-email", "interest": "go-live", "estimated_value": 400, "stage": "call_booked", "score": 70, "created_at": (now - timedelta(days=5)).isoformat(), "notes": []},
            {"id": "L003", "name": "Prospect Gamma", "company": "Gamma Co", "email": "gamma@test.com", "source": "referral", "interest": "comms", "estimated_value": 300, "stage": "replied", "score": 60, "created_at": (now - timedelta(days=4)).isoformat(), "notes": ["Referred by Client A"]},
            {"id": "L004", "name": "Prospect Delta", "company": "Delta Corp", "email": "delta@test.com", "source": "linkedin", "interest": "cro", "estimated_value": 750, "stage": "proposal_sent", "score": 75, "created_at": (now - timedelta(days=3)).isoformat(), "notes": []},
            {"id": "L005", "name": "Prospect Epsilon", "company": "Epsilon Ltd", "email": "epsilon@test.com", "source": "cold-email", "interest": "go-live", "estimated_value": 400, "stage": "sent", "score": 40, "created_at": (now - timedelta(days=2)).isoformat(), "notes": []},
            {"id": "L006", "name": "Prospect Zeta", "company": "Zeta Group", "email": "zeta@test.com", "source": "webinar", "interest": "bundle", "estimated_value": 1750, "stage": "call_done", "score": 80, "created_at": (now - timedelta(days=1)).isoformat(), "notes": ["High-value prospect"]},
        ],
        "stats": {"total": 6, "by_source": {"linkedin": 2, "cold-email": 2, "referral": 1, "webinar": 1}},
    }

    # Clients
    sample_clients = {
        "clients": [
            {"name": "Client A", "status": "active", "monthly_value": 400, "since": "2026-06-24", "service": "go-live"},
            {"name": "Client B", "status": "active", "monthly_value": 300, "since": "2026-06-25", "service": "comms"},
            {"name": "Client C", "status": "active", "monthly_value": 500, "since": "2026-06-26", "service": "ai-ops"},
        ]
    }

    # Metrics snapshot
    sample_metrics = {
        "snapshots": [
            {
                "date": now.strftime("%Y-%m-%d"),
                "timestamp": now.isoformat(),
                "cash_balance": 4500.0,
                "total_leads": 6,
                "new_leads_today": 1,
                "qualified_leads": 4,
                "active_clients": 3,
                "mrr": 1200.0,
                "arr": 14400.0,
                "pipeline_value": 3150.0,
                "wins": ["Closed first Go Live Stream client", "Signed Communications package", "New AI Operations contract"],
                "lessons": ["Cold outreach works better with personalized subject lines", "Referrals convert 3x better than cold"],
            }
        ]
    }

    # Deals
    sample_deals = {
        "deals": [
            {"id": "D001", "client": "Client A", "service": "go-live", "value": 400, "stage": "won", "created_at": (now - timedelta(days=6)).isoformat()},
            {"id": "D002", "client": "Client B", "service": "comms", "value": 300, "stage": "won", "created_at": (now - timedelta(days=4)).isoformat()},
            {"id": "D003", "client": "Client C", "service": "ai-ops", "value": 500, "stage": "won", "created_at": (now - timedelta(days=2)).isoformat()},
            {"id": "D004", "client": "Prospect Delta", "service": "cro", "value": 750, "stage": "proposal_sent", "created_at": (now - timedelta(days=3)).isoformat()},
            {"id": "D005", "client": "Prospect Zeta", "service": "bundle", "value": 1750, "stage": "call_done", "created_at": (now - timedelta(days=1)).isoformat()},
        ]
    }

    files = {
        "revenue_log.json": sample_revenue,
        "cash.json": sample_cash,
        "leads.json": sample_leads,
        "clients.json": sample_clients,
        "metrics.json": sample_metrics,
        "deals.json": sample_deals,
    }

    for filename, content in files.items():
        filepath = data_dir / filename
        with open(filepath, "w") as f:
            json.dump(content, f, indent=2, default=str)
        print(f"  Created {filepath}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly accountability report for GoTechSolutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python weekly-accountability.py --week 1
  python weekly-accountability.py --week 1 --save
  python weekly-accountability.py --week 1 --send --save
  python weekly-accountability.py --week 1 --dry-run
  python weekly-accountability.py --init-sample-data
  python weekly-accountability.py  # defaults to current week
        """,
    )
    parser.add_argument(
        "--week",
        type=int,
        default=None,
        help="ISO week number (default: current week, or plan week based on date)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Year (default: current year)",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Email the report via email-sender.py",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save the report to reports/weekly-accountability-WW.md",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate report but don't save or send",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help=f"Path to data directory (default: {DATA_DIR})",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR,
        help=f"Path to reports directory (default: {REPORTS_DIR})",
    )
    parser.add_argument(
        "--init-sample-data",
        action="store_true",
        help="Create sample data files for testing",
    )

    args = parser.parse_args()

    # Handle sample data initialization
    if args.init_sample_data:
        print("📦 Creating sample data files...")
        create_sample_data(args.data_dir)
        print("✅ Sample data created successfully!")
        print("   Run again without --init-sample-data to generate a report.")
        return

    # Validate data directory exists
    if not args.data_dir.exists():
        print(f"❌ Data directory not found: {args.data_dir}")
        print("   Run with --init-sample-data to create sample data files.")
        sys.exit(1)

    # Determine week number
    if args.week:
        week_number = args.week
    else:
        # Auto-detect: use plan week if within plan, else ISO week
        plan_week = get_plan_week_for_date(date.today())
        if plan_week > 0:
            week_number = plan_week
        else:
            week_number = week_number_from_date(date.today())

    # Load all data
    print(f"📊 Loading data for Week {week_number}...")
    all_data = load_all_data(args.data_dir)
    week_data = filter_data_by_week(all_data, week_number, args.year)

    # Get plan targets
    plan_targets = get_plan_targets(week_number)
    cumulative_targets = get_cumulative_targets(week_number)

    # Calculate metrics
    total_revenue = calc_total_revenue(week_data["week_revenue"])
    outreach_metrics = calc_outreach_metrics(
        week_data["week_leads"], week_data["week_deals"], week_data["metrics"]
    )
    conversion_rates = calc_conversion_rates(outreach_metrics)
    cash_current, cash_change = calc_cash_position(week_data["cash"])
    mrr, active_clients, total_clients = calc_mrr(week_data["all_clients"])
    pipeline_value = calc_pipeline_value(week_data["all_leads"])
    week_leads_count = len(week_data["week_leads"])

    # Calculate accountability score
    score, score_breakdown = calc_accountability_score(
        outreach_metrics, conversion_rates, total_revenue, plan_targets, week_leads_count
    )

    # Generate report
    print("📝 Generating report...")
    report = generate_report(
        week_data=week_data,
        plan_targets=plan_targets,
        cumulative_targets=cumulative_targets,
        outreach_metrics=outreach_metrics,
        conversion_rates=conversion_rates,
        cash_current=cash_current,
        cash_change=cash_change,
        mrr=mrr,
        active_clients=active_clients,
        total_clients=total_clients,
        pipeline_value=pipeline_value,
        score=score,
        score_breakdown=score_breakdown,
    )

    # Output
    if args.dry_run:
        print("\n" + "=" * 70)
        print("🔍 DRY RUN — Report preview:")
        print("=" * 70)
        print(report)
        print("=" * 70)
        print("📌 Dry run complete. Report was not saved or sent.")
    else:
        print(report)

    # Save if requested
    if args.save and not args.dry_run:
        save_report(report, week_number, args.reports_dir)

    # Send if requested
    if args.send and not args.dry_run:
        send_report_email(report, week_number, dry_run=False)

    if not args.save and not args.send and not args.dry_run:
        print("\n💡 Tip: Use --save to save the report or --send to email it.")


if __name__ == "__main__":
    main()
