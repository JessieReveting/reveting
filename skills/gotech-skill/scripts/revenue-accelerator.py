#!/usr/bin/env python3
"""
Revenue Acceleration Engine for GoTechSolutions
==============================================
Manages outreach planning, execution, tracking, reporting, and campaign generation.

Usage:
    python revenue-accelerator.py --mode plan --phase 1
    python revenue-accelerator.py --mode execute --service ai-ops --phase 2
    python revenue-accelerator.py --mode track --outreach 30 --replies 8 --calls 3 --closes 1 --revenue 2500
    python revenue-accelerator.py --mode report --dry-run
    python revenue-accelerator.py --mode campaign --service ai-ops
    python revenue-accelerator.py --mode campaign --service ai-ops --dry-run
"""

import argparse
import json
import os
import sys
import datetime
from pathlib import Path

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates" / "campaigns"
LOG_FILE = DATA_DIR / "revenue_log.json"
PLAN_FILE = DATA_DIR / "revenue_plan.json"

SERVICES = {
    "ai-ops": {
        "name": "AI Operations",
        "price": 1500,
        "description": "AI-powered ops automation for scaling teams",
        "target": "Founders, CTOs, Ops Leaders at tech companies 10-100 employees",
    },
    "communications": {
        "name": "Communications",
        "price": 1000,
        "description": "Full communications stack for content-driven orgs",
        "target": "Marketing agencies, churches, content creators, podcasters",
    },
    "cro": {
        "name": "Technical CRO",
        "price": 1200,
        "description": "Conversion rate optimization audits and implementation",
        "target": "E-commerce founders, SaaS companies, agencies",
    },
    "golive": {
        "name": "Go Live Stream",
        "price": 900,
        "description": "End-to-end live streaming setup and production",
        "target": "Churches, influencers, event companies, educators",
    },
    "bundle": {
        "name": "Full Bundle",
        "price": 3500,
        "description": "All services bundle - full growth stack",
        "target": "Scaling businesses, serial entrepreneurs, CEOs",
    },
    "founding-member": {
        "name": "Founding Member",
        "price": 1750,
        "description": "50% off first 3 months - limited to first 20 clients",
        "target": "High-intent buyers ready to commit",
    },
}

PHASES = {
    1: {"name": "Foundation", "days": "1-14", "outreach": 25, "reply_rate": 0.20, "close_rate": 0.10},
    2: {"name": "Traction", "days": "15-30", "outreach": 35, "reply_rate": 0.25, "close_rate": 0.12},
    3: {"name": "Acceleration", "days": "31-45", "outreach": 40, "reply_rate": 0.28, "close_rate": 0.15},
    4: {"name": "Scale", "days": "46-60", "outreach": 50, "reply_rate": 0.30, "close_rate": 0.18},
}

CAMPAIGN_DIR = TEMPLATES_DIR


# --- Utility Functions ---
def ensure_directories():
    """Ensure all required directories exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def load_json(filepath):
    """Load JSON file or return empty dict."""
    if filepath.exists():
        with open(filepath, "r") as f:
            return json.load(f)
    return {}


def save_json(filepath, data):
    """Save data to JSON file."""
    ensure_directories()
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  ✓ Saved: {filepath}")


def load_campaign_template(service):
    """Load a campaign template markdown file."""
    template_path = CAMPAIGN_DIR / f"{service}.md"
    if template_path.exists():
        with open(template_path, "r") as f:
            return f.read()
    return None


def get_current_phase():
    """Determine current phase from today's date relative to plan start."""
    plan = load_json(PLAN_FILE)
    if not plan:
        return 1
    start = datetime.datetime.strptime(plan["start_date"], "%Y-%m-%d").date()
    today = datetime.date.today()
    day_num = (today - start).days + 1
    for phase_num in sorted(PHASES.keys()):
        phase = PHASES[phase_num]
        day_range = phase["days"].split("-")
        start_day, end_day = int(day_range[0]), int(day_range[1])
        if start_day <= day_num <= end_day:
            return phase_num
    return 4


def format_currency(amount):
    """Format amount as currency string."""
    return f"${amount:,.0f}"


# --- Mode: Plan ---
def generate_plan(args):
    """Generate a 60-day revenue plan with weekly targets."""
    ensure_directories()
    service_key = args.service or "bundle"
    service = SERVICES.get(service_key, SERVICES["bundle"])

    today = datetime.date.today()
    plan = {
        "generated": datetime.datetime.now().isoformat(),
        "start_date": today.isoformat(),
        "end_date": (today + datetime.timedelta(days=59)).isoformat(),
        "service": service_key,
        "service_name": service["name"],
        "price": service["price"],
        "weekly_targets": [],
        "total_outreach": 0,
        "total_replies": 0,
        "total_calls": 0,
        "total_closes": 0,
        "total_revenue": 0,
    }

    print(f"\n{'='*60}")
    print(f"  60-DAY REVENUE PLAN")
    print(f"  Service: {service['name']} @ {format_currency(service['price'])}/mo")
    print(f"  Period: {plan['start_date']} → {plan['end_date']}")
    print(f"{'='*60}\n")

    for phase_num in sorted(PHASES.keys()):
        phase = PHASES[phase_num]
        phase_outreach = phase["outreach"] * 7  # 7 days
        phase_replies = int(phase_outreach * phase["reply_rate"])
        phase_calls = int(phase_replies * 0.6)
        phase_closes = int(phase_calls * phase["close_rate"])
        phase_revenue = phase_closes * service["price"]

        week_target = {
            "phase": phase_num,
            "phase_name": phase["name"],
            "days": phase["days"],
            "outreach": phase_outreach,
            "replies": phase_replies,
            "calls": phase_calls,
            "closes": phase_closes,
            "revenue": phase_revenue,
        }

        plan["weekly_targets"].append(week_target)
        plan["total_outreach"] += phase_outreach
        plan["total_replies"] += phase_replies
        plan["total_calls"] += phase_calls
        plan["total_closes"] += phase_closes
        plan["total_revenue"] += phase_revenue

        print(f"  Phase {phase_num}: {phase['name']} (Days {phase['days']})")
        print(f"    Outreach: {phase_outreach} | Replies: {phase_replies} | Calls: {phase_calls}")
        print(f"    Closes: {phase_closes} | Revenue: {format_currency(phase_revenue)}")
        print()

    print(f"{'─'*60}")
    print(f"  TOTALS:")
    print(f"    Outreach: {plan['total_outreach']}")
    print(f"    Replies:  {plan['total_replies']}")
    print(f"    Calls:    {plan['total_calls']}")
    print(f"    Closes:   {plan['total_closes']}")
    print(f"    Revenue:  {format_currency(plan['total_revenue'])}")
    print(f"{'='*60}\n")

    if not args.dry_run:
        save_json(PLAN_FILE, plan)
        return plan
    else:
        print("  ⚠ DRY RUN - plan not saved to disk.\n")
        return plan


# --- Mode: Execute ---
def generate_outreach_list(args):
    """Generate today's outreach list based on current phase."""
    ensure_directories()
    service_key = args.service or "bundle"
    service = SERVICES.get(service_key, SERVICES["bundle"])

    plan = load_json(PLAN_FILE)
    phase_num = args.phase or get_current_phase()
    phase = PHASES.get(phase_num, PHASES[1])

    # Daily targets
    daily_outreach = phase["outreach"]
    daily_replies = int(daily_outreach * phase["reply_rate"])
    daily_calls = int(daily_replies * 0.6)
    daily_closes = int(daily_calls * phase["close_rate"])
    daily_revenue_potential = daily_closes * service["price"]

    today = datetime.date.today().isoformat()

    outreach_entry = {
        "date": today,
        "service": service_key,
        "phase": phase_num,
        "phase_name": phase["name"],
        "targets": {
            "outreach": daily_outreach,
            "replies": daily_replies,
            "calls": daily_calls,
            "closes": daily_closes,
            "revenue_potential": daily_revenue_potential,
        },
        "prospects": generate_prospects(service_key, daily_outreach),
    }

    print(f"\n{'='*60}")
    print(f"  TODAY'S OUTREACH LIST")
    print(f"  Date: {today} | Service: {service['name']}")
    print(f"  Phase {phase_num}: {phase['name']}")
    print(f"{'='*60}\n")

    print(f"  Daily Targets:")
    print(f"    📧 Outreach: {daily_outreach}")
    print(f"    💬 Replies (goal): {daily_replies}")
    print(f"    📞 Calls (goal): {daily_calls}")
    print(f"    Closes (goal): {daily_closes}")
    print(f"    💰 Revenue Potential: {format_currency(daily_revenue_potential)}")
    print()

    print(f"  Sample Prospects to Contact Today:")
    print(f"  {'─'*50}")
    for i, prospect in enumerate(outreach_entry["prospects"][:10], 1):
        print(f"  {i:2}. {prospect['name']} — {prospect['title']} @ {prospect['company']}")
        print(f"      Pain: {prospect['pain_point']}")
    print(f"{'─'*50}")
    print(f"  ({len(outreach_entry['prospects'])} total prospects generated)\n")

    if not args.dry_run:
        log_data = load_json(LOG_FILE)
        if "outreach_days" not in log_data:
            log_data["outreach_days"] = []
        log_data["outreach_days"].append(outreach_entry)
        save_json(LOG_FILE, log_data)
        print("  ✓ Outreach list logged.\n")
    else:
        print("  ⚠ DRY RUN - not logged.\n")

    return outreach_entry


def generate_prospects(service_key, count):
    """Generate sample prospect profiles based on service."""
    prospect_templates = {
        "ai-ops": [
            {"name": "Alex Chen", "title": "CTO", "company": "NovaTech (25 employees)", "pain_point": "Manual onboarding processes"},
            {"name": "Sarah Williams", "title": "VP Operations", "company": "ScaleAI (60 employees)", "pain_point": "Slow customer support response"},
            {"name": "Marcus Johnson", "title": "Founder", "company": "DevFlow (15 employees)", "pain_point": "Content creation bottlenecks"},
            {"name": "Priya Patel", "title": "Head of Ops", "company": "byteForge (45 employees)", "pain_point": "Tool sprawl and inefficiency"},
            {"name": "Jordan Lee", "title": "CEO", "company": "AppStack (80 employees)", "pain_point": "Scaling team operations"},
        ],
        "communications": [
            {"name": "Megan Torres", "title": "Creative Director", "company": "BrightWave Agency", "pain_point": "Inconsistent content quality"},
            {"name": "David Kim", "title": "Communications Lead", "company": "Faith Community Church", "pain_point": "Multi-platform distribution"},
            {"name": "Rachel Green", "title": "Content Creator", "company": "Self-employed", "pain_point": "Time management across platforms"},
            {"name": "Tom Bradley", "title": "Podcast Producer", "company": "PodWorks Studio", "pain_point": "Production workflow"},
            {"name": "Lisa Nguyen", "title": "Marketing Manager", "company": "CreativeForge Co", "pain_point": "Audience engagement"},
        ],
        "cro": [
            {"name": "Chris Martinez", "title": "Founder", "company": "ShopNova E-com", "pain_point": "Low product page conversion"},
            {"name": "Emily Davis", "title": "Growth Lead", "company": "SaaSly (SaaS, 30 employees)", "pain_point": "Wasted ad spend"},
            {"name": "Ryan O'Connor", "title": "CEO", "company": "CRO Agency Pro", "pain_point": "Landing page underperformance"},
            {"name": "Anna Petrov", "title": "Marketing Director", "company": "BuyNow D2C", "pain_point": "Cart abandonment"},
            {"name": "James Liu", "title": "Head of Growth", "company": "SubBox (SaaS)", "pain_point": "Trial-to-paid conversion"},
        ],
        "golive": [
            {"name": "Pastor Mike Harris", "title": "Tech Director", "company": "Grace Community Church", "pain_point": "Complex streaming setup"},
            {"name": "Influencer Jade", "title": "Content Creator", "company": "JadeLive (50K followers)", "pain_point": "Reaching wider audience"},
            {"name": "Event Pro Carlos", "title": "Founder", "company": "LiveEvent Co", "pain_point": "Production quality"},
            {"name": "Prof. Amanda Cole", "title": "Online Educator", "company": "EduStream Academy", "pain_point": "Technical streaming barriers"},
            {"name": "Worship Leader Sam", "title": "Media Director", "company": "Hills Church", "pain_point": "Multi-camera production"},
        ],
        "bundle": [
            {"name": "Serialón García", "title": "Serial Entrepreneur", "company": "3 ventures (active)", "pain_point": "Managing multiple vendor relationships"},
            {"name": "Catherine Wells", "title": "CEO", "company": "GrowthCo (75 employees)", "pain_point": "Need full-stack growth solution"},
            {"name": "Nathan Park", "title": "Managing Partner", "company": "Venture Builders", "pain_point": "Fragmented tool stack"},
            {"name": "Diana Reeves", "title": "Founder & CEO", "company": "ScaleUp Inc", "pain_point": "Scaling cost-effectively"},
            {"name": "Oscar Mendez", "title": "COO", "company": "TechGroup Holdings", "pain_point": "Integration overhead"},
        ],
        "founding-member": [
            {"name": "High-Intent Lead", "title": "Decision Maker", "company": "Target Company", "pain_point": "Price sensitivity / commitment"},
            {"name": "Active Prospect", "title": "Buyer", "company": "Warm Lead Co", "pain_point": "Waiting for right timing"},
            {"name": "Referral Contact", "title": "Champion", "company": "Client Referral", "pain_point": "Trust building"},
            {"name": "Engaged Visitor", "title": "CEO", "company": "Webinar Attendee Co", "pain_point": "Needs social proof"},
            {"name": "Returning Lead", "title": "Founder", "company": "Follow-up Prospect", "pain_point": "Comparing options"},
        ],
    }

    template = prospect_templates.get(service_key, prospect_templates["bundle"])
    prospects = []
    for i in range(count):
        base = template[i % len(template)]
        prospect = base.copy()
        prospect["priority"] = "high" if i < count * 0.3 else ("medium" if i < count * 0.7 else "standard")
        prospects.append(prospect)
    return prospects


# --- Mode: Track ---
def log_results(args):
    """Log daily results (outreach sent, replies, calls, closes, revenue)."""
    ensure_directories()

    log_data = load_json(LOG_FILE)
    today = datetime.date.today().isoformat()

    # Extract metrics from args
    outreach = int(getattr(args, "outreach", 0) or 0)
    replies = int(getattr(args, "replies", 0) or 0)
    calls = int(getattr(args, "calls", 0) or 0)
    closes = int(getattr(args, "closes", 0) or 0)
    revenue = float(getattr(args, "revenue", 0) or 0)

    daily_entry = {
        "date": today,
        "outreach": outreach,
        "replies": replies,
        "calls": calls,
        "closes": closes,
        "revenue": revenue,
        "reply_rate": round(replies / outreach * 100, 1) if outreach > 0 else 0,
        "close_rate": round(closes / calls * 100, 1) if calls > 0 else 0,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    if "daily_log" not in log_data:
        log_data["daily_log"] = []

    # Check if today's entry already exists and update it
    updated = False
    for i, entry in enumerate(log_data["daily_log"]):
        if entry.get("date") == today:
            log_data["daily_log"][i] = daily_entry
            updated = True
            break

    if not updated:
        log_data["daily_log"].append(daily_entry)

    # Update running totals
    totals = {
        "total_outreach": sum(e.get("outreach", 0) for e in log_data["daily_log"]),
        "total_replies": sum(e.get("replies", 0) for e in log_data["daily_log"]),
        "total_calls": sum(e.get("calls", 0) for e in log_data["daily_log"]),
        "total_closes": sum(e.get("closes", 0) for e in log_data["daily_log"]),
        "total_revenue": sum(e.get("revenue", 0) for e in log_data["daily_log"]),
    }
    log_data["totals"] = totals

    print(f"\n{'='*60}")
    print(f"  DAILY RESULTS LOGGED — {today}")
    print(f"{'='*60}\n")
    print(f"  📧 Outreach Sent:    {outreach}")
    print(f"  💬 Replies:          {replies} ({daily_entry['reply_rate']}%)")
    print(f"  📞 Calls:            {calls}")
    print(f"  🤝 Closes:           {closes} ({daily_entry['close_rate']}%)")
    print(f"  💰 Revenue:          {format_currency(revenue)}")
    print()
    print(f"  Running Totals:")
    print(f"    Outreach: {totals['total_outreach']}")
    print(f"    Replies:  {totals['total_replies']}")
    print(f"    Calls:    {totals['total_calls']}")
    print(f"    Closes:   {totals['total_closes']}")
    print(f"    Revenue:  {format_currency(totals['total_revenue'])}")
    print(f"{'='*60}\n")

    save_json(LOG_FILE, log_data)
    return daily_entry


# --- Mode: Report ---
def generate_report(args):
    """Show progress vs plan with variance analysis."""
    ensure_directories()

    plan = load_json(PLAN_FILE)
    log_data = load_json(LOG_FILE)

    daily_log = log_data.get("daily_log", [])
    totals = log_data.get("totals", {})
    today = datetime.date.today()

    print(f"\n{'='*60}")
    print(f"  PROGRESS REPORT vs PLAN")
    print(f"  Generated: {today.isoformat()}")
    print(f"{'='*60}\n")

    if not plan:
        print("  ⚠ No plan found. Run 'plan' mode first.\n")
        return None

    # Plan totals
    plan_outreach = plan.get("total_outreach", 0)
    plan_replies = plan.get("total_replies", 0)
    plan_calls = plan.get("total_calls", 0)
    plan_closes = plan.get("total_closes", 0)
    plan_revenue = plan.get("total_revenue", 0)

    # Actual totals
    actual_outreach = totals.get("total_outreach", 0)
    actual_replies = totals.get("total_replies", 0)
    actual_calls = totals.get("total_calls", 0)
    actual_closes = totals.get("total_closes", 0)
    actual_revenue = totals.get("total_revenue", 0)

    # Calculate elapsed time
    start = datetime.datetime.strptime(plan["start_date"], "%Y-%m-%d").date()
    end = datetime.datetime.strptime(plan["end_date"], "%Y-%m-%d").date()
    total_days = (end - start).days + 1
    elapsed_days = min((today - start).days + 1, total_days)
    elapsed_pct = min(elapsed_days / total_days * 100, 100)

    print(f"  Timeline: Day {elapsed_days} of {total_days} ({elapsed_pct:.0f}% elapsed)")
    print(f"  Service:  {plan.get('service_name', 'N/A')}")
    print(f"{'─'*60}\n")

    # Variance table
    metrics = [
        ("📧 Outreach Sent", actual_outreach, plan_outreach),
        ("💬 Replies", actual_replies, plan_replies),
        ("📞 Calls", actual_calls, plan_calls),
        ("🤝 Closes", actual_closes, plan_closes),
        ("💰 Revenue", actual_revenue, plan_revenue, True),
    ]

    print(f"  {'Metric':<20} {'Actual':>10} {'Plan':>10} {'Variance':>10} {'Status':>10}")
    print(f"  {'─'*60}")

    for metric_name, actual, planned, *is_money in metrics:
        variance = actual - planned
        if planned > 0:
            variance_pct = (variance / planned) * 100
        else:
            variance_pct = 0

        if is_money:
            actual_str = format_currency(actual)
            planned_str = format_currency(planned)
            var_str = format_currency(variance)
        else:
            actual_str = str(actual)
            planned_str = str(planned)
            var_str = str(variance)

        # Status indicator
        if variance_pct >= 10:
            status = "Above"
        elif variance_pct >= -10:
            status = "On Track"
        elif variance_pct >= -25:
            status = "🟠 Behind"
        else:
            status = "🔴 Critical"

        print(f"  {metric_name:<20} {actual_str:>10} {planned_str:>10} {var_str:>10} {status:>10}")

    print(f"{'─'*60}\n")

    # Pace analysis
    print(f"  PACE ANALYSIS:")
    if elapsed_days > 0 and elapsed_pct > 0:
        daily_revenue_needed = (plan_revenue - actual_revenue) / max(total_days - elapsed_days, 1)
        daily_outreach_needed = (plan_outreach - actual_outreach) / max(total_days - elapsed_days, 1)

        print(f"    Avg Revenue/Day (so far): {format_currency(actual_revenue / elapsed_days)}")
        print(f"    Required Revenue/Day (remaining): {format_currency(daily_revenue_needed)}")
        print(f"    Remaining Days: {max(total_days - elapsed_days, 0)}")
        print(f"    Remaining Revenue Gap: {format_currency(max(plan_revenue - actual_revenue, 0))}")
        print(f"    Avg Outreach/Day (so far): {actual_outreach / elapsed_days:.0f}")
        print(f"    Required Outreach/Day: {daily_outreach_needed:.0f}")

        if actual_revenue >= plan_revenue * (elapsed_pct / 100):
            print(f"\n    Pace: AHEAD of plan!")
        elif actual_revenue >= plan_revenue * (elapsed_pct / 100) * 0.85:
            print(f"\n    Pace: ON TRACK (within 85%)")
        else:
            print(f"\n    🔴 Pace: BEHIND — needs acceleration")

    # Phase breakdown
    if plan.get("weekly_targets"):
        print(f"\n{'─'*60}")
        print(f"  PHASE BREAKDOWN:")
        for wt in plan["weekly_targets"]:
            print(f"    Phase {wt['phase']}: {wt['phase_name']} (Days {wt['days']})"
                  f" — {wt['outreach']} outreach → {format_currency(wt['revenue'])} revenue")

    print(f"\n{'='*60}\n")

    return {
        "plan": plan,
        "actuals": totals,
        "elapsed_pct": elapsed_pct,
        "variance": {
            "outreach": actual_outreach - plan_outreach,
            "replies": actual_replies - plan_replies,
            "calls": actual_calls - plan_calls,
            "closes": actual_closes - plan_closes,
            "revenue": actual_revenue - plan_revenue,
        }
    }


# --- Mode: Campaign ---
def generate_campaign(args, service=None):
    """Output a full outreach campaign for a specific service."""
    ensure_directories()
    svc = service or args.service
    if svc not in SERVICES:
        print(f"\n  ✗ Unknown service: {svc}")
        print(f"  Available services: {', '.join(SERVICES.keys())}\n")
        return None

    campaign_content = load_campaign_template(svc)
    if campaign_content:
        print(f"\n{'='*60}")
        print(f"  CAMPAIGN: {SERVICES[svc]['name']}")
        print(f"{'='*60}")
        print(campaign_content)
        print(f"\n{'='*60}\n")

        if args.dry_run:
            print("  ⚠ DRY RUN — campaign output above (no action needed).\n")

        return campaign_content
    else:
        print(f"\n  ⚠ No campaign template found for '{svc}'.")
        print(f"  Expected file: {CAMPAIGN_DIR / f'{svc}.md'}")
        print(f"  Generate it with the --dry-run flag after creating templates.\n")
        return None


# --- Argument Parser ---
def build_parser():
    parser = argparse.ArgumentParser(
        prog="revenue-accelerator",
        description="Revenue Acceleration Engine — manages outreach planning, execution, tracking, and reporting.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --mode plan --service bundle
  %(prog)s --mode execute --service ai-ops --phase 2
  %(prog)s --mode track --outreach 30 --replies 8 --calls 3 --closes 1 --revenue 2500
  %(prog)s --mode report
  %(prog)s --mode campaign --service communications
  %(prog)s --mode plan --dry-run
        """,
    )

    parser.add_argument(
        "--mode",
        required=True,
        choices=["plan", "execute", "track", "report", "campaign"],
        help="Operational mode: plan, execute, track, report, or campaign",
    )
    parser.add_argument(
        "--service",
        choices=list(SERVICES.keys()),
        default=None,
        help="Service line to operate on",
    )
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        help="Plan phase (1-4)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview actions without writing to disk",
    )

    # Track mode arguments
    parser.add_argument("--outreach", type=int, default=0, help="Outreach sent (for track mode)")
    parser.add_argument("--replies", type=int, default=0, help="Replies received (for track mode)")
    parser.add_argument("--calls", type=int, default=0, help="Calls completed (for track mode)")
    parser.add_argument("--closes", type=int, default=0, help="Deals closed (for track mode)")
    parser.add_argument("--revenue", type=float, default=0, help="Revenue logged (for track mode)")

    return parser


# --- Main Entry Point ---
def main():
    parser = build_parser()
    args = parser.parse_args()

    ensure_directories()

    print(f"\nRevenue Acceleration Engine")
    print(f"   Mode: {args.mode.upper()}")
    if args.service:
        print(f"   Service: {SERVICES.get(args.service, {}).get('name', args.service)}")
    if args.phase:
        print(f"   Phase: {args.phase} ({PHASES.get(args.phase, {}).get('name', 'Unknown')})")
    if args.dry_run:
        print(f"   ⚠ DRY RUN ENABLED")
    print()

    if args.mode == "plan":
        generate_plan(args)
    elif args.mode == "execute":
        generate_outreach_list(args)
    elif args.mode == "track":
        log_results(args)
    elif args.mode == "report":
        generate_report(args)
    elif args.mode == "campaign":
        generate_campaign(args)


if __name__ == "__main__":
    main()
