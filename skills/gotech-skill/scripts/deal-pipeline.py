#!/usr/bin/env python3
"""
Deal Pipeline Manager
Automates deal tracking, advancement, forecasting, and reporting.
Data stored in data/deals.json with full transition history.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# --- Configuration ---
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "deals.json"

STAGES = ["Prospect", "Contacted", "Qualified", "Proposal", "Negotiation", "Closed-Won", "Closed-Lost"]

STAGE_PROBABILITY = {
    "Prospect": 0.10,
    "Contacted": 0.20,
    "Qualified": 0.40,
    "Proposal": 0.60,
    "Negotiation": 0.80,
    "Closed-Won": 1.00,
    "Closed-Lost": 0.00,
}

STAGE_AVG_DAYS = {
    "Prospect": 3,
    "Contacted": 5,
    "Qualified": 7,
    "Proposal": 10,
    "Negotiation": 5,
    "Closed-Won": 0,
    "Closed-Lost": 0,
}

DEFAULT_STUCK_THRESHOLD_DAYS = 14

ACTIVE_STAGES = ["Prospect", "Contacted", "Qualified", "Proposal", "Negotiation"]


def load_deals():
    """Load deals from JSON file, creating file if it doesn't exist."""
    if not DATA_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        save_deals({"deals": [], "history": []})
        return {"deals": [], "history": []}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_deals(data):
    """Save deals data to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def find_deal(data, deal_id):
    """Find a deal by ID."""
    for deal in data["deals"]:
        if deal["id"].lower() == deal_id.lower():
            return deal
    return None


def days_in_stage(deal):
    """Calculate how many days a deal has been in its current stage."""
    if not deal.get("stage_history"):
        return 0
    last_transition = deal["stage_history"][-1]
    entry_date = datetime.fromisoformat(last_transition["date"])
    return (datetime.now() - entry_date).days


def days_since_activity(deal):
    """Calculate days since last activity/note."""
    if deal.get("last_activity"):
        last = datetime.fromisoformat(deal["last_activity"])
        return (datetime.now() - last).days
    return days_in_stage(deal)


def mode_status(args, data):
    """Show full pipeline with deal count, value, and avg time per stage."""
    print("\n" + "=" * 70)
    print("  DEAL PIPELINE STATUS")
    print("=" * 70)

    stages_order = [s for s in STAGES if s not in ("Closed-Won", "Closed-Lost")]
    deals_by_stage = defaultdict(list)
    for deal in data["deals"]:
        if deal["stage"] not in ("Closed-Won", "Closed-Lost"):
            deals_by_stage[deal["stage"]].append(deal)

    total_value = sum(d["amount"] for d in data["deals"] if d["stage"] not in ("Closed-Won", "Closed-Lost"))
    total_deals = sum(len(deals_by_stage[s]) for s in stages_order)

    print(f"\n{'Stage':<15} {'Count':>6} {'Value':>12} {'Avg Days':>10}")
    print("-" * 45)

    for stage in stages_order:
        deals = deals_by_stage.get(stage, [])
        count = len(deals)
        value = sum(d["amount"] for d in deals)
        if count > 0:
            avg_days = sum(days_in_stage(d) for d in deals) / count
        else:
            avg_days = 0
        print(f"{stage:<15} {count:>6} ${value:>10,.0f} {avg_days:>9.1f}d")

    print("-" * 45)
    print(f"{'TOTAL':<15} {total_deals:>6} ${total_value:>10,.0f}")

    # Show recently closed
    closed = [d for d in data["deals"] if d["stage"] in ("Closed-Won", "Closed-Lost")]
    if closed:
        print(f"\nClosed deals: {len(closed)}")
        won = sum(1 for d in closed if d["stage"] == "Closed-Won")
        print(f"  Won: {won} | Lost: {len(closed) - won}")

    print("=" * 70)


def mode_advance(args, data):
    """Move a deal to next stage, log the transition."""
    if not args.deal_id:
        print("Error: --deal-id is required for advance mode")
        print("Usage: deal-pipeline.py --mode advance --deal-id DEAL001 [--stage StageName] [--note 'Notes']")
        sys.exit(1)

    deal = find_deal(data, args.deal_id)
    if not deal:
        print(f"Error: Deal '{args.deal_id}' not found")
        sys.exit(1)

    current_idx = STAGES.index(deal["stage"])

    # If --stage is specified, jump to that stage; otherwise advance one step
    if args.stage:
        if args.stage not in STAGES:
            print(f"Error: Invalid stage '{args.stage}'. Valid stages: {', '.join(STAGES)}")
            sys.exit(1)
        new_idx = STAGES.index(args.stage)
        if new_idx <= current_idx:
            print(f"Warning: Target stage '{args.stage}' is not later than current stage '{deal['stage']}'")
    else:
        new_idx = current_idx + 1

    if new_idx >= len(STAGES):
        print(f"Deal '{args.deal_id}' is already at final stage: {deal['stage']}")
        sys.exit(0)

    old_stage = deal["stage"]
    new_stage = STAGES[new_idx]

    # Update deal
    deal["stage"] = new_stage
    deal["last_activity"] = datetime.now().isoformat()

    # Log transition
    transition = {
        "deal_id": args.deal_id,
        "from_stage": old_stage,
        "to_stage": new_stage,
        "date": datetime.now().isoformat(),
        "note": args.note or "",
    }
    deal["stage_history"].append(transition)
    data["history"].append(transition)

    save_deals(data)
    print(f"\n✓ Deal '{args.deal_id}' advanced: {old_stage} → {new_stage}")
    if args.note:
        print(f"  Note: {args.note}")
    print(f"  Stage history entries: {len(deal['stage_history'])}")


def mode_stuck(args, data):
    """Identify deals stuck in the same stage too long."""
    print("\n" + "=" * 70)
    print("  STUCK DEALS REPORT")
    print("=" * 70)

    threshold = args.threshold if args.threshold else DEFAULT_STUCK_THRESHOLD_DAYS

    active_deals = [d for d in data["deals"] if d["stage"] in ACTIVE_STAGES]
    stuck_deals = []

    for deal in active_deals:
        days = days_in_stage(deal)
        expected = STAGE_AVG_DAYS.get(deal["stage"], threshold)
        limit = max(expected * 1.5, threshold)
        if days >= limit:
            stuck_deals.append((deal, days, limit))

    stuck_deals.sort(key=lambda x: x[1], reverse=True)

    if not stuck_deals:
        print(f"\nNo deals stuck beyond threshold ({threshold} days). Pipeline is healthy! ✓")
    else:
        print(f"\n{len(stuck_deals)} deal(s) exceeded threshold:\n")
        print(f"{'ID':<12} {'Name':<25} {'Stage':<13} {'Days':>6} {'Limit':>6} {'Amount':>12}")
        print("-" * 75)
        for deal, days, limit in stuck_deals:
            print(f"{deal['id']:<12} {deal['name'][:24]:<25} {deal['stage']:<13} {days:>5}d {limit:>5.0f}d ${deal['amount']:>10,.0f}")

    print("=" * 70)


def mode_forecast(args, data):
    """Project revenue based on pipeline weighted by stage probability."""
    print("\n" + "=" * 70)
    print("  REVENUE FORECAST")
    print("=" * 70)

    active_deals = [d for d in data["deals"] if d["stage"] in ACTIVE_STAGES]
    total_pipeline = sum(d["amount"] for d in active_deals)
    weighted_revenue = sum(d["amount"] * STAGE_PROBABILITY.get(d["stage"], 0) for d in active_deals)

    print(f"\n{'Stage':<15} {'Probability':>11} {'# Deals':>7} {'Pipeline':>12} {'Weighted':>12} {'Expected':>12}")
    print("-" * 72)

    for stage in ACTIVE_STAGES:
        deals = [d for d in active_deals if d["stage"] == stage]
        prob = STAGE_PROBABILITY[stage]
        pipeline = sum(d["amount"] for d in deals)
        weighted = pipeline * prob
        count = len(deals)
        exp_close = weighted  # probability-weighted expected close
        if count > 0:
            print(f"{stage:<15} {prob:>10.0%} {count:>7} ${pipeline:>10,.0f} ${weighted:>10,.0f} ${exp_close:>10,.0f}")

    print("-" * 72)
    print(f"{'TOTAL':<15} {'':>11} {len(active_deals):>7} ${total_pipeline:>10,.0f} ${weighted_revenue:>10,.0f} ${weighted_revenue:>10,.0f}")

    if total_pipeline > 0:
        overall_prob = weighted_revenue / total_pipeline
        print(f"\nOverall weighted close probability: {overall_prob:.1%}")

    # Expected deals count
    expected_deals = sum(
        1 * STAGE_PROBABILITY.get(d["stage"], 0)
        for d in active_deals
    )
    print(f"Expected deals to close: {expected_deals:.1f}")
    print("=" * 70)


def mode_report(args, data):
    """Full pipeline report."""
    print("\n" + "=" * 70)
    print("  COMPREHENSIVE PIPELINE REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    active_deals = [d for d in data["deals"] if d["stage"] in ACTIVE_STAGES]
    total_pipeline = sum(d["amount"] for d in active_deals)
    weighted_revenue = sum(d["amount"] * STAGE_PROBABILITY.get(d["stage"], 0) for d in active_deals)

    # --- Summary ---
    print(f"\n📊 SUMMARY")
    print(f"   Total active pipeline: ${total_pipeline:,.0f}")
    print(f"   Weighted forecast:     ${weighted_revenue:,.0f}")
    print(f"   Active deals:          {len(active_deals)}")
    print(f"   Conversion rate (weighted): {weighted_revenue/total_pipeline*100:.1f}%" if total_pipeline > 0 else "   N/A")

    # --- Deals by stage with aging ---
    print(f"\n📋 DEALS BY STAGE")
    print("-" * 70)

    for stage in ACTIVE_STAGES:
        deals = [d for d in active_deals if d["stage"] == stage]
        if not deals:
            continue
        stage_value = sum(d["amount"] for d in deals)
        avg_age = sum(days_in_stage(d) for d in deals) / len(deals)
        max_age = max(days_in_stage(d) for d in deals)
        print(f"\n  {stage} ({len(deals)} deals, ${stage_value:,.0f})")
        print(f"  Avg age: {avg_age:.1f}d | Max age: {max_age}d | Expected: {STAGE_AVG_DAYS[stage]}d")
        for d in sorted(deals, key=lambda x: days_in_stage(x), reverse=True):
            age = days_in_stage(d)
            flag = " ⚠️" if age > STAGE_AVG_DAYS[stage] * 1.5 else ""
            print(f"    {d['id']:<10} {d['name'][:20]:<22} ${d['amount']:>10,.0f} ({age}d){flag}")

    # --- Bottleneck identification ---
    print(f"\n🔍 BOTTLENECK ANALYSIS")
    print("-" * 70)

    bottlenecks = []
    for stage in ACTIVE_STAGES:
        deals = [d for d in active_deals if d["stage"] == stage]
        if not deals:
            continue
        avg_age = sum(days_in_stage(d) for d in deals) / len(deals)
        expected = STAGE_AVG_DAYS[stage]
        ratio = avg_age / expected if expected > 0 else 0
        if ratio > 1.5:
            bottlenecks.append((stage, len(deals), avg_age, expected, ratio))

    if bottlenecks:
        bottlenecks.sort(key=lambda x: x[4], reverse=True)
        for stage, count, avg, exp, ratio in bottlenecks:
            print(f"  ⚠️  {stage}: {count} deals, avg {avg:.0f}d (expected {exp}d) — {ratio:.1f}x slower")
    else:
        print("  ✓ No major bottlenecks detected")

    # --- Recommended actions ---
    print(f"\n💡 RECOMMENDED ACTIONS")
    print("-" * 70)

    recommendations = []
    for deal in active_deals:
        age = days_in_stage(deal)
        expected = STAGE_AVG_DAYS.get(deal["stage"], 0)
        if age > expected * 2:
            recommendations.append(f"🚨 URGENT: {deal['id']} ({deal['name']}) in '{deal['stage']}' for {age}d — escalate or close")
        elif age > expected * 1.5:
            recommendations.append(f"⚠️  {deal['id']} ({deal['name']}) in '{deal['stage']}' for {age}d — needs follow-up")

    if recommendations:
        for rec in recommendations:
            print(f"  {rec}")
    else:
        print("  ✓ All deals within expected timeframes")

    print("\n" + "=" * 70)


def mode_remind(args, data):
    """Show deals needing follow-up today."""
    print("\n" + "=" * 70)
    print("  FOLLOW-UP REMINDERS")
    print(f"  {datetime.now().strftime('%A, %B %d, %Y')}")
    print("=" * 70)

    followups = []
    for deal in data["deals"]:
        if deal["stage"] not in ACTIVE_STAGES:
            continue
        age = days_in_stage(deal)
        expected = STAGE_AVG_DAYS.get(deal["stage"], 0)
        overdue = age > expected

        # Check if followed up recently (within expected window)
        if followup_due(deal):
            followups.append(deal)

    if not followups:
        print("\n🎉 No follow-ups due today! All deals are within expected timeframes.")
    else:
        followups.sort(key=lambda d: days_in_stage(d), reverse=True)
        print(f"\n{len(followups)} deal(s) need follow-up:\n")
        for deal in followups:
            age = days_in_stage(deal)
            status = "🔴 OVERDUE" if age > STAGE_AVG_DAYS.get(deal["stage"], 0) else "🟡 DUE"
            print(f"  {status}  {deal['id']:<10} {deal['name'][:25]:<27} | Stage: {deal['stage']:<12} | Age: {age}d")
            if deal.get("contact"):
                print(f"           Contact: {deal['contact']}")
            print()

    print("=" * 70)


def followup_due(deal):
    """Check if a follow-up is due for this deal."""
    age = days_in_stage(deal)
    expected = STAGE_AVG_DAYS.get(deal["stage"], 1)
    # Follow-up due when approaching or at expected time
    if age >= expected * 0.8:
        return True
    # Or if no activity in last 3 days
    if deal.get("last_activity"):
        last = datetime.fromisoformat(deal["last_activity"])
        if (datetime.now() - last).days >= 3:
            return True
    return False


def add_sample_data(data):
    """Add sample deals for testing if pipeline is empty."""
    if data["deals"]:
        return data

    sample_deals = [
        {
            "id": "DEAL001",
            "name": "Acme Corp - Enterprise",
            "contact": "John Smith (john@acme.com)",
            "amount": 50000,
            "stage": "Qualified",
            "created": (datetime.now() - timedelta(days=12)).isoformat(),
            "last_activity": (datetime.now() - timedelta(days=2)).isoformat(),
            "stage_history": [
                {"from_stage": None, "to_stage": "Prospect", "date": (datetime.now() - timedelta(days=12)).isoformat(), "note": "Inbound lead"},
                {"from_stage": "Prospect", "to_stage": "Contacted", "date": (datetime.now() - timedelta(days=9)).isoformat(), "note": "Demo call completed"},
                {"from_stage": "Contacted", "to_stage": "Qualified", "date": (datetime.now() - timedelta(days=5)).isoformat(), "note": "Budget confirmed, BANT qualified"},
            ]
        },
        {
            "id": "DEAL002",
            "name": "TechStart Inc - SMB",
            "contact": "Sarah Lee (sarah@techstart.io)",
            "amount": 15000,
            "stage": "Proposal",
            "created": (datetime.now() - timedelta(days=20)).isoformat(),
            "last_activity": (datetime.now() - timedelta(days=1)).isoformat(),
            "stage_history": [
                {"from_stage": None, "to_stage": "Prospect", "date": (datetime.now() - timedelta(days=20)).isoformat(), "note": "Referral"},
                {"from_stage": "Prospect", "to_stage": "Contacted", "date": (datetime.now() - timedelta(days=17)).isoformat(), "note": "Cold outreach"},
                {"from_stage": "Contacted", "to_stage": "Qualified", "date": (datetime.now() - timedelta(days=12)).isoformat(), "note": "Needs identified"},
                {"from_stage": "Qualified", "to_stage": "Proposal", "date": (datetime.now() - timedelta(days=5)).isoformat(), "note": "Proposal sent"},
            ]
        },
        {
            "id": "DEAL003",
            "name": "GlobalTech - Mid-Market",
            "contact": "Mike Chen (mike@globaltech.com)",
            "amount": 75000,
            "stage": "Negotiation",
            "created": (datetime.now() - timedelta(days=30)).isoformat(),
            "last_activity": (datetime.now() - timedelta(days=1)).isoformat(),
            "stage_history": [
                {"from_stage": None, "to_stage": "Prospect", "date": (datetime.now() - timedelta(days=30)).isoformat(), "note": "Trade show lead"},
                {"from_stage": "Prospect", "to_stage": "Contacted", "date": (datetime.now() - timedelta(days=27)).isoformat(), "note": "Follow-up call"},
                {"from_stage": "Contacted", "to_stage": "Qualified", "date": (datetime.now() - timedelta(days=20)).isoformat(), "note": "Qualified on call"},
                {"from_stage": "Qualified", "to_stage": "Proposal", "date": (datetime.now() - timedelta(days=14)).isoformat(), "note": "Custom proposal"},
                {"from_stage": "Proposal", "to_stage": "Negotiation", "date": (datetime.now() - timedelta(days=7)).isoformat(), "note": "Terms discussion"},
            ]
        },
        {
            "id": "DEAL004",
            "name": "StartupXYZ - Seed",
            "contact": "Alex Rivera (alex@startupxyz.co)",
            "amount": 8000,
            "stage": "Contacted",
            "created": (datetime.now() - timedelta(days=8)).isoformat(),
            "last_activity": (datetime.now() - timedelta(days=6)).isoformat(),
            "stage_history": [
                {"from_stage": None, "to_stage": "Prospect", "date": (datetime.now() - timedelta(days=8)).isoformat(), "note": "Website inquiry"},
                {"from_stage": "Prospect", "to_stage": "Contacted", "date": (datetime.now() - timedelta(days=6)).isoformat(), "note": "Initial call"},
            ]
        },
        {
            "id": "DEAL005",
            "name": "MegaCorp - Expansion",
            "contact": "Lisa Park (lisa@megacorp.com)",
            "amount": 120000,
            "stage": "Prospect",
            "created": (datetime.now() - timedelta(days=2)).isoformat(),
            "last_activity": (datetime.now() - timedelta(days=2)).isoformat(),
            "stage_history": [
                {"from_stage": None, "to_stage": "Prospect", "date": (datetime.now() - timedelta(days=2)).isoformat(), "note": "Partner referral"},
            ]
        },
    ]

    data["deals"] = sample_deals
    data["history"] = []
    save_deals(data)
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Deal Pipeline Manager - Track, advance, forecast, and report on your sales pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --mode status
  %(prog)s --mode advance --deal-id DEAL001 --note "Sent proposal"
  %(prog)s --mode advance --deal-id DEAL001 --stage Negotiation
  %(prog)s --mode stuck --threshold 10
  %(prog)s --mode forecast
  %(prog)s --mode report
  %(prog)s --mode remind
  %(prog)s --seed   (add sample data for testing)
        """
    )

    parser.add_argument("--mode", choices=["status", "advance", "stuck", "forecast", "report", "remind"],
                        default="status", help="Operation mode (default: status)")
    parser.add_argument("--deal-id", help="Deal identifier (required for advance mode)")
    parser.add_argument("--stage", help="Target stage for advance (optional, advances one step if not specified)")
    parser.add_argument("--amount", type=float, help="Deal amount (for reference)")
    parser.add_argument("--note", help="Note to log with the transition")
    parser.add_argument("--threshold", type=int, help="Custom stuck threshold in days (default: 14)")
    parser.add_argument("--seed", action="store_true", help="Add sample data for testing")

    args = parser.parse_args()

    data = load_deals()

    if args.seed:
        data = add_sample_data(data)
        print("✓ Sample data added. Run with --mode status to see the pipeline.")
        return

    if args.mode == "status":
        mode_status(args, data)
    elif args.mode == "advance":
        mode_advance(args, data)
    elif args.mode == "stuck":
        mode_stuck(args, data)
    elif args.mode == "forecast":
        mode_forecast(args, data)
    elif args.mode == "report":
        mode_report(args, data)
    elif args.mode == "remind":
        mode_remind(args, data)


if __name__ == "__main__":
    main()
