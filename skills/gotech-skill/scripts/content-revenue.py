#!/usr/bin/env python3
"""
Content-to-Revenue Tracker & Optimizer
Tracks, analyzes, and optimizes content-to-revenue conversion for GoTechSolutions.

Usage:
    python content-revenue.py --mode track --content-type video --content-id yt_001 --metric leads --value 5 --platform youtube --attribution first-touch
    python content-revenue.py --mode analyze
    python content-revenue.py --mode optimize
    python content-revenue.py --mode report
    python content-revenue.py --mode plan
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# --- Configuration ---
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "content-attribution.json"

VALID_MODES = ["track", "analyze", "optimize", "report", "plan"]
VALID_METRICS = ["leads", "qualified_leads", "clients", "revenue", "cost"]
VALID_PLATFORMS = ["youtube", "linkedin", "podcast", "blog", "twitter", "email", "webinar", "tiktok"]
VALID_ATTRIBUTION = ["first-touch", "last-touch"]
VALID_CONTENT_TYPES = ["video", "article", "podcast", "webinar", "email", "social_post", "whitepaper", "case_study"]


def load_data():
    """Load existing attribution data or return empty structure."""
    if not DATA_FILE.exists():
        return {"events": [], "content": {}, "costs": {}}
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        # Ensure all expected keys exist
        data.setdefault("events", [])
        data.setdefault("content", {})
        data.setdefault("costs", {})
        return data
    except (json.JSONDecodeError, IOError):
        return {"events": [], "content": {}, "costs": {}}


def save_data(data):
    """Save attribution data to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Track and optimize content-to-revenue conversion."
    )
    parser.add_argument(
        "--mode",
        choices=VALID_MODES,
        required=True,
        help="Operation mode: track, analyze, optimize, report, or plan",
    )
    parser.add_argument(
        "--content-type",
        choices=VALID_CONTENT_TYPES,
        help="Type of content (video, article, podcast, etc.)",
    )
    parser.add_argument(
        "--content-id",
        help="Unique identifier for the content piece",
    )
    parser.add_argument(
        "--metric",
        choices=VALID_METRICS,
        help="Metric to track: leads, qualified_leads, clients, revenue, cost",
    )
    parser.add_argument(
        "--value",
        type=float,
        help="Numeric value for the metric",
    )
    parser.add_argument(
        "--platform",
        choices=VALID_PLATFORMS,
        help="Platform where content was published",
    )
    parser.add_argument(
        "--attribution",
        choices=VALID_ATTRIBUTION,
        default="last-touch",
        help="Attribution model: first-touch or last-touch",
    )
    parser.add_argument(
        "--topic",
        help="Content topic/tag for categorization",
    )
    parser.add_argument(
        "--title",
        help="Human-readable title of the content",
    )
    parser.add_argument(
        "--start-date",
        help="Start date for analysis (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        help="End date for analysis (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--topic-filter",
        help="Filter by topic",
    )
    parser.add_argument(
        "--export",
        help="Export report to file (CSV or JSON depending on mode)",
    )
    return parser.parse_args()


# =============================================================================
# TRACK MODE
# =============================================================================
def cmd_track(args):
    """Log a content-to-lead conversion event."""
    if not args.content_id:
        print("Error: --content-id is required for track mode.")
        sys.exit(1)
    if not args.metric:
        print("Error: --metric is required for track mode.")
        sys.exit(1)
    if args.value is None:
        print("Error: --value is required for track mode.")
        sys.exit(1)

    data = load_data()
    now = datetime.utcnow().isoformat() + "Z"

    # Create the event
    event = {
        "id": f"evt_{len(data['events']) + 1:06d}",
        "timestamp": now,
        "content_id": args.content_id,
        "content_type": args.content_type or "unknown",
        "platform": args.platform or "unknown",
        "attribution": args.attribution,
        "metric": args.metric,
        "value": args.value,
        "topic": args.topic or "uncategorized",
        "title": args.title or args.content_id,
    }
    data["events"].append(event)

    # Update content metadata
    if args.content_id not in data["content"]:
        data["content"][args.content_id] = {
            "id": args.content_id,
            "title": args.title or args.content_id,
            "type": args.content_type or "unknown",
            "platform": args.platform or "unknown",
            "topic": args.topic or "uncategorized",
            "created_at": now,
        }

    # Track costs separately
    if args.metric == "cost":
        if args.content_id not in data["costs"]:
            data["costs"][args.content_id] = {"total": 0, "entries": []}
        data["costs"][args.content_id]["total"] += args.value
        data["costs"][args.content_id]["entries"].append({
            "amount": args.value,
            "timestamp": now,
        })

    save_data(data)

    print(f"✅ Tracked: {args.metric}={args.value} for content '{args.content_id}'")
    print(f"   Platform: {args.platform or 'unknown'} | Attribution: {args.attribution}")
    print(f"   Total events logged: {len(data['events'])}")
    return event


# =============================================================================
# ANALYZE MODE
# =============================================================================
def cmd_analyze(args):
    """Analyze which content produces the most value."""
    data = load_data()

    if not data["events"]:
        print("No events tracked yet. Use --mode track to log conversions first.")
        return

    # Aggregate metrics by content
    content_metrics = defaultdict(lambda: {
        "leads": 0, "qualified_leads": 0, "clients": 0, "revenue": 0.0
    })
    content_info = {}

    for event in data["events"]:
        cid = event["content_id"]
        metric = event["metric"]
        value = event["value"]
        if metric in content_metrics[cid]:
            content_metrics[cid][metric] += value
        content_info[cid] = {
            "title": event.get("title", cid),
            "type": event.get("content_type", "unknown"),
            "platform": event.get("platform", "unknown"),
            "topic": event.get("topic", "uncategorized"),
        }

    # Add costs
    for cid, cost_data in data.get("costs", {}).items():
        if cid not in content_metrics:
            content_metrics[cid] = {"leads": 0, "qualified_leads": 0, "clients": 0, "revenue": 0.0}
            content_info[cid] = {"title": cid, "type": "unknown", "platform": "unknown", "topic": "uncategorized"}
        content_metrics[cid]["cost"] = cost_data["total"]

    # Compute ROI
    for cid in content_metrics:
        rev = content_metrics[cid]["revenue"]
        cost = content_metrics[cid].get("cost", 0)
        content_metrics[cid]["roi"] = ((rev - cost) / cost * 100) if cost > 0 else None

    # Sort by revenue
    sorted_content = sorted(
        content_metrics.items(),
        key=lambda x: x[1]["revenue"],
        reverse=True
    )

    print("\n" + "=" * 70)
    print("📊 CONTENT PERFORMANCE ANALYSIS")
    print("=" * 70)

    # Summary totals
    total_leads = sum(m["leads"] for m in content_metrics.values())
    total_qualified = sum(m["qualified_leads"] for m in content_metrics.values())
    total_clients = sum(m["clients"] for m in content_metrics.values())
    total_revenue = sum(m["revenue"] for m in content_metrics.values())
    total_cost = sum(m.get("cost", 0) for m in content_metrics.values())

    print(f"\n📈 TOTALS:")
    print(f"   Leads: {total_leads:.0f}")
    print(f"   Qualified Leads: {total_qualified:.0f}")
    print(f"   Clients: {total_clients:.0f}")
    print(f"   Revenue: ${total_revenue:,.2f}")
    print(f"   Content Cost: ${total_cost:,.2f}")
    if total_cost > 0:
        overall_roi = (total_revenue - total_cost) / total_cost * 100
        print(f"   Overall ROI: {overall_roi:.1f}%")

    # By content type
    print(f"\n📁 BY CONTENT TYPE:")
    type_metrics = defaultdict(lambda: {"leads": 0, "revenue": 0.0, "count": 0})
    for cid, metrics in content_metrics.items():
        ctype = content_info[cid]["type"]
        type_metrics[ctype]["leads"] += metrics["leads"]
        type_metrics[ctype]["revenue"] += metrics["revenue"]
        type_metrics[ctype]["count"] += 1

    for ctype, tm in sorted(type_metrics.items(), key=lambda x: x[1]["revenue"], reverse=True):
        avg_rev = tm["revenue"] / tm["count"] if tm["count"] > 0 else 0
        print(f"   {ctype}: {tm['count']} pieces | {tm['leads']:.0f} leads | ${tm['revenue']:,.2f} rev | ${avg_rev:,.2f} avg")

    # By platform
    print(f"\n🌐 BY PLATFORM:")
    platform_metrics = defaultdict(lambda: {"leads": 0, "revenue": 0.0, "count": 0})
    for cid, metrics in content_metrics.items():
        plat = content_info[cid]["platform"]
        platform_metrics[plat]["leads"] += metrics["leads"]
        platform_metrics[plat]["revenue"] += metrics["revenue"]
        platform_metrics[plat]["count"] += 1

    for plat, pm in sorted(platform_metrics.items(), key=lambda x: x[1]["revenue"], reverse=True):
        print(f"   {plat}: {pm['count']} pieces | {pm['leads']:.0f} leads | ${pm['revenue']:,.2f} rev")

    # By topic
    print(f"\n🏷️  BY TOPIC:")
    topic_metrics = defaultdict(lambda: {"leads": 0, "revenue": 0.0, "clients": 0})
    for cid, metrics in content_metrics.items():
        topic = content_info[cid]["topic"]
        topic_metrics[topic]["leads"] += metrics["leads"]
        topic_metrics[topic]["revenue"] += metrics["revenue"]
        topic_metrics[topic]["clients"] += metrics["clients"]

    for topic, tm in sorted(topic_metrics.items(), key=lambda x: x[1]["revenue"], reverse=True):
        print(f"   {topic}: {tm['leads']:.0f} leads | {tm['clients']:.0f} clients | ${tm['revenue']:,.2f} rev")

    # Top performers
    print(f"\n🏆 TOP 5 REVENUE GENERATORS:")
    for i, (cid, metrics) in enumerate(sorted_content[:5], 1):
        info = content_info[cid]
        roi_str = f"{metrics['roi']:.1f}%" if metrics['roi'] is not None else "N/A"
        print(f"   {i}. [{info['type']}] {info['title']}")
        print(f"      Revenue: ${metrics['revenue']:,.2f} | Clients: {metrics['clients']:.0f} | ROI: {roi_str}")

    return content_metrics


# =============================================================================
# OPTIMIZE MODE
# =============================================================================
def cmd_optimize(args):
    """Recommend content strategy based on conversion data."""
    data = load_data()

    if not data["events"]:
        print("No data to optimize. Track some events first with --mode track")
        return

    content_metrics = defaultdict(lambda: {
        "leads": 0, "qualified_leads": 0, "clients": 0, "revenue": 0.0
    })
    content_info = {}

    for event in data["events"]:
        cid = event["content_id"]
        metric = event["metric"]
        value = event["value"]
        if metric in content_metrics[cid]:
            content_metrics[cid][metric] += value
        content_info[cid] = {
            "title": event.get("title", cid),
            "type": event.get("content_type", "unknown"),
            "platform": event.get("platform", "unknown"),
            "topic": event.get("topic", "uncategorized"),
        }

    for cid, cost_data in data.get("costs", {}).items():
        if cid not in content_metrics:
            content_metrics[cid] = {"leads": 0, "qualified_leads": 0, "clients": 0, "revenue": 0.0}
        content_metrics[cid]["cost"] = cost_data["total"]

    print("\n" + "=" * 70)
    print("🚀 CONTENT STRATEGY OPTIMIZATION RECOMMENDATIONS")
    print("=" * 70)

    # 1. Topics driving highest-value clients
    print("\n🎯 TOPICS DRIVING HIGHEST-VALUE CLIENTS:")
    topic_data = defaultdict(lambda: {"clients": 0, "revenue": 0.0, "leads": 0})
    for cid, m in content_metrics.items():
        topic = content_info[cid]["topic"]
        topic_data[topic]["clients"] += m["clients"]
        topic_data[topic]["revenue"] += m["revenue"]
        topic_data[topic]["leads"] += m["leads"]

    sorted_topics = sorted(topic_data.items(), key=lambda x: x[1]["revenue"], reverse=True)
    for topic, td in sorted_topics[:5]:
        avg_deal = td["revenue"] / td["clients"] if td["clients"] > 0 else 0
        print(f"   • {topic}: {td['clients']:.0f} clients, ${td['revenue']:,.2f} (${avg_deal:,.2f} avg deal)")

    # 2. Platforms driving most leads
    print("\n📱 PLATFORMS BY LEAD VOLUME:")
    platform_data = defaultdict(lambda: {"leads": 0, "revenue": 0.0, "count": 0})
    for cid, m in content_metrics.items():
        plat = content_info[cid]["platform"]
        platform_data[plat]["leads"] += m["leads"]
        platform_data[plat]["revenue"] += m["revenue"]
        platform_data[plat]["count"] += 1

    for plat, pd in sorted(platform_data.items(), key=lambda x: x[1]["leads"], reverse=True):
        print(f"   • {plat}: {pd['leads']:.0f} leads, ${pd['revenue']:,.2f} revenue")

    # 3. Best posting times (from event timestamps)
    print("\n⏰ BEST POSTING TIMES (by conversion activity):")
    hour_dist = defaultdict(int)
    for event in data["events"]:
        try:
            ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
            hour_dist[ts.hour] += 1
        except (ValueError, KeyError):
            pass

    if hour_dist:
        peak_hours = sorted(hour_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        for hour, count in peak_hours:
            print(f"   • {hour:02d}:00 UTC — {count} conversion events")

    # 4. Content gaps
    print("\n🔍 CONTENT GAPS TO FILL:")
    all_types = set(ct["type"] for ct in content_info.values())
    all_topics = set(ct["topic"] for ct in content_info.values())
    all_platforms = set(ct["platform"] for ct in content_info.values())

    missing_types = set(VALID_CONTENT_TYPES) - all_types
    missing_platforms = set(VALID_PLATFORMS) - all_platforms

    if missing_types:
        print(f"   Content types not yet explored: {', '.join(missing_types)}")
    if missing_platforms:
        print(f"   Platforms not yet explored: {', '.join(missing_platforms)}")
    if not missing_types and not missing_platforms:
        print("   All content types and platforms have some data. Focus on doubling down on top performers.")

    # 5. ROI recommendations
    print("\n💡 ROI-BASED RECOMMENDATIONS:")
    roi_data = []
    for cid, m in content_metrics.items():
        cost = m.get("cost", 0)
        if cost > 0 and m["revenue"] > 0:
            roi = (m["revenue"] - cost) / cost * 100
            roi_data.append((cid, roi, m["revenue"], cost))

    roi_data.sort(key=lambda x: x[1], reverse=True)
    if roi_data:
        print("   Top ROI content (increase investment):")
        for cid, roi, rev, cost in roi_data[:3]:
            print(f"   • {content_info[cid]['title']}: {roi:.0f}% ROI (${rev:,.2f} rev, ${cost:,.2f} cost)")
        print("   Lowest ROI content (reduce or improve):")
        for cid, roi, rev, cost in roi_data[-2:]:
            print(f"   • {content_info[cid]['title']}: {roi:.0f}% ROI — consider refreshing or retiring")

    # 6. Conversion rate insights
    print("\n📊 CONVERSION FUNNEL INSIGHTS:")
    total_leads = sum(m["leads"] for m in content_metrics.values())
    total_qualified = sum(m["qualified_leads"] for m in content_metrics.values())
    total_clients = sum(m["clients"] for m in content_metrics.values())

    if total_leads > 0:
        lead_to_qualified = (total_qualified / total_leads * 100) if total_leads else 0
        lead_to_client = (total_clients / total_leads * 100) if total_leads else 0
        qualified_to_client = (total_clients / total_qualified * 100) if total_qualified else 0
        print(f"   Leads → Qualified: {lead_to_qualified:.1f}%")
        print(f"   Qualified → Client: {qualified_to_client:.1f}%")
        print(f"   Overall Lead → Client: {lead_to_client:.1f}%")

        if lead_to_qualified < 20:
            print("   ⚠️  Lead qualification rate is low. Consider better CTAs or lead magnets.")
        if lead_to_client < 5:
            print("   ⚠️  Lead-to-client conversion is low. Review sales follow-up sequences.")


# =============================================================================
# REPORT MODE
# =============================================================================
def cmd_report(args):
    """Generate full content attribution report."""
    data = load_data()

    if not data["events"]:
        print("No events to report. Track some data first.")
        return

    # Build comprehensive content attribution
    content_metrics = defaultdict(lambda: {
        "leads": 0, "qualified_leads": 0, "clients": 0, "revenue": 0.0
    })
    content_info = {}

    for event in data["events"]:
        cid = event["content_id"]
        metric = event["metric"]
        value = event["value"]
        if metric in content_metrics[cid]:
            content_metrics[cid][metric] += value
        content_info[cid] = {
            "title": event.get("title", cid),
            "type": event.get("content_type", "unknown"),
            "platform": event.get("platform", "unknown"),
            "topic": event.get("topic", "uncategorized"),
        }

    for cid, cost_data in data.get("costs", {}).items():
        if cid not in content_metrics:
            content_metrics[cid] = {"leads": 0, "qualified_leads": 0, "clients": 0, "revenue": 0.0}
            content_info[cid] = {"title": cid, "type": "unknown", "platform": "unknown", "topic": "uncategorized"}
        content_metrics[cid]["cost"] = cost_data["total"]

    print("\n" + "=" * 70)
    print("📋 FULL CONTENT ATTRIBUTION REPORT")
    print(f"   Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)

    # Section 1: Content piece → leads → clients → revenue
    print("\n🔗 CONTENT → LEADS → CLIENTS → REVENUE:")
    print(f"   {'Content':<30} {'Type':<12} {'Leads':>6} {'Clients':>8} {'Revenue':>12}")
    print("   " + "-" * 70)

    sorted_content = sorted(content_metrics.items(), key=lambda x: x[1]["revenue"], reverse=True)
    for cid, metrics in sorted_content:
        info = content_info[cid]
        title = info["title"][:28]
        print(f"   {title:<30} {info['type']:<12} {metrics['leads']:>6.0f} {metrics['clients']:>8.0f} ${metrics['revenue']:>11,.2f}")

    # Section 2: Conversion rates by content type
    print("\n📊 CONVERSION RATES BY CONTENT TYPE:")
    type_funnel = defaultdict(lambda: {"leads": 0, "qualified_leads": 0, "clients": 0, "revenue": 0.0, "count": 0})
    for cid, metrics in content_metrics.items():
        ctype = content_info[cid]["type"]
        for key in ["leads", "qualified_leads", "clients", "revenue"]:
            type_funnel[ctype][key] += metrics[key]
        type_funnel[ctype]["count"] += 1

    print(f"   {'Type':<15} {'Pieces':>7} {'Leads':>7} {'Qual':>7} {'Clients':>8} {'Rev':>12} {'L→C%':>7}")
    print("   " + "-" * 65)
    for ctype, tf in sorted(type_funnel.items(), key=lambda x: x[1]["revenue"], reverse=True):
        l_to_c = (tf["clients"] / tf["leads"] * 100) if tf["leads"] > 0 else 0
        print(f"   {ctype:<15} {tf['count']:>7} {tf['leads']:>7.0f} {tf['qualified_leads']:>7.0f} {tf['clients']:>8.0f} ${tf['revenue']:>11,.2f} {l_to_c:>6.1f}%")

    # Section 3: Top 10 revenue-generating content pieces
    print("\n💰 TOP 10 REVENUE-GENERATING CONTENT PIECES:")
    for i, (cid, metrics) in enumerate(sorted_content[:10], 1):
        info = content_info[cid]
        cost = metrics.get("cost", 0)
        roi_str = f"{(metrics['revenue'] - cost) / cost * 100:.0f}%" if cost > 0 else "N/A"
        print(f"   {i:>2}. [{info['platform']}] {info['title']}")
        print(f"       ${metrics['revenue']:>10,.2f} revenue | {metrics['clients']:.0f} clients | ROI: {roi_str}")

    # Section 4: Funnel visualization data
    print("\n🔻 FUNNEL VISUALIZATION DATA:")
    total_leads = sum(m["leads"] for m in content_metrics.values())
    total_qualified = sum(m["qualified_leads"] for m in content_metrics.values())
    total_clients = sum(m["clients"] for m in content_metrics.values())
    total_revenue = sum(m["revenue"] for m in content_metrics.values())

    funnel_stages = [
        ("Leads", total_leads),
        ("Qualified Leads", total_qualified),
        ("Clients", total_clients),
    ]

    max_width = 40
    max_val = max((v for _, v in funnel_stages if v > 0), default=1)
    for stage, value in funnel_stages:
        bar_width = int((value / max_val) * max_width) if max_val > 0 else 0
        pct = (value / total_leads * 100) if total_leads > 0 and value > 0 else 0
        bar = "█" * bar_width
        print(f"   {stage:<18} {bar} {value:.0f} ({pct:.1f}%)")

    print(f"\n   Total Revenue: ${total_revenue:,.2f}")

    # Export if requested
    if args.export:
        export_data = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total_leads": total_leads,
                "total_qualified_leads": total_qualified,
                "total_clients": total_clients,
                "total_revenue": total_revenue,
            },
            "content_attribution": [
                {
                    "content_id": cid,
                    **content_info[cid],
                    **metrics,
                }
                for cid, metrics in sorted_content
            ],
        }
        with open(args.export, "w") as f:
            json.dump(export_data, f, indent=2)
        print(f"\n📁 Report exported to: {args.export}")


# =============================================================================
# PLAN MODE
# =============================================================================
def cmd_plan(args):
    """Suggest next week's content based on data and strategy."""
    data = load_data()

    print("\n" + "=" * 70)
    print("📅 NEXT WEEK CONTENT PLAN")
    print(f"   Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)

    # Analyze what's converting best
    content_metrics = defaultdict(lambda: {
        "leads": 0, "qualified_leads": 0, "clients": 0, "revenue": 0.0
    })
    content_info = {}

    for event in data.get("events", []):
        cid = event["content_id"]
        metric = event["metric"]
        value = event["value"]
        if metric in content_metrics[cid]:
            content_metrics[cid][metric] += value
        content_info[cid] = {
            "title": event.get("title", cid),
            "type": event.get("content_type", "unknown"),
            "platform": event.get("platform", "unknown"),
            "topic": event.get("topic", "uncategorized"),
        }

    # Determine current month for seasonal relevance
    current_month = datetime.utcnow().month
    seasonal_themes = {
        1: ["New Year planning", "Annual tech reviews", "Goal setting"],
        2: ["Valentine's partnerships", "Love your stack", "Team collaboration"],
        3: ["Spring cleaning code", "Q1 reviews", "Tax automation"],
        4: ["AI spring updates", "Growth hacking", "Scale up strategies"],
        5: ["Mother's Day automation", "Pre-summer planning", "Security audits"],
        6: ["Mid-year reviews", "Summer kickoff", "Remote work tech"],
        7: ["Independence from legacy", "Mid-summer optimization", "Automation"],
        8: ["Back-to-school tech", "Fall prep", "Migration strategies"],
        9: ["Q4 planning prep", "Fall launch", "Enterprise readiness"],
        10: ["Halloween horror stories", "Cybersecurity month", "Year-end prep"],
        11: ["Black Friday deals", "Thanksgiving gratitude", "Giving back"],
        12: ["Year in review", "Holiday automation", "2026 predictions"],
    }

    # 1. What's converting best
    print("\n🔥 TOP PERFORMING CONTENT (double down on these):")
    sorted_content = sorted(content_metrics.items(), key=lambda x: x[1]["revenue"], reverse=True)
    top_performers = sorted_content[:3]
    for cid, metrics in top_performers:
        info = content_info[cid]
        print(f"   • [{info['type']}] {info['title']} — ${metrics['revenue']:,.2f} revenue")
        print(f"     Suggestion: Create a follow-up or sequel piece on the same topic")

    # 2. What's in the pipeline (content with costs but low revenue = in progress)
    print("\n🔧 PIPELINE CONTENT (needs promotion push):")
    pipeline_found = False
    for cid, metrics in content_metrics.items():
        cost = metrics.get("cost", 0)
        if cost > 0 and metrics["revenue"] == 0:
            info = content_info[cid]
            print(f"   • [{info['type']}] {info['title']} — ${cost:,.2f} invested, no revenue yet")
            print(f"     Action: Promote on additional platforms, add stronger CTAs")
            pipeline_found = True
    if not pipeline_found:
        print("   No content currently in pipeline. Consider creating new pieces.")

    # 3. Seasonal relevance
    print(f"\n🌟 SEASONAL THEMES FOR {datetime.utcnow().strftime('%B')}:")
    for theme in seasonal_themes.get(current_month, []):
        print(f"   • {theme}")

    # 4. Service promotion schedule
    print("\n📢 SERVICE PROMOTION SUGGESTIONS:")
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    suggestions = [
        ("Monday", "Publish thought-leadership article on LinkedIn"),
        ("Tuesday", "Release educational video on YouTube"),
        ("Wednesday", "Send newsletter with case study + CTA"),
        ("Thursday", "Go live or host webinar on trending topic"),
        ("Friday", "Share social proof / client success story"),
    ]
    for day, suggestion in suggestions:
        print(f"   {day}: {suggestion}")

    # 5. Weekly content mix recommendation
    print("\n📋 RECOMMENDED WEEKLY CONTENT MIX:")
    if top_performers:
        top_type = content_info[top_performers[0][0]]["type"]
        top_platform = content_info[top_performers[0][0]]["platform"]
        print(f"   • 2x {top_type} posts on {top_platform} (your best converter)")
        print(f"   • 1x long-form article (SEO + lead gen)")
        print(f"   • 1x email newsletter (nurture sequence)")
        print(f"   • 1x social proof post (testimonial/case study)")
    else:
        print("   • 2x video content (YouTube)")
        print("   • 1x blog article (SEO)")
        print("   • 1x LinkedIn post (professional reach)")
        print("   • 1x email newsletter")

    # 6. Quick wins
    print("\n⚡ QUICK WINS FOR THIS WEEK:")
    print("   • Add UTM parameters to all content links")
    print("   • Create a lead magnet (checklist, template, or guide)")
    print("   • Set up email automation for content downloads")
    print("   • Repurpose top-performing content into different formats")


# =============================================================================
# MAIN
# =============================================================================
def main():
    args = parse_args()

    mode_handlers = {
        "track": cmd_track,
        "analyze": cmd_analyze,
        "optimize": cmd_optimize,
        "report": cmd_report,
        "plan": cmd_plan,
    }

    handler = mode_handlers.get(args.mode)
    if handler:
        handler(args)
    else:
        print(f"Unknown mode: {args.mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
