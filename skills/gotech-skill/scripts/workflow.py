#!/usr/bin/env python3
"""
GoTech Solutions — Master Workflow Engine
North Star: $1,000,000 cash in bank ASAP
Starting Point: $500 (June 24, 2026)

Usage:
  python3 workflow.py --mode daily
  python3 workflow.py --mode weekly
  python3 workflow.py --mode cash-update --amount 1200
  python3 workflow.py --mode lead-add --name "John" --email "john@co.com" --source "linkedin"
  python3 workflow.py --mode content-plan
  python3 workflow.py --mode status
  python3 workflow.py --mode full
"""

import argparse
import json
import os
import sys
import subprocess
import datetime
import csv
from pathlib import Path

# === CONFIG ===
STARTUP_DIR = Path(__file__).parent
DATA_DIR = STARTUP_DIR / "data"
LOGS_DIR = STARTUP_DIR / "logs"
REPORTS_DIR = STARTUP_DIR / "reports"
WORKFLOWS_DIR = STARTUP_DIR / "workflows"
SCRIPTS_DIR = STARTUP_DIR / "scripts"

# Ensure directories exist
for d in [DATA_DIR, LOGS_DIR, REPORTS_DIR, WORKFLOWS_DIR]:
    d.mkdir(exist_ok=True)

# === DATA STORE ===
CASH_FILE = DATA_DIR / "cash.json"
LEADS_FILE = DATA_DIR / "leads.json"
CLIENTS_FILE = DATA_DIR / "clients.json"
CONTENT_FILE = DATA_DIR / "content_calendar.json"
METRICS_FILE = DATA_DIR / "metrics.json"
TASKS_FILE = DATA_DIR / "tasks.json"

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def today_str():
    return datetime.date.today().isoformat()

def load_json(path, default=None):
    if default is None:
        default = {}
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def log(msg, level="INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    log_file = LOGS_DIR / f"workflow-{today_str()}.log"
    with open(log_file, 'a') as f:
        f.write(line + "\n")

# === CASH WORKFLOW ===
def cash_update(amount, note=""):
    """Update cash balance and log the transaction."""
    data = load_json(CASH_FILE, {"balance": 500, "transactions": [], "starting_balance": 500, "start_date": "2026-06-24"})
    old_balance = data["balance"]
    data["balance"] += amount
    tx = {
        "date": now_iso(),
        "amount": amount,
        "balance": data["balance"],
        "note": note,
        "running_total": data["balance"]
    }
    data["transactions"].append(tx)
    save_json(CASH_FILE, data)
    
    # Calculate days to $1M
    target = 1_000_000
    daily_rate = calculate_daily_rate(data)
    if daily_rate > 0:
        days_to_go = (target - data["balance"]) / daily_rate
    else:
        days_to_go = float('inf')
    
    log(f"Cash update: {'+'if amount>=0 else ''}{amount} | Balance: ${data['balance']:,} | Note: {note}")
    log(f"Days to $1M at current rate: {days_to_go:.0f} days ({days_to_go/30:.1f} months)")
    
    return data

def calculate_daily_rate(data):
    """Calculate average daily revenue rate from transaction history."""
    txs = data.get("transactions", [])
    if len(txs) < 2:
        return 0
    # Use last 30 days of positive transactions
    recent = [t for t in txs if t["amount"] > 0][-30:]
    if not recent:
        return 0
    total = sum(t["amount"] for t in recent)
    # Estimate days covered
    return total / 30  # Simplified: 30-day rolling average

def cash_status():
    """Show current cash position."""
    data = load_json(CASH_FILE, {"balance": 500, "transactions": []})
    target = 1_000_000
    progress = (data["balance"] / target) * 100
    daily_rate = calculate_daily_rate(data)
    
    print(f"""
╔══════════════════════════════════════════════════╗
║          GOTECH CASH POSITION                   ║
╠══════════════════════════════════════════════════╣
║  Current Balance:     ${data['balance']:>12,}              ║
║  Starting Balance:    ${data.get('starting_balance', 500):>12,}              ║
║  Target:             ${target:>12,}              ║
║  Progress:            {progress:>11.4f}%              ║
║  Daily Rate (avg):    ${daily_rate:>12,.0f}              ║
║  Days to $1M:         {((target - data['balance']) / daily_rate) if daily_rate > 0 else 'N/A':>12}              ║
╚══════════════════════════════════════════════════╝
""")
    return data

# === LEAD WORKFLOW ===
def lead_add(name, email, source, interest="", company="", phone="", value=0):
    """Add a new lead to the pipeline."""
    leads = load_json(LEADS_FILE, {"leads": [], "stats": {"total": 0, "by_source": {}}})
    
    lead = {
        "id": f"lead-{len(leads['leads'])+1:04d}",
        "name": name,
        "email": email,
        "company": company,
        "phone": phone,
        "source": source,
        "interest": interest,
        "estimated_value": value,
        "stage": "new",
        "score": score_lead(interest, source, value),
        "created_at": now_iso(),
        "last_contact": None,
        "notes": []
    }
    
    leads["leads"].append(lead)
    leads["stats"]["total"] += 1
    leads["stats"]["by_source"][source] = leads["stats"]["by_source"].get(source, 0) + 1
    save_json(LEADS_FILE, leads)
    
    log(f"New lead added: {name} ({email}) from {source} | Score: {lead['score']} | Value: ${value}")
    return lead

def score_lead(interest, source, value):
    """Score a lead 1-100 based on ICP fit."""
    score = 50
    # Source quality
    source_scores = {"referral": 20, "linkedin": 15, "website": 10, "cold": 0, "event": 12}
    score += source_scores.get(source, 5)
    # Interest alignment
    high_value = ["ai-ops", "bundle", "cro"]
    if interest in high_value:
        score += 15
    # Estimated value
    if value > 1000:
        score += 10
    elif value > 500:
        score += 5
    return min(100, score)

def lead_list(stage=None, limit=20):
    """List leads, optionally filtered by stage."""
    leads = load_json(LEADS_FILE, {"leads": []})
    filtered = leads["leads"]
    if stage:
        filtered = [l for l in filtered if l["stage"] == stage]
    filtered = sorted(filtered, key=lambda x: x.get("score", 0), reverse=True)[:limit]
    
    print(f"\n{'ID':<12} {'Name':<25} {'Stage':<12} {'Score':<6} {'Value':<10} {'Source':<12}")
    print("-" * 80)
    for l in filtered:
        print(f"{l['id']:<12} {l['name']:<25} {l['stage']:<12} {l['score']:<6} ${l['estimated_value']:<9,} {l['source']:<12}")
    print(f"\nTotal: {len(filtered)} leads")
    return filtered

def lead_advance(lead_id, new_stage, note=""):
    """Move a lead to a new pipeline stage."""
    leads = load_json(LEADS_FILE, {"leads": []})
    for l in leads["leads"]:
        if l["id"] == lead_id:
            old_stage = l["stage"]
            l["stage"] = new_stage
            l["last_contact"] = now_iso()
            if note:
                l["notes"].append({"date": now_iso(), "note": note})
            save_json(LEADS_FILE, leads)
            log(f"Lead {lead_id} advanced: {old_stage} -> {new_stage} | {note}")
            return l
    log(f"Lead {lead_id} not found", "ERROR")
    return None

# === CLIENT WORKFLOW ===
def client_add(name, email, company, service, plan, monthly_value):
    """Convert a lead to a client."""
    clients = load_json(CLIENTS_FILE, {"clients": [], "total_mrr": 0})
    
    client = {
        "id": f"client-{len(clients['clients'])+1:04d}",
        "name": name,
        "email": email,
        "company": company,
        "service": service,
        "plan": plan,
        "monthly_value": monthly_value,
        "status": "active",
        "start_date": today_str(),
        "onboarding_complete": False,
        "notes": []
    }
    
    clients["clients"].append(client)
    clients["total_mrr"] += monthly_value
    save_json(CLIENTS_FILE, clients)
    
    # Update cash
    cash_update(monthly_value, f"New client: {company} — {service} ({plan})")
    
    log(f"New client: {name} ({company}) | {service} | ${monthly_value}/mo | MRR: ${clients['total_mrr']:,}")
    return client

def client_list():
    """Show all active clients."""
    clients = load_json(CLIENTS_FILE, {"clients": [], "total_mrr": 0})
    
    print(f"\n{'ID':<12} {'Company':<25} {'Service':<18} {'Plan':<10} {'Value':<10} {'Status':<10}")
    print("-" * 95)
    for c in clients["clients"]:
        print(f"{c['id']:<12} {c['company']:<25} {c['service']:<18} {c['plan']:<10} ${c['monthly_value']:<9,} {c['status']:<10}")
    
    total_annual = clients["total_mrr"] * 12
    print(f"\nMRR: ${clients['total_mrr']:,}/mo | ARR: ${total_annual:,}/yr | Clients: {len(clients['clients'])}")
    return clients

# === CONTENT WORKFLOW ===
def content_plan():
    """Generate a weekly content plan."""
    plan = load_json(CONTENT_FILE, {"week_of": today_str(), "items": []})
    
    # Auto-generate from episode data
    seo_data = load_json(SCRIPTS_DIR / "yt_seo_full.json", [])
    
    items = []
    today = datetime.date.today()
    for i, ep in enumerate(seo_data[:7]):
        publish_date = (today + datetime.timedelta(days=i)).isoformat()
        items.append({
            "date": publish_date,
            "type": "episode",
            "title": ep.get("title", ep.get("topic", f"EP{ep['ep']}")),
            "platforms": ["youtube", "facebook", "tiktok"],
            "shorts_count": 3,
            "status": "planned"
        })
    
    plan = {
        "week_of": today_str(),
        "items": items,
        "shorts_target": 21,
        "posts_target": 14,
        "created_at": now_iso()
    }
    save_json(CONTENT_FILE, plan)
    
    log(f"Content plan generated: {len(items)} episodes, {plan['shorts_target']} shorts, {plan['posts_target']} posts")
    return plan

# === METRICS WORKFLOW ===
def metrics_update():
    """Aggregate all metrics into a single snapshot."""
    cash = load_json(CASH_FILE, {"balance": 500})
    leads = load_json(LEADS_FILE, {"leads": []})
    clients = load_json(CLIENTS_FILE, {"clients": [], "total_mrr": 0})
    
    metrics = {
        "date": today_str(),
        "timestamp": now_iso(),
        "cash_balance": cash["balance"],
        "total_leads": len(leads["leads"]),
        "new_leads_today": len([l for l in leads["leads"] if l.get("created_at", "").startswith(today_str())]),
        "qualified_leads": len([l for l in leads["leads"] if l["stage"] in ["qualified", "proposal"]]),
        "active_clients": len([c for c in clients["clients"] if c["status"] == "active"]),
        "mrr": clients["total_mrr"],
        "arr": clients["total_mrr"] * 12,
        "pipeline_value": sum(l.get("estimated_value", 0) for l in leads["leads"] if l["stage"] not in ["won", "lost"]),
        "days_to_1m": ((1_000_000 - cash["balance"]) / calculate_daily_rate(cash)) if calculate_daily_rate(cash) > 0 else None
    }
    
    # Append to metrics history
    history = load_json(METRICS_FILE, {"snapshots": []})
    history["snapshots"].append(metrics)
    save_json(METRICS_FILE, history)
    
    log(f"Metrics snapshot: ${cash['balance']:,} cash | {metrics['total_leads']} leads | {metrics['active_clients']} clients | ${metrics['mrr']:,} MRR")
    return metrics

def metrics_show():
    """Display latest metrics dashboard."""
    history = load_json(METRICS_FILE, {"snapshots": []})
    if not history["snapshots"]:
        log("No metrics yet. Run --mode metrics-update first.", "WARN")
        return {}
    
    m = history["snapshots"][-1]
    print(f"""
╔══════════════════════════════════════════════════╗
║          GOTECH METRICS DASHBOARD               ║
║          {m['date']}                        ║
╠══════════════════════════════════════════════════╣
║  Cash Balance:        ${m['cash_balance']:>12,}              ║
║  Total Leads:         {m['total_leads']:>12}              ║
║  Qualified Leads:     {m['qualified_leads']:>12}              ║
║  Active Clients:      {m['active_clients']:>12}              ║
║  MRR:                 ${m['mrr']:>12,}              ║
║  ARR:                 ${m['arr']:>12,}              ║
║  Pipeline Value:      ${m['pipeline_value']:>12,}              ║
║  Days to $1M:         {str(m.get('days_to_1m', 'N/A')):>12}              ║
╚══════════════════════════════════════════════════╝
""")
    return m

# === DAILY WORKFLOW ===
def daily():
    """Run the daily workflow."""
    log("=== DAILY WORKFLOW START ===")
    
    # 1. Update metrics
    metrics_update()
    
    # 2. Cash status
    cash_status()
    
    # 3. Lead summary
    leads = load_json(LEADS_FILE, {"leads": []})
    new_leads = [l for l in leads["leads"] if l.get("created_at", "").startswith(today_str())]
    if new_leads:
        log(f"New leads today: {len(new_leads)}")
        for l in new_leads:
            log(f"  - {l['name']} ({l['source']}) | Score: {l['score']}")
    
    # 4. Content plan check
    plan = load_json(CONTENT_FILE, {})
    if plan.get("week_of") != today_str():
        content_plan()
        log("Weekly content plan generated")
    
    # 5. Generate daily report
    report = generate_daily_report()
    report_path = REPORTS_DIR / f"daily-{today_str()}.md"
    with open(report_path, 'w') as f:
        f.write(report)
    log(f"Daily report saved: {report_path}")
    
    log("=== DAILY WORKFLOW COMPLETE ===")
    return True

def generate_daily_report():
    """Generate a daily markdown report."""
    cash = load_json(CASH_FILE, {"balance": 500, "transactions": []})
    leads = load_json(LEADS_FILE, {"leads": []})
    clients = load_json(CLIENTS_FILE, {"clients": [], "total_mrr": 0})
    
    today_leads = [l for l in leads["leads"] if l.get("created_at", "").startswith(today_str())]
    recent_tx = cash.get("transactions", [])[-5:]
    
    report = f"""# GoTech Daily Report — {today_str()}

## Cash Position
- **Balance:** ${cash['balance']:,}
- **Starting:** ${cash.get('starting_balance', 500):,} (2026-06-24)
- **Net Change:** ${cash['balance'] - cash.get('starting_balance', 500):+,}

### Recent Transactions
"""
    for tx in recent_tx:
        report += f"- {tx['date'][:10]} | {'+'if tx['amount']>=0 else ''}${tx['amount']:,} | {tx.get('note', '')} | Balance: ${tx['balance']:,}\n"
    
    report += f"""
## Leads
- **New Today:** {len(today_leads)}
- **Total Pipeline:** {len(leads['leads'])}
- **Qualified:** {len([l for l in leads['leads'] if l['stage'] in ['qualified', 'proposal']])}

### New Leads
"""
    for l in today_leads:
        report += f"- [{l['score']}] {l['name']} ({l['source']}) — {l.get('interest', 'unknown')} | ${l.get('estimated_value', 0):,}\n"
    
    report += f"""
## Clients
- **Active:** {len([c for c in clients['clients'] if c['status'] == 'active'])}**
- **MRR:** ${clients['total_mrr']:,}/mo
- **ARR:** ${clients['total_mrr'] * 12:,}/yr

## Action Items
- [ ] Review new leads and follow up
- [ ] Check pipeline for stalled deals
- [ ] Post daily content
- [ ] Update cash balance if changed

---
*Generated by GoTech Workflow Engine*
"""
    return report

# === WEEKLY WORKFLOW ===
def weekly():
    """Run the weekly workflow."""
    log("=== WEEKLY WORKFLOW START ===")
    
    # 1. Run daily first
    daily()
    
    # 2. Generate weekly report
    report = generate_weekly_report()
    report_path = REPORTS_DIR / f"weekly-{today_str()}.md"
    with open(report_path, 'w') as f:
        f.write(report)
    log(f"Weekly report saved: {report_path}")
    
    # 3. Content plan for next week
    content_plan()
    log("Next week content plan generated")
    
    log("=== WEEKLY WORKFLOW COMPLETE ===")
    return True

def generate_weekly_report():
    """Generate a weekly markdown report."""
    cash = load_json(CASH_FILE, {"balance": 500, "transactions": []})
    leads = load_json(LEADS_FILE, {"leads": []})
    clients = load_json(CLIENTS_FILE, {"clients": [], "total_mrr": 0})
    
    # Get this week's transactions
    week_start = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
    week_tx = [t for t in cash.get("transactions", []) if t.get("date", "") >= week_start.isoformat()]
    week_revenue = sum(t["amount"] for t in week_tx if t["amount"] > 0)
    week_expenses = sum(abs(t["amount"]) for t in week_tx if t["amount"] < 0)
    
    # Leads this week
    week_leads = [l for l in leads["leads"] if l.get("created_at", "") >= week_start.isoformat()]
    
    report = f"""# GoTech Weekly Report — Week of {week_start.isoformat()}

## Cash Summary
- **Balance:** ${cash['balance']:,}
- **This Week Revenue:** ${week_revenue:,}
- **This Week Expenses:** ${week_expenses:,}
- **Net Cash Flow:** ${week_revenue - week_expenses:+,}

## Leads Summary
- **New This Week:** {len(week_leads)}
- **Total Pipeline:** {len(leads['leads'])}
- **By Stage:"""
    
    stages = {}
    for l in leads["leads"]:
        stages[l["stage"]] = stages.get(l["stage"], 0) + 1
    for stage, count in sorted(stages.items()):
        report += f"\n  - {stage}: {count}"
    
    report += f"""

## Clients
- **Active:** {len([c for c in clients['clients'] if c['status'] == 'active'])}**
- **MRR:** ${clients['total_mrr']:,}/mo
- **ARR:** ${clients['total_mrr'] * 12:,}/yr

## Top Priorities Next Week
1. Follow up on qualified leads
2. Convert pipeline to clients
3. Post 21 shorts across platforms
4. Review and update cash forecast

---
*Generated by GoTech Workflow Engine*
"""
    return report

# === FULL WORKFLOW ===
def full():
    """Run the complete workflow."""
    log("=== FULL WORKFLOW START ===")
    daily()
    weekly()
    metrics_show()
    log("=== FULL WORKFLOW COMPLETE ===")

# === STATUS ===
def status():
    """Show system status."""
    print(f"""
╔══════════════════════════════════════════════════╗
║          GOTECH WORKFLOW ENGINE                  ║
║          Status Check                           ║
╠══════════════════════════════════════════════════╣
║  Data Files:                                    ║
║    Cash:     {'EXISTS' if CASH_FILE.exists() else 'MISSING':<10}  ({CASH_FILE.name})              ║
║    Leads:    {'EXISTS' if LEADS_FILE.exists() else 'MISSING':<10}  ({LEADS_FILE.name})              ║
║    Clients:  {'EXISTS' if CLIENTS_FILE.exists() else 'MISSING':<10}  ({CLIENTS_FILE.name})              ║
║    Content:  {'EXISTS' if CONTENT_FILE.exists() else 'MISSING':<10}  ({CONTENT_FILE.name})              ║
║    Metrics:  {'EXISTS' if METRICS_FILE.exists() else 'MISSING':<10}  ({METRICS_FILE.name})              ║
║    Tasks:    {'EXISTS' if TASKS_FILE.exists() else 'MISSING':<10}  ({TASKS_FILE.name})              ║
╠══════════════════════════════════════════════════╣
║  Directories:                                   ║
║    Workflows: {'EXISTS' if WORKFLOWS_DIR.exists() else 'MISSING':<10}  ({WORKFLOWS_DIR.name})              ║
║    Logs:      {'EXISTS' if LOGS_DIR.exists() else 'MISSING':<10}  ({LOGS_DIR.name})              ║
║    Reports:   {'EXISTS' if REPORTS_DIR.exists() else 'MISSING':<10}  ({REPORTS_DIR.name})              ║
║    Scripts:   {'EXISTS' if SCRIPTS_DIR.exists() else 'MISSING':<10}  ({SCRIPTS_DIR.name})              ║
╠══════════════════════════════════════════════════╣
║  Version: 2.0.0                                  ║
║  North Star: $1,000,000 cash ASAP               ║
║  Starting: $500 (2026-06-24)                    ║
╚══════════════════════════════════════════════════╝
""")

# === MAIN ===
def main():
    parser = argparse.ArgumentParser(description="GoTech Workflow Engine — $1M Cash ASAP")
    parser.add_argument("--mode", default="status",
                        choices=["daily", "weekly", "full", "status", "cash-update",
                                 "cash-status", "lead-add", "lead-list", "lead-advance",
                                 "client-add", "client-list", "content-plan",
                                 "metrics-update", "metrics-show"],
                        help="Workflow mode")
    parser.add_argument("--amount", type=float, help="Cash amount (for cash-update)")
    parser.add_argument("--note", default="", help="Note for cash transaction")
    parser.add_argument("--name", help="Lead/Client name")
    parser.add_argument("--email", help="Lead/Client email")
    parser.add_argument("--company", default="", help="Company name")
    parser.add_argument("--phone", default="", help="Phone number")
    parser.add_argument("--source", default="manual", help="Lead source")
    parser.add_argument("--interest", default="", help="Interest/service of interest")
    parser.add_argument("--value", type=float, default=0, help="Estimated value")
    parser.add_argument("--service", default="", help="Service line")
    parser.add_argument("--plan", default="monthly", help="Plan type")
    parser.add_argument("--stage", default="", help="Pipeline stage")
    parser.add_argument("--limit", type=int, default=20, help="Limit results")
    
    args = parser.parse_args()
    
    if args.mode == "status":
        status()
    elif args.mode == "daily":
        daily()
    elif args.mode == "weekly":
        weekly()
    elif args.mode == "full":
        full()
    elif args.mode == "cash-update":
        if args.amount is None:
            print("ERROR: --amount required for cash-update")
            sys.exit(1)
        cash_update(args.amount, args.note)
    elif args.mode == "cash-status":
        cash_status()
    elif args.mode == "lead-add":
        if not args.name or not args.email:
            print("ERROR: --name and --email required for lead-add")
            sys.exit(1)
        lead_add(args.name, args.email, args.source, args.interest, args.company, args.phone, args.value)
    elif args.mode == "lead-list":
        lead_list(args.stage, args.limit)
    elif args.mode == "lead-advance":
        if not args.name or not args.stage:
            print("ERROR: --name (ID) and --stage required for lead-advance")
            sys.exit(1)
        lead_advance(args.name, args.stage, args.note)
    elif args.mode == "client-add":
        if not args.name or not args.email or not args.service:
            print("ERROR: --name, --email, --service required for client-add")
            sys.exit(1)
        client_add(args.name, args.email, args.company, args.service, args.plan, args.value)
    elif args.mode == "client-list":
        client_list()
    elif args.mode == "content-plan":
        content_plan()
    elif args.mode == "metrics-update":
        metrics_update()
    elif args.mode == "metrics-show":
        metrics_show()
    else:
        print(f"Unknown mode: {args.mode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
