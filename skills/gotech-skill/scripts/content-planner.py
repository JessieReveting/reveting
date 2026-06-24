#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The David Daily Show — Episode Content Planner
Auto-generates episode content plans with topic suggestions, guest matching,
SEO metadata, and weekly calendar scheduling.

Usage:
  python3 content-planner.py --weeks 4
  python3 content-planner.py --weeks 2 --topics "AI,Investing,Leadership" --format json
  python3 content-planner.py --weeks 3 --guests guests.csv --export
  python3 content-planner.py --weeks 4 --guests guests.csv --trending --export
  python3 content-planner.py --dry-run --weeks 2
  python3 content-planner.py --review content-plan-2026-06-24.md

Data Sources:
  - yt_seo_full.json  — Existing episode data (for duplication avoidance)
  - guests CSV file    — Guest availability data
"""

import argparse
import csv
import datetime
import json
import logging
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# === CONFIG ===
STARTUP_DIR = Path("/Users/davidgo/Documents/GoTechSolutions/startup")
SCRIPTS_DIR = STARTUP_DIR / "scripts"
DATA_DIR = STARTUP_DIR / "data"
CONTENT_DIR = STARTUP_DIR / "content"

YT_SEO_FILE = STARTUP_DIR / "yt_seo_full.json"

# Show constants
SHOW_NAME = "The David Daily Show"
HOST_NAME = "David Goecke"
MAX_SEO_TITLE_LEN = 60
DESC_PREVIEW_LEN = 50

# === LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("content-planner")


# === CONTENT PILLARS & TOPIC TEMPLATES ===
CONTENT_PILLARS = {
    "AI & Technology": {
        "tags": ["artificial intelligence", "AI", "machine learning", "AI technology", "AI business", "frontier technology"],
        "topic_templates": [
            "How {trend} Is Reshaping {industry} in {year}",
            "{trend} Practical Applications for Small Business",
            "The {trend} Playbook: From Hype to Real Strategy",
            "Building AI-First Teams: Lessons from {guest}",
            "AI Governance & Ethics: What {audience} Must Know",
            "Quantum + AI: The Next Frontier for {industry}",
            "AI Literacy: What Every Leader Needs to Know",
            "From LLM to ROI: Measuring AI Impact",
            "AI Capital: Funding the Next Wave of Innovation",
            "Deep Tech Investing: {trend} and Beyond",
        ],
        "talking_points": [
            "Current state of {trend} and real-world adoption rates",
            "Practical steps to integrate AI into existing workflows",
            "Common pitfalls and how to avoid them",
            "ROI measurement frameworks for AI initiatives",
            "Ethical considerations and governance best practices",
        ],
        "industries": ["Healthcare", "Finance", "Real Estate", "Small Business", "Enterprise", "Education"],
        "trends": ["Generative AI", "Agentic AI", "AI Agents", "Multimodal AI", "Edge AI", "AI-powered automation"],
    },
    "Leadership & Influence": {
        "tags": ["leadership", "business leadership", "tech leadership", "CEO", "influence"],
        "topic_templates": [
            "Leading Through Uncertainty: {year}'s Playbook",
            "The Faith-Driven Leader: Balancing Profit & Purpose",
            "Building Influence in the Age of {trend}",
            "Decision-Making Frameworks with {guest}",
            "Conscious Capitalism: Beyond the Buzzword",
            "Leading Tech Teams: Lessons from the Frontier",
            "From Founder to Leader: Scaling Yourself",
            "Stakeholder Trust in an AI-Augmented World",
        ],
        "talking_points": [
            "Emotional intelligence in high-growth environments",
            "Building trust with remote and hybrid teams",
            "Decision-making under uncertainty",
            "Balancing innovation with operational excellence",
            "Developing leadership pipeline in startups",
        ],
        "audiences": ["Founders", "CEOs", "Tech Leaders", "Pastors", "Non-profit Leaders"],
    },
    "Financial Stewardship": {
        "tags": ["finance", "fintech", "banking", "lending", "small business", "cash flow"],
        "topic_templates": [
            "Financial Stewardship for {audience} in {year}",
            "Cash Flow Mastery: {guest}'s Framework",
            "Smart Money: Budgeting for Growth",
            "Tax Planning Strategies for Entrepreneurs",
            "Fintech Solutions for Small Business",
            "The Stewardship Mindset: Wealth as a Tool",
            "Revenue Diversification in Uncertain Markets",
        ],
        "talking_points": [
            "Cash flow optimization strategies",
            "Tax planning for Q{quarter} — key deadlines",
            "Revenue diversification models",
            "Financial reporting best practices",
            "Stewardship principles in business finance",
        ],
        "audiences": ["Small Business Owners", "Entrepreneurs", "Startups", "Non-profits"],
    },
    "Faith & Business": {
        "tags": ["faith", "faith-driven", "christian", "kingdom first", "faith and tech", "purpose"],
        "topic_templates": [
            "Faith at Work: Integrating Belief & Business",
            "Kingdom Capital: {guest} on Faith-Driven Investing",
            "The Theology of Wealth: Stewardship Principles",
            "Building a Business with Eternal Impact",
            "Faith & Entrepreneurship: Navigating Tensions",
            "Values-Based Leadership in {year}",
            "When Faith Meets the Bottom Line",
        ],
        "talking_points": [
            "Biblical principles of stewardship and wealth",
            "Building a business aligned with faith values",
            "Navigating ethical dilemmas with faith as a compass",
            "Community impact through faith-driven entrepreneurship",
            "Balancing profit motives with purpose",
        ],
    },
    "Entrepreneurship": {
        "tags": ["entrepreneurship", "startup", "founder", "small business", "business growth"],
        "topic_templates": [
            "From Idea to Impact: {guest}'s Startup Journey",
            "The {year} Entrepreneur's Survival Guide",
            "Scaling Smart: When & How to Grow",
            "Building a Business That Lasts",
            "Startup Lessons: What {guest} Wish They Knew",
            "Product-Market Fit in the Age of AI",
            "The Solo Founder's Playbook",
        ],
        "talking_points": [
            "Validating ideas without over-building",
            "Customer discovery and feedback loops",
            "Building MVP to MVP (Minimum Viable Product to Maximum Value Product)",
            "Hiring your first team members",
            "Common founder mistakes and recovery strategies",
        ],
    },
    "Investing": {
        "tags": ["investing", "venture capital", "funding", "startup funding", "capital", "angels", "investors"],
        "topic_templates": [
            "Angel Investing 101: {guest}'s Framework",
            "What VCs Look for in {year}",
            "Alternative Investments: Beyond Stocks & Bonds",
            "Deal Flow Deep Dive with {guest}",
            "The Future of {trend} Investing",
            "Precious Metals & Portfolio Resilience",
            "Early-Stage Valuations: Art & Science",
            "Building a Portfolio for Impact & Returns",
        ],
        "talking_points": [
            "Due diligence frameworks for early-stage deals",
            "Portfolio construction strategies",
            "Market trend analysis and timing",
            "Risk management in venture investing",
            "LP perspectives on emerging managers",
        ],
        "asset_classes": ["Venture Capital", "Real Estate", "Precious Metals", "Crypto/Blockchain", "Private Equity", "SPACs"],
    },
    "Real Estate": {
        "tags": ["real estate", "property", "commercial real estate", "housing", "REIT"],
        "topic_templates": [
            "Real Estate Investing in {year}: {guest}'s Outlook",
            "Commercial Real Estate After {trend}",
            "Faith-Driven Real Estate Development",
            "The Future of Work Spaces",
            "Real Estate Tech: PropTech Innovations",
            "Housing Market Outlook & Opportunity",
        ],
        "talking_points": [
            "Market cycle analysis and timing",
            "Commercial vs. residential opportunities",
            "PropTech innovations changing the industry",
            "Financing strategies for investment properties",
            "Tax advantages of real estate investing",
        ],
    },
}

# === SEASONAL TOPICS ===
SEASONAL_TOPICS = {
    1: {  # Q1 (Jan-Mar)
        "themes": ["Goal Setting", "New Year Strategy", "Tax Preparation", "Annual Planning"],
        "weight": 1.5,
    },
    2: {  # Q2 (Apr-Jun)
        "themes": ["Growth", "Scaling", "Mid-Year Review", "Team Building"],
        "weight": 1.2,
    },
    3: {  # Q3 (Jul-Sep)
        "themes": ["Innovation", "Summer Intensives", "Product Launch", "Partnerships"],
        "weight": 1.0,
    },
    4: {  # Q4 (Oct-Dec)
        "themes": ["Tax Planning", "Year-End Giving", "Reflection", "Budget Planning"],
        "weight": 1.5,
    },
}

# === BEST PUBLISH TIMES ===
PUBLISH_SCHEDULE = [
    {"day": "Monday", "time": "7:00 AM", "reason": "Start of week, high engagement"},
    {"day": "Tuesday", "time": "12:00 PM", "reason": "Midday break, peak browsing"},
    {"day": "Wednesday", "time": "8:00 AM", "reason": "Mid-week content consumption peak"},
    {"day": "Thursday", "time": "5:00 PM", "reason": "End of workday wind-down"},
    {"day": "Friday", "time": "9:00 AM", "reason": "Weekend prep, leisure browsing"},
]

# === GUEST DATABASE (built-in fallback) ===
BUILT_IN_GUESTS = [
    {"name": "Neil Sahota", "company": "AI Initiative", "topic": "AI & Technology", "availability": "Q1,Q2,Q3,Q4"},
    {"name": "Daniel Burrus", "company": "Burrus Research", "topic": "AI & Technology", "availability": "Q1,Q2,Q3,Q4"},
    {"name": "Collin Plume", "company": "Noble Gold", "topic": "Investing", "availability": "Q1,Q2,Q3,Q4"},
    {"name": "Andrejka Bernatova", "company": "AI Fund", "topic": "Investing", "availability": "Q2,Q3,Q4"},
    {"name": "Michelle Urben", "company": "Conscious Capitalism", "topic": "Leadership & Influence", "availability": "Q1,Q2,Q3"},
    {"name": "Abishek Chopra", "company": "Quantum Computing Inc", "topic": "AI & Technology", "availability": "Q1,Q2,Q4"},
    {"name": "Nita Laad", "company": "Nexia AI", "topic": "AI & Technology", "availability": "Q2,Q3,Q4"},
    {"name": "Sonali Vijayavargiya", "company": "AI Founders", "topic": "Investing", "availability": "Q1,Q2,Q3"},
    {"name": "Shaker Rawan", "company": "Infant Care Tech", "topic": "Entrepreneurship", "availability": "Q1,Q3,Q4"},
    {"name": "Jake Cutler", "company": "Fintech Solutions", "topic": "Financial Stewardship", "availability": "Q1,Q2,Q3,Q4"},
    {"name": "Afsheen Afshar", "company": "AI Capital", "topic": "Investing", "availability": "Q2,Q3,Q4"},
    {"name": "Vince Vavrunek", "company": "Quantum Security", "topic": "AI & Technology", "availability": "Q1,Q2,Q3"},
    {"name": "Greg Cootsona", "company": "Theology & Tech", "topic": "Faith & Business", "availability": "Q1,Q2,Q4"},
    {"name": "Kris Henri Naudts", "company": "Quantum Health", "topic": "AI & Technology", "availability": "Q2,Q3,Q4"},
    {"name": "Scott Stevens", "company": "Tech Leadership", "topic": "Leadership & Influence", "availability": "Q1,Q2,Q3,Q4"},
    {"name": "Aaron McReynolds", "company": "Real Estate Tech", "topic": "Real Estate", "availability": "Q1,Q3,Q4"},
    {"name": "Graeme Barlow", "company": "Deep Tech Ventures", "topic": "Investing", "availability": "Q2,Q3,Q4"},
    {"name": "Anthony Georgiades", "company": "PropTech", "topic": "Real Estate", "availability": "Q1,Q2,Q4"},
    {"name": "Dr. Katrina Rosseini", "company": "HealthTech", "topic": "AI & Technology", "availability": "Q1,Q2,Q3"},
    {"name": "David Munson", "company": "Leadership Coaching", "topic": "Leadership & Influence", "availability": "Q1,Q2,Q3,Q4"},
    {"name": "Jason Alexander", "company": "Faith Ventures", "topic": "Faith & Business", "availability": "Q2,Q3,Q4"},
    {"name": "Igor Pejic", "company": "Fintech", "topic": "Financial Stewardship", "availability": "Q1,Q2,Q4"},
    {"name": "Yoon Auh", "company": "Startup Accelerator", "topic": "Entrepreneurship", "availability": "Q1,Q3,Q4"},
    {"name": "Deondré Wyche", "company": "Tech Innovation", "topic": "AI & Technology", "availability": "Q2,Q3,Q4"},
]


# === DATA LOADING ===
def load_existing_episodes() -> List[Dict]:
    """Load existing episode data from yt_seo_full.json."""
    if YT_SEO_FILE.exists():
        try:
            with open(YT_SEO_FILE) as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} existing episodes from yt_seo_full.json")
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load yt_seo_full.json: {e}")
    return []


def load_guests_from_csv(filepath: str) -> List[Dict]:
    """Load guest list from CSV file.
    
    Expected CSV format:
      name,company,topic,availability
      John Doe,Acme Corp,AI & Technology,Q1,Q2
    """
    guests = []
    path = Path(filepath)
    if not path.exists():
        logger.error(f"Guest file not found: {filepath}")
        return guests

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normalize field names (strip whitespace, lowercase keys)
                cleaned = {k.strip().lower(): v.strip() for k, v in row.items()}
                guest = {
                    "name": cleaned.get("name", ""),
                    "company": cleaned.get("company", ""),
                    "topic": cleaned.get("topic", ""),
                    "availability": cleaned.get("availability", "Q1,Q2,Q3,Q4"),
                }
                if guest["name"]:
                    guests.append(guest)
        logger.info(f"Loaded {len(guests)} guests from {filepath}")
    except Exception as e:
        logger.error(f"Error reading guest file: {e}")

    return guests


def get_trending_topics() -> List[str]:
    """Fetch trending topics for content relevance.
    
    In production, this would call a web search API.
    Returns curated trending topics relevant to the show's pillars.
    """
    # Simulated trending topics — in production, replace with actual web search
    trending = [
        "Agentic AI",
        "AI Regulation 2026",
        "Quantum Machine Learning",
        "AI-Powered Healthcare",
        "Faith-Driven Investing",
        "Climate Tech",
        "AI Cybersecurity",
        "Remote Work Tech",
        "AI Education",
        "Deep Tech SPACs",
        "AI Real Estate",
        "Generative AI Business",
        "AI Governance Frameworks",
        "Tech IPO Market",
        "AI Small Business Tools",
    ]
    logger.info(f"Using {len(trending)} trending topics")
    return trending


# === TOPIC GENERATION ===
def get_quarter(date: Optional[datetime.date] = None) -> int:
    """Get the fiscal quarter for a given date."""
    if date is None:
        date = datetime.date.today()
    return (date.month - 1) // 3 + 1


def get_seasonal_themes() -> Tuple[List[str], float]:
    """Get seasonally relevant themes and their weight."""
    quarter = get_quarter()
    seasonal = SEASONAL_TOPICS.get(quarter, {"themes": [], "weight": 1.0})
    return seasonal["themes"], seasonal["weight"]


def extract_used_topics(episodes: List[Dict]) -> set:
    """Extract topics already covered to avoid duplication."""
    used = set()
    for ep in episodes:
        topic = ep.get("topic", "")
        if topic:
            # Normalize for comparison
            normalized = topic.lower().strip()
            used.add(normalized)
            # Also add key terms
            for term in re.split(r'[,\s&|]+', normalized):
                if len(term) > 3:
                    used.add(term)
    return used


def generate_topic_title(
    pillar: str,
    trend: str,
    guest: Optional[Dict] = None,
    seasonal_themes: List[str] = None,
    used_topics: set = None,
) -> str:
    """Generate a unique topic title based on pillar, trends, and season."""
    if used_topics is None:
        used_topics = set()
    if seasonal_themes is None:
        seasonal_themes = []

    pillar_data = CONTENT_PILLARS.get(pillar, {})
    templates = pillar_data.get("topic_templates", ["{trend} with {guest}"])

    # Try multiple templates to find a unique topic
    random.shuffle(templates)
    year = str(datetime.date.today().year)

    for template in templates:
        # Fill in template variables
        industry = random.choice(pillar_data.get("industries", ["Business"]))
        audience = random.choice(pillar_data.get("audiences", ["Leaders"]))

        title = template.format(
            trend=trend,
            guest=guest["name"] if guest else HOST_NAME,
            industry=industry,
            audience=audience,
            year=year,
        )

        # Add seasonal relevance if applicable
        if seasonal_themes and random.random() > 0.6:
            theme = random.choice(seasonal_themes)
            if theme.lower() not in title.lower():
                title = f"{title}: {theme} Edition"

        # Check uniqueness
        normalized = title.lower().strip()
        if normalized not in used_topics:
            return title

    # Fallback: append a number to ensure uniqueness
    base_title = templates[0].format(
        trend=trend,
        guest=guest["name"] if guest else HOST_NAME,
        industry="Business",
        audience="Leaders",
        year=year,
    )
    counter = 2
    while base_title.lower().strip() in used_topics:
        base_title = f"{templates[0].format(trend=trend, guest=guest['name'] if guest else HOST_NAME, industry='Business', audience='Leaders', year=year)} (Part {counter})"
        counter += 1
    return base_title


def generate_talking_points(pillar: str, topic: str, guest: Optional[Dict] = None) -> List[str]:
    """Generate key talking points for an episode."""
    pillar_data = CONTENT_PILLARS.get(pillar, {})
    templates = pillar_data.get("talking_points", [
        "Key insights and takeaways",
        "Practical applications for the audience",
        "Future outlook and predictions",
    ])

    points = []
    year = str(datetime.date.today().year)

    for template in templates[:5]:
        point = template.format(
            trend=topic.split(" with ")[0] if " with " in topic else topic,
            guest=guest["name"] if guest else HOST_NAME,
            year=year,
            quarter=f"Q{get_quarter()}",
        )
        points.append(point)

    return points[:5]


def generate_seo_title(topic: str, guest: Optional[Dict] = None) -> str:
    """Generate an SEO-optimized title (max 60 chars)."""
    ep_num_placeholder = "EP###"

    if guest:
        # Format: "Topic with Guest Name | David Goecke EP###"
        base = f"{topic} with {guest['name']}"
        suffix = f" | {HOST_NAME} {ep_num_placeholder}"
    else:
        # Format: "Topic | David Goecke EP###"
        base = topic
        suffix = f" | {HOST_NAME} {ep_num_placeholder}"

    max_base_len = MAX_SEO_TITLE_LEN - len(suffix)
    if len(base) > max_base_len:
        base = base[: max_base_len - 3] + "..."

    return base + suffix


def generate_description_preview(topic: str, guest: Optional[Dict] = None) -> str:
    """Generate a description preview (first 50 chars)."""
    if guest:
        desc = f"{topic} with {guest['name']} on {SHOW_NAME}"
    else:
        desc = f"{topic} on {SHOW_NAME} with {HOST_NAME}"

    if len(desc) > DESC_PREVIEW_LEN:
        desc = desc[: DESC_PREVIEW_LEN - 3] + "..."
    return desc


def generate_tags(pillar: str, topic: str, guest: Optional[Dict] = None) -> str:
    """Generate suggested tags for the episode."""
    base_tags = [SHOW_NAME.lower().replace(" ", " "), HOST_NAME.lower().replace(" ", " "), HOST_NAME.lower()]

    pillar_data = CONTENT_PILLARS.get(pillar, {})
    pillar_tags = pillar_data.get("tags", [])

    # Extract topic-specific tags
    topic_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', topic)
    topic_tags = [w.lower() for w in topic_words if len(w) > 2]

    # Add guest tag
    guest_tag = ""
    if guest:
        guest_tag = guest["name"].lower().replace(" ", "")

    # Combine and deduplicate
    all_tags = list(set(base_tags + pillar_tags + topic_tags))
    if guest_tag:
        all_tags.append(guest_tag)

    # Limit to ~15 tags
    return ", ".join(all_tags[:15])


def get_best_publish_time(week_num: int, episode_in_week: int) -> Dict:
    """Get the best publish day and time for an episode."""
    schedule_idx = (week_num * 3 + episode_in_week) % len(PUBLISH_SCHEDULE)
    return PUBLISH_SCHEDULE[schedule_idx]


def match_guest_to_pillar(
    pillar: str,
    guests: List[Dict],
    used_guests: List[str],
) -> Optional[Dict]:
    """Find an available guest for a given content pillar."""
    if not guests:
        return None

    quarter = f"Q{get_quarter()}"
    available = [
        g for g in guests
        if (g["topic"] == pillar or g["topic"] == "")
        and quarter in g.get("availability", "Q1,Q2,Q3,Q4")
        and g["name"] not in used_guests
    ]

    if available:
        return random.choice(available)
    return None


# === PLAN GENERATION ===
def generate_episode_plan(
    episode_num: int,
    pillar: str,
    trend: str,
    guest: Optional[Dict],
    seasonal_themes: List[str],
    used_topics: set,
    week_num: int,
    episode_in_week: int,
) -> Dict:
    """Generate a complete episode plan."""
    topic_title = generate_topic_title(pillar, trend, guest, seasonal_themes, used_topics)
    talking_points = generate_talking_points(pillar, topic_title, guest)
    seo_title = generate_seo_title(topic_title, guest)
    desc_preview = generate_description_preview(topic_title, guest)
    tags = generate_tags(pillar, topic_title, guest)
    publish_time = get_best_publish_time(week_num, episode_in_week)

    # Calculate the publish date
    today = datetime.date.today()
    start_of_plan = today - datetime.timedelta(days=today.weekday())  # Monday of current week
    days_offset = week_num * 7 + (["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"].index(publish_time["day"]))
    publish_date = start_of_plan + datetime.timedelta(days=days_offset)

    return {
        "episode": f"EP{episode_num:03d}",
        "topic_title": topic_title,
        "content_pillar": pillar,
        "guest": guest["name"] if guest else None,
        "guest_company": guest["company"] if guest else None,
        "talking_points": talking_points,
        "seo_title": seo_title,
        "description_preview": desc_preview,
        "tags": tags,
        "publish_day": publish_time["day"],
        "publish_time": publish_time["time"],
        "publish_reason": publish_time["reason"],
        "publish_date": publish_date.isoformat(),
        "format": "interview" if guest else "solo",
    }


def generate_content_plan(
    weeks: int,
    custom_topics: Optional[List[str]] = None,
    guests: Optional[List[Dict]] = None,
    use_trending: bool = False,
    episodes_per_week: int = 5,
) -> Dict:
    """Generate a full content plan for the specified number of weeks."""
    # Load existing episodes to avoid duplication
    existing_episodes = load_existing_episodes()
    used_topics = extract_used_topics(existing_episodes)

    # Get trending topics if requested
    trending = get_trending_topics() if use_trending else []

    # Get seasonal themes
    seasonal_themes, seasonal_weight = get_seasonal_themes()

    # Use built-in guests if none provided
    if guests is None:
        guests = BUILT_IN_GUESTS

    # Determine episode number start
    max_ep = 0
    for ep in existing_episodes:
        ep_str = ep.get("ep", "EP000")
        try:
            ep_num = int(re.search(r'\d+', ep_str).group())
            max_ep = max(max_ep, ep_num)
        except (AttributeError, ValueError):
            pass
    start_ep = max_ep + 1

    # Generate plan
    plan = {
        "generated_at": datetime.datetime.now().isoformat(),
        "weeks": weeks,
        "total_episodes": weeks * episodes_per_week,
        "start_episode": f"EP{start_ep:03d}",
        "seasonal_context": {
            "quarter": f"Q{get_quarter()}",
            "themes": seasonal_themes,
        },
        "episodes": [],
        "weekly_calendar": [],
    }

    used_guests = []
    pillars_list = list(CONTENT_PILLARS.keys())
    episode_num = start_ep

    # Track pillar distribution for balance
    pillar_counts = {p: 0 for p in pillars_list}
    total_target = weeks * episodes_per_week

    for week in range(weeks):
        week_episodes = []
        week_start = datetime.date.today() + datetime.timedelta(weeks=week)
        week_start = week_start - datetime.timedelta(days=week_start.weekday())

        for ep_in_week in range(episodes_per_week):
            # Select pillar with weighted distribution (underrepresented pillars get priority)
            min_count = min(pillar_counts.values()) if pillar_counts else 0
            underrepresented = [p for p, c in pillar_counts.items() if c <= min_count]
            if underrepresented and random.random() > 0.3:
                pillar = random.choice(underrepresented)
            else:
                pillar = random.choice(pillars_list)

            # Select trend
            if trending:
                trend = random.choice(trending)
            else:
                pillar_trends = CONTENT_PILLARS[pillar].get("trends", [pillar])
                trend = random.choice(pillar_trends)

            # Match guest (50% chance if guests available)
            guest = None
            if random.random() > 0.4:
                guest = match_guest_to_pillar(pillar, guests, used_guests)
                if guest:
                    used_guests.append(guest["name"])

            # Generate episode
            episode = generate_episode_plan(
                episode_num=episode_num,
                pillar=pillar,
                trend=trend,
                guest=guest,
                seasonal_themes=seasonal_themes,
                used_topics=used_topics,
                week_num=week,
                episode_in_week=ep_in_week,
            )

            plan["episodes"].append(episode)
            week_episodes.append(episode)
            used_topics.add(episode["topic_title"].lower().strip())
            pillar_counts[pillar] += 1
            episode_num += 1

        # Build weekly calendar entry
        plan["weekly_calendar"].append({
            "week_number": week + 1,
            "date_range": f"{week_start.isoformat()} to {(week_start + datetime.timedelta(days=6)).isoformat()}",
            "episode_count": len(week_episodes),
            "episodes": [
                {
                    "episode": ep["episode"],
                    "topic": ep["topic_title"],
                    "guest": ep["guest"],
                    "pillar": ep["content_pillar"],
                    "publish_day": ep["publish_day"],
                    "publish_time": ep["publish_time"],
                }
                for ep in week_episodes
            ],
        })

    return plan


# === OUTPUT FORMATTERS ===
def format_markdown(plan: Dict) -> str:
    """Format the content plan as Markdown."""
    lines = [
        f"# 📺 {SHOW_NAME} — Content Plan",
        "",
        f"**Generated:** {plan['generated_at'][:10]}",
        f"**Weeks Planned:** {plan['weeks']}",
        f"**Total Episodes:** {plan['total_episodes']}",
        f"**Starting Episode:** {plan['start_episode']}",
        f"**Seasonal Context:** {plan['seasonal_context']['quarter']} — {', '.join(plan['seasonal_context']['themes'])}",
        "",
        "---",
        "",
        "## 📅 Weekly Calendar",
        "",
    ]

    for week in plan["weekly_calendar"]:
        lines.append(f"### Week {week['week_number']} ({week['date_range']})")
        lines.append("")
        lines.append("| Day | Episode | Topic | Guest | Pillar |")
        lines.append("|-----|---------|-------|-------|--------|")
        for ep in week["episodes"]:
            guest = ep["guest"] or "Solo"
            lines.append(
                f"| {ep['publish_day']} {ep['publish_time']} | {ep['episode']} | "
                f"{ep['topic'][:40]}{'...' if len(ep['topic']) > 40 else ''} | "
                f"{guest} | {ep['pillar']} |"
            )
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 📋 Episode Details",
        "",
    ])

    for ep in plan["episodes"]:
        lines.append(f"### {ep['episode']}: {ep['topic_title']}")
        lines.append("")
        lines.append(f"- **Pillar:** {ep['content_pillar']}")
        if ep["guest"]:
            lines.append(f"- **Guest:** {ep['guest']} ({ep['guest_company']})")
        lines.append(f"- **Format:** {ep['format'].title()}")
        lines.append(f"- **Publish:** {ep['publish_day']} at {ep['publish_time']} ({ep['publish_reason']})")
        lines.append(f"- **Date:** {ep['publish_date']}")
        lines.append("")
        lines.append("**Talking Points:**")
        for point in ep["talking_points"]:
            lines.append(f"  - {point}")
        lines.append("")
        lines.append(f"**SEO Title:** `{ep['seo_title']}` ({len(ep['seo_title'])} chars)")
        lines.append(f"**Description Preview:** `{ep['description_preview']}`")
        lines.append(f"**Tags:** {ep['tags']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def format_json(plan: Dict) -> str:
    """Format the content plan as JSON."""
    return json.dumps(plan, indent=2, ensure_ascii=False)


def format_csv(plan: Dict) -> str:
    """Format the content plan as CSV."""
    import io
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Episode", "Topic Title", "Content Pillar", "Guest", "Guest Company",
        "Format", "Publish Day", "Publish Time", "Publish Date",
        "SEO Title", "Description Preview", "Talking Points", "Tags"
    ])

    for ep in plan["episodes"]:
        writer.writerow([
            ep["episode"],
            ep["topic_title"],
            ep["content_pillar"],
            ep["guest"] or "Solo",
            ep["guest_company"] or "",
            ep["format"],
            ep["publish_day"],
            ep["publish_time"],
            ep["publish_date"],
            ep["seo_title"],
            ep["description_preview"],
            " | ".join(ep["talking_points"]),
            ep["tags"],
        ])

    return output.getvalue()


# === EXPORT ===
def export_plan(plan: Dict, format_type: str = "markdown") -> str:
    """Export the plan to a file."""
    today = datetime.date.today().isoformat()
    filename = f"content-plan-{today}"

    if format_type == "json":
        filepath = CONTENT_DIR / f"{filename}.json"
        content = format_json(plan)
    elif format_type == "csv":
        filepath = CONTENT_DIR / f"{filename}.csv"
        content = format_csv(plan)
    else:
        filepath = CONTENT_DIR / f"{filename}.md"
        content = format_markdown(plan)

    # Ensure content directory exists
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Plan exported to {filepath}")
    return str(filepath)


# === REVIEW MODE ===
def review_plan(plan_file: str) -> str:
    """Review an existing content plan and suggest improvements."""
    filepath = Path(plan_file)
    if not filepath.exists():
        # Try in content directory
        filepath = CONTENT_DIR / plan_file
    if not filepath.exists():
        return f"Error: Plan file not found: {plan_file}"

    with open(filepath) as f:
        content = f.read()

    suggestions = []
    suggestions.append("# 🔍 Content Plan Review & Suggestions")
    suggestions.append("")
    suggestions.append(f"**Plan File:** {filepath}")
    suggestions.append(f"**Review Date:** {datetime.date.today().isoformat()}")
    suggestions.append("")

    # Parse the plan (basic analysis)
    lines = content.split("\n")
    episode_count = content.count("### EP")
    topic_lines = [l for l in lines if l.startswith("### EP")]

    suggestions.append("## 📊 Plan Overview")
    suggestions.append("")
    suggestions.append(f"- **Episodes Found:** {episode_count}")
    suggestions.append(f"- **Plan Length:** ~{len(lines)} lines")
    suggestions.append("")

    # Check for pillar diversity
    pillars_found = {}
    for pillar in CONTENT_PILLARS.keys():
        count = content.lower().count(pillar.lower())
        if count > 0:
            pillars_found[pillar] = count

    suggestions.append("## 🎯 Pillar Distribution")
    suggestions.append("")
    for pillar, count in sorted(pillars_found.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * count
        suggestions.append(f"- {pillar}: {bar} ({count} mentions)")
    suggestions.append("")

    # Suggestions
    suggestions.append("## 💡 Improvement Suggestions")
    suggestions.append("")

    if len(pillars_found) < len(CONTENT_PILLARS):
        missing = set(CONTENT_PILLARS.keys()) - set(pillars_found.keys())
        suggestions.append(f"### Missing Pillars")
        suggestions.append(f"Consider adding episodes for: {', '.join(missing)}")
        suggestions.append("")

    # Check for guest diversity
    guest_mentions = content.count("Guest:")
    solo_count = content.count("Guest: Solo") + content.count("Guest: None")
    if solo_count > guest_mentions * 0.7:
        suggestions.append("### Guest Ratio")
        suggestions.append("- Consider increasing guest episodes (currently >70% solo)")
        suggestions.append("- Aim for 40-60% guest episodes for variety")
        suggestions.append("")

    # SEO checks
    long_titles = [l for l in lines if "|" in l and len(l) > 80]
    if long_titles:
        suggestions.append("### SEO Optimization")
        suggestions.append(f"- {len(long_titles)} lines exceed typical display width")
        suggestions.append("- Ensure SEO titles are ≤ 60 characters")
        suggestions.append("")

    # Seasonal relevance
    quarter = get_quarter()
    seasonal = SEASONAL_TOPICS.get(quarter, {})
    suggestions.append("### Seasonal Relevance")
    suggestions.append(f"- Current Quarter: Q{quarter}")
    suggestions.append(f"- Suggested Themes: {', '.join(seasonal.get('themes', []))}")
    suggestions.append("- Consider weaving seasonal themes into episode topics")
    suggestions.append("")

    # Action items
    suggestions.append("## ✅ Recommended Actions")
    suggestions.append("")
    suggestions.append("1. **Balance pillar coverage** — Ensure all 7 content pillars are represented")
    suggestions.append("2. **Diversify guests** — Mix industry practitioners, thought leaders, and faith-driven entrepreneurs")
    suggestions.append("3. **Optimize publish schedule** — Tuesday/Wednesday/Thursday typically perform best")
    suggestions.append("4. **SEO audit** — Verify all titles ≤ 60 chars, descriptions ≤ 155 chars")
    suggestions.append("5. **Cross-promote** — Plan clip extraction for shorts from each episode")
    suggestions.append("")

    return "\n".join(suggestions)


# === CLI ===
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=f"{SHOW_NAME} — Episode Content Planner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 content-planner.py --weeks 4
  python3 content-planner.py --weeks 2 --topics "AI,Leadership,Investing" --format json
  python3 content-planner.py --weeks 3 --guests guests.csv --trending --export
  python3 content-planner.py --dry-run --weeks 2
  python3 content-planner.py --review content-plan-2026-06-24.md
        """,
    )

    parser.add_argument(
        "--weeks",
        type=int,
        default=2,
        help="Number of weeks to plan (default: 2)",
    )
    parser.add_argument(
        "--topics",
        type=str,
        default=None,
        help="Comma-separated list of topics to prioritize",
    )
    parser.add_argument(
        "--guests",
        type=str,
        default=None,
        help="Path to CSV file with guest list (name, company, topic, availability)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["markdown", "json", "csv"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export plan to content/ directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate plan without saving (preview only)",
    )
    parser.add_argument(
        "--trending",
        action="store_true",
        help="Include trending topics in generation",
    )
    parser.add_argument(
        "--review",
        type=str,
        default=None,
        help="Review an existing plan file and suggest improvements",
    )
    parser.add_argument(
        "--episodes-per-week",
        type=int,
        default=5,
        help="Number of episodes per week (default: 5)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output file path",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    logger.info(f"{'=' * 50}")
    logger.info(f"  {SHOW_NAME} — Content Planner")
    logger.info(f"{'=' * 50}")

    # Review mode
    if args.review:
        review_output = review_plan(args.review)
        print(review_output)
        if args.export:
            CONTENT_DIR.mkdir(parents=True, exist_ok=True)
            review_path = Path(args.output or CONTENT_DIR / f"review-{datetime.date.today().isoformat()}.md")
            with open(review_path, "w") as f:
                f.write(review_output)
            logger.info(f"Review saved to {review_path}")
        return

    # Parse custom topics
    custom_topics = None
    if args.topics:
        custom_topics = [t.strip() for t in args.topics.split(",")]
        logger.info(f"Custom topics: {custom_topics}")

    # Load guests
    guests = None
    if args.guests:
        guests = load_guests_from_csv(args.guests)
        if not guests:
            logger.warning("No guests loaded from file, using built-in guest list")
            guests = BUILT_IN_GUESTS
    else:
        guests = BUILT_IN_GUESTS

    # Generate plan
    logger.info(f"Generating {args.weeks}-week content plan...")
    plan = generate_content_plan(
        weeks=args.weeks,
        custom_topics=custom_topics,
        guests=guests,
        use_trending=args.trending,
        episodes_per_week=args.episodes_per_week,
    )

    # Format output
    if args.format == "json":
        output = format_json(plan)
    elif args.format == "csv":
        output = format_csv(plan)
    else:
        output = format_markdown(plan)

    # Display or export
    if args.dry_run:
        logger.info("DRY RUN — Plan preview (not saved)")
        print(output)
    elif args.export:
        filepath = export_plan(plan, args.format)
        logger.info(f"Plan exported to: {filepath}")
        # Also print summary
        print(f"\n✅ Content plan exported: {filepath}")
        print(f"   Episodes: {plan['total_episodes']}")
        print(f"   Weeks: {plan['weeks']}")
        print(f"   Format: {args.format}")
    else:
        print(output)

    logger.info("Content planning complete!")


if __name__ == "__main__":
    main()
