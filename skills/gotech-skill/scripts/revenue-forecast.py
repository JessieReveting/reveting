#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Revenue Forecast & Growth Projections for GoTechSolutions.

Generates revenue forecasts, growth scenarios, and actionable recommendations
to reach $1M cash. Reads historical data from cash.json and metrics.json.

Usage:
    python3 revenue-forecast.py                           # Default forecast
    python3 revenue-forecast.py --months 18               # 18-month projection
    python3 revenue-forecast.py --scenarios conservative  # Single scenario
    python3 revenue-forecast.py --chart                   # ASCII chart output
    python3 revenue-forecast.py --export                  # Export CSV
    python3 revenue-forecast.py --simulate                # Monte Carlo (1000 runs)
    python3 revenue-forecast.py --target 2000000          # Custom target
    python3 revenue-forecast.py --required                # Required monthly revenue
    python3 revenue-forecast.py --start-date 2026-07-01   # Override start date
"""

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# --- Paths ---
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"

CASH_FILE = DATA_DIR / "cash.json"
METRICS_FILE = DATA_DIR / "metrics.json"

# --- Constants ---
DEFAULT_TARGET = 1_000_000
DEFAULT_MONTHS = 12
DEFAULT_STARTING_BALANCE = 500.0
MONTE_CARLO_RUNS = 1000

# Scenario multipliers
SCENARIO_MULTIPLIERS = {
    "conservative": 0.7,
    "moderate": 1.0,
    "aggressive": 1.5,
}

# Aggressive scenario: additional monthly acceleration from new client acquisition
AGGRESSIVE_CLIENT_ACCELERATION = 0.02  # 2% additional monthly growth from new clients


# ===========================================================================
# Data Loading
# ===========================================================================

def load_cash_data() -> dict:
    """Load cash data from cash.json.

    Returns:
        dict: Cash data with balance, transactions, starting_balance, start_date.
              Returns default data structure if file not found.
    """
    default_data = {
        "balance": DEFAULT_STARTING_BALANCE,
        "transactions": [],
        "starting_balance": DEFAULT_STARTING_BALANCE,
        "start_date": "2026-06-24",
    }
    try:
        with open(CASH_FILE, "r") as f:
            data = json.load(f)
        # Validate required keys
        if "balance" not in data:
            data["balance"] = default_data["balance"]
        if "transactions" not in data:
            data["transactions"] = []
        if "starting_balance" not in data:
            data["starting_balance"] = data["balance"]
        if "start_date" not in data:
            data["start_date"] = default_data["start_date"]
        return data
    except FileNotFoundError:
        print(f"[WARN] cash.json not found at {CASH_FILE}. Using defaults.")
        return default_data
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[WARN] Could not parse cash.json: {e}. Using defaults.")
        return default_data


def load_metrics_data() -> dict:
    """Load metrics data from metrics.json.

    Returns:
        dict: Metrics snapshots with MRR, ARR, leads, clients, pipeline.
              Returns default data structure if file not found.
    """
    default_data = {
        "snapshots": [
            {
                "date": "2026-06-24",
                "cash_balance": DEFAULT_STARTING_BALANCE,
                "total_leads": 0,
                "new_leads_today": 0,
                "qualified_leads": 0,
                "active_clients": 0,
                "mrr": 0,
                "arr": 0,
                "pipeline_value": 0.0,
                "days_to_1m": None,
            }
        ]
    }
    try:
        with open(METRICS_FILE, "r") as f:
            data = json.load(f)
        if "snapshots" not in data or len(data["snapshots"]) == 0:
            return default_data
        return data
    except FileNotFoundError:
        print(f"[WARN] metrics.json not found at {METRICS_FILE}. Using defaults.")
        return default_data
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[WARN] Could not parse metrics.json: {e}. Using defaults.")
        return default_data


# ===========================================================================
# Growth Rate Calculation
# ===========================================================================

def calculate_growth_rate(cash_data: dict, metrics_data: dict) -> dict:
    """Calculate current growth rate from transaction history and metrics.

    Uses month-over-month balance changes from transactions. If insufficient
    data, falls back to metrics-based estimation or defaults.

    Returns:
        dict: Growth statistics including monthly_rate, monthly_revenue, etc.
    """
    transactions = cash_data.get("transactions", [])
    starting_balance = cash_data.get("starting_balance", DEFAULT_STARTING_BALANCE)
    current_balance = cash_data.get("balance", DEFAULT_STARTING_BALANCE)
    snapshots = metrics_data.get("snapshots", [])
    latest_metrics = snapshots[-1] if snapshots else {}

    # Calculate total net inflow from transactions
    total_inflow = sum(t["amount"] for t in transactions if t["amount"] > 0)
    total_outflow = sum(abs(t["amount"]) for t in transactions if t["amount"] < 0)
    net_revenue = total_inflow - total_outflow + (current_balance - starting_balance)

    # Try to compute monthly rate from transaction timeline
    if len(transactions) >= 2:
        # Get date range of transactions
        dates = []
        for t in transactions:
            try:
                if "date" in t:
                    dt = datetime.fromisoformat(t["date"])
                    dates.append(dt)
            except (ValueError, TypeError):
                continue

        if len(dates) >= 2:
            date_span = (max(dates) - min(dates)).days
            if date_span > 0:
                months_elapsed = date_span / 30.44  # avg days per month
                if months_elapsed > 0 and starting_balance > 0:
                    # Compound monthly growth rate
                    if current_balance > 0 and net_revenue > 0:
                        monthly_rate = (1 + net_revenue / starting_balance) ** (1 / months_elapsed) - 1
                    else:
                        monthly_rate = 0.0
                else:
                    monthly_rate = 0.0

                # Clamp to reasonable bounds
                monthly_rate = max(-0.5, min(monthly_rate, 5.0))

                # Calculate average monthly revenue
                monthly_revenue = net_revenue / max(months_elapsed, 1)

                return {
                    "monthly_rate": monthly_rate,
                    "monthly_revenue": monthly_revenue,
                    "months_elapsed": months_elapsed,
                    "total_inflow": total_inflow,
                    "total_outflow": total_outflow,
                    "net_revenue": net_revenue,
                    "starting_balance": starting_balance,
                    "current_balance": current_balance,
                    "mrr": latest_metrics.get("mrr", 0),
                    "arr": latest_metrics.get("arr", 0),
                    "pipeline_value": latest_metrics.get("pipeline_value", 0),
                    "active_clients": latest_metrics.get("active_clients", 0),
                }

    # Fallback: use MRR from metrics or estimate
    mrr = latest_metrics.get("mrr", 0)
    active_clients = latest_metrics.get("active_clients", 0)
    pipeline = latest_metrics.get("pipeline_value", 0)

    if mrr > 0:
        monthly_rate = 0.05  # 5% default if we have MRR but no growth history
        monthly_revenue = mrr
    elif active_clients > 0:
        # Estimate based on average revenue per client
        est_arpc = 500  # conservative estimate
        monthly_revenue = active_clients * est_arpc
        monthly_rate = monthly_revenue / starting_balance if starting_balance > 0 else 0.05
    else:
        # No revenue yet - estimate a modest starting growth assumption
        # This is a startup with $500-$1000 cash. Assume first revenue imminent.
        monthly_rate = 0.0  # No measurable growth yet
        monthly_revenue = 0.0

    return {
        "monthly_rate": monthly_rate,
        "monthly_revenue": monthly_revenue,
        "months_elapsed": 0,
        "total_inflow": total_inflow,
        "total_outflow": total_outflow,
        "net_revenue": net_revenue,
        "starting_balance": starting_balance,
        "current_balance": current_balance,
        "mrr": mrr,
        "arr": latest_metrics.get("arr", 0),
        "pipeline_value": pipeline,
        "active_clients": active_clients,
    }


# ===========================================================================
# Scenario Projections
# ===========================================================================

def generate_projections(
    growth_stats: dict,
    months: int,
    target: float,
    start_date: Optional[datetime] = None,
    selected_scenarios: Optional[list] = None,
) -> dict:
    """Generate revenue projections for each scenario.

    Args:
        growth_stats: Growth statistics from calculate_growth_rate()
        months: Number of months to forecast
        target: Target cash amount
        start_date: Starting date for projections (defaults to today)
        selected_scenarios: List of scenario names to run (default: all)

    Returns:
        dict: Per-scenario projections with monthly balances and metadata.
    """
    if start_date is None:
        start_date = datetime.now()

    current_balance = growth_stats["current_balance"]
    base_monthly_rate = growth_stats["monthly_rate"]
    monthly_revenue = growth_stats["monthly_revenue"]

    if selected_scenarios is None:
        selected_scenarios = ["conservative", "moderate", "aggressive"]

    projections = {}

    for scenario in selected_scenarios:
        multiplier = SCENARIO_MULTIPLIERS.get(scenario, 1.0)
        rate = base_monthly_rate * multiplier

        # For aggressive scenario, add client acceleration
        if scenario == "aggressive":
            rate += AGGRESSIVE_CLIENT_ACCELERATION

        # Ensure minimum growth rate (startups should grow)
        if rate <= 0 and monthly_revenue <= 0:
            # No data - use a reasonable startup default
            if scenario == "conservative":
                rate = 0.05  # 5% monthly
            elif scenario == "moderate":
                rate = 0.10  # 10% monthly
            elif scenario == "aggressive":
                rate = 0.20  # 20% monthly

        monthly_data = []
        balance = current_balance
        target_month = None

        for month in range(1, months + 1):
            # Compound growth: apply rate to balance
            if rate > 0:
                balance = balance * (1 + rate)
            elif rate < 0:
                balance = balance * (1 + rate)
            # If rate == 0, balance stays flat (no growth, no decay from rate)

            # Add base monthly revenue component (first month starts from actual)
            if monthly_revenue > 0:
                balance += monthly_revenue * (multiplier if scenario != "conservative" else 0.7)

            # Determine projection date
            proj_year = start_date.year + (start_date.month + month - 1) // 12
            proj_month = (start_date.month + month - 1) % 12 + 1
            proj_date = datetime(proj_year, proj_month, start_date.day)

            entry = {
                "month": month,
                "date": proj_date.strftime("%Y-%m-%d"),
                "balance": round(balance, 2),
                "growth_rate": round(rate * 100, 2),
            }
            monthly_data.append(entry)

            if target_month is None and balance >= target:
                target_month = month

        # Calculate when target is reached
        months_to_target = None
        target_date = None
        if target_month:
            months_to_target = target_month
            tgt_entry = monthly_data[target_month - 1]
            target_date = tgt_entry["date"]
        elif rate > 0:
            # Calculate analytically: balance * (1+rate)^n = target
            # n = log(target/balance) / log(1+rate)
            if balance < target and current_balance > 0:
                try:
                    n = math.log(target / current_balance) / math.log(1 + rate)
                    if n > 0:
                        months_to_target = math.ceil(n)
                        proj_year = start_date.year + (start_date.month + months_to_target - 1) // 12
                        proj_month = (start_date.month + months_to_target - 1) % 12 + 1
                        target_date = datetime(proj_year, proj_month, start_date.day).strftime("%Y-%m-%d")
                except (ValueError, ZeroDivisionError):
                    months_to_target = None
                    target_date = None

        projections[scenario] = {
            "rate": round(rate * 100, 2),
            "multiplier": multiplier,
            "monthly_data": monthly_data,
            "final_balance": round(balance, 2),
            "months_to_target": months_to_target,
            "target_date": target_date,
            "target_reached": target_month is not None or months_to_target is not None,
        }

    return projections


# ===========================================================================
# Required Monthly Revenue Calculator
# ===========================================================================

def calculate_required_monthly(
    current_balance: float,
    target: float,
    timeframes: list = None,
) -> list:
    """Calculate required monthly revenue to reach target by specific timeframes.

    Uses the compound growth formula to determine the fixed monthly addition
    needed to reach a target balance in N months.

    Args:
        current_balance: Current cash balance
        target: Target cash amount
        timeframes: List of months (default: [6, 12, 18, 24])

    Returns:
        list of dicts with timeframe info, required monthly revenue, and growth rate.
    """
    if timeframes is None:
        timeframes = [6, 12, 18, 24]

    results = []
    for n in timeframes:
        if current_balance <= 0 or target <= 0:
            continue

        # Required monthly addition (simple calculation):
        # We need: current_balance + n * monthly = target
        # monthly = (target - current_balance) / n
        simple_monthly = (target - current_balance) / n

        # Growth rate implied: if we want compound growth
        # target = current_balance * (1 + r)^n + monthly * ((1+r)^n - 1) / r
        # This requires iterative solution, so we provide both:

        # Simple linear required revenue
        linear_monthly = (target - current_balance) / n

        # Required compound monthly growth rate (if no additional revenue beyond growth)
        # target = current * (1+r)^n => r = (target/current)^(1/n) - 1
        try:
            compound_rate = (target / current_balance) ** (1 / n) - 1
        except (ValueError, ZeroDivisionError):
            compound_rate = 0.0

        results.append({
            "months": n,
            "years": round(n / 12, 1),
            "required_monthly_revenue": round(linear_monthly, 2),
            "required_compound_growth_rate": round(compound_rate * 100, 2),
            "gap": round(target - current_balance, 2),
            "target": target,
            "starting_balance": current_balance,
        })

    return results


# ===========================================================================
# Monte Carlo Simulation
# ===========================================================================

def run_monte_carlo(
    growth_stats: dict,
    months: int,
    target: float,
    num_runs: int = MONTE_CARLO_RUNS,
) -> dict:
    """Run Monte Carlo simulation for revenue forecasting.

    Simulates multiple possible paths using random variation around the base
    growth rate, with volatility estimated from historical data or defaults.

    Args:
        growth_stats: Growth statistics
        months: Forecast horizon
        target: Target cash amount
        num_runs: Number of simulation runs (default 1000)

    Returns:
        dict: Simulation results with percentiles, probability, and paths.
    """
    import random

    base_rate = growth_stats["monthly_rate"]
    current_balance = growth_stats["current_balance"]

    # Estimate volatility (standard deviation of monthly growth)
    # Default: 15% volatility for early-stage startup
    volatility = 0.15

    # If base rate is 0 (no revenue yet), assume higher volatility and positive drift
    if base_rate <= 0:
        base_rate = 0.10  # Assume 10% baseline for simulation
        volatility = 0.25

    final_balances = []
    target_hits = 0
    all_paths = []

    random.seed(42)  # Reproducible results

    for run in range(num_runs):
        balance = current_balance
        path = [balance]
        hit_target = False

        for month in range(months):
            # Random monthly growth rate: normal distribution around base_rate
            monthly_rate = random.gauss(base_rate, volatility)
            # Floor at -50% (can't lose more than half in a month from operations)
            monthly_rate = max(-0.5, monthly_rate)

            balance = balance * (1 + monthly_rate)
            balance = max(0, balance)  # Can't go below zero
            path.append(round(balance, 2))

            if balance >= target:
                hit_target = True

        final_balances.append(balance)
        if hit_target:
            target_hits += 1

        # Store a sample of paths (every 10th) for display
        if run % 10 == 0:
            all_paths.append(path)

    # Calculate statistics
    final_balances.sort()
    n = len(final_balances)

    mean_balance = sum(final_balances) / n
    median_balance = final_balances[n // 2]

    # Percentiles
    p10 = final_balances[int(n * 0.10)]
    p25 = final_balances[int(n * 0.25)]
    p75 = final_balances[int(n * 0.75)]
    p90 = final_balances[int(n * 0.90)]

    probability = (target_hits / num_runs) * 100

    return {
        "num_runs": num_runs,
        "months": months,
        "target": target,
        "probability_hit_target": round(probability, 1),
        "mean_final_balance": round(mean_balance, 2),
        "median_final_balance": round(median_balance, 2),
        "min_final_balance": round(final_balances[0], 2),
        "max_final_balance": round(final_balances[-1], 2),
        "percentile_10": round(p10, 2),
        "percentile_25": round(p25, 2),
        "percentile_75": round(p75, 2),
        "percentile_90": round(p90, 2),
        "sample_paths": all_paths,
        "base_rate_used": round(base_rate * 100, 2),
        "volatility_used": round(volatility * 100, 2),
    }


# ===========================================================================
# ASCII Chart Generation
# ===========================================================================

def generate_ascii_chart(projections: dict, width: int = 70, height: int = 20) -> str:
    """Generate an ASCII line chart of revenue projections.

    Args:
        projections: Output from generate_projections()
        width: Chart width in characters
        height: Chart height in rows

    Returns:
        str: ASCII chart string
    """
    # Collect all balance values
    all_values = []
    scenario_data = {}

    for scenario, data in projections.items():
        balances = [d["balance"] for d in data["monthly_data"]]
        scenario_data[scenario] = balances
        all_values.extend(balances)

    if not all_values:
        return "No data to chart."

    min_val = min(all_values)
    max_val = max(all_values)

    # Ensure some range
    if max_val == min_val:
        max_val = min_val + 1

    # Axis formatting
    def format_value(val):
        if val >= 1_000_000:
            return f"${val / 1_000_000:.1f}M"
        elif val >= 1_000:
            return f"${val / 1_000:.0f}k"
        else:
            return f"${val:.0f}"

    # Chart characters per scenario
    scenario_chars = {
        "conservative": "-",
        "moderate": "=",
        "aggressive": "#",
    }

    # Build chart
    lines = []
    lines.append(" " + "=" * (width + 10))
    lines.append(f"  Revenue Forecast Chart ({len(all_values)} scenarios, {len(balances)} months)")
    lines.append(" " + "=" * (width + 10))

    # Y-axis labels and grid
    plot_width = width - 8

    for row in range(height):
        val = max_val - (max_val - min_val) * (row / (height - 1))
        label = format_value(val).rjust(8)

        # Build row content
        row_chars = [" "] * plot_width

        for scenario, balances in scenario_data.items():
            char = scenario_chars.get(scenario, "*")
            for i, b in enumerate(balances):
                # Map balance to row
                if max_val > min_val:
                    normalized = (b - min_val) / (max_val - min_val)
                else:
                    normalized = 0.5
                point_row = int((1 - normalized) * (height - 1))

                # Map month to column
                col = int(i * (plot_width - 1) / max(len(balances) - 1, 1))

                if abs(point_row - row) <= 0:
                    if 0 <= col < plot_width:
                        if row_chars[col] == " ":
                            row_chars[col] = char

        lines.append(f"{label} |{''.join(row_chars)}")

    # X-axis
    lines.append(" " * 8 + "+" + "-" * plot_width)

    # X-axis label
    months_label = f"{'Month 1':<{plot_width // 3}}{'Month ' + str(len(balances) // 2):^{plot_width // 3}}{'Month ' + str(len(balances)):>{plot_width // 3}}"
    lines.append(" " * 9 + months_label[:plot_width])

    # Legend
    lines.append("")
    lines.append("  Legend:")
    for scenario, char in scenario_chars.items():
        if scenario in projections:
            rate = projections[scenario]["rate"]
            lines.append(f"    {char * 3} {scenario.capitalize()} ({rate}% monthly)")

    lines.append(" " + "=" * (width + 10))
    return "\n".join(lines)


def generate_monte_carlo_chart(sim_results: dict, width: int = 60) -> str:
    """Generate a summary ASCII display for Monte Carlo results.

    Args:
        sim_results: Output from run_monte_carlo()
        width: Display width

    Returns:
        str: Formatted ASCII display
    """
    lines = []
    lines.append(" " + "=" * width)
    lines.append(f"  Monte Carlo Simulation Results ({sim_results['num_runs']} runs)")
    lines.append("=" * width)
    lines.append(f"  Target:                  ${sim_results['target']:>12,.0f}")
    lines.append(f"  Forecast Horizon:        {sim_results['months']} months")
    lines.append(f"  Base Growth Rate:       {sim_results['base_rate_used']}% monthly")
    lines.append(f"  Volatility:             {sim_results['volatility_used']}% monthly")
    lines.append("-" * width)
    lines.append(f"  P(target hit):          {sim_results['probability_hit_target']:>10.1f}%")
    lines.append(f"  Mean final balance:     ${sim_results['mean_final_balance']:>12,.2f}")
    lines.append(f"  Median final balance:   ${sim_results['median_final_balance']:>12,.2f}")
    lines.append("-" * width)
    lines.append(f"  Percentile 10:          ${sim_results['percentile_10']:>12,.2f}")
    lines.append(f"  Percentile 25:          ${sim_results['percentile_25']:>12,.2f}")
    lines.append(f"  Percentile 50:          ${sim_results['median_final_balance']:>12,.2f}")
    lines.append(f"  Percentile 75:          ${sim_results['percentile_75']:>12,.2f}")
    lines.append(f"  Percentile 90:          ${sim_results['percentile_90']:>12,.2f}")
    lines.append("-" * width)
    lines.append(f"  Min final balance:      ${sim_results['min_final_balance']:>12,.2f}")
    lines.append(f"  Max final balance:      ${sim_results['max_final_balance']:>12,.2f}")
    lines.append("=" * width)

    return "\n".join(lines)


# ===========================================================================
# CSV Export
# ===========================================================================

def export_csv(projections: dict, filename: str = "revenue-forecast.csv") -> str:
    """Export projections to CSV file.

    Args:
        projections: Output from generate_projections()
        filename: Output filename

    Returns:
        str: Path to the exported CSV file.
    """
    filepath = SCRIPT_DIR / filename

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)

        # Header
        header = ["Month", "Date"]
        for scenario in projections:
            header.append(f"{scenario.capitalize()} Balance")
            header.append(f"{scenario.capitalize()} Growth Rate %")
        writer.writerow(header)

        # Find max months
        max_months = max(len(d["monthly_data"]) for d in projections.values())

        for i in range(max_months):
            row = []
            for scenario in projections:
                data = projections[scenario]
                if i < len(data["monthly_data"]):
                    entry = data["monthly_data"][i]
                    if not row:
                        row.append(entry["month"])
                        row.append(entry["date"])
                    row.append(entry["balance"])
                    row.append(entry["growth_rate"])
                else:
                    if not row:
                        row.append(i + 1)
                        row.append("")
                    row.append("")
                    row.append("")
            writer.writerow(row)

    return str(filepath)


# ===========================================================================
# Recommendations
# ===========================================================================

def generate_recommendations(
    growth_stats: dict,
    projections: dict,
    required_data: list,
    target: float,
) -> list:
    """Generate actionable recommendations based on current trajectory.

    Args:
        growth_stats: Current growth statistics
        projections: Scenario projections
        required_data: Required monthly calculations
        target: Target amount

    Returns:
        list: List of recommendation strings.
    """
    recommendations = []
    current_balance = growth_stats["current_balance"]
    monthly_rate = growth_stats["monthly_rate"]
    mrr = growth_stats["mrr"]
    active_clients = growth_stats["active_clients"]
    pipeline = growth_stats["pipeline_value"]

    # Check if aggressive scenario hits target first
    aggressive = projections.get("aggressive", {})
    moderate = projections.get("moderate", {})
    conservative = projections.get("conservative", {})

    if aggressive.get("target_reached"):
        months = aggressive["months_to_target"]
        recommendations.append(
            f"✅ AGGRESSIVE path reaches ${target:,.0f} in {months} months "
            f"({aggressive.get('target_date', 'N/A')}). Execute aggressively!"
        )

    if moderate.get("target_reached"):
        months = moderate["months_to_target"]
        recommendations.append(
            f"📊 MODERATE path reaches ${target:,.0f} in {months} months "
            f"({moderate.get('target_date', 'N/A')}). Sustainable growth trajectory."
        )

    if not aggressive.get("target_reached") and not moderate.get("target_reached"):
        recommendations.append(
            "⚠️ Current trajectory won't reach $1M in the forecast horizon. "
            "Consider increasing revenue velocity or extending timeline."
        )

    # Revenue recommendations based on required monthly
    if required_data:
        req_6m = next((r for r in required_data if r["months"] == 6), None)
        req_12m = next((r for r in required_data if r["months"] == 12), None)

        if req_6m:
            recommendations.append(
                f"� To hit $1M in 6 months: generate ${req_6m['required_monthly_revenue'] + growth_stats['monthly_revenue']:,.0f}/mo additional revenue "
                f"(+{req_6m['required_compound_growth_rate']}% monthly growth)"
            )

        if req_12m:
            recommendations.append(
                f"📈 To hit $1M in 12 months: generate ${req_12m['required_monthly_revenue'] + growth_stats['monthly_revenue']:,.0f}/mo additional revenue "
                f"(+{req_12m['required_compound_growth_rate']}% monthly growth)"
            )

    # Client-based recommendations
    if active_clients == 0:
        recommendations.append(
            "🎯 PRIORITY: Acquire your first paying clients. Pipeline value: "
            f"${pipeline:,.0f} — convert pipeline to revenue ASAP."
        )
    elif active_clients < 5:
        recommendations.append(
            f"👥 With {active_clients} active client(s), focus on retention and upselling. "
            f"Each new client adds ~${mrr / max(active_clients, 1):,.0f}/mo MRR."
        )

    # Pipeline recommendations
    if pipeline > 0:
        recommendations.append(
            f"💰 Pipeline: ${pipeline:,.0f} in progress. Push deals to close."
        )

    # Growth rate recommendations
    if monthly_rate <= 0:
        recommendations.append(
            "⚡ No measurable growth detected. Start tracking MRR/ARR weekly. "
            "Set up a revenue dashboard."
        )
    elif monthly_rate < 0.05:
        recommendations.append(
            f"📈 Growth rate ({monthly_rate * 100:.1f}%/mo) is below healthy startup threshold. "
            "Aim for 10-20% monthly growth in early stage."
        )
    elif monthly_rate < 0.15:
        recommendations.append(
            f"👍 Growth rate ({monthly_rate * 100:.1f}%/mo) is solid. "
            "Consider investing in sales to accelerate."
        )
    else:
        recommendations.append(
            f"🔥 Growth rate ({monthly_rate * 100:.1f}%/mo) is excellent! "
            "Focus on maintaining and scaling operations."
        )

    # Milestone recommendations
    milestones = [50000, 100000, 250000, 500000]
    for m in milestones:
        if current_balance < m:
            gap = m - current_balance
            next_req = next((r for r in required_data if r["months"] == 12), None)
            if next_req:
                monthly_needed = gap / 12
                recommendations.append(
                    f"� Next milestone ${m:,.0f}: ${monthly_needed:,.0f}/mo additional needed"
                )
            break

    return recommendations


# ===========================================================================
# Display Formatting
# ===========================================================================

def format_currency(amount: float) -> str:
    """Format a number as currency string."""
    if abs(amount) >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    elif abs(amount) >= 1_000:
        return f"${amount / 1_000:,.2f}"
    else:
        return f"${amount:,.2f}"


def print_forecast_report(
    projections: dict,
    growth_stats: dict,
    target: float,
    required_data: list,
    recommendations: list,
):
    """Print a formatted forecast report to stdout."""
    bar = "=" * 70
    thin_bar = "-" * 70

    print(f"\n{bar}")
    print(f"  💰 GoTech Solutions - Revenue Forecast & Growth Projections")
    print(f"{bar}")
    print(f"  Target: {format_currency(target)}")
    print(f"  Current Balance: {format_currency(growth_stats['current_balance'])}")
    print(f"  Starting Balance: {format_currency(growth_stats['starting_balance'])}")
    print(f"  Current MRR: {format_currency(growth_stats['mrr'])}/mo")
    print(f"  ARR: {format_currency(growth_stats['arr'])}")
    print(f"  Active Clients: {growth_stats['active_clients']}")
    print(f"  Pipeline: {format_currency(growth_stats['pipeline_value'])}")
    print(f"  Measurable Growth Rate: {growth_stats['monthly_rate'] * 100:.2f}%/mo")
    print(f"{bar}")

    # Projections
    print(f"\n  📊 MONTHLY PROJECTIONS BY SCENARIO")
    print(f"  {thin_bar}")

    for scenario, data in projections.items():
        print(f"\n  {scenario.upper()} (growth: {data['rate']}%/mo)")
        print(f"  {'-' * 40}")

        monthly = data["monthly_data"]

        # Print first 6 months and last 3
        print(f"    {'Month':<8} {'Date':<12} {'Balance':>15}")
        print(f"    {'-----':<8} {'----':<12} {'-------':>15}")

        for entry in monthly:
            if entry["month"] <= 6 or entry["month"] > len(monthly) - 3:
                marker = ""
                if entry["month"] == len(monthly):
                    marker = " ← end"
                print(
                    f"    {entry['month']:<8} {entry['date']:<12} "
                    f"{format_currency(entry['balance']):>15}{marker}"
                )
            elif entry["month"] == 7:
                print(f"    {'...':<8} {'...':<12} {'...':>15}")

        # Target achievement
        if data["target_reached"]:
            if data["target_date"]:
                print(f"    ✅ Target reached: {data['target_date']} (month {data['months_to_target']})")
            else:
                print(f"    ✅ Target reachable in {data['months_to_target']} months")
        else:
            print(f"    ❌ Target NOT reached in {len(monthly)} months")
            if data["final_balance"] > growth_stats["current_balance"]:
                print(f"       Final balance: {format_currency(data['final_balance'])}")

    # Required Monthly Revenue
    if required_data:
        print(f"\n  REQUIRED MONTHLY REVENUE TO HIT {format_currency(target)}")
        print(f"  {thin_bar}")
        print(f"    {'Timeframe':<12} {'Linear $/mo':>15} {'Growth Rate':>15} {'Gap':>15}")
        print(f"    {'--------':<12} {'-----------':>15} {'-----------':>15} {'---':>15}")

        for req in required_data:
            timeframe = f"{req['months']}mo ({req['years']}yr)"
            print(
                f"    {timeframe:<12} "
                f"{format_currency(req['required_monthly_revenue']):>15} "
                f"{req['required_compound_growth_rate']:>14.2f}% "
                f"{format_currency(req['gap']):>15}"
            )

    # Recommendations
    print(f"\n  � ACTIONABLE RECOMMENDATIONS")
    print(f"  {thin_bar}")
    for i, rec in enumerate(recommendations, 1):
        print(f"    {i}. {rec}")

    print(f"\n{bar}\n")


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Revenue Forecast & Growth Projections for GoTechSolutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 revenue-forecast.py                              # Default 12-month forecast
  python3 revenue-forecast.py --months 18                  # 18-month projection
  python3 revenue-forecast.py --scenarios aggressive       # Only aggressive scenario
  python3 revenue-forecast.py --chart                      # Show ASCII chart
  python3 revenue-forecast.py --export                     # Export CSV
  python3 revenue-forecast.py --simulate                   # Monte Carlo simulation
  python3 revenue-forecast.py --target 2000000             # Custom target $2M
  python3 revenue-forecast.py --required                   # Show required monthly revenue
  python3 revenue-forecast.py --start-date 2026-07-01      # Override start date
  python3 revenue-forecast.py --chart --export --simulate  # All features
        """,
    )

    parser.add_argument(
        "--months",
        type=int,
        default=DEFAULT_MONTHS,
        help=f"Forecast horizon in months (default: {DEFAULT_MONTHS})",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=["conservative", "moderate", "aggressive"],
        default=None,
        help="Scenarios to include (default: all)",
    )
    parser.add_argument(
        "--chart",
        action="store_true",
        default=False,
        help="Generate ASCII chart visualization",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        default=False,
        help="Export projections to CSV file",
    )
    parser.add_argument(
        "--target",
        type=float,
        default=DEFAULT_TARGET,
        help=f"Custom target amount (default: ${DEFAULT_TARGET:,.0f})",
    )
    parser.add_argument(
        "--required",
        action="store_true",
        default=False,
        help="Show required monthly revenue calculations",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        default=False,
        help=f"Run Monte Carlo simulation ({MONTE_CARLO_RUNS} runs)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=MONTE_CARLO_RUNS,
        help=f"Number of Monte Carlo runs (default: {MONTE_CARLO_RUNS})",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Override start date (YYYY-MM-DD format)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Minimal output (data only, JSON format)",
    )

    args = parser.parse_args()

    # Parse start date
    start_date = None
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        except ValueError:
            print(f"[ERROR] Invalid start date: {args.start_date}. Use YYYY-MM-DD format.")
            sys.exit(1)

    if not start_date:
        start_date = datetime.now()

    # Load data
    cash_data = load_cash_data()
    metrics_data = load_metrics_data()

    # Calculate growth rate
    growth_stats = calculate_growth_rate(cash_data, metrics_data)

    # Generate projections
    projections = generate_projections(
        growth_stats=growth_stats,
        months=args.months,
        target=args.target,
        start_date=start_date,
        selected_scenarios=args.scenarios,
    )

    # Required monthly revenue
    required_data = calculate_required_monthly(
        current_balance=growth_stats["current_balance"],
        target=args.target,
    )

    # Recommendations
    recommendations = generate_recommendations(
        growth_stats=growth_stats,
        projections=projections,
        required_data=required_data,
        target=args.target,
    )

    # Output
    if not args.quiet:
        print_forecast_report(
            projections=projections,
            growth_stats=growth_stats,
            target=args.target,
            required_data=required_data if args.required else [],
            recommendations=recommendations,
        )

    # Chart
    if args.chart:
        chart = generate_ascii_chart(projections)
        print(chart)

    # Monte Carlo simulation
    sim_results = None
    if args.simulate:
        sim_results = run_monte_carlo(
            growth_stats=growth_stats,
            months=args.months,
            target=args.target,
            num_runs=args.runs,
        )
        if not args.quiet:
            mc_chart = generate_monte_carlo_chart(sim_results)
            print(mc_chart)

    # CSV Export
    if args.export:
        filepath = export_csv(projections)
        if not args.quiet:
            print(f"  � Exported to: {filepath}")

    # Quiet mode: output JSON for piping/integration
    if args.quiet:
        output = {
            "current_balance": growth_stats["current_balance"],
            "target": args.target,
            "monthly_growth_rate": round(growth_stats["monthly_rate"] * 100, 2),
            "projections": {},
        }
        for scenario, data in projections.items():
            output["projections"][scenario] = {
                "rate": data["rate"],
                "final_balance": data["final_balance"],
                "target_reached": data["target_reached"],
                "months_to_target": data["months_to_target"],
                "target_date": data["target_date"],
            }

        if sim_results:
            output["monte_carlo"] = {
                "probability": sim_results["probability_hit_target"],
                "mean_balance": sim_results["mean_final_balance"],
                "median_balance": sim_results["median_final_balance"],
                "p10": sim_results["percentile_10"],
                "p90": sim_results["percentile_90"],
            }

        if args.required:
            output["required"] = required_data

        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
