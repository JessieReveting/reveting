#!/usr/bin/env python3
"""
Read-only Operations Audit

Compares HighLevel Discovery V1 artifacts against a ww@reveting.com
Google Calendar event export and writes an operations audit report.

This script never modifies Google Calendar, HighLevel, or email.
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from html import escape, unescape
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).parent.parent
DISCOVERY_DIR = REPO_ROOT / "data" / "discovery"
DEFAULT_CALENDAR_EVENTS_PATH = REPO_ROOT / "data" / "calendar" / "ww_reveting_events.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "audit"
DEFAULT_COMPLETED_TASKS_PATH = DEFAULT_OUTPUT_DIR / "completed_tasks.json"
DEFAULT_RULES_PATH = REPO_ROOT / "config" / "operations_rules.json"
DEFAULT_PRODUCTION_TIMELINE_RULES_PATH = REPO_ROOT / "config" / "production_timeline_rules.json"
DEFAULT_KNOWLEDGE_DIR = REPO_ROOT / "config" / "knowledge"
DEFAULT_CALENDAR_ID = "ww@reveting.com"
DEFAULT_PRESHOW_MINUTES = 15
DEFAULT_TIME_TOLERANCE_MINUTES = 10
DEFAULT_DAYS_AHEAD = 180
INTERNAL_EMAIL_DOMAINS = {"reveting.com"}

FALLBACK_SHOW_KEYS = [
    "cherry-willow",
    "david-daily",
    "beyond-the-cart",
    "deconstructing-data",
    "winsday",
]

FALLBACK_INACTIVE_STATUSES = {
    "cancelled",
    "canceled",
    "cancelled_by_user",
    "canceled_by_user",
    "deleted",
    "invalid",
    "no_show",
    "noshow",
}

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://[^\s>)\]]+", re.IGNORECASE)
RAW_URL_RE = re.compile(r"https?://[^\s<>\")\]]+", re.IGNORECASE)
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
DAILY_BRIEF_NEXT_DAYS = 7
DAILY_BRIEF_REPLACEMENT_DAYS = 30

FALLBACK_REQUIRED_FIELD_KEYWORDS = {
    "guest email": ("email",),
    "linkedin profile": ("linkedin",),
    "job title/company": ("job title", "company name"),
    "topic 1": ("first", "topic"),
    "topic 2": ("second", "topic"),
    "guru of the week": ("guru of the week",),
    "promotion commitment": ("help promote",),
    "live show acknowledgement": ("live show",),
}

FALLBACK_HEALTH_SCORE_RULES = {
    "base": 100,
    "minimum": 0,
    "deductions_by_severity": {
        "Critical": 25,
        "Warning": 10,
        "Informational": 2,
    },
    "deductions_by_issue_code": {},
    "labels": [
        {"min": 90, "label": "Ready for production"},
        {"min": 75, "label": "Warnings requiring attention"},
        {"min": 50, "label": "Major production risks"},
        {"min": 25, "label": "Critical failures"},
        {"min": 0, "label": "Not production ready"},
    ],
}

SEVERITY_ORDER = {"Critical": 0, "Warning": 1, "Informational": 2}
TRUST_BUCKETS = [
    "Confirmed Issues",
    "Needs Verification",
    "PR Representative Booking / Guest Represented",
    "Waiting on Guest",
    "Waiting on Guest Topics",
    "Waiting on Client",
    "Waiting on Internal Team",
    "Known Exceptions",
    "Known Calendar Ownership Exception",
    "Human Confirmed Active",
    "Needs Human Follow-Up",
    "Needs Guest Replacement",
    "Not Due Yet",
    "Future Safe Actions",
]
KNOWLEDGE_FILE_DEFAULTS = {
    "known_exceptions": ("known_exceptions.json", {"version": "1.0", "exceptions": []}),
    "known_decisions": ("known_decisions.json", {"version": "1.0", "decisions": []}),
    "known_patterns": ("known_patterns.json", {"version": "1.0", "patterns": []}),
    "linkedin_events": ("linkedin_events.json", {"version": "1.0", "events": []}),
    "show_preferences": ("show_preferences.json", {"version": "1.0", "shows": {}}),
}
COMPLETED_TASKS_DEFAULT = {
    "version": "1.0",
    "purpose": "Read-only local completion claims. These claims are never treated as source of truth unless the fresh audit confirms them from source data.",
    "task_record_fields": [
        "task_id (optional)",
        "task_kind",
        "show_key",
        "show_name (optional)",
        "episode_date or episode_time",
        "guest_name",
        "marked_complete_at",
        "marked_complete_by",
        "claimed_actions",
        "notes",
    ],
    "example_task": {
        "task_kind": "production_links",
        "show_key": "beyond-the-cart",
        "episode_date": "2026-07-07",
        "guest_name": "Tim Berney",
        "marked_complete_at": "2026-07-06T15:30:00-04:00",
        "marked_complete_by": "Jessie",
        "claimed_actions": [
            "Calendar updated",
            "StreamYard URL added",
            "LinkedIn URL added",
            "SOP email sent"
        ],
        "notes": "Local completion claim only; must be verified against source data on the next audit run."
    },
    "tasks": [],
}
COMPLETION_STATUSES = (
    "Completed and verified",
    "Completed but not verified",
    "Still open",
    "Needs human review",
)


def read_json(path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_rules(path):
    rules = read_json(path, default={})
    if not isinstance(rules, dict):
        raise RuntimeError(f"Operations rules file must contain a JSON object: {path}")
    return rules


def load_production_timeline_rules(path):
    rules = read_json(path, default={})
    if not isinstance(rules, dict):
        raise RuntimeError(f"Production timeline rules file must contain a JSON object: {path}")
    return rules


def load_knowledge(knowledge_dir):
    knowledge = {"path": str(knowledge_dir), "files": {}}
    for key, (filename, default_payload) in KNOWLEDGE_FILE_DEFAULTS.items():
        path = knowledge_dir / filename
        payload = read_json(path, default=default_payload)
        if not isinstance(payload, dict):
            raise RuntimeError(f"Knowledge file must contain a JSON object: {path}")
        knowledge["files"][key] = {
            "path": str(path),
            "payload": payload,
            "exists": path.exists(),
        }
    return knowledge


def ensure_json_file(path, default_payload):
    if not path.exists():
        write_json(path, default_payload)


def load_completed_tasks(path):
    ensure_json_file(path, COMPLETED_TASKS_DEFAULT)
    payload = read_json(path, default=COMPLETED_TASKS_DEFAULT)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Completed tasks file must contain a JSON object: {path}")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        payload["tasks"] = []
    return payload


def rule_list(rules, key, fallback=None):
    value = rules.get(key)
    if isinstance(value, list):
        return value
    return list(fallback or [])


def rule_dict(rules, key, fallback=None):
    value = rules.get(key)
    if isinstance(value, dict):
        return value
    return dict(fallback or {})


def rule_section(rules, key):
    value = rules.get(key)
    return value if isinstance(value, dict) else {}


def show_rule(rules, show_key):
    shows = rule_dict(rules, "shows")
    value = shows.get(show_key)
    return value if isinstance(value, dict) else {}


def issue_metadata(rules, code):
    metadata = rule_dict(rules, "issue_metadata")
    value = metadata.get(code)
    return value if isinstance(value, dict) else {}


def configured_show_keys(rules):
    return rule_list(rules, "show_keys", FALLBACK_SHOW_KEYS)


def configured_show_name(rules, show_key):
    return show_rule(rules, show_key).get("show_name") or show_key


def configured_calendar_id(rules):
    return rules.get("calendar_id") or DEFAULT_CALENDAR_ID


def guest_lifecycle_rules(rules):
    return rule_section(rules, "guest_lifecycle_rules")


def calendar_export_window_rules(rules):
    return rule_section(rules, "calendar_export_window_rules")


def suppression_rules(rules):
    suppressions = rule_section(rules, "suppression_rules")
    rules_list = []
    for key in ("known_exceptions", "suppressed_issues"):
        value = suppressions.get(key, [])
        if isinstance(value, list):
            rules_list.extend(item for item in value if isinstance(item, dict))
    return rules_list


def manual_issue_overrides(rules):
    return rule_list(rules, "manual_issue_overrides")


def manual_episode_issues(rules):
    return rule_list(rules, "manual_episode_issues")


def manual_calendar_event_issues(rules):
    return rule_list(rules, "manual_calendar_event_issues")


def parse_datetime(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def date_key(value):
    parsed = parse_datetime(value)
    if parsed:
        return parsed.date().isoformat()
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else text


def calendar_datetime(value):
    if isinstance(value, dict):
        return parse_datetime(value.get("dateTime") or value.get("date"))
    return parse_datetime(value)


def normalize_text(value):
    text = "" if value is None else str(value)
    text = unescape(TAG_RE.sub(" ", text))
    text = text.replace("\u2122", "")
    text = re.sub(r"[\W_]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def normalize_email(value):
    return str(value or "").strip().lower()


def extract_emails(value):
    if value is None:
        return []
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=True)
    return sorted({normalize_email(email) for email in EMAIL_RE.findall(str(value))})


def compact(value, limit=220):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def md_escape(value):
    return compact(value, limit=260).replace("|", "\\|").replace("\n", " ")


def html_escape(value):
    return escape("" if value is None else str(value), quote=True)


def html_text(value, limit=500):
    return html_escape(compact(value, limit=limit))


def short_date(value):
    parsed = parse_datetime(value)
    if not parsed:
        return str(value or "Unscheduled")
    return parsed.strftime("%a, %b %-d, %Y at %-I:%M %p %Z")


def issue_sort_key(item):
    return (
        SEVERITY_ORDER.get(effective_issue_severity(item), 9),
        item.get("episode_time") or "",
        item.get("show_name") or "",
        item.get("code") or "",
    )


def severity_rank(severity):
    return SEVERITY_ORDER.get(severity, 9)


def episode_sort_key(episode):
    return episode.get("episode_time") or ""


def active_appointment_ids(episode, guests=None):
    source = guests if guests is not None else episode.get("guests") or []
    ids = []
    for item in source:
        appointment_id = item.get("appointment_id") if isinstance(item, dict) else None
        if appointment_id and appointment_id not in ids:
            ids.append(appointment_id)
    if ids:
        return ids
    return [item for item in episode.get("appointment_ids") or [] if item]


def unique_guest_key(guest):
    email = normalize_email(guest.get("email"))
    if email:
        return f"email:{email}"
    name = normalize_text(guest.get("name"))
    appointment_id = guest.get("appointment_id") or ""
    return f"name:{name}:appointment:{appointment_id}"


def unique_guest_count(guests):
    return len({unique_guest_key(guest) for guest in guests})


def guest_names(guests):
    names = []
    for guest in guests or []:
        label = display_guest_name(guest) or display_guest_email(guest) or "Unknown guest"
        if label not in names:
            names.append(label)
    return names


def attendee_email_set(event):
    return set(normalize_email(email) for email in event.get("attendee_emails") or [])


def episode_readiness(episode):
    issues = episode.get("issues") or []
    if any(effective_issue_severity(item) == "Critical" for item in issues):
        return "Needs action"
    if any(effective_issue_severity(item) == "Warning" for item in issues):
        return "Needs review"
    return "Ready"


def issue_counts_for_episode(episode):
    return severity_counts(episode.get("issues") or [])


def repo_relative(path):
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except (OSError, ValueError):
        return str(path)


def source_ref(path, html_output_dir=None):
    path = Path(path)
    ref = {
        "path": repo_relative(path),
        "absolute_path": str(path.resolve()),
    }
    if html_output_dir:
        try:
            ref["href"] = str(path.resolve().relative_to(Path(html_output_dir).resolve()))
        except ValueError:
            try:
                ref["href"] = str(path.resolve().relative_to(Path(html_output_dir).resolve().parent))
            except ValueError:
                ref["href"] = str(path)
    return ref


def linkedin_event_guest_tokens(guests):
    tokens = set()
    for guest in guests or []:
        for value in (
            display_guest_name(guest),
            display_guest_email(guest),
            guest.get("contact_name"),
            guest.get("contact_email"),
            guest.get("represented_guest_name"),
            guest.get("represented_guest_email"),
        ):
            if not value:
                continue
            text = normalize_email(value) if "@" in str(value) else normalize_text(value)
            if text:
                tokens.add(text)
    return tokens


def known_linkedin_event_record(show_key, episode_time, guests, knowledge):
    episode_day = date_key(episode_time)
    guest_tokens = linkedin_event_guest_tokens(guests)
    for record in linkedin_events_from_knowledge(knowledge):
        if not isinstance(record, dict):
            continue
        if record.get("show_key") != show_key:
            continue
        if date_key(record.get("episode_date")) != episode_day:
            continue
        record_guest = record.get("guest_name")
        if record_guest:
            guest_key = normalize_text(record_guest)
            if guest_key not in guest_tokens:
                continue
        return record
    return None


def discovery_source_refs(show_key, discovery_dir):
    base = Path(discovery_dir)
    return [
        source_ref(base / f"{show_key}_episodes.json"),
        source_ref(base / f"{show_key}_appointments.json"),
        source_ref(base / f"{show_key}_form_submissions.json"),
    ]


def calendar_source_ref(calendar_events_path):
    return source_ref(Path(calendar_events_path))


def issue(
    *,
    severity,
    code,
    show_key,
    show_name,
    episode_time=None,
    calendar_event_id=None,
    appointment_ids=None,
    message,
    recommended_action,
    details=None,
    reason=None,
    evidence=None,
    confidence=None,
    explanation=None,
):
    details = details or {}
    evidence = evidence if evidence is not None else details
    reason = reason or message
    confidence = confidence or "medium"
    explanation = explanation or f"{message} Recommended action: {recommended_action}"
    return {
        "severity": severity,
        "code": code,
        "show_key": show_key,
        "show_name": show_name,
        "episode_time": episode_time,
        "calendar_event_id": calendar_event_id,
        "appointment_ids": appointment_ids or [],
        "message": message,
        "recommended_action": recommended_action,
        "reason": reason,
        "evidence": evidence,
        "confidence": confidence,
        "explanation": explanation,
        "details": details,
    }


def apply_issue_metadata(item, rules):
    metadata = issue_metadata(rules, item.get("code"))
    for key in ("severity", "confidence", "recommended_action", "reason", "explanation"):
        if metadata.get(key):
            item[key] = metadata[key]
    if not item.get("evidence"):
        item["evidence"] = item.get("details") or {}
    if not item.get("reason"):
        item["reason"] = item.get("message")
    if not item.get("confidence"):
        item["confidence"] = "medium"
    if not item.get("explanation"):
        item["explanation"] = f"{item.get('message')} Recommended action: {item.get('recommended_action')}"
    return item


def apply_metadata_to_issues(issues, rules):
    for item in issues:
        apply_issue_metadata(item, rules)
    return issues


def flatten_calendar_payload(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("items", "events", "results"):
        items = payload.get(key)
        if isinstance(items, list):
            return items
    return []


def load_calendar_payload(path):
    payload = read_json(path, default=None)
    if payload is None:
        raise RuntimeError(
            f"Missing Google Calendar event export: {path}. "
            f"Export/read upcoming events from {DEFAULT_CALENDAR_ID} and save them there, "
            "or pass --calendar-events /path/to/events.json."
        )
    return payload


def calendar_export_window_from_payload(payload):
    if not isinstance(payload, dict):
        return {
            "time_min": None,
            "time_max": None,
            "event_count": None,
            "has_explicit_window": False,
        }
    time_min = payload.get("time_min") or payload.get("timeMin")
    time_max = payload.get("time_max") or payload.get("timeMax")
    return {
        "time_min": time_min,
        "time_max": time_max,
        "event_count": payload.get("event_count") or len(flatten_calendar_payload(payload)),
        "has_explicit_window": bool(time_min or time_max),
    }


def load_calendar_events(path):
    payload = load_calendar_payload(path)
    return [normalize_calendar_event(event) for event in flatten_calendar_payload(payload)]


def normalize_attendees(event):
    attendees = event.get("attendees")
    if attendees is None:
        attendees = event.get("participants")
    normalized = []
    if not isinstance(attendees, list):
        return normalized, "attendees" in event or "participants" in event
    for attendee in attendees:
        if isinstance(attendee, str):
            email = normalize_email(attendee)
            normalized.append({"email": email, "display_name": "", "raw": attendee})
            continue
        if not isinstance(attendee, dict):
            continue
        email = normalize_email(attendee.get("email") or attendee.get("address"))
        if not email:
            continue
        normalized.append(
            {
                "email": email,
                "display_name": attendee.get("displayName") or attendee.get("name") or "",
                "response_status": attendee.get("responseStatus"),
                "raw": attendee,
            }
        )
    return normalized, True


def normalize_calendar_event(event):
    attendees, attendee_list_available = normalize_attendees(event)
    start = calendar_datetime(event.get("start") or event.get("start_time") or event.get("startTime"))
    end = calendar_datetime(event.get("end") or event.get("end_time") or event.get("endTime"))
    title = event.get("summary") or event.get("title") or event.get("display_title") or ""
    description = event.get("description") or event.get("notes") or ""
    location = event.get("location") or ""
    event_id = event.get("id") or event.get("event_id") or event.get("eventId")
    return {
        "id": event_id,
        "title": title,
        "description": description,
        "location": location,
        "start": start,
        "end": end,
        "attendees": attendees,
        "attendee_emails": sorted({item["email"] for item in attendees if item.get("email")}),
        "attendee_list_available": attendee_list_available,
        "url": event.get("htmlLink") or event.get("url") or event.get("display_url"),
        "raw_event_payload": event,
    }


def event_text(event):
    return normalize_text(" ".join([event.get("title", ""), event.get("description", ""), event.get("location", "")]))


def event_full_text(event):
    attendee_bits = [item.get("display_name", "") + " " + item.get("email", "") for item in event.get("attendees", [])]
    return normalize_text(
        " ".join(
            [
                event.get("title", ""),
                event.get("description", ""),
                event.get("location", ""),
                " ".join(attendee_bits),
            ]
        )
    )


def has_show_signal(event, show_name):
    title_text = normalize_text(event.get("title", ""))
    body_text = event_text(event)
    show_text = normalize_text(show_name)
    if not show_text:
        return False
    compact_show = show_text.replace(" ", "")
    return show_text in body_text or compact_show in title_text.replace(" ", "")


def name_tokens(name):
    return [token for token in normalize_text(name).split() if len(token) >= 3]


def contains_person(text, name=None, email=None):
    if email and normalize_email(email) in text:
        return True
    tokens = name_tokens(name)
    if not tokens:
        return False
    if len(tokens) == 1:
        return tokens[0] in text
    return tokens[0] in text and tokens[-1] in text


def display_guest_name(guest):
    represented = guest.get("represented_guest_name")
    confidence = normalize_text(guest.get("represented_guest_confidence"))
    if represented and confidence == "high":
        return represented
    return guest.get("name") or guest.get("contact_name") or guest.get("email") or guest.get("contact_email")


def display_guest_email(guest):
    represented = normalize_email(guest.get("represented_guest_email"))
    confidence = normalize_text(guest.get("represented_guest_confidence"))
    if confidence == "high":
        return represented or ""
    return normalize_email(guest.get("email") or guest.get("contact_email"))


def first_nonempty(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def unique_text_list(values):
    seen = set()
    ordered = []
    for value in values or []:
        text = str(value or "").strip()
        key = normalize_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return ordered


def contact_custom_fields(appointment, custom_field_map_by_id):
    payload = appointment.get("enriched_contact_payload") or {}
    raw_fields = payload.get("customFields") or []
    normalized = []
    for field in raw_fields:
        if not isinstance(field, dict):
            continue
        field_id = field.get("id")
        metadata = custom_field_map_by_id.get(field_id) or {}
        label = metadata.get("field_label") or metadata.get("name") or field_id
        key = metadata.get("field_key_or_name") or metadata.get("form_field_key") or field_id
        normalized.append(
            {
                "field_id": field_id,
                "field_label": label,
                "field_key_or_name": key,
                "value": field.get("value"),
                "required": metadata.get("required"),
                "raw_field_metadata": metadata.get("raw_field_metadata") or metadata,
                "appears_to_contain_pr_email": metadata.get("appears_to_contain_pr_email"),
                "appears_to_contain_assistant_email": metadata.get("appears_to_contain_assistant_email"),
                "appears_to_contain_alternate_calendar_invite_email": metadata.get("appears_to_contain_alternate_calendar_invite_email"),
                "appears_to_contain_calendar_invite_notes": metadata.get("appears_to_contain_calendar_invite_notes"),
            }
        )
    return normalized


def linkedin_slug_to_name(url):
    cleaned = clean_url(url)
    if "linkedin.com/in/" not in cleaned.lower():
        return None
    slug = cleaned.rstrip("/").split("/in/", 1)[-1].split("/", 1)[0]
    slug = re.sub(r"\?.*$", "", slug)
    slug = re.sub(r"[^a-zA-Z0-9-]", "-", slug)
    parts = [part for part in slug.split("-") if part]
    if not parts:
        return None
    if len(parts) == 1:
        token = parts[0]
        if len(token) >= 6:
            token = re.sub(r"([a-z])([A-Z])", r"\1 \2", token)
            token = re.sub(r"([a-z]{2,})([A-Z][a-z]+)", r"\1 \2", token)
        guesses = re.findall(r"[A-Za-z][a-z]+", token.title())
        if len(guesses) >= 2:
            return " ".join(guesses[:2])
        if len(token) >= 6:
            return token[:3].title() + " " + token[3:].title()
        return token.title()
    return " ".join(part.title() for part in parts[:3])


def field_values_for_labels(fields, include_terms):
    values = []
    for field in fields or []:
        label = normalize_text(field.get("field_label") or field.get("field_key_or_name"))
        if any(term in label for term in include_terms):
            value = field.get("value")
            if meaningful_value(value):
                values.append(str(value).strip())
    return unique_text_list(values)


def internal_email(email):
    domain = normalize_email(email).split("@")[-1]
    return domain in INTERNAL_EMAIL_DOMAINS


def attendee_email_candidates(event, excluded_emails=None):
    excluded = {normalize_email(email) for email in (excluded_emails or []) if email}
    candidates = []
    for email in event.get("attendee_emails") or []:
        normalized = normalize_email(email)
        if not normalized or normalized in excluded or internal_email(normalized):
            continue
        candidates.append(normalized)
    return candidates


def extract_guest_from_event_title(event, show_name):
    title = event.get("title") or ""
    cleaned = re.sub(re.escape(show_name), "", title, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bwith\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:")
    return cleaned or None


def represented_guest_context(guest, show_name, event=None):
    contact_name = guest.get("contact_name") or guest.get("name")
    contact_email = normalize_email(guest.get("contact_email") or guest.get("email"))
    fields = guest.get("contact_custom_fields") or guest.get("field_values") or []
    linkedin_values = field_values_for_labels(fields, ("linkedin",))
    episode_titles = field_values_for_labels(fields, ("title", "episode"))
    topics = field_values_for_labels(fields, ("topic",))
    linkedin_name = linkedin_slug_to_name(linkedin_values[0]) if linkedin_values else None
    calendar_guest = extract_guest_from_event_title(event, show_name) if event else None
    calendar_text = event_full_text(event) if event else ""
    evidence = []
    score = 0
    represented_name = None

    if linkedin_name:
        represented_name = linkedin_name
        evidence.append("LinkedIn URL")
        score += 3
    if calendar_guest and normalize_text(calendar_guest) != normalize_text(contact_name):
        if represented_name and normalize_text(calendar_guest) == normalize_text(represented_name):
            evidence.append("calendar title")
            score += 4
        elif not represented_name:
            represented_name = calendar_guest
            evidence.append("calendar title")
            score += 2
    if episode_titles:
        evidence.append("episode title")
        score += 1
    if topics:
        evidence.append("topics field")
        score += 1
    if fields:
        evidence.append("custom fields")
        score += 1

    represented_email = None
    if event and represented_name:
        for email in attendee_email_candidates(event, excluded_emails=[contact_email]):
            local = email.split("@", 1)[0]
            tokens = name_tokens(represented_name)
            if tokens and any(token in normalize_text(local) for token in (tokens[0], tokens[-1])):
                represented_email = email
                evidence.append("calendar attendees")
                score += 2
                break
    contact_name_differs = bool(represented_name and normalize_text(represented_name) != normalize_text(contact_name))
    rep_clue = contact_name_differs or any(term in contact_email for term in ("pr", "press", "media", "assistant", "coord", "agency"))
    if rep_clue and represented_name:
        score += 1
    corroborated_identity = "calendar title" in evidence or "calendar attendees" in evidence
    confidence = "low"
    if represented_name and contact_name_differs and ("LinkedIn URL" in evidence and "calendar title" in evidence):
        confidence = "high"
    elif represented_name and score >= 5 and corroborated_identity:
        confidence = "medium"
    if represented_name and represented_email and score >= 7:
        confidence = "high"
    return {
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contact_is_submitter_rep": bool(contact_name_differs and represented_name and confidence != "low"),
        "represented_guest_name": represented_name,
        "represented_guest_email": represented_email,
        "represented_guest_confidence": confidence if represented_name else "low",
        "represented_guest_evidence": unique_text_list(evidence),
        "episode_titles": episode_titles,
        "topics": topics,
        "linkedin_urls": linkedin_values,
    }


def same_local_date(a, b):
    if not a or not b:
        return False
    return a.date() == b.astimezone(a.tzinfo or timezone.utc).date()


def minutes_between(a, b):
    if not a or not b:
        return None
    return abs((a.astimezone(timezone.utc) - b.astimezone(timezone.utc)).total_seconds()) / 60


def calendar_export_gap_for_time(coverage_time, options):
    if not coverage_time:
        return None
    window = options.get("calendar_export_window") or {}
    if not window.get("has_explicit_window"):
        return None
    export_min = parse_datetime(window.get("time_min"))
    export_max = parse_datetime(window.get("time_max"))
    if export_min and coverage_time < export_min:
        return {
            "direction": "before_export_window",
            "coverage_time": coverage_time.isoformat(),
            "calendar_export_time_min": window.get("time_min"),
            "calendar_export_time_max": window.get("time_max"),
            "calendar_events_loaded": window.get("event_count"),
        }
    if export_max and coverage_time > export_max:
        return {
            "direction": "after_export_window",
            "coverage_time": coverage_time.isoformat(),
            "calendar_export_time_min": window.get("time_min"),
            "calendar_export_time_max": window.get("time_max"),
            "calendar_events_loaded": window.get("event_count"),
        }
    return None


def appointment_is_active(appointment, rules):
    status = normalize_text(appointment.get("status"))
    lifecycle = guest_lifecycle_rules(rules)
    inactive_statuses = {normalize_text(item) for item in rule_list(rules, "inactive_statuses", FALLBACK_INACTIVE_STATUSES)}
    for key in (
        "canceled_statuses",
        "rescheduled_statuses",
        "replaced_statuses",
        "non_actionable_statuses",
    ):
        inactive_statuses.update(normalize_text(item) for item in lifecycle.get(key, []) if item)
    return status not in inactive_statuses


def merged_required_field_keywords(rules, show_key):
    merged = rule_dict(rules, "required_field_keywords", FALLBACK_REQUIRED_FIELD_KEYWORDS)
    show_keywords = show_rule(rules, show_key).get("required_field_keywords")
    if isinstance(show_keywords, dict):
        merged = {**merged, **show_keywords}
    return merged


def field_is_required(field, rules, show_key=None):
    raw_metadata = field.get("raw_field_metadata") or {}
    required = field.get("required")
    if required is None:
        required = raw_metadata.get("required") or raw_metadata.get("isRequired")
    if required is True:
        return True
    label = normalize_text(field.get("field_label") or field.get("field_key_or_name"))
    for keywords in merged_required_field_keywords(rules, show_key).values():
        if all(keyword in label for keyword in keywords):
            return True
    return False


def meaningful_value(value):
    if value in (None, ""):
        return False
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=True)
    text = str(value).strip()
    if not text:
        return False
    return True


def field_value_present_in_description(field, description_text):
    value = field.get("value")
    label = normalize_text(field.get("field_label") or field.get("field_key_or_name"))
    normalized_description = normalize_text(description_text)
    if label and label in normalized_description:
        if str(value).strip().lower() in {"yes", "no", "n/a", "na"}:
            return True
    for email in extract_emails(value):
        if email in description_text.lower():
            return True
    urls = URL_RE.findall(str(value or ""))
    for url in urls:
        normalized_url = url.lower().strip("<>()[]")
        if normalized_url and normalized_url in description_text.lower():
            return True
    value_text = normalize_text(value)
    if len(value_text) >= 6 and value_text in normalized_description:
        return True
    return False


def extract_field_emails(fields, flag_name):
    emails = []
    for field in fields:
        if field.get(flag_name):
            emails.extend(field.get("emails_found") or extract_emails(field.get("value")))
    return sorted(set(emails))


def load_show_context(show_key, discovery_dir):
    episodes = read_json(discovery_dir / f"{show_key}_episodes.json", [])
    appointments = read_json(discovery_dir / f"{show_key}_appointments.json", [])
    submissions = read_json(discovery_dir / f"{show_key}_form_submissions.json", [])
    custom_field_map = read_json(discovery_dir / f"{show_key}_custom_field_map.json", [])
    appointments_by_id = {
        item.get("appointment_id"): item
        for item in appointments
        if item.get("appointment_id")
    }
    submissions_by_id = {
        item.get("submission_id"): item
        for item in submissions
        if item.get("submission_id")
    }
    custom_field_map_by_id = {
        item.get("field_id"): item
        for item in custom_field_map
        if isinstance(item, dict) and item.get("field_id")
    }
    return episodes, appointments_by_id, submissions_by_id, custom_field_map_by_id


DISCOVERY_FILE_SUFFIXES = (
    "appointments",
    "forms",
    "form_fields",
    "form_submissions",
    "custom_field_map",
    "episodes",
)


def discovery_file_path(discovery_dir, show_key, suffix):
    return discovery_dir / f"{show_key}_{suffix}.json"


def list_missing_discovery_files(show_key, discovery_dir):
    return [
        str(discovery_file_path(discovery_dir, show_key, suffix))
        for suffix in DISCOVERY_FILE_SUFFIXES
        if not discovery_file_path(discovery_dir, show_key, suffix).exists()
    ]


def count_discovery_file(path):
    data = read_json(path, default=[])
    if isinstance(data, (list, dict)):
        return len(data)
    return 0


def discovery_diagnostic(show_key, discovery_dir, rules, episodes, appointments_by_id, submissions_by_id):
    show_config = show_rule(rules, show_key)
    show_name = configured_show_name(rules, show_key)
    missing_files = list_missing_discovery_files(show_key, discovery_dir)
    env_vars = {
        "token_env_var": show_config.get("highlevel_token_env_var"),
        "location_id_env_var": show_config.get("highlevel_location_id_env_var"),
    }
    counts = {
        suffix: count_discovery_file(discovery_file_path(discovery_dir, show_key, suffix))
        for suffix in DISCOVERY_FILE_SUFFIXES
        if discovery_file_path(discovery_dir, show_key, suffix).exists()
    }
    if missing_files:
        return {
            "show_key": show_key,
            "show_name": show_name,
            "status": "missing_discovery_files",
            "severity": "Warning",
            "message": "Normalized HighLevel discovery files are missing for this show.",
            "what_is_needed": "Run HighLevel discovery for this show after configuring its private integration token and location ID.",
            "missing_files": missing_files,
            "env_vars": env_vars,
            "how_to_fix": f"Set {env_vars.get('location_id_env_var') or 'the show location ID env var'} in `.env`, then run `python3 scripts/show-launch.py --discover-highlevel --show-key {show_key}`.",
            "discovery_counts": counts,
        }
    if not episodes and not appointments_by_id and not submissions_by_id:
        return {
            "show_key": show_key,
            "show_name": show_name,
            "status": "no_discovery_data",
            "severity": "Warning",
            "message": "Discovery files exist, but no appointments, episodes, or form submissions are available for this show.",
            "what_is_needed": "A successful HighLevel discovery pull with upcoming appointment data.",
            "missing_files": [],
            "env_vars": env_vars,
            "how_to_fix": f"Confirm {env_vars.get('location_id_env_var') or 'the show location ID env var'} is set in `.env`, then rerun `python3 scripts/show-launch.py --discover-highlevel --show-key {show_key}`.",
            "discovery_counts": counts,
        }
    if not episodes and appointments_by_id:
        return {
            "show_key": show_key,
            "show_name": show_name,
            "status": "episodes_not_normalized",
            "severity": "Warning",
            "message": "Appointments were discovered, but normalized episode records are missing.",
            "what_is_needed": f"`data/discovery/{show_key}_episodes.json` must contain normalized upcoming episode records.",
            "missing_files": [],
            "env_vars": env_vars,
            "how_to_fix": f"Rerun `python3 scripts/show-launch.py --discover-highlevel --show-key {show_key}` to regenerate normalized episode structures.",
            "discovery_counts": counts,
        }
    return None


def guest_submission_fields(guest, submissions_by_id):
    fields = []
    seen = set()
    for submission_id in guest.get("form_submission_ids") or []:
        if not submission_id or submission_id in seen:
            continue
        seen.add(submission_id)
        submission = submissions_by_id.get(submission_id)
        if submission:
            fields.extend(submission.get("field_values") or [])
    return fields


def enrich_guest(guest, appointments_by_id, submissions_by_id, rules, show_key=None, custom_field_map_by_id=None):
    appointment = appointments_by_id.get(guest.get("appointment_id")) or {}
    fields = guest_submission_fields(guest, submissions_by_id)
    contact_fields = contact_custom_fields(appointment, custom_field_map_by_id or {})
    fields.extend(contact_fields)
    pr_related = list(guest.get("pr_assistant_alternate_emails") or [])
    for field in fields:
        if any(
            field.get(flag)
            for flag in (
                "appears_to_contain_pr_email",
                "appears_to_contain_assistant_email",
                "appears_to_contain_alternate_calendar_invite_email",
                "appears_to_contain_calendar_invite_notes",
            )
        ):
            pr_related.append(
                {
                    "field_id": field.get("field_id"),
                    "field_label": field.get("field_label"),
                    "value": field.get("value"),
                    "emails_found": field.get("emails_found") or extract_emails(field.get("value")),
                    "classification": {
                        "pr_email": field.get("appears_to_contain_pr_email"),
                        "assistant_email": field.get("appears_to_contain_assistant_email"),
                        "alternate_calendar_invite_email": field.get("appears_to_contain_alternate_calendar_invite_email"),
                        "calendar_invite_notes": field.get("appears_to_contain_calendar_invite_notes"),
                    },
                }
            )
    pr_emails = set(extract_field_emails(fields, "appears_to_contain_pr_email"))
    assistant_emails = set(extract_field_emails(fields, "appears_to_contain_assistant_email"))
    alternate_invite_emails = set(extract_field_emails(fields, "appears_to_contain_alternate_calendar_invite_email"))
    for related in pr_related:
        classification = related.get("classification") or {}
        emails = related.get("emails_found") or extract_emails(related.get("value"))
        if classification.get("pr_email"):
            pr_emails.update(emails)
        if classification.get("assistant_email"):
            assistant_emails.update(emails)
        if classification.get("alternate_calendar_invite_email"):
            alternate_invite_emails.update(emails)
    return {
        **guest,
        "contact_name": guest.get("name"),
        "contact_email": guest.get("email"),
        "status": appointment.get("status"),
        "appointment": appointment,
        "field_values": fields,
        "contact_custom_fields": contact_fields,
        "pr_emails": sorted(pr_emails),
        "assistant_emails": sorted(assistant_emails),
        "alternate_invite_emails": sorted(alternate_invite_emails),
        "calendar_relevant_fields": pr_related,
        "required_fields": [field for field in fields if field_is_required(field, rules, show_key) and meaningful_value(field.get("value"))],
    }


def active_episode_guests(show_key, episode, appointments_by_id, submissions_by_id, rules, custom_field_map_by_id=None):
    active = []
    inactive = []
    for guest in episode.get("guests") or []:
        enriched = enrich_guest(guest, appointments_by_id, submissions_by_id, rules, show_key, custom_field_map_by_id)
        appointment_id = enriched.get("appointment_id")
        appointment = appointments_by_id.get(appointment_id) if appointment_id else None
        if appointment and not appointment_is_active(appointment, rules):
            inactive.append(enriched)
            continue
        active.append(enriched)
    return active, inactive


def score_event_for_episode(event, episode, guests, expected_calendar_start, live_start, tolerance_minutes):
    if not event.get("start"):
        return 0
    score = 0
    title_and_body = event_full_text(event)
    preshow_diff = minutes_between(event.get("start"), expected_calendar_start)
    live_diff = minutes_between(event.get("start"), live_start)
    if preshow_diff is not None and preshow_diff <= tolerance_minutes:
        score += 55
    elif live_diff is not None and live_diff <= tolerance_minutes:
        score += 35
    elif event.get("end") and event["start"] <= live_start <= event["end"]:
        score += 25
    if same_local_date(event.get("start"), live_start):
        score += 15
    if has_show_signal(event, episode.get("show_name")):
        score += 25
    for guest in guests:
        if contains_person(title_and_body, guest.get("name"), guest.get("email")):
            score += 8
    return score


def find_calendar_match(events, episode, guests, expected_calendar_start, live_start, tolerance_minutes, match_threshold):
    scored = []
    for event in events:
        score = score_event_for_episode(event, episode, guests, expected_calendar_start, live_start, tolerance_minutes)
        if score:
            scored.append((score, event))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored or scored[0][0] < match_threshold:
        return None, []
    duplicates = [
        event
        for _score, event in scored
        if minutes_between(event.get("start"), expected_calendar_start) is not None
        and minutes_between(event.get("start"), expected_calendar_start) <= tolerance_minutes
        and has_show_signal(event, episode.get("show_name"))
    ]
    return scored[0][1], duplicates


def episode_pairing_summary(show_key, episode, guests, event, rules):
    expected_guest_count = show_rule(rules, show_key).get("expected_guest_count")
    title_text = normalize_text(event.get("title", "")) if event else ""
    full_text = event_full_text(event) if event else ""
    attendees = attendee_email_set(event) if event else set()
    unique_count = unique_guest_count(guests)
    title_guests = []
    detail_guests = []
    invited_guests = []
    missing_invites = []
    for guest in guests:
        label = display_guest_name(guest) or display_guest_email(guest)
        if contains_person(title_text, display_guest_name(guest), display_guest_email(guest)):
            title_guests.append(label)
        if contains_person(full_text, display_guest_name(guest), display_guest_email(guest)):
            detail_guests.append(label)
        guest_email = display_guest_email(guest)
        if guest_email and guest_email in attendees:
            invited_guests.append(label)
        elif guest_email:
            missing_invites.append(label)
    is_expected_pair = bool(expected_guest_count and unique_count >= int(expected_guest_count))
    recognized_pair = bool(is_expected_pair and unique_count >= 2 and (len(title_guests) >= 2 or len(detail_guests) >= 2))
    return {
        "expected_guest_count": expected_guest_count,
        "active_guest_count": len(guests),
        "unique_active_guest_count": unique_count,
        "is_expected_two_guest_episode": bool(is_expected_pair),
        "recognized_two_guest_pair": recognized_pair,
        "title_guest_names_found": title_guests,
        "calendar_detail_guest_names_found": detail_guests,
        "invited_guest_names_found": invited_guests,
        "guest_names_missing_invites": missing_invites,
        "needs_pairing_review": bool(is_expected_pair and unique_count >= 2 and not recognized_pair),
    }


def highlevel_guest_summary(guest):
    return {
        "name": display_guest_name(guest),
        "email": display_guest_email(guest),
        "contact_name": guest.get("contact_name") or guest.get("name"),
        "contact_email": guest.get("contact_email") or guest.get("email"),
        "appointment_id": guest.get("appointment_id"),
        "contact_id": guest.get("contact_id"),
        "status": guest.get("status"),
        "represented_guest_name": guest.get("represented_guest_name"),
        "represented_guest_email": guest.get("represented_guest_email"),
        "represented_guest_confidence": guest.get("represented_guest_confidence"),
        "represented_guest_evidence": guest.get("represented_guest_evidence") or [],
        "form_submission_ids": guest.get("form_submission_ids") or [],
        "possible_form_submissions": guest.get("possible_form_submissions") or [],
        "pr_emails": guest.get("pr_emails") or [],
        "assistant_emails": guest.get("assistant_emails") or [],
        "alternate_invite_emails": guest.get("alternate_invite_emails") or [],
    }


def calendar_event_summary(event):
    if not event:
        return {
            "event_found": False,
            "event_id": None,
            "title": None,
            "start": None,
            "end": None,
            "attendee_emails": [],
            "event_url": None,
        }
    return {
        "event_found": True,
        "event_id": event.get("id"),
        "title": event.get("title"),
        "start": event.get("start").isoformat() if event.get("start") else None,
        "end": event.get("end").isoformat() if event.get("end") else None,
        "attendee_emails": event.get("attendee_emails") or [],
        "attendee_count": len(event.get("attendee_emails") or []),
        "event_url": event.get("url"),
    }


def apply_represented_guest_inference(guests, show_name, event=None):
    enriched = []
    for guest in guests or []:
        context = represented_guest_context(guest, show_name, event)
        enriched.append({**guest, **context})
    return enriched


def represented_guest_issue(show_key, show_name, episode_time, event, guest, appointment_ids, confidence=None):
    confidence = confidence or guest.get("represented_guest_confidence") or "medium"
    represented = guest.get("represented_guest_name")
    contact = guest.get("contact_name") or guest.get("name")
    evidence = guest.get("represented_guest_evidence") or []
    details = {
        "highlevel_submitter_contact": contact,
        "highlevel_submitter_email": guest.get("contact_email") or guest.get("email"),
        "represented_guest": represented,
        "represented_guest_email": guest.get("represented_guest_email"),
        "represented_guest_confidence": confidence.title(),
        "represented_guest_evidence": evidence,
        "episode_title_candidates": guest.get("episode_titles") or [],
        "topic_candidates": guest.get("topics") or [],
        "linkedin_urls": guest.get("linkedin_urls") or [],
    }
    if normalize_text(confidence) == "high":
        return issue(
            severity="Informational",
            code="pr_representative_booking_guest_represented",
            show_key=show_key,
            show_name=show_name,
            episode_time=episode_time,
            calendar_event_id=event.get("id") if event else None,
            appointment_ids=appointment_ids,
            message=f"HighLevel submitter/contact {contact} appears to represent guest {represented}.",
            recommended_action="No mismatch action needed. Keep the represented guest as the calendar-facing guest unless later human review changes the booking context.",
            details=details,
            confidence="high",
        )
    return issue(
        severity="Warning",
        code="calendar_event_needs_confirmation",
        show_key=show_key,
        show_name=show_name,
        episode_time=episode_time,
        calendar_event_id=event.get("id") if event else None,
        appointment_ids=appointment_ids,
        message=f"HighLevel contact {contact} may be a PR/submitter while the calendar appears to use guest {represented}.",
        recommended_action="Confirm the represented guest before treating the calendar event as fully trusted.",
        details=details,
        confidence=confidence,
    )


def issue_operational_impact(rules, code):
    impacts = rule_dict(rules, "issue_operational_impacts")
    return impacts.get(code) or impacts.get("default") or "This can create manual production risk unless an operator verifies it before showtime."


def confidence_label(value):
    text = normalize_text(value)
    if text == "high":
        return "High confidence"
    if text == "low":
        return "Low confidence"
    return "Medium confidence"


def confidence_explanation(rules, item):
    explanations = rule_dict(rules, "confidence_explanations")
    code = item.get("code")
    configured = explanations.get(code) or explanations.get(item.get("confidence")) or explanations.get("default")
    if configured:
        return configured
    if item.get("confidence") == "low":
        return "The audit evidence is incomplete, so this result needs human verification."
    if item.get("confidence") == "high":
        return "The audit is based on direct HighLevel and Google Calendar evidence."
    return "The audit found a likely issue, but one or more links or source fields require human review."


def autofix_classification(rules, item):
    policy = rule_section(rules, "future_autofix_policy")
    by_code = rule_dict(policy, "issue_codes")
    configured = by_code.get(item.get("code"))
    if isinstance(configured, dict):
        return {
            "classification": configured.get("classification") or "Needs approval",
            "reason": configured.get("reason") or "Configured in future_autofix_policy.",
        }
    by_severity = rule_dict(policy, "default_by_severity")
    classification = by_severity.get(item.get("severity"), "Needs approval")
    return {
        "classification": classification,
        "reason": "Default policy by severity. Autofix is not implemented in Version 1.",
    }


def issue_due_soon(item, now, days=7):
    episode_time = parse_datetime(item.get("episode_time"))
    if not episode_time:
        return True
    return episode_time <= now + timedelta(days=days)


def operator_recommendation(rules, item, now, is_first_critical=False):
    configured = rule_section(rules, "operator_recommendation_rules")
    if is_first_critical:
        return {
            "category": "Fix First",
            "reason": "This is the highest-priority active Critical issue in the current audit.",
        }
    if item.get("severity") == "Critical":
        return {
            "category": "Fix Today",
            "reason": configured.get("critical_reason") or "Critical issues can block a successful show and should be reviewed today.",
        }
    if item.get("severity") == "Warning":
        if issue_due_soon(item, now, int(configured.get("warning_due_days", 14))):
            return {
                "category": "Fix Today",
                "reason": configured.get("warning_due_reason") or "This Warning affects an upcoming episode inside the configured action window.",
            }
        return {
            "category": "Monitor",
            "reason": configured.get("warning_monitor_reason") or "This Warning is not inside the configured immediate action window.",
        }
    return {
        "category": "Monitor",
        "reason": configured.get("informational_reason") or "Informational issues do not require immediate action but should stay visible.",
    }


def severity_from_stage_rules(item, timeline_rules, stage_context):
    base_severity = item.get("base_severity") or item.get("severity") or "Informational"
    severity_rules = timeline_rules.get("stage_aware_issue_severity") or {}
    rule = severity_rules.get(item.get("code")) or severity_rules.get("default")
    if not isinstance(rule, dict):
        return base_severity, "No stage-aware severity override is configured for this issue code."
    stage_key = stage_context.get("key")
    by_stage = rule.get("by_stage") or {}
    adjusted = by_stage.get(stage_key)
    if not adjusted:
        adjusted = rule.get("default_severity") or base_severity
    if adjusted == "{base_severity}":
        adjusted = base_severity
    reason_template = rule.get("reason") or "Severity is adjusted for the current production stage."
    return adjusted, reason_template.format(
        stage=stage_context.get("label"),
        base_severity=base_severity,
        adjusted_severity=adjusted,
        issue_code=item.get("code"),
    )


def stage_adjusted_issue_sort_key(item):
    return (
        SEVERITY_ORDER.get(item.get("stage_adjusted_severity") or item.get("severity"), 9),
        item.get("episode_time") or "",
        item.get("show_name") or "",
        item.get("code") or "",
    )


def stage_operator_recommendation(item, timeline_rules=None, is_first_stage_critical=False):
    severity = item.get("stage_adjusted_severity") or item.get("severity")
    stage = item.get("production_stage") or {}
    urgency = (timeline_rules or {}).get("urgent_uncertainty") or {}
    urgent_issue_codes = set(urgency.get("issue_codes") or [])
    urgent_stage_keys = {"48_hours_7_days", "24_48_hours", "day_of_show"}
    if is_first_stage_critical:
        return {
            "category": "Fix First",
            "reason": f"This is the highest-priority stage-adjusted Critical issue for the current audit. Stage: {stage.get('label')}.",
        }
    if severity == "Critical":
        return {
            "category": "Fix Today",
            "reason": f"This issue is Critical for the current production stage: {stage.get('label')}.",
        }
    if severity == "Warning":
        if item.get("code") in urgent_issue_codes and stage.get("key") in urgent_stage_keys:
            return {
                "category": urgency.get("operator_category") or "Urgent Review",
                "reason": urgency.get("reason") or f"This issue needs urgent review because the show is close. Stage: {stage.get('label')}.",
            }
        return {
            "category": "Fix Today",
            "reason": f"This issue is due for operator attention during the current production stage: {stage.get('label')}.",
        }
    return {
        "category": "Monitor",
        "reason": f"This issue is not blocking the current production stage: {stage.get('label')}.",
    }


def attach_stage_decisions(issues, timeline_rules, now):
    for item in issues:
        stage_context = production_stage_context(item.get("episode_time"), timeline_rules, now)
        item["base_severity"] = item.get("severity")
        item["production_stage"] = stage_context
        adjusted, reason = severity_from_stage_rules(item, timeline_rules, stage_context)
        item["stage_adjusted_severity"] = adjusted
        item["stage_severity_reason"] = reason
        item["base_operator_recommendation"] = item.get("operator_recommendation")
    critical_issues = [
        item
        for item in sorted(issues, key=stage_adjusted_issue_sort_key)
        if item.get("stage_adjusted_severity") == "Critical"
    ]
    first_critical_key = issue_fingerprint(critical_issues[0]) if critical_issues else None
    for item in issues:
        item["operator_recommendation"] = stage_operator_recommendation(
            item,
            timeline_rules=timeline_rules,
            is_first_stage_critical=bool(first_critical_key and issue_fingerprint(item) == first_critical_key),
        )


def attach_issue_decisions(issues, rules, now):
    critical_issues = [item for item in sorted(issues, key=issue_sort_key) if item.get("severity") == "Critical"]
    first_critical_key = issue_fingerprint(critical_issues[0]) if critical_issues else None
    for item in issues:
        item["confidence_label"] = confidence_label(item.get("confidence"))
        item["confidence_explanation"] = confidence_explanation(rules, item)
        item["operator_recommendation"] = operator_recommendation(
            rules,
            item,
            now,
            is_first_critical=bool(first_critical_key and issue_fingerprint(item) == first_critical_key),
        )
        item["autofix"] = autofix_classification(rules, item)
    return issues


def trust_layer_rules(rules):
    return rule_section(rules, "trust_layer")


def trust_rule_for_issue(rules, item):
    layer = trust_layer_rules(rules)
    default_rule = rule_dict(layer, "default")
    issue_rules = rule_dict(layer, "issue_codes")
    configured = issue_rules.get(item.get("code"))
    if isinstance(configured, dict):
        return {**default_rule, **configured}
    return dict(default_rule)


def trust_known_context(rules):
    return rule_list(trust_layer_rules(rules), "known_context")


def issue_guest_display(item):
    panel = item.get("evidence_panel") or {}
    details = item.get("details") or {}
    guests = []
    for guest in panel.get("evidence_from_highlevel", {}).get("active_guests") or []:
        name = guest.get("name")
        email = guest.get("email")
        if name and email:
            guests.append(f"{name} <{email}>")
        elif name or email:
            guests.append(name or email)
    for key in (
        "calendar_guest",
        "guest",
        "replacement_guest",
        "canceled_or_rescheduled_guest",
        "represented_guest",
        "highlevel_submitter_contact",
    ):
        value = details.get(key)
        if value:
            guests.append(str(value))
    for key in (
        "missing_guests",
        "guests",
        "missing_guest_emails",
        "guests_missing_emails",
        "missing_pr_emails",
    ):
        value = details.get(key)
        if isinstance(value, list):
            guests.extend(str(entry) for entry in value if entry)
    seen = set()
    deduped = []
    for guest in guests:
        guest_key = normalize_text(guest)
        if guest_key and guest_key not in seen:
            seen.add(guest_key)
            deduped.append(guest)
    return ", ".join(deduped) or "Unknown / not directly identified"


def issue_not_due_yet(item):
    if item.get("suppressed"):
        return False
    stage_key = (item.get("production_stage") or {}).get("key")
    severity = effective_issue_severity(item)
    due_later_codes = {
        "booking_without_calendar_event",
        "required_attendee_not_invited",
        "pr_email_not_invited",
        "sop_required_assets_missing",
        "required_custom_fields_missing_from_description",
    }
    if item.get("code") in due_later_codes and stage_key == "30_plus_days" and severity != "Critical":
        return True
    recommendation = (item.get("operator_recommendation") or {}).get("category")
    if item.get("code") in due_later_codes and recommendation == "Monitor" and severity != "Critical":
        return True
    return False


def normalized_automation_candidate(value):
    text = normalize_text(value)
    return "yes" if text in {"yes", "true", "safe to autofix"} else "no"


def trust_decision_for_issue(item, rules):
    configured = trust_rule_for_issue(rules, item)
    category = configured.get("category") or "Needs Human Verification"
    bucket = configured.get("dashboard_bucket") or "Needs Verification"
    if item.get("knowledge_trust_category") or item.get("knowledge_trust_dashboard_bucket"):
        category = item.get("knowledge_trust_category") or category
        bucket = item.get("knowledge_trust_dashboard_bucket") or bucket
    elif item.get("suppressed"):
        category = "Known Exception"
        bucket = "Known Exceptions"
    elif issue_not_due_yet(item):
        category = "Not Due Yet"
        bucket = "Not Due Yet"
    return {
        "category": category,
        "dashboard_bucket": bucket,
        "what_jessie_should_verify": configured.get("what_jessie_should_verify")
        or "Review the evidence before taking any external action.",
        "future_automation_candidate": normalized_automation_candidate(configured.get("future_automation_candidate")),
        "automation_risk_level": configured.get("automation_risk_level") or "high",
        "approval_required_before_action": configured.get("approval_required_before_action")
        or "Human approval is required before any external system is changed.",
    }


def build_trust_finding(item, rules):
    panel = item.get("evidence_panel") or {}
    decision = trust_decision_for_issue(item, rules)
    suppression = item.get("suppression") or {}
    why_flagged = item.get("message") or panel.get("difference_detected") or "The audit found a production mismatch."
    if item.get("suppressed") and suppression.get("reason"):
        why_flagged = f"Suppressed known exception: {suppression.get('reason')}"
    return {
        "finding_id": issue_identity_key(item),
        "show": item.get("show_name"),
        "show_key": item.get("show_key"),
        "episode": item.get("episode_time"),
        "guest": issue_guest_display(item),
        "issue": item.get("message"),
        "issue_code": item.get("code"),
        "category": decision["category"],
        "dashboard_bucket": decision["dashboard_bucket"],
        "severity": effective_issue_severity(item),
        "base_severity": item.get("base_severity") or item.get("severity"),
        "confidence": item.get("confidence_label") or confidence_label(item.get("confidence")),
        "confidence_raw": item.get("confidence"),
        "why_it_was_flagged": why_flagged,
        "evidence_from_highlevel": panel.get("evidence_from_highlevel") or item.get("evidence_from_highlevel") or {},
        "evidence_from_google_calendar": panel.get("evidence_from_google_calendar") or item.get("evidence_from_google_calendar") or {},
        "difference_detected": panel.get("difference_detected") or item.get("difference_detected"),
        "what_jessie_should_verify": decision["what_jessie_should_verify"],
        "recommended_human_action": item.get("recommended_action"),
        "operator_recommendation": item.get("operator_recommendation") or {},
        "future_automation_candidate": decision["future_automation_candidate"],
        "automation_risk_level": decision["automation_risk_level"],
        "approval_required_before_action": decision["approval_required_before_action"],
        "raw_ids": panel.get("relevant_raw_ids") or item.get("relevant_raw_ids") or {},
        "why_this_matters_operationally": panel.get("why_this_matters_operationally") or item.get("why_this_matters_operationally"),
        "source_json_files": panel.get("source_json_files") or [],
        "operational_status": item.get("operational_status") or (item.get("knowledge_decision") or {}).get("status_category"),
        "knowledge_decision": item.get("knowledge_decision") or {},
        "suppressed": bool(item.get("suppressed")),
        "suppression": suppression,
    }


def attach_trust_layer(issues, rules):
    for item in issues or []:
        item["trust"] = build_trust_finding(item, rules)
        item["trust_category"] = item["trust"].get("category")
        item["trust_dashboard_bucket"] = item["trust"].get("dashboard_bucket")
        item["future_automation_candidate"] = item["trust"].get("future_automation_candidate")
        item["automation_risk_level"] = item["trust"].get("automation_risk_level")
        item["approval_required_before_action"] = item["trust"].get("approval_required_before_action")
    return issues


def trust_findings_from_issues(issues):
    findings = []
    for item in issues or []:
        finding = item.get("trust")
        if isinstance(finding, dict):
            findings.append(finding)
    return findings


def group_trust_findings(findings):
    grouped = {bucket: [] for bucket in TRUST_BUCKETS}
    for finding in findings or []:
        bucket = finding.get("dashboard_bucket") or "Needs Verification"
        grouped.setdefault(bucket, []).append(finding)
    for bucket, items in grouped.items():
        grouped[bucket] = sorted(
            items,
            key=lambda item: (
                SEVERITY_ORDER.get(item.get("severity"), 9),
                item.get("episode") or "",
                item.get("show") or "",
                item.get("issue_code") or "",
            ),
        )
    return grouped


def trust_counts(findings, key):
    counts = {}
    for item in findings or []:
        value = item.get(key) or "Unknown"
        counts[value] = counts.get(value, 0) + 1
    return counts


def build_trust_review(report, rules, completion_tracking=None):
    findings = trust_findings_from_issues(report.get("issues") or []) + trust_findings_from_issues(report.get("suppressed_issues") or [])
    grouped = group_trust_findings(findings)
    high_confidence = [
        item
        for item in findings
        if item.get("category") == "Confirmed Issue" and normalize_text(item.get("confidence")) == "high confidence"
    ]
    automation_candidates = [item for item in findings if item.get("future_automation_candidate") == "yes"]
    approval_required = [
        item
        for item in findings
        if item.get("automation_risk_level") in {"medium", "high"}
        or normalize_text(item.get("approval_required_before_action")) not in {"", "none"}
    ]
    return {
        "generated_at": report.get("generated_at"),
        "read_only": True,
        "overall_production_health": report.get("overall_production_health") or {},
        "summary": {
            "total_findings": len(findings),
            "counts_by_category": trust_counts(findings, "category"),
            "counts_by_dashboard_bucket": trust_counts(findings, "dashboard_bucket"),
            "future_automation_candidate_count": len(automation_candidates),
        },
        "completion_tracking": completion_tracking or {"summary": {"total_claims": 0, "counts_by_status": {}, "completed_today_count": 0}, "claims": [], "completed_today": []},
        "what_the_system_is_highly_confident_about": high_confidence,
        "what_needs_human_verification": grouped.get("Needs Verification", []) + grouped.get("Waiting on Client", []),
        "what_is_waiting_on_someone": grouped.get("Waiting on Guest", []) + grouped.get("Waiting on Internal Team", []),
        "waiting_on_guest_topics": grouped.get("Waiting on Guest Topics", []),
        "needs_guest_replacement": grouped.get("Needs Guest Replacement", []),
        "human_confirmed_active": grouped.get("Human Confirmed Active", []),
        "known_calendar_ownership_exceptions": grouped.get("Known Calendar Ownership Exception", []),
        "needs_human_follow_up": grouped.get("Needs Human Follow-Up", []),
        "known_exceptions": grouped.get("Known Exceptions", []),
        "known_context_from_config": trust_known_context(rules),
        "not_due_yet": grouped.get("Not Due Yet", []),
        "future_safe_actions": automation_candidates,
        "automation_candidates": automation_candidates,
        "approval_required_findings": approval_required,
        "automation_readiness": {
            "could_eventually_be_safe_after_approval": [
                "Adding a configured internal attendee to a matched Google Calendar event.",
                "Adding a known PR or assistant email captured from approved HighLevel fields.",
                "Adding a StreamYard link to a calendar description if the same link is already present in another approved event field.",
                "Updating a calendar description from approved SOP fields and verified HighLevel form values.",
            ],
            "requires_human_approval": [
                "Creating new calendar events.",
                "Emailing guests, PR people, clients, or internal team members.",
                "Changing guest-facing details such as title, timing, location, invite list, or instructions.",
                "Deleting, canceling, or replacing calendar events.",
                "Editing HighLevel appointment status or contact records.",
            ],
            "current_mode": "Read-only trust review. No automation is implemented.",
        },
    }


def difference_for_issue(item):
    code = item.get("code")
    details = item.get("details") or {}
    if code == "guest_email_not_invited":
        missing = ", ".join(details.get("missing_guest_emails") or [])
        return f"HighLevel lists active guest email(s), but these email(s) are absent from the Google Calendar attendee list: {missing}."
    if code == "active_guest_email_missing":
        missing = ", ".join(details.get("guests_missing_emails") or [])
        return f"HighLevel has active guest(s) but no usable guest email for invite verification: {missing}."
    if code == "title_missing_guest":
        missing = ", ".join(details.get("missing_guests") or [])
        return f"HighLevel lists active guest(s), but the Google Calendar title does not include: {missing}."
    if code == "guest_not_represented":
        missing = ", ".join(details.get("missing_guests") or [])
        return f"The guest is invited but not clearly named in the Google Calendar title or description: {missing}."
    if code == "required_attendee_not_invited":
        missing = ", ".join(details.get("missing_required_attendee_emails") or [])
        return f"Configured required attendee email(s) are absent from Google Calendar attendees: {missing}."
    if code == "pr_email_not_invited":
        missing = ", ".join(details.get("missing_pr_emails") or [])
        return f"HighLevel booking fields include PR/contact email(s), but Google Calendar attendees do not include: {missing}."
    if code == "sop_required_assets_missing":
        assets = ", ".join(item.get("asset") or "" for item in details.get("missing_assets") or [])
        return f"Google Calendar description/location does not satisfy configured SOP asset check(s): {assets}."
    if code == "required_custom_fields_missing_from_description":
        labels = ", ".join(item.get("field_label") or item.get("field_key") or "" for item in details.get("missing_fields") or [])
        return f"HighLevel form data includes required field value(s) that were not found in the Google Calendar description: {labels}."
    if code == "form_submission_not_exactly_linked":
        guests = ", ".join(details.get("guests") or [])
        return f"Discovery could not prove exact HighLevel form submission linkage for: {guests}."
    if code == "calendar_export_window_gap":
        coverage_time = details.get("coverage_time") or item.get("episode_time")
        time_min = details.get("calendar_export_time_min")
        time_max = details.get("calendar_export_time_max")
        return (
            "HighLevel has an active booking, but the loaded Google Calendar export does not cover "
            f"the expected event start ({coverage_time}). Export window: {time_min} to {time_max}."
        )
    if code == "booking_without_calendar_event":
        return "HighLevel has an active upcoming booking, but no matching Google Calendar event passed the configured matching threshold."
    if code == "calendar_event_without_booking":
        return "Google Calendar has a show-like event, but no active HighLevel booking matched it."
    if code == "linkedin_event_exists_calendar_needs_update":
        url = details.get("linkedin_event_url") or "a verified LinkedIn event URL"
        return f"A verified LinkedIn event already exists ({url}), but the Google Calendar event description/location does not include that URL yet."
    if code == "pr_representative_booking_guest_represented":
        contact = details.get("highlevel_submitter_contact") or "Unknown contact"
        guest = details.get("represented_guest") or "Unknown guest"
        evidence = ", ".join(details.get("represented_guest_evidence") or [])
        return f"HighLevel contact {contact} appears to be a submitter/PR representative, while the actual guest is {guest}. Evidence: {evidence or 'inferred from booking and calendar context'}."
    if code == "show_needs_guest_replacement":
        guest_status = details.get("guest_status") or "No confirmed active guest"
        highlevel_status = details.get("highlevel_status") or "Unknown HighLevel status"
        calendar_status = details.get("calendar_status") or "Unknown calendar status"
        return f"The upcoming show does not have a confirmed active guest. Guest status: {guest_status}. HighLevel: {highlevel_status}. Calendar: {calendar_status}."
    if code == "needs_human_follow_up":
        guest_status = details.get("guest_status") or "Guest status needs human follow-up"
        highlevel_status = details.get("highlevel_status") or "Unknown HighLevel status"
        calendar_status = details.get("calendar_status") or "Unknown calendar status"
        return f"Google Calendar and HighLevel disagree or are incomplete for this guest. Guest status: {guest_status}. HighLevel: {highlevel_status}. Calendar: {calendar_status}."
    if code == "duplicate_calendar_event":
        return "More than one Google Calendar event appears to match the same HighLevel episode slot."
    if code == "calendar_missing_preshow_block":
        return "The Google Calendar event is aligned to the live time but not the configured pre-show block."
    if code == "date_time_mismatch":
        return "The HighLevel episode time and Google Calendar event time differ outside the configured tolerance."
    if code == "calendar_end_time_mismatch":
        return "The Google Calendar event end time differs from the HighLevel booking window outside the configured tolerance."
    return item.get("message") or "The configured audit rule detected a difference that needs operator review."


def raw_id_summary(guests, event, item):
    appointment_ids = []
    contact_ids = []
    form_submission_ids = []
    possible_form_submission_ids = []
    for guest in guests or []:
        if guest.get("appointment_id") and guest["appointment_id"] not in appointment_ids:
            appointment_ids.append(guest["appointment_id"])
        if guest.get("contact_id") and guest["contact_id"] not in contact_ids:
            contact_ids.append(guest["contact_id"])
        for submission_id in guest.get("form_submission_ids") or []:
            if submission_id not in form_submission_ids:
                form_submission_ids.append(submission_id)
        for submission in guest.get("possible_form_submissions") or []:
            submission_id = submission.get("submission_id") if isinstance(submission, dict) else submission
            if submission_id and submission_id not in possible_form_submission_ids:
                possible_form_submission_ids.append(submission_id)
    return {
        "highlevel_appointment_ids": appointment_ids or item.get("appointment_ids") or [],
        "highlevel_contact_ids": contact_ids,
        "highlevel_form_submission_ids": form_submission_ids,
        "highlevel_possible_form_submission_ids": possible_form_submission_ids,
        "google_calendar_event_id": item.get("calendar_event_id") or (event.get("id") if event else None),
        "google_calendar_event_url": event.get("url") if event else None,
    }


def build_issue_evidence_panel(item, show_key, episode, guests, inactive_guests, event, duplicate_events, expected_calendar_start, expected_end, options):
    highlevel_evidence = {
        "show_key": show_key,
        "episode_date_time": episode.get("episode_date_time") if episode else item.get("episode_time"),
        "expected_calendar_start": expected_calendar_start.isoformat() if expected_calendar_start else None,
        "expected_calendar_end": expected_end.isoformat() if expected_end else None,
        "active_guests": [highlevel_guest_summary(guest) for guest in guests or []],
        "inactive_or_non_actionable_guests_ignored": [highlevel_guest_summary(guest) for guest in inactive_guests or []],
    }
    google_evidence = calendar_event_summary(event)
    if item.get("code") == "calendar_export_window_gap":
        google_evidence["calendar_export_window"] = options.get("calendar_export_window") or {}
    if duplicate_events:
        google_evidence["duplicate_event_ids"] = [item.get("id") for item in duplicate_events if item.get("id")]
    raw_ids = raw_id_summary(guests, event, item)
    source_json_files = discovery_source_refs(show_key, options["discovery_dir"]) if show_key and show_key != "unknown" else []
    source_json_files.append(calendar_source_ref(options["calendar_events_path"]))
    panel = {
        "issue_code": item.get("code"),
        "severity": item.get("severity"),
        "episode_date_time": item.get("episode_time"),
        "guests": guest_names(guests),
        "recommended_action": item.get("recommended_action"),
        "confidence": item.get("confidence"),
        "evidence_from_highlevel": highlevel_evidence,
        "evidence_from_google_calendar": google_evidence,
        "difference_detected": difference_for_issue(item),
        "relevant_raw_ids": raw_ids,
        "why_this_matters_operationally": issue_operational_impact(options["rules"], item.get("code")),
        "source_json_files": source_json_files,
    }
    item["evidence_panel"] = panel
    item["evidence_from_highlevel"] = panel["evidence_from_highlevel"]
    item["evidence_from_google_calendar"] = panel["evidence_from_google_calendar"]
    item["difference_detected"] = panel["difference_detected"]
    item["relevant_raw_ids"] = panel["relevant_raw_ids"]
    item["why_this_matters_operationally"] = panel["why_this_matters_operationally"]
    return item


def attach_issue_evidence(issues, show_key, episode, guests, inactive_guests, event, duplicate_events, expected_calendar_start, expected_end, options):
    for item in issues:
        build_issue_evidence_panel(
            item,
            show_key,
            episode,
            guests,
            inactive_guests,
            event,
            duplicate_events,
            expected_calendar_start,
            expected_end,
            options,
        )
    return issues


def issue_guest_tokens(item):
    panel = item.get("evidence_panel") or {}
    tokens = set()
    for guest in panel.get("evidence_from_highlevel", {}).get("active_guests", []):
        if guest.get("name"):
            tokens.add(normalize_text(guest["name"]))
        if guest.get("email"):
            tokens.add(normalize_email(guest["email"]))
    for detail_key in (
        "missing_guests",
        "guests",
        "missing_guest_emails",
        "guests_missing_emails",
        "missing_pr_emails",
        "calendar_guest",
        "guest_name",
        "replacement_guest",
        "canceled_or_rescheduled_guest",
        "represented_guest",
        "highlevel_submitter_contact",
    ):
        value = (item.get("details") or {}).get(detail_key)
        if isinstance(value, list):
            for entry in value:
                tokens.add(normalize_email(entry) if "@" in str(entry) else normalize_text(entry))
        elif value:
            tokens.add(normalize_email(value) if "@" in str(value) else normalize_text(value))
    return {token for token in tokens if token}


def suppression_expired(rule, now):
    expires_on = rule.get("expires_on") or rule.get("expiration_date")
    if not expires_on:
        return False
    expiration_key = date_key(expires_on)
    current_key = now.date().isoformat()
    return bool(expiration_key and expiration_key < current_key)


def suppression_matches(rule, item, now):
    if rule.get("enabled") is False:
        return False
    if suppression_expired(rule, now):
        return False
    issue_code = rule.get("issue_code")
    if issue_code and issue_code != "*" and issue_code != item.get("code"):
        return False
    show_key = rule.get("show_key")
    if show_key and show_key != "*" and show_key != item.get("show_key"):
        return False
    episode_date = rule.get("episode_date") or rule.get("episode_time")
    if episode_date and date_key(episode_date) != date_key(item.get("episode_time")):
        return False
    calendar_event_id = rule.get("calendar_event_id")
    if calendar_event_id and calendar_event_id != item.get("calendar_event_id"):
        return False
    appointment_id = rule.get("appointment_id")
    if appointment_id and appointment_id not in (item.get("appointment_ids") or []):
        return False
    guest_name = normalize_text(rule.get("guest_name"))
    guest_email = normalize_email(rule.get("guest_email"))
    if guest_name or guest_email:
        tokens = issue_guest_tokens(item)
        if guest_name and guest_name not in tokens:
            return False
        if guest_email and guest_email not in tokens:
            return False
    return True


def rule_text_contains(value, needle):
    if not needle:
        return True
    return normalize_text(needle) in normalize_text(value)


def rule_matches_event(rule, event, now=None):
    if rule.get("enabled") is False:
        return False
    if now and suppression_expired(rule, now):
        return False
    calendar_event_id = rule.get("calendar_event_id")
    if calendar_event_id and calendar_event_id != event.get("id"):
        return False
    episode_date = rule.get("episode_date") or rule.get("episode_time")
    if episode_date and date_key(episode_date) != date_key(event.get("start")):
        return False
    title_contains = rule.get("calendar_title_contains") or rule.get("title_contains")
    if title_contains and not rule_text_contains(event.get("title"), title_contains):
        return False
    full_text_contains = rule.get("event_text_contains")
    if full_text_contains and not rule_text_contains(event_full_text(event), full_text_contains):
        return False
    return True


def rule_matches_episode(rule, show_key, episode, event=None, now=None):
    if rule.get("enabled") is False:
        return False
    if now and suppression_expired(rule, now):
        return False
    configured_show_key = rule.get("show_key")
    if configured_show_key and configured_show_key != "*" and configured_show_key != show_key:
        return False
    episode_date = rule.get("episode_date") or rule.get("episode_time")
    if episode_date and date_key(episode_date) != date_key(episode.get("episode_date_time")):
        return False
    calendar_event_id = rule.get("calendar_event_id")
    if calendar_event_id and (not event or calendar_event_id != event.get("id")):
        return False
    title_contains = rule.get("calendar_title_contains") or rule.get("title_contains")
    if title_contains and (not event or not rule_text_contains(event.get("title"), title_contains)):
        return False
    guest_name = normalize_text(rule.get("guest_name"))
    guest_email = normalize_email(rule.get("guest_email"))
    if guest_name or guest_email:
        guest_tokens = set()
        for guest in episode.get("guests") or []:
            if guest.get("name"):
                guest_tokens.add(normalize_text(guest.get("name")))
            if guest.get("email"):
                guest_tokens.add(normalize_email(guest.get("email")))
        if guest_name and guest_name not in guest_tokens:
            return False
        if guest_email and guest_email not in guest_tokens:
            return False
    return True


def apply_manual_issue_overrides(issues, rules, now):
    for item in issues:
        for configured_rule in manual_issue_overrides(rules):
            if suppression_matches(configured_rule, item, now):
                item["manual_override"] = {
                    "reason": configured_rule.get("reason") or "Adjusted by configured manual review rule.",
                    "rule": {
                        key: configured_rule.get(key)
                        for key in (
                            "show_key",
                            "episode_date",
                            "calendar_event_id",
                            "issue_code",
                            "reason",
                        )
                        if configured_rule.get(key) not in (None, "")
                    },
                }
                if configured_rule.get("new_issue_code"):
                    item["code"] = configured_rule["new_issue_code"]
                for key in ("severity", "message", "recommended_action", "confidence", "reason", "explanation"):
                    if configured_rule.get(key):
                        item[key] = configured_rule[key]
                details_update = configured_rule.get("details")
                if isinstance(details_update, dict):
                    details = item.get("details") or {}
                    item["details"] = {**details, **details_update}
                    item["evidence"] = item["details"]
                break
    return issues


def configured_manual_issue(rule, show_key, show_name, episode_time, calendar_event_id=None, appointment_ids=None):
    return issue(
        severity=rule.get("severity") or "Warning",
        code=rule.get("issue_code") or "manual_review_required",
        show_key=rule.get("show_key") or show_key,
        show_name=rule.get("show_name") or show_name or show_key,
        episode_time=episode_time,
        calendar_event_id=calendar_event_id,
        appointment_ids=appointment_ids or [],
        message=rule.get("message") or "Manual operator review is required for this episode.",
        recommended_action=rule.get("recommended_action") or "Review this item manually before making any external changes.",
        details=rule.get("details") if isinstance(rule.get("details"), dict) else {},
        confidence=rule.get("confidence") or "medium",
    )


def apply_suppression_rules(issues, rules, now):
    active = []
    suppressed = []
    configured_rules = suppression_rules(rules)
    for item in issues:
        matched_rule = None
        for rule in configured_rules:
            if suppression_matches(rule, item, now):
                matched_rule = rule
                break
        if matched_rule:
            item["suppressed"] = True
            item["suppression"] = {
                "reason": matched_rule.get("reason") or "Suppressed by configured known exception.",
                "expires_on": matched_rule.get("expires_on") or matched_rule.get("expiration_date"),
                "configured_rule": {
                    key: matched_rule.get(key)
                    for key in (
                        "show_key",
                        "episode_date",
                        "guest_name",
                        "guest_email",
                        "issue_code",
                        "reason",
                        "expires_on",
                    )
                    if matched_rule.get(key) not in (None, "")
                },
            }
            suppressed.append(item)
        else:
            item["suppressed"] = False
            active.append(item)
    return active, suppressed


def audit_title_and_guest_representation(show_key, episode, guests, event, issues):
    title_text = normalize_text(event.get("title", ""))
    calendar_detail_text = normalize_text(" ".join([event.get("title", ""), event.get("description", ""), event.get("location", "")]))
    attendee_emails = attendee_email_set(event)
    show_name = episode.get("show_name") or show_key
    appointment_ids = active_appointment_ids(episode, guests)
    if normalize_text(show_name) not in title_text:
        issues.append(
            issue(
                severity="Warning",
                code="title_missing_show_name",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message=f"Calendar title does not clearly include the show name: {event.get('title')}",
                recommended_action="Review the event title and rename it to the standard show naming format.",
            )
        )
    title_missing_guests = []
    represented_missing_guests = []
    for guest in guests:
        guest_name = display_guest_name(guest)
        guest_email = display_guest_email(guest)
        if not contains_person(title_text, guest_name, guest_email):
            title_missing_guests.append(guest_name or guest_email)
        guest_is_invited = bool(guest_email and guest_email in attendee_emails)
        if guest_is_invited and not contains_person(calendar_detail_text, guest_name, guest_email):
            represented_missing_guests.append(guest_name or guest_email)
    if title_missing_guests:
        issues.append(
            issue(
                severity="Warning",
                code="title_missing_guest",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message=f"Calendar title is missing active guest(s): {', '.join(title_missing_guests)}",
                recommended_action="Update the calendar title so every active guest is represented.",
                details={"missing_guests": title_missing_guests},
            )
        )
    if represented_missing_guests:
        issues.append(
            issue(
                severity="Warning",
                code="guest_not_represented",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message=f"Invited guest(s) are missing from the calendar title/description details: {', '.join(represented_missing_guests)}",
                recommended_action="Add the missing guest name(s) to the calendar title or description after human review.",
                details={"missing_guests": represented_missing_guests},
            )
        )


def audit_time(show_key, episode, guests, event, expected_calendar_start, live_start, expected_end, tolerance_minutes, issues, rules):
    show_name = episode.get("show_name") or show_key
    appointment_ids = active_appointment_ids(episode, guests)
    preshow_diff = minutes_between(event.get("start"), expected_calendar_start)
    live_diff = minutes_between(event.get("start"), live_start)
    if preshow_diff is None:
        issues.append(
            issue(
                severity="Critical",
                code="calendar_event_missing_start",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message="Calendar event has no readable start time.",
                recommended_action="Open the event and verify the start time manually.",
            )
        )
        return
    if preshow_diff > tolerance_minutes:
        severity = "Warning" if live_diff is not None and live_diff <= tolerance_minutes else "Critical"
        code = "calendar_missing_preshow_block" if severity == "Warning" else "date_time_mismatch"
        if code == "calendar_missing_preshow_block" and preshow_instruction_satisfied(show_key, event, rules):
            severity = None
        if severity is not None:
            expected = expected_calendar_start.isoformat()
            actual = event["start"].isoformat()
            issues.append(
                issue(
                    severity=severity,
                    code=code,
                    show_key=show_key,
                    show_name=show_name,
                    episode_time=episode.get("episode_date_time"),
                    calendar_event_id=event.get("id"),
                    appointment_ids=appointment_ids,
                    message=f"Calendar event starts at {actual}; expected pre-show start is {expected}.",
                    recommended_action="Review the ww@reveting.com event time and align it with the SOP pre-show/live schedule.",
                    details={"expected_calendar_start": expected, "actual_calendar_start": actual},
                )
            )
    if expected_end and event.get("end"):
        end_diff = minutes_between(event["end"], expected_end)
        if end_diff is not None and end_diff > tolerance_minutes:
            issues.append(
                issue(
                    severity="Warning",
                    code="calendar_end_time_mismatch",
                    show_key=show_key,
                    show_name=show_name,
                    episode_time=episode.get("episode_date_time"),
                    calendar_event_id=event.get("id"),
                    appointment_ids=appointment_ids,
                    message=f"Calendar event end time differs from HighLevel by about {round(end_diff)} minutes.",
                    recommended_action="Review the event duration and ensure it reserves the intended live-show window.",
                    details={
                        "expected_end": expected_end.isoformat(),
                        "actual_end": event["end"].isoformat(),
                    },
                )
            )


def audit_attendees(show_key, episode, guests, event, issues, rules):
    show_name = episode.get("show_name") or show_key
    appointment_ids = active_appointment_ids(episode, guests)
    if not event.get("attendee_list_available"):
        issues.append(
            issue(
                severity="Warning",
                code="attendee_list_unavailable",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message="Calendar export does not include attendee data, so guest/PR invitations cannot be verified.",
                recommended_action="Re-export/read the event with full Google Calendar details including attendees.",
            )
        )
        return

    attendee_emails = set(event.get("attendee_emails") or [])
    missing_guest_emails = []
    guests_missing_emails = []
    missing_pr_emails = []
    assistant_emails_present = []
    for guest in guests:
        guest_email = display_guest_email(guest)
        submitter_email = normalize_email(guest.get("contact_email") or guest.get("email"))
        represented_high = normalize_text(guest.get("represented_guest_confidence")) == "high"
        if not guest_email:
            if not represented_high:
                guests_missing_emails.append(display_guest_name(guest) or guest.get("appointment_id") or "Unknown guest")
        elif guest_email not in attendee_emails:
            missing_guest_emails.append(guest_email)
        if represented_high and submitter_email and submitter_email != guest_email and submitter_email not in attendee_emails:
            missing_pr_emails.append(submitter_email)
        for email in guest.get("pr_emails") or []:
            if email and email not in attendee_emails:
                missing_pr_emails.append(email)
        known_assistant_emails = set(guest.get("assistant_emails") or [])
        known_assistant_emails.update(email for email in guest.get("alternate_invite_emails") or [])
        for email in sorted(known_assistant_emails):
            if email in attendee_emails:
                assistant_emails_present.append(email)

    inferred_assistant_emails = [
        email
        for email in attendee_emails
        if any(signal in email for signal in ("assistant", "scheduler", "coordinator"))
    ]
    assistant_emails_present.extend(inferred_assistant_emails)
    assistant_emails_present = sorted(set(assistant_emails_present))

    if missing_guest_emails:
        issues.append(
            issue(
                severity="Critical",
                code="guest_email_not_invited",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message=f"Guest email(s) are not invited: {', '.join(sorted(set(missing_guest_emails)))}",
                recommended_action="Add the missing active guest email(s) to the Google Calendar invite after human review.",
                details={"missing_guest_emails": sorted(set(missing_guest_emails))},
            )
        )
    if guests_missing_emails:
        issues.append(
            issue(
                severity="Critical",
                code="active_guest_email_missing",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message=f"Active guest(s) have no email address available for invite verification: {', '.join(guests_missing_emails)}",
                recommended_action="Review the HighLevel booking/contact record and confirm the correct guest invite email manually.",
                details={"guests_missing_emails": guests_missing_emails},
            )
        )
    if missing_pr_emails:
        issues.append(
            issue(
                severity="Warning",
                code="pr_email_not_invited",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message=f"PR/contact email(s) appear in booking data but are not invited: {', '.join(sorted(set(missing_pr_emails)))}",
                recommended_action="Confirm whether each PR/contact should be included, then add the approved email(s) manually.",
                details={"missing_pr_emails": sorted(set(missing_pr_emails))},
            )
        )
    required_attendees = set(normalize_email(email) for email in rule_list(rules, "required_attendee_emails"))
    required_attendees.update(normalize_email(email) for email in show_rule(rules, show_key).get("required_attendee_emails", []))
    missing_required_attendees = sorted(email for email in required_attendees if email and email not in attendee_emails)
    if missing_required_attendees:
        issues.append(
            issue(
                severity="Warning",
                code="required_attendee_not_invited",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message=f"Required operations attendee(s) are not invited: {', '.join(missing_required_attendees)}",
                recommended_action="Review the configured required attendee list and manually add any missing required recipients if appropriate.",
                details={"missing_required_attendee_emails": missing_required_attendees},
            )
        )
    if assistant_emails_present:
        issues.append(
            issue(
                severity="Informational",
                code="assistant_email_present",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message=f"Assistant/alternate email(s) are present on the invite: {', '.join(assistant_emails_present)}",
                recommended_action="No automatic action. Confirm these attendees are intended for the episode.",
                details={"assistant_emails": assistant_emails_present},
            )
        )


def audit_required_fields(show_key, episode, guests, event, issues):
    show_name = episode.get("show_name") or show_key
    appointment_ids = active_appointment_ids(episode, guests)
    description = event.get("description") or ""
    missing = []
    unlinked_guests = []
    for guest in guests:
        if not guest.get("form_submission_ids"):
            unlinked_guests.append(display_guest_name(guest) or display_guest_email(guest))
        for field in guest.get("required_fields") or []:
            if not field_value_present_in_description(field, description):
                missing.append(
                    {
                        "guest": display_guest_name(guest) or display_guest_email(guest),
                        "field_label": field.get("field_label"),
                        "field_key": field.get("field_key_or_name"),
                    }
                )
    if missing:
        labels = []
        for item in missing:
            label = f"{item['guest']}: {item['field_label']}"
            if label not in labels:
                labels.append(label)
        issues.append(
            issue(
                severity="Warning",
                code="required_custom_fields_missing_from_description",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message=f"Required booking field(s) are missing from the calendar description: {', '.join(labels[:8])}",
                recommended_action="Compare the original HighLevel form submission with the calendar description and add missing required fields manually.",
                details={"missing_fields": missing},
            )
        )
    if unlinked_guests:
        issues.append(
            issue(
                severity="Informational",
                code="form_submission_not_exactly_linked",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message=f"Exact form submission linkage is unavailable for: {', '.join(unlinked_guests)}",
                recommended_action="Review possible related submissions before making any calendar-description changes.",
                details={"guests": unlinked_guests},
            )
        )


def rule_applies_within_days(rule, expected_calendar_start, now):
    within_days = rule.get("within_days")
    if within_days is None:
        return True
    if not expected_calendar_start:
        return False
    days_until = (expected_calendar_start.astimezone(timezone.utc) - now.astimezone(timezone.utc)).days
    return days_until <= int(within_days)


def missing_text_rule(rule, description, location, normalized_text, raw_text, expected_calendar_start, now):
    if not rule_applies_within_days(rule, expected_calendar_start, now):
        return None
    if rule.get("type") == "description_present" and not description.strip():
        return "Calendar description is empty."
    any_terms = [normalize_text(term) for term in rule.get("any_terms", [])]
    if any_terms and not any(term in normalized_text for term in any_terms):
        return f"None of these required terms were found: {', '.join(rule.get('any_terms', []))}."
    all_terms = [normalize_text(term) for term in rule.get("all_terms", [])]
    if all_terms and not all(term in normalized_text for term in all_terms):
        return f"Not all required terms were found: {', '.join(rule.get('all_terms', []))}."
    any_raw_terms = [str(term).lower() for term in rule.get("any_raw_terms", [])]
    if any_raw_terms and not any(term in raw_text for term in any_raw_terms):
        return f"None of these required raw terms were found: {', '.join(rule.get('any_raw_terms', []))}."
    forbid_raw_terms = [str(term).lower() for term in rule.get("forbid_raw_terms", [])]
    if forbid_raw_terms and any(term in raw_text for term in forbid_raw_terms):
        return f"One or more placeholder terms are still present: {', '.join(rule.get('forbid_raw_terms', []))}."
    return None


def audit_sop_assets(show_key, episode, guests, event, expected_calendar_start, now, issues, rules):
    show_name = episode.get("show_name") or show_key
    appointment_ids = active_appointment_ids(episode, guests)
    description = event.get("description") or ""
    location = event.get("location") or ""
    normalized_text = normalize_text(" ".join([description, location]))
    raw_text = f"{description}\n{location}".lower()
    asset_checks = []
    configured_rules = []
    configured_rules.extend(rule_list(rules, "calendar_description_sections"))
    configured_rules.extend(rule_list(rules, "sop_assets"))
    show_config = show_rule(rules, show_key)
    configured_rules.extend(item for item in show_config.get("calendar_description_sections", []) if isinstance(item, dict))
    configured_rules.extend(item for item in show_config.get("sop_assets", []) if isinstance(item, dict))
    known_linkedin = known_linkedin_event_record(
        show_key,
        episode.get("episode_date_time"),
        guests,
        rules.get("_loaded_knowledge") if isinstance(rules.get("_loaded_knowledge"), dict) else {},
    )
    for configured_rule in configured_rules:
        if not isinstance(configured_rule, dict):
            continue
        reason = missing_text_rule(
            configured_rule,
            description,
            location,
            normalized_text,
            raw_text,
            expected_calendar_start,
            now,
        )
        if reason:
            asset_label = configured_rule.get("label") or configured_rule.get("key") or "Configured asset"
            if known_linkedin and "linkedin" in normalize_text(asset_label):
                continue
            asset_checks.append((asset_label, reason))

    if asset_checks:
        issues.append(
            issue(
                severity="Warning",
                code="sop_required_assets_missing",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message="SOP-required calendar asset(s) appear incomplete: "
                + ", ".join(item[0] for item in asset_checks),
                recommended_action="Review the SOP calendar-description checklist and update the event manually if the missing asset is truly absent.",
                details={"missing_assets": [{"asset": item[0], "reason": item[1]} for item in asset_checks]},
            )
        )
    if known_linkedin and not extract_linkedin_urls(calendar_text_for_brief(event)):
        issues.append(
            issue(
                severity="Warning",
                code="linkedin_event_exists_calendar_needs_update",
                show_key=show_key,
                show_name=show_name,
                episode_time=episode.get("episode_date_time"),
                calendar_event_id=event.get("id"),
                appointment_ids=appointment_ids,
                message="A verified LinkedIn event exists, but the Google Calendar event still needs the LinkedIn URL added.",
                recommended_action="Add the verified LinkedIn event URL to the Google Calendar description after review, then send or schedule the SOP emails that depend on the event link.",
                details={
                    "guest_name": known_linkedin.get("guest_name"),
                    "linkedin_event_url": known_linkedin.get("linkedin_event_url"),
                    "source": known_linkedin.get("source"),
                    "verified_by": known_linkedin.get("verified_by"),
                    "verified_at": known_linkedin.get("verified_at"),
                    "notes": known_linkedin.get("notes"),
                    "calendar_needs_update": True,
                },
                confidence="high",
            )
        )


def add_manual_episode_issues(show_key, episode, event, guests, issues, rules, now):
    show_name = episode.get("show_name") or show_key
    appointment_ids = active_appointment_ids(episode, guests)
    for configured_rule in manual_episode_issues(rules):
        if not isinstance(configured_rule, dict):
            continue
        if not rule_matches_episode(configured_rule, show_key, episode, event, now):
            continue
        issues.append(
            configured_manual_issue(
                configured_rule,
                show_key,
                show_name,
                episode.get("episode_date_time"),
                calendar_event_id=event.get("id") if event else None,
                appointment_ids=appointment_ids,
            )
        )


def expected_episode_end(guests, live_start, duration_minutes=60):
    ends = []
    for guest in guests:
        appointment = guest.get("appointment") or {}
        end = parse_datetime(appointment.get("end_time"))
        if end:
            ends.append(end)
    if ends:
        return max(ends)
    return live_start + timedelta(minutes=int(duration_minutes or 60))


def show_int_option(rules, show_key, key, default):
    value = show_rule(rules, show_key).get(key)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def merged_preshow_validation_rule(rules, show_key):
    merged = rule_section(rules, "preshow_validation")
    show_config = show_rule(rules, show_key).get("preshow_validation")
    if isinstance(show_config, dict):
        merged = {**merged, **show_config}
    return merged


def preshow_instruction_satisfied(show_key, event, rules):
    validation = merged_preshow_validation_rule(rules, show_key)
    mode = validation.get("mode") or "calendar_start_required"
    if mode == "calendar_start_required":
        return False
    normalized_text = event_full_text(event)
    raw_text = "\n".join(
        str(value or "")
        for value in (
            event.get("title"),
            event.get("description"),
            event.get("location"),
        )
    ).lower()
    all_terms = [normalize_text(term) for term in validation.get("instruction_all_terms", []) if term]
    if all_terms and not all(term in normalized_text for term in all_terms):
        return False
    any_terms = [normalize_text(term) for term in validation.get("instruction_any_terms", []) if term]
    if any_terms and not any(term in normalized_text for term in any_terms):
        return False
    any_raw_terms = [str(term).lower() for term in validation.get("instruction_any_raw_terms", []) if term]
    if any_raw_terms and not any(term in raw_text for term in any_raw_terms):
        return False
    return mode in {"calendar_start_or_description_instruction", "description_instruction_allowed"}


def health_rules(rules):
    return rule_dict(rules, "health_score", FALLBACK_HEALTH_SCORE_RULES)


def health_label(score, rules):
    labels = health_rules(rules).get("labels") or FALLBACK_HEALTH_SCORE_RULES["labels"]
    for item in sorted(labels, key=lambda value: value.get("min", 0), reverse=True):
        if score >= item.get("min", 0):
            return item.get("label") or "Unknown"
    return "Unknown"


def production_health(issues, rules):
    scoring = health_rules(rules)
    base = int(scoring.get("base", 100))
    minimum = int(scoring.get("minimum", 0))
    by_severity = scoring.get("deductions_by_severity") or FALLBACK_HEALTH_SCORE_RULES["deductions_by_severity"]
    by_code = scoring.get("deductions_by_issue_code") or {}
    score = base
    deductions = []
    for item in issues:
        effective_severity = effective_issue_severity(item)
        if item.get("stage_adjusted_severity") and item.get("stage_adjusted_severity") != item.get("severity"):
            points = int(by_severity.get(effective_severity, 0))
        else:
            points = int(by_code.get(item.get("code"), by_severity.get(effective_severity, 0)))
        if points <= 0:
            continue
        score -= points
        deductions.append(
            {
                "issue_code": item.get("code"),
                "severity": effective_severity,
                "base_severity": item.get("base_severity") or item.get("severity"),
                "points_lost": points,
                "reason": item.get("reason") or item.get("message"),
                "evidence": item.get("evidence") or {},
            }
        )
    score = max(minimum, min(base, score))
    return {
        "score": score,
        "label": health_label(score, rules),
        "deductions": deductions,
    }


def aggregate_health(episode_health_items, rules):
    if not episode_health_items:
        return {
            "score": None,
            "label": "No upcoming episodes audited",
            "deductions": [],
        }
    score = round(sum(item["score"] for item in episode_health_items) / len(episode_health_items), 1)
    deductions = []
    for item in episode_health_items:
        deductions.extend(item.get("deductions") or [])
    return {
        "score": score,
        "label": health_label(score, rules),
        "deductions": deductions[:25],
    }


def audit_episode(show_key, episode, appointments_by_id, submissions_by_id, custom_field_map_by_id, calendar_events, options):
    now = options["now"]
    rules = options["rules"]
    preshow_minutes = show_int_option(rules, show_key, "preshow_offset_minutes", options["preshow_minutes"])
    tolerance_minutes = show_int_option(rules, show_key, "time_tolerance_minutes", options["tolerance_minutes"])
    match_threshold = show_int_option(rules, show_key, "calendar_match_threshold", options["match_threshold"])
    duration_minutes = show_int_option(rules, show_key, "episode_duration_minutes", 60)
    issues = []
    live_start = parse_datetime(episode.get("episode_date_time"))
    if not live_start:
        return None
    if not options["include_past"] and live_start < now:
        return None
    if options["days_ahead"] is not None and live_start > now + timedelta(days=options["days_ahead"]):
        return None

    guests, inactive_guests = active_episode_guests(show_key, episode, appointments_by_id, submissions_by_id, rules, custom_field_map_by_id)
    if not guests:
        return None

    expected_calendar_start = live_start - timedelta(minutes=preshow_minutes)
    expected_end = expected_episode_end(guests, live_start, duration_minutes)
    active_ids = active_appointment_ids(episode, guests)
    matched_event, duplicate_events = find_calendar_match(
        calendar_events,
        episode,
        guests,
        expected_calendar_start,
        live_start,
        tolerance_minutes,
        match_threshold,
    )
    matched_event_ids = []

    if not matched_event:
        export_gap = calendar_export_gap_for_time(expected_calendar_start, options)
        if export_gap:
            coverage_rules = calendar_export_window_rules(rules)
            issues.append(
                issue(
                    severity=coverage_rules.get("severity") or "Warning",
                    code=coverage_rules.get("issue_code") or "calendar_export_window_gap",
                    show_key=show_key,
                    show_name=episode.get("show_name") or show_key,
                    episode_time=episode.get("episode_date_time"),
                    appointment_ids=active_ids,
                    message="HighLevel has an active booking outside the loaded Google Calendar export window.",
                    recommended_action=coverage_rules.get("recommended_action")
                    or "Extend the Google Calendar export window to include this episode, rerun the export, then rerun the audit.",
                    details={
                        "guest_names": [guest.get("name") for guest in guests],
                        **export_gap,
                    },
                )
            )
        else:
            issues.append(
                issue(
                    severity="Critical",
                    code="booking_without_calendar_event",
                    show_key=show_key,
                    show_name=episode.get("show_name") or show_key,
                    episode_time=episode.get("episode_date_time"),
                    appointment_ids=active_ids,
                    message="HighLevel has an active upcoming booking/episode with no matching ww@reveting.com calendar event.",
                    recommended_action="Manually inspect ww@reveting.com for this episode and create/escalate the missing event according to SOP.",
                    details={"guest_names": [guest.get("name") for guest in guests]},
                )
            )
    else:
        guests = apply_represented_guest_inference(guests, episode.get("show_name") or show_key, matched_event)
        for guest in guests:
            if guest.get("contact_is_submitter_rep") and guest.get("represented_guest_name"):
                issues.append(
                    represented_guest_issue(
                        show_key,
                        episode.get("show_name") or show_key,
                        episode.get("episode_date_time"),
                        matched_event,
                        guest,
                        active_ids,
                        confidence=guest.get("represented_guest_confidence"),
                    )
                )
        matched_event_ids.append(matched_event.get("id"))
        if len(duplicate_events) > 1:
            matched_event_ids.extend(event.get("id") for event in duplicate_events if event.get("id"))
            issues.append(
                issue(
                    severity="Critical",
                    code="duplicate_calendar_event",
                    show_key=show_key,
                    show_name=episode.get("show_name") or show_key,
                    episode_time=episode.get("episode_date_time"),
                    calendar_event_id=matched_event.get("id"),
                    appointment_ids=active_ids,
                    message=f"Multiple matching calendar events found for the same episode slot: {len(duplicate_events)}",
                    recommended_action="Review duplicate ww@reveting.com events and decide which single event should remain authoritative.",
                    details={"calendar_event_ids": [event.get("id") for event in duplicate_events]},
                )
            )
        audit_time(show_key, episode, guests, matched_event, expected_calendar_start, live_start, expected_end, tolerance_minutes, issues, rules)
        audit_title_and_guest_representation(show_key, episode, guests, matched_event, issues)
        audit_attendees(show_key, episode, guests, matched_event, issues, rules)
        audit_required_fields(show_key, episode, guests, matched_event, issues)
        audit_sop_assets(show_key, episode, guests, matched_event, expected_calendar_start, now, issues, rules)

    add_manual_episode_issues(show_key, episode, matched_event, guests, issues, rules, now)
    apply_manual_issue_overrides(issues, rules, now)
    apply_metadata_to_issues(issues, rules)
    attach_issue_evidence(
        issues,
        show_key,
        episode,
        guests,
        inactive_guests,
        matched_event,
        duplicate_events,
        expected_calendar_start,
        expected_end,
        options,
    )
    active_issues, suppressed_issues = apply_suppression_rules(issues, rules, now)
    active_issues, suppressed_issues = apply_knowledge_to_issue_sets(
        active_issues,
        suppressed_issues,
        options.get("knowledge") or {},
        now,
    )
    health = production_health(active_issues, rules)

    return {
        "show_key": show_key,
        "show_name": episode.get("show_name") or show_key,
        "episode_time": episode.get("episode_date_time"),
        "expected_calendar_start": expected_calendar_start.isoformat(),
        "expected_calendar_end": expected_end.isoformat() if expected_end else None,
        "appointment_ids": active_ids,
        "guest_count": len(guests),
        "unique_guest_count": unique_guest_count(guests),
        "pairing": episode_pairing_summary(show_key, episode, guests, matched_event, rules),
        "active_guests": [
            {
                "name": display_guest_name(guest),
                "email": display_guest_email(guest),
                "contact_name": guest.get("contact_name") or guest.get("name"),
                "contact_email": guest.get("contact_email") or guest.get("email"),
                "appointment_id": guest.get("appointment_id"),
                "status": guest.get("status"),
                "represented_guest_name": guest.get("represented_guest_name"),
                "represented_guest_email": guest.get("represented_guest_email"),
                "represented_guest_confidence": guest.get("represented_guest_confidence"),
                "represented_guest_evidence": guest.get("represented_guest_evidence") or [],
                "form_submission_ids": guest.get("form_submission_ids") or [],
                "possible_form_submissions": guest.get("possible_form_submissions") or [],
                "pr_emails": guest.get("pr_emails"),
                "assistant_emails": guest.get("assistant_emails"),
                "alternate_invite_emails": guest.get("alternate_invite_emails"),
            }
            for guest in guests
        ],
        "inactive_guests_ignored": [
            {
                "name": guest.get("name"),
                "email": guest.get("email"),
                "appointment_id": guest.get("appointment_id"),
                "status": guest.get("status"),
            }
            for guest in inactive_guests
        ],
        "calendar_event_found": matched_event is not None,
        "calendar_event_id": matched_event.get("id") if matched_event else None,
        "calendar_event_url": matched_event.get("url") if matched_event else None,
        "calendar_event_title": matched_event.get("title") if matched_event else None,
        "production_health": health,
        "issues": active_issues,
        "suppressed_issues": suppressed_issues,
        "matched_calendar_event_ids": sorted(set(item for item in matched_event_ids if item)),
    }


def infer_pr_rep_booking_for_event(event, show_name, options):
    show_contexts = options.get("show_contexts") or {}
    target_date = date_key(event.get("start"))
    for show_key, context in show_contexts.items():
        if configured_show_name(options["rules"], show_key) != show_name:
            continue
        episodes = context.get("episodes") or []
        appointments_by_id = context.get("appointments_by_id") or {}
        submissions_by_id = context.get("submissions_by_id") or {}
        custom_field_map_by_id = context.get("custom_field_map_by_id") or {}
        for episode in episodes:
            if date_key(episode.get("episode_date_time")) != target_date:
                continue
            guests = [
                enrich_guest(guest, appointments_by_id, submissions_by_id, options["rules"], show_key, custom_field_map_by_id)
                for guest in (episode.get("guests") or [])
            ]
            guests = apply_represented_guest_inference(guests, show_name, event)
            for guest in guests:
                if not guest.get("contact_is_submitter_rep") or not guest.get("represented_guest_name"):
                    continue
                return represented_guest_issue(
                    show_key,
                    show_name,
                    event.get("start").isoformat() if event.get("start") else None,
                    event,
                    guest,
                    [guest.get("appointment_id")] if guest.get("appointment_id") else [],
                    confidence=guest.get("represented_guest_confidence"),
                )
    return None


def find_calendar_events_without_bookings(calendar_events, audited_episodes, show_names, options):
    matched_event_ids = {
        event_id
        for episode in audited_episodes
        for event_id in episode.get("matched_calendar_event_ids", [])
        if event_id
    }
    issues = []
    now = options["now"]
    max_time = now + timedelta(days=options["days_ahead"] or DEFAULT_DAYS_AHEAD)
    manually_classified_event_ids = set()
    for configured_rule in manual_calendar_event_issues(options["rules"]):
        if not isinstance(configured_rule, dict):
            continue
        for event in calendar_events:
            event_start = event.get("start")
            if not event_start:
                continue
            if not options["include_past"] and event_start < now:
                continue
            if event_start > max_time:
                continue
            if event.get("id") in matched_event_ids:
                continue
            if not rule_matches_event(configured_rule, event, now):
                continue
            item = configured_manual_issue(
                configured_rule,
                configured_rule.get("show_key") or "unknown",
                configured_rule.get("show_name") or "Unknown show",
                event_start.isoformat(),
                calendar_event_id=event.get("id"),
            )
            apply_issue_metadata(item, options["rules"])
            build_issue_evidence_panel(
                item,
                item.get("show_key") or "unknown",
                {"episode_date_time": event_start.isoformat()},
                [],
                [],
                event,
                [],
                None,
                None,
                options,
            )
            issues.append(item)
            if event.get("id"):
                manually_classified_event_ids.add(event.get("id"))
    for event in calendar_events:
        event_start = event.get("start")
        if not event_start:
            continue
        if not options["include_past"] and event_start < now:
            continue
        if event_start > max_time:
            continue
        if event.get("id") in matched_event_ids:
            continue
        if event.get("id") in manually_classified_event_ids:
            continue
        matching_show_name = None
        for show_name in show_names:
            if has_show_signal(event, show_name):
                matching_show_name = show_name
                break
        if not matching_show_name:
            continue
        represented_match = infer_pr_rep_booking_for_event(event, matching_show_name, options)
        if represented_match:
            issues.append(represented_match)
            continue
        item = issue(
            severity="Warning",
            code="calendar_event_without_booking",
            show_key="unknown",
            show_name=matching_show_name,
            episode_time=event_start.isoformat(),
            calendar_event_id=event.get("id"),
            message=f"ww@reveting.com has a show-like event with no matching active HighLevel booking: {event.get('title')}",
            recommended_action="Review whether this event is a placeholder, a manually created episode, or an orphaned calendar event.",
            details={"calendar_event_title": event.get("title"), "calendar_event_url": event.get("url")},
        )
        apply_manual_issue_overrides([item], options["rules"], now)
        apply_issue_metadata(item, options["rules"])
        build_issue_evidence_panel(
            item,
            "unknown",
            {"episode_date_time": event_start.isoformat()},
            [],
            [],
            event,
            [],
            None,
            None,
            options,
        )
        issues.append(item)
    return issues


def severity_counts(issues):
    counts = {"Critical": 0, "Warning": 0, "Informational": 0}
    for item in issues:
        severity = effective_issue_severity(item)
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def base_severity_counts(issues):
    counts = {"Critical": 0, "Warning": 0, "Informational": 0}
    for item in issues:
        severity = item.get("base_severity") or item.get("severity") or "Informational"
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def show_summary(audited_episodes, issues, rules, show_diagnostics=None):
    summary = {}
    diagnostics_by_show = {
        item.get("show_key"): item
        for item in (show_diagnostics or [])
        if item.get("show_key")
    }
    for show_key in configured_show_keys(rules):
        diagnostic = diagnostics_by_show.get(show_key)
        summary[show_key] = {
            "show_name": configured_show_name(rules, show_key),
            "episodes_audited": 0,
            "calendar_matches": 0,
            "production_health_score": None,
            "production_health_label": "Missing configuration" if diagnostic else "No upcoming episodes audited",
            "critical": 0,
            "warning": 0,
            "informational": 0,
            "health_scores": [],
            "configuration_status": diagnostic.get("status") if diagnostic else "ready",
            "configuration_message": diagnostic.get("message") if diagnostic else "",
        }
    for episode in audited_episodes:
        show_key = episode["show_key"]
        row = summary.setdefault(
            show_key,
            {
                "show_name": episode["show_name"],
                "episodes_audited": 0,
                "calendar_matches": 0,
                "health_scores": [],
                "production_health_score": None,
                "production_health_label": "No upcoming episodes audited",
                "critical": 0,
                "warning": 0,
                "informational": 0,
                "configuration_status": "ready",
                "configuration_message": "",
            },
        )
        row["episodes_audited"] += 1
        if episode.get("calendar_event_found"):
            row["calendar_matches"] += 1
        if episode.get("production_health", {}).get("score") is not None:
            row["health_scores"].append(episode["production_health"]["score"])
    for item in issues:
        show_key = item.get("show_key") or "unknown"
        row = summary.setdefault(
            show_key,
            {
                "show_name": item.get("show_name") or show_key,
                "episodes_audited": 0,
                "calendar_matches": 0,
                "health_scores": [],
                "production_health_score": None,
                "production_health_label": "No upcoming episodes audited",
                "critical": 0,
                "warning": 0,
                "informational": 0,
                "configuration_status": "ready",
                "configuration_message": "",
            },
        )
        key = effective_issue_severity(item).lower()
        row[key] = row.get(key, 0) + 1
    for row in summary.values():
        if row["health_scores"]:
            score = round(sum(row["health_scores"]) / len(row["health_scores"]), 1)
            row["production_health_score"] = score
            row["production_health_label"] = health_label(score, rules)
        row.pop("health_scores", None)
    return summary


def build_executive_summary(report):
    episodes = report.get("episodes") or []
    issues = report.get("issues") or []
    suppressed = report.get("suppressed_issues") or []
    ready_episodes = [episode for episode in episodes if episode_readiness(episode) == "Ready"]
    action_episodes = [episode for episode in episodes if episode_readiness(episode) == "Needs action"]
    review_episodes = [episode for episode in episodes if episode_readiness(episode) == "Needs review"]
    critical_issues = [item for item in issues if item.get("severity") == "Critical"]
    warning_issues = [item for item in issues if item.get("severity") == "Warning"]
    first_issue = None
    if critical_issues:
        first_issue = sorted(critical_issues, key=issue_sort_key)[0]
    elif warning_issues:
        first_issue = sorted(warning_issues, key=issue_sort_key)[0]

    if first_issue:
        fix_first = {
            "severity": first_issue.get("severity"),
            "episode_time": first_issue.get("episode_time"),
            "show_name": first_issue.get("show_name"),
            "issue": first_issue.get("message"),
            "recommended_action": first_issue.get("recommended_action"),
        }
    else:
        fix_first = {
            "severity": "Ready",
            "episode_time": None,
            "show_name": None,
            "issue": "No Critical or Warning issues found.",
            "recommended_action": "No manual fixes are required from this audit.",
        }

    return {
        "what_is_ready": (
            f"{len(ready_episodes)} of {len(episodes)} audited episode(s) have no Critical or Warning issues."
            if episodes
            else "No upcoming episodes were audited."
        ),
        "what_needs_action": (
            f"{len(action_episodes)} episode(s) have Critical issues and {len(review_episodes)} episode(s) have Warning-only issues."
            if issues
            else "No action items were found."
        ),
        "what_should_be_fixed_first": fix_first,
        "suppressed_issue_summary": f"{len(suppressed)} issue(s) are suppressed by configured known exceptions.",
        "ready_episode_count": len(ready_episodes),
        "critical_episode_count": len(action_episodes),
        "warning_only_episode_count": len(review_episodes),
        "ready_episodes": [episode.get("episode_time") for episode in ready_episodes],
        "not_ready_episodes": [episode.get("episode_time") for episode in action_episodes + review_episodes],
    }


def health_class(score):
    if score is None:
        return "unknown"
    if score >= 90:
        return "ready"
    if score >= 75:
        return "warning"
    return "critical"


def severity_class(severity):
    return {
        "Critical": "critical",
        "Warning": "warning",
        "Informational": "info",
        "Ready": "ready",
    }.get(severity, "info")


def readiness_class(readiness):
    return {
        "Ready": "ready",
        "Needs review": "warning",
        "Needs action": "critical",
    }.get(readiness, "info")


def badge(label, class_name):
    return f'<span class="badge {html_escape(class_name)}">{html_escape(label)}</span>'


def grouped_issues_by_episode(issues):
    grouped = {}
    for item in sorted(issues, key=issue_sort_key):
        key = item.get("episode_time") or "No episode date"
        grouped.setdefault(key, []).append(item)
    return grouped


def render_issue_rows(issues):
    if not issues:
        return '<tr><td colspan="6" class="muted">No issues found.</td></tr>'
    rows = []
    for item in issues:
        severity = item.get("severity") or "Informational"
        rows.append(
            "<tr>"
            f"<td>{badge(severity, severity_class(severity))}</td>"
            f"<td>{html_text(item.get('code'), 120)}</td>"
            f"<td>{html_text(item.get('show_name'), 120)}</td>"
            f"<td>{html_text(short_date(item.get('episode_time')), 120)}</td>"
            f"<td>{html_text(item.get('message'), 360)}</td>"
            f"<td>{html_text(item.get('recommended_action'), 360)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_episode_rows(episodes):
    if not episodes:
        return '<tr><td colspan="9" class="muted">No episodes audited.</td></tr>'
    rows = []
    for episode in sorted(episodes, key=episode_sort_key):
        readiness = episode_readiness(episode)
        counts = issue_counts_for_episode(episode)
        pairing = episode.get("pairing") or {}
        health = episode.get("production_health", {})
        score = health.get("score")
        pairing_label = "Two guests" if pairing.get("is_expected_two_guest_episode") else "Single guest"
        if pairing.get("recognized_two_guest_pair"):
            pairing_label = "Two guests recognized"
        elif pairing.get("needs_pairing_review"):
            pairing_label = "Two guests need review"
        rows.append(
            "<tr>"
            f"<td>{badge(readiness, readiness_class(readiness))}</td>"
            f"<td>{html_text(short_date(episode.get('episode_time')), 140)}</td>"
            f"<td>{html_text(episode.get('show_name'), 120)}</td>"
            f"<td>{html_text(', '.join(guest_names(episode.get('active_guests'))), 260)}</td>"
            f"<td>{badge(pairing_label, 'info' if 'review' not in pairing_label.lower() else 'warning')}</td>"
            f"<td><span class=\"score {health_class(score)}\">{html_escape('n/a' if score is None else score)}</span></td>"
            f"<td>{html_text(episode.get('calendar_event_title') or 'Missing', 260)}</td>"
            f"<td>{counts.get('Critical', 0)} / {counts.get('Warning', 0)} / {counts.get('Informational', 0)}</td>"
            f"<td>{html_text(episode.get('calendar_event_id') or '', 160)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def html_link(url, label):
    if not url:
        return ""
    return f'<a href="{html_escape(url)}" target="_blank" rel="noopener noreferrer">{html_escape(label)}</a>'


def html_email(email):
    if not email:
        return ""
    return f'<a href="mailto:{html_escape(email)}">{html_escape(email)}</a>'


def source_file_link(ref):
    path = ref.get("path") if isinstance(ref, dict) else str(ref or "")
    if not path:
        return ""
    href = None
    if path.startswith("data/"):
        href = "../" + path[len("data/") :]
    if href:
        return html_link(href, path)
    return html_escape(path)


def render_guest_list(guests):
    if not guests:
        return '<p class="muted">No guest evidence available.</p>'
    items = []
    for guest in guests:
        bits = []
        if guest.get("email"):
            bits.append(html_email(guest.get("email")))
        if guest.get("contact_name") and normalize_text(guest.get("contact_name")) != normalize_text(guest.get("name")):
            bits.append(f"submitter/contact: {html_text(guest.get('contact_name'), 120)}")
        if guest.get("contact_email") and normalize_email(guest.get("contact_email")) != normalize_email(guest.get("email")):
            bits.append(f"submitter email: {html_email(guest.get('contact_email'))}")
        if guest.get("represented_guest_confidence"):
            bits.append(f"represented confidence: {html_text(guest.get('represented_guest_confidence'), 60)}")
        if guest.get("represented_guest_evidence"):
            bits.append(f"evidence: {html_text(', '.join(guest.get('represented_guest_evidence') or []), 180)}")
        if guest.get("status"):
            bits.append(f"status: {html_text(guest.get('status'), 80)}")
        if guest.get("appointment_id"):
            bits.append(f"appointment: <code>{html_text(guest.get('appointment_id'), 120)}</code>")
        if guest.get("contact_id"):
            bits.append(f"contact: <code>{html_text(guest.get('contact_id'), 120)}</code>")
        items.append(f"<li><strong>{html_text(guest.get('name') or 'Unknown guest', 140)}</strong> {'; '.join(bits)}</li>")
    return "<ul>" + "".join(items) + "</ul>"


def render_attendee_list(attendees):
    if not attendees:
        return '<p class="muted">No attendees in the exported Google Calendar payload.</p>'
    return "<ul>" + "".join(f"<li>{html_email(email)}</li>" for email in attendees) + "</ul>"


def render_raw_ids(raw_ids):
    if not raw_ids:
        return '<p class="muted">No raw IDs available.</p>'
    blocks = []
    for label, value in raw_ids.items():
        if not value:
            continue
        if isinstance(value, list):
            rendered = ", ".join(f"<code>{html_text(item, 160)}</code>" for item in value)
        elif str(value).startswith("http"):
            rendered = html_link(value, value)
        else:
            rendered = f"<code>{html_text(value, 220)}</code>"
        blocks.append(f"<dt>{html_text(label.replace('_', ' ').title(), 80)}</dt><dd>{rendered}</dd>")
    return "<dl>" + "".join(blocks) + "</dl>" if blocks else '<p class="muted">No raw IDs available.</p>'


def render_source_files(source_files):
    if not source_files:
        return '<p class="muted">No source JSON references available.</p>'
    return "<ul>" + "".join(f"<li>{source_file_link(ref)}</li>" for ref in source_files) + "</ul>"


def operations_manager_rules(rules):
    return rule_section(rules, "operations_manager")


def configured_stages(timeline_rules):
    stages = timeline_rules.get("stages")
    if isinstance(stages, list) and stages:
        return [item for item in stages if isinstance(item, dict)]
    return [
        {"key": "30_plus_days", "label": "30+ days out", "min_hours_until": 720},
        {"key": "14_30_days", "label": "14-30 days out", "min_hours_until": 336, "max_hours_until": 720},
        {"key": "7_14_days", "label": "7-14 days out", "min_hours_until": 168, "max_hours_until": 336},
        {"key": "48_hours_7_days", "label": "48 hours-7 days out", "min_hours_until": 48, "max_hours_until": 168},
        {"key": "24_48_hours", "label": "24-48 hours out", "min_hours_until": 24, "max_hours_until": 48},
        {"key": "day_of_show", "label": "Day of show", "min_hours_until": 0, "max_hours_until": 24},
        {"key": "post_show", "label": "Post-show", "min_hours_since_show": 0, "max_hours_since_show": 168},
        {"key": "post_production", "label": "Post-production", "min_hours_since_show": 168},
    ]


def stage_order(timeline_rules):
    return [stage.get("key") for stage in configured_stages(timeline_rules) if stage.get("key")]


def stage_index(stage_key, timeline_rules):
    try:
        return stage_order(timeline_rules).index(stage_key)
    except ValueError:
        return -1


def stage_by_key(stage_key, timeline_rules):
    for stage in configured_stages(timeline_rules):
        if stage.get("key") == stage_key:
            return stage
    return {}


def match_stage(stage, hours_until):
    if hours_until is None:
        return False
    if hours_until < 0:
        hours_since = abs(hours_until)
        min_since = stage.get("min_hours_since_show")
        max_since = stage.get("max_hours_since_show")
        if min_since is None and max_since is None:
            return False
        if min_since is not None and hours_since < float(min_since):
            return False
        if max_since is not None and hours_since >= float(max_since):
            return False
        return True
    min_until = stage.get("min_hours_until")
    max_until = stage.get("max_hours_until")
    if min_until is not None and hours_until < float(min_until):
        return False
    if max_until is not None and hours_until >= float(max_until):
        return False
    return min_until is not None or max_until is not None


def production_stage_context(episode_or_time, timeline_rules, now):
    episode_time = episode_or_time.get("episode_time") if isinstance(episode_or_time, dict) else episode_or_time
    parsed = parse_datetime(episode_time)
    if not parsed:
        return {
            "key": "unknown",
            "label": "Unknown stage",
            "index": -1,
            "hours_until_show": None,
            "days_until_show": None,
            "reason": "Episode time is unavailable.",
        }
    hours_until = (parsed - now).total_seconds() / 3600
    for stage in configured_stages(timeline_rules):
        if match_stage(stage, hours_until):
            key = stage.get("key") or "unknown"
            return {
                "key": key,
                "label": stage.get("label") or key,
                "index": stage_index(key, timeline_rules),
                "hours_until_show": round(hours_until, 2),
                "days_until_show": round(hours_until / 24, 2),
                "reason": stage.get("operator_focus") or stage.get("description") or "",
            }
    fallback = configured_stages(timeline_rules)[0]
    key = fallback.get("key") or "unknown"
    return {
        "key": key,
        "label": fallback.get("label") or key,
        "index": stage_index(key, timeline_rules),
        "hours_until_show": round(hours_until, 2),
        "days_until_show": round(hours_until / 24, 2),
        "reason": fallback.get("operator_focus") or fallback.get("description") or "",
    }


def checklist_items(rules, timeline_rules=None):
    configured = (timeline_rules or {}).get("checklist_items")
    if isinstance(configured, list):
        return [item for item in configured if isinstance(item, dict)]
    if isinstance(configured, dict):
        items = []
        for key, value in configured.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("key", key)
                items.append(item)
        return items
    manager = operations_manager_rules(rules)
    items = manager.get("checklist_items")
    return items if isinstance(items, list) else []


def timeline_steps(rules, timeline_rules=None):
    configured = (timeline_rules or {}).get("timeline_steps")
    if isinstance(configured, list):
        return [item for item in configured if isinstance(item, dict)]
    manager = operations_manager_rules(rules)
    steps = manager.get("timeline_steps")
    return steps if isinstance(steps, list) else []


def earliest_required_stage_for_item(item, timeline_rules):
    if item.get("due_stage"):
        return item.get("due_stage")
    key = item.get("key")
    requirements = timeline_rules.get("stage_requirements") or {}
    for stage_key in stage_order(timeline_rules):
        required = requirements.get(stage_key) or []
        if key in required:
            return stage_key
    return None


def checklist_due_state(item, stage_context, timeline_rules, status):
    if status == "Not Applicable":
        return "not_applicable"
    due_stage = earliest_required_stage_for_item(item, timeline_rules)
    if not due_stage:
        return "not_yet_due"
    current_index = stage_context.get("index", -1)
    due_index = stage_index(due_stage, timeline_rules)
    if current_index < 0 or due_index < 0:
        return "unknown"
    if current_index < due_index:
        return "not_yet_due"
    if status == "Complete":
        return "complete"
    if current_index == due_index:
        return "due_now"
    return "overdue"


def checklist_due_label(due_state):
    return {
        "complete": "Complete",
        "due_now": "Due now",
        "overdue": "Overdue",
        "not_yet_due": "Not yet due",
        "not_applicable": "Not applicable",
        "unknown": "Unknown due date",
    }.get(due_state, "Unknown due date")


def checklist_due_reason(item, due_state, stage_context, timeline_rules):
    due_stage_key = earliest_required_stage_for_item(item, timeline_rules)
    due_stage = stage_by_key(due_stage_key, timeline_rules) if due_stage_key else {}
    due_label = due_stage.get("label") or due_stage_key or "a later stage"
    if due_state == "complete":
        return "This item is complete."
    if due_state == "due_now":
        return f"This item is required during the current stage: {stage_context.get('label')}."
    if due_state == "overdue":
        return f"This item was required by {due_label} and is still unresolved."
    if due_state == "not_yet_due":
        return f"This item is not due until {due_label}."
    if due_state == "not_applicable":
        return "This item is not applicable for this episode based on normalized data."
    return "The due stage could not be determined from the configured timeline."


def episode_issue_codes(episode):
    return {item.get("code") for item in episode.get("issues") or []}


def episode_issue_by_code(episode, code):
    return [item for item in episode.get("issues") or [] if item.get("code") == code]


def has_missing_asset(episode, needle):
    needle = normalize_text(needle)
    for item in episode_issue_by_code(episode, "sop_required_assets_missing"):
        for asset in (item.get("details") or {}).get("missing_assets") or []:
            if needle in normalize_text(asset.get("asset")):
                return True
    return False


def episode_production_status(episode):
    counts = issue_counts_for_episode(episode)
    if counts.get("Critical", 0):
        return "Blocked"
    if counts.get("Warning", 0):
        return "Needs Attention"
    return "Ready"


def status_result(status, reason):
    return {"status": status, "reason": reason}


def checklist_due(item, episode, now):
    within_days = item.get("due_within_days")
    if within_days is None:
        return True
    episode_time = parse_datetime(episode.get("episode_time"))
    if not episode_time:
        return False
    return episode_time <= now + timedelta(days=int(within_days))


def checklist_status(item, episode, now, stage_context=None):
    key = item.get("key")
    guests = episode.get("active_guests") or []
    codes = episode_issue_codes(episode)
    if key == "highlevel_booking":
        return status_result("Complete" if episode.get("appointment_ids") else "Unknown", "Active HighLevel booking data is present." if episode.get("appointment_ids") else "No active appointment ID is available in discovery.")
    if key in {"guest_1_form", "guest_2_form"}:
        index = 0 if key == "guest_1_form" else 1
        if index >= len(guests):
            return status_result("Not Applicable", "This episode does not currently have that guest slot active.")
        guest = guests[index]
        if guest.get("form_submission_ids"):
            return status_result("Complete", "Exact HighLevel form submission ID is linked.")
        if guest.get("possible_form_submissions"):
            return status_result("Complete", "A likely related HighLevel form submission exists; exact linkage remains tracked as an audit-confidence note.")
        return status_result("Unknown", "Discovery did not provide an exact form submission link for this guest.")
    if key == "calendar_created":
        return status_result("Complete" if episode.get("calendar_event_found") else "Incomplete", "A matching Google Calendar event was found." if episode.get("calendar_event_found") else "No matching Google Calendar event was found.")
    if key == "calendar_title_correct":
        bad_codes = {"title_missing_guest", "title_missing_show_name", "guest_not_represented"}
        if bad_codes & codes:
            return status_result("Incomplete", "The audit found a title or guest-representation issue.")
        return status_result("Complete" if episode.get("calendar_event_found") else "Unknown", "No title issue was found." if episode.get("calendar_event_found") else "No calendar event is available to inspect.")
    if key == "title_drafted":
        if not episode.get("calendar_event_found"):
            return status_result("Unknown", "No calendar event is available to inspect for a drafted title.")
        if not episode.get("calendar_event_title"):
            return status_result("Incomplete", "The matching Google Calendar event does not have a title.")
        return status_result("Complete", "A Google Calendar title is present.")
    if key in {"topics_present", "title_topic_fields_complete"}:
        bad_codes = {"required_custom_fields_missing_from_description"}
        if bad_codes & codes:
            return status_result("Incomplete", "One or more configured topic/custom fields are missing from the calendar description.")
        return status_result("Complete" if episode.get("calendar_event_found") else "Unknown", "No required topic/custom field issue was found." if episode.get("calendar_event_found") else "No calendar event is available to inspect.")
    if key == "pr_assistant_emails_captured":
        guests_with_support_emails = [
            guest
            for guest in guests
            if guest.get("pr_emails") or guest.get("assistant_emails") or guest.get("alternate_invite_emails")
        ]
        if guests_with_support_emails:
            return status_result("Complete", "At least one PR, assistant, or alternate invite email was captured in normalized HighLevel data.")
        return status_result("Unknown", "No PR, assistant, or alternate invite email is available in normalized HighLevel data.")
    if key == "calendar_description_complete":
        bad_codes = {"required_custom_fields_missing_from_description", "sop_required_assets_missing"}
        if bad_codes & codes:
            return status_result("Incomplete", "The audit found missing description fields or SOP assets.")
        return status_result("Complete" if episode.get("calendar_event_found") else "Unknown", "No description issue was found." if episode.get("calendar_event_found") else "No calendar event is available to inspect.")
    if key == "guest_invites_sent":
        bad_codes = {"guest_email_not_invited", "active_guest_email_missing", "attendee_list_unavailable"}
        if bad_codes & codes:
            return status_result("Incomplete", "Guest invite verification failed or attendee data is unavailable.")
        return status_result("Complete" if episode.get("calendar_event_found") else "Unknown", "All active guest invite emails found in the calendar attendee list." if episode.get("calendar_event_found") else "No calendar event is available to inspect.")
    if key in {"internal_invites_sent", "required_attendees_present"}:
        if "required_attendee_not_invited" in codes:
            return status_result("Incomplete", "A configured required attendee is missing from the calendar invite.")
        return status_result("Complete" if episode.get("calendar_event_found") else "Unknown", "Configured required attendees are present." if episode.get("calendar_event_found") else "No calendar event is available to inspect.")
    if key == "pr_assistant_invited":
        if "pr_email_not_invited" in codes:
            return status_result("Incomplete", "A captured PR or assistant email is missing from the calendar invite.")
        support_emails = []
        for guest in guests:
            support_emails.extend(guest.get("pr_emails") or [])
            support_emails.extend(guest.get("assistant_emails") or [])
            support_emails.extend(guest.get("alternate_invite_emails") or [])
        if not support_emails:
            return status_result("Not Applicable", "No PR, assistant, or alternate invite emails were captured for this episode.")
        return status_result("Complete" if episode.get("calendar_event_found") else "Unknown", "Captured PR, assistant, or alternate emails appear covered by the calendar invite." if episode.get("calendar_event_found") else "No calendar event is available to inspect.")
    if key == "linkedin_event_created":
        if item.get("due_within_days") is not None and not checklist_due(item, episode, now):
            return status_result("Not Applicable", "This check is not due yet under the configured window.")
        if "linkedin_event_exists_calendar_needs_update" in codes:
            return status_result("Complete", "A verified LinkedIn event exists from manual/read-only evidence, but the Google Calendar description still needs the URL added.")
        if has_missing_asset(episode, "linkedin event"):
            return status_result("Incomplete", "Configured LinkedIn event link check failed.")
        return status_result("Complete" if episode.get("calendar_event_found") else "Unknown", "No LinkedIn event asset issue was found." if episode.get("calendar_event_found") else "No calendar event is available to inspect.")
    if key == "streamyard_created":
        if item.get("due_within_days") is not None and not checklist_due(item, episode, now):
            return status_result("Not Applicable", "This check is not due yet under the configured window.")
        if has_missing_asset(episode, "streamyard"):
            return status_result("Incomplete", "Configured StreamYard asset check failed.")
        return status_result("Complete" if episode.get("calendar_event_found") else "Unknown", "No StreamYard asset issue was found." if episode.get("calendar_event_found") else "No calendar event is available to inspect.")
    if key == "guest_promotion_instructions_included":
        if has_missing_asset(episode, "promotion"):
            return status_result("Incomplete", "Configured guest promotion instruction check failed.")
        return status_result("Complete" if episode.get("calendar_event_found") else "Unknown", "No guest promotion instruction issue was found." if episode.get("calendar_event_found") else "No calendar event is available to inspect.")
    if key == "guests_confirmed":
        return status_result("Unknown", "No normalized guest confirmation or reminder-response data is available yet.")
    if key == "recording_exists":
        episode_time = parse_datetime(episode.get("episode_time"))
        if episode_time and episode_time > now:
            return status_result("Not Applicable", "Recording checks are not due before the livestream.")
        return status_result("Unknown", "No normalized recording data is available yet.")
    if key in {"episode_folder_exists", "transcript_exists", "ai_clips_complete", "newsletter_complete", "social_assets_complete", "post_production_complete"}:
        episode_time = parse_datetime(episode.get("episode_time"))
        if episode_time and episode_time > now:
            return status_result("Not Applicable", "This post-production or asset check is not due before the livestream.")
        return status_result("Unknown", "No normalized Google Drive, transcript, clips, newsletter, or social asset data is available yet.")
    return status_result("Unknown", "No status rule is configured for this checklist item.")


def build_episode_checklist(episode, rules, timeline_rules, stage_context, now):
    results = []
    for item in checklist_items(rules, timeline_rules):
        if not isinstance(item, dict):
            continue
        result = checklist_status(item, episode, now, stage_context)
        due_state = checklist_due_state(item, stage_context, timeline_rules, result["status"])
        due_stage_key = earliest_required_stage_for_item(item, timeline_rules)
        due_stage = stage_by_key(due_stage_key, timeline_rules) if due_stage_key else {}
        results.append(
            {
                "key": item.get("key"),
                "label": item.get("label") or item.get("key"),
                "status": result["status"],
                "reason": result["reason"],
                "due_state": due_state,
                "due_label": checklist_due_label(due_state),
                "due_reason": checklist_due_reason(item, due_state, stage_context, timeline_rules),
                "due_stage": due_stage_key,
                "due_stage_label": due_stage.get("label") or due_stage_key,
                "stage_required": due_state in {"complete", "due_now", "overdue"},
                "counts_toward_readiness": due_state in {"complete", "due_now", "overdue"},
                "source": item.get("source", "normalized_audit_json"),
            }
        )
    return results


def checklist_completion_summary(checklist):
    counted = [item for item in checklist if item.get("counts_toward_readiness")]
    complete = [item for item in counted if item.get("status") == "Complete"]
    incomplete = [item for item in counted if item.get("status") != "Complete"]
    percentage = 100 if not counted else round((len(complete) / len(counted)) * 100)
    return {
        "percentage": percentage,
        "complete_count": len(complete),
        "required_count": len(counted),
        "incomplete_count": len(incomplete),
        "due_now_count": sum(1 for item in checklist if item.get("due_state") == "due_now"),
        "overdue_count": sum(1 for item in checklist if item.get("due_state") == "overdue"),
        "not_yet_due_count": sum(1 for item in checklist if item.get("due_state") == "not_yet_due"),
    }


def checklist_bucket(checklist, due_state):
    return [item for item in checklist if item.get("due_state") == due_state]


def timeline_status(step, episode, checklist_by_key, now):
    key = step.get("key")
    episode_time = parse_datetime(episode.get("episode_time"))
    if key == "guest_forms_submitted":
        guest_form_items = [
            checklist_by_key.get("guest_1_form"),
            checklist_by_key.get("guest_2_form"),
        ]
        active_items = [item for item in guest_form_items if item and item.get("status") != "Not Applicable"]
        if not active_items:
            return status_result("Not Applicable", "No active guest form slots are available.")
        if all(item.get("status") == "Complete" for item in active_items):
            return status_result("Complete", "All active guest form slots are linked to exact submissions.")
        if any(item.get("status") == "Incomplete" for item in active_items):
            return status_result("Blocked", "At least one active guest form is incomplete.")
        return status_result("Unknown", "At least one active guest form cannot be exactly linked from normalized discovery data.")
    checklist_keys = step.get("checklist_keys") or []
    if checklist_keys:
        linked = [checklist_by_key[item_key] for item_key in checklist_keys if item_key in checklist_by_key]
        applicable = [item for item in linked if item.get("status") != "Not Applicable"]
        if not applicable:
            return status_result("Not Applicable", "No linked checklist items apply to this episode.")
        due_or_complete = [
            item
            for item in applicable
            if item.get("due_state") in {"complete", "due_now", "overdue"}
        ]
        if not due_or_complete:
            next_due = sorted(
                [item.get("due_stage_label") for item in applicable if item.get("due_stage_label")],
                key=lambda value: value or "",
            )
            return status_result("Upcoming", f"This step is not due yet. Next due stage: {next_due[0] if next_due else 'later'}.")
        if all(item.get("status") == "Complete" for item in due_or_complete):
            return status_result("Complete", "All due checklist items for this step are complete.")
        if any(item.get("due_state") == "overdue" for item in due_or_complete):
            return status_result("Blocked", "At least one checklist item for this step is overdue.")
        return status_result("In Progress", "One or more checklist items for this step are due now.")
    if key == "livestream":
        if not episode_time:
            return status_result("Unknown", "Episode time is unavailable.")
        expected_end = parse_datetime(episode.get("expected_calendar_end")) or episode_time + timedelta(hours=1)
        if now < episode_time:
            return status_result("Upcoming", "Livestream has not happened yet.")
        if episode_time <= now <= expected_end:
            return status_result("In Progress", "The current time is inside the live production window.")
        return status_result("Complete", "The live production window has passed.")
    checklist_key = step.get("checklist_key")
    if checklist_key and checklist_key in checklist_by_key:
        checklist = checklist_by_key[checklist_key]
        timeline_map = {
            "Complete": "Complete",
            "Incomplete": "Blocked",
            "Unknown": "Unknown",
            "Not Applicable": "Not Applicable",
        }
        return status_result(timeline_map.get(checklist["status"], checklist["status"]), checklist.get("reason"))
    if key in {"post_production", "newsletter", "follow_up"}:
        if episode_time and episode_time > now:
            return status_result("Upcoming", "This work starts after the livestream.")
        return status_result("Unknown", "No normalized post-production data is available yet.")
    return status_result("Unknown", "No timeline rule is configured for this step.")


def build_episode_timeline(episode, checklist, rules, timeline_rules, now):
    checklist_by_key = {item["key"]: item for item in checklist}
    results = []
    for index, step in enumerate(timeline_steps(rules, timeline_rules), start=1):
        if not isinstance(step, dict):
            continue
        result = timeline_status(step, episode, checklist_by_key, now)
        step_checklist_keys = step.get("checklist_keys") or []
        if not step_checklist_keys and step.get("checklist_key"):
            step_checklist_keys = [step.get("checklist_key")]
        linked_items = [checklist_by_key[key] for key in step_checklist_keys if key in checklist_by_key]
        due_states = sorted({item.get("due_state") for item in linked_items if item.get("due_state")})
        results.append(
            {
                "order": index,
                "key": step.get("key"),
                "label": step.get("label") or step.get("key"),
                "status": result["status"],
                "reason": result["reason"],
                "checklist_keys": step_checklist_keys,
                "due_states": due_states,
            }
        )
    return results


def episode_confidence_summary(episode):
    issues = episode.get("issues") or []
    if not issues:
        return {
            "confidence": "High confidence",
            "reason": "No active Critical, Warning, or Informational issues were found for this episode.",
        }
    if any(item.get("confidence") == "low" for item in issues):
        reasons = [item.get("confidence_explanation") for item in issues if item.get("confidence") == "low"]
        return {"confidence": "Low confidence", "reason": compact("; ".join(reason for reason in reasons if reason), 500)}
    if any(item.get("confidence") == "medium" for item in issues):
        reasons = [item.get("confidence_explanation") for item in issues if item.get("confidence") == "medium"]
        return {"confidence": "Medium confidence", "reason": compact("; ".join(reason for reason in reasons if reason), 500)}
    return {
        "confidence": "High confidence",
        "reason": "All active findings for this episode are high confidence.",
    }


def episode_operator_recommendation(episode):
    status = episode_production_status(episode)
    issues = sorted(episode.get("issues") or [], key=issue_sort_key)
    if status == "Blocked":
        critical = [item for item in issues if item.get("severity") == "Critical"]
        first = critical[0] if critical else issues[0]
        return {
            "category": first.get("operator_recommendation", {}).get("category") or "Fix First",
            "reason": first.get("operator_recommendation", {}).get("reason") or first.get("recommended_action"),
        }
    if status == "Needs Attention":
        first = issues[0] if issues else {}
        return {
            "category": "Fix Today",
            "reason": first.get("recommended_action") or "Warning-level items should be reviewed before showtime.",
        }
    if issues:
        return {
            "category": "Monitor",
            "reason": "Only Informational findings are present.",
        }
    return {
        "category": "No Action Needed",
        "reason": "No active issues were found for this episode.",
    }


def count_for_status(counts, *names):
    if not isinstance(counts, dict):
        return 0
    for name in names:
        if name in counts:
            return counts.get(name) or 0
    return 0


def operational_status_from_counts(counts):
    if count_for_status(counts, "Critical", "critical") > 0:
        return "Blocked"
    if count_for_status(counts, "Warning", "warning") > 0:
        return "Needs Attention"
    return "Ready"


def effective_issue_severity(item):
    return item.get("stage_adjusted_severity") or item.get("severity") or "Informational"


def effective_issue_counts(issues):
    counts = {"Critical": 0, "Warning": 0, "Informational": 0}
    for item in issues or []:
        severity = effective_issue_severity(item)
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def manager_issue_sort_key(item):
    return (
        SEVERITY_ORDER.get(effective_issue_severity(item), 9),
        item.get("episode_time") or "",
        item.get("show_name") or "",
        item.get("code") or "",
    )


def manager_production_status(issue_counts, checklist_summary):
    if issue_counts.get("Critical", 0):
        return "Blocked"
    if issue_counts.get("Warning", 0) or checklist_summary.get("overdue_count", 0) or checklist_summary.get("due_now_count", 0):
        return "Needs Attention"
    return "Ready"


def episode_operator_recommendation_from_manager(status, issues, checklist_summary):
    sorted_issues = sorted(issues or [], key=manager_issue_sort_key)
    if status == "Blocked":
        first = sorted_issues[0] if sorted_issues else {}
        return {
            "category": (first.get("operator_recommendation") or {}).get("category") or "Fix First",
            "reason": (first.get("operator_recommendation") or {}).get("reason") or "A stage-adjusted Critical issue is active.",
        }
    if status == "Needs Attention":
        if not any(effective_issue_severity(item) in {"Critical", "Warning"} for item in sorted_issues):
            if checklist_summary.get("overdue_count", 0):
                return {
                    "category": "Fix Today",
                    "reason": f"{checklist_summary.get('overdue_count')} checklist item(s) are overdue for the current production stage.",
                }
            if checklist_summary.get("due_now_count", 0):
                return {
                    "category": "Fix Today",
                    "reason": f"{checklist_summary.get('due_now_count')} checklist item(s) are due during the current production stage.",
                }
        first = sorted_issues[0] if sorted_issues else {}
        category = (first.get("operator_recommendation") or {}).get("category") or "Fix Today"
        return {
            "category": "Fix Today" if category == "Monitor" else category,
            "reason": (first.get("operator_recommendation") or {}).get("reason") or "One or more due checklist items need operator attention.",
        }
    if sorted_issues:
        return {
            "category": "Monitor",
            "reason": "Only stage-adjusted Informational findings are present.",
        }
    return {
        "category": "No Action Needed",
        "reason": "No active issues were found for this episode.",
    }


def build_manager_episode(episode, rules, timeline_rules, now):
    stage_context = production_stage_context(episode, timeline_rules, now)
    checklist = build_episode_checklist(episode, rules, timeline_rules, stage_context, now)
    checklist_summary = checklist_completion_summary(checklist)
    timeline = build_episode_timeline(episode, checklist, rules, timeline_rules, now)
    issues = episode.get("issues") or []
    effective_counts = effective_issue_counts(issues)
    production_status = manager_production_status(effective_counts, checklist_summary)
    return {
        "show_key": episode.get("show_key"),
        "show_name": episode.get("show_name"),
        "episode_time": episode.get("episode_time"),
        "episode_time_display": short_date(episode.get("episode_time")),
        "production_stage": stage_context,
        "production_status": production_status,
        "production_health": episode.get("production_health"),
        "readiness_percentage": checklist_summary["percentage"],
        "checklist_completion": checklist_summary,
        "guest_names": guest_names(episode.get("active_guests")),
        "represented_guest_matches": [
            {
                "highlevel_submitter_contact": guest.get("contact_name"),
                "highlevel_submitter_email": guest.get("contact_email"),
                "represented_guest": guest.get("represented_guest_name"),
                "represented_guest_email": guest.get("represented_guest_email"),
                "confidence": guest.get("represented_guest_confidence"),
                "evidence": guest.get("represented_guest_evidence") or [],
            }
            for guest in episode.get("active_guests") or []
            if guest.get("represented_guest_name")
        ],
        "calendar_event_title": episode.get("calendar_event_title"),
        "calendar_event_url": episode.get("calendar_event_url"),
        "calendar_event_id": episode.get("calendar_event_id"),
        "issue_counts": effective_counts,
        "base_issue_counts": issue_counts_for_episode(episode),
        "confidence": episode_confidence_summary(episode),
        "operator_recommendation": episode_operator_recommendation_from_manager(production_status, issues, checklist_summary),
        "checklist": checklist,
        "due_now_checklist": checklist_bucket(checklist, "due_now"),
        "overdue_checklist": checklist_bucket(checklist, "overdue"),
        "not_yet_due_checklist": checklist_bucket(checklist, "not_yet_due"),
        "timeline": timeline,
        "issues": issues,
        "suppressed_issues": episode.get("suppressed_issues") or [],
    }


def aggregate_checklist_bucket(episodes, bucket_name):
    rows = []
    for episode in episodes:
        for item in episode.get(bucket_name) or []:
            rows.append(
                {
                    "show_key": episode.get("show_key"),
                    "show_name": episode.get("show_name"),
                    "episode_time": episode.get("episode_time"),
                    "episode_time_display": episode.get("episode_time_display"),
                    "guest_names": episode.get("guest_names") or [],
                    "production_stage": episode.get("production_stage"),
                    "checklist_key": item.get("key"),
                    "checklist_label": item.get("label"),
                    "status": item.get("status"),
                    "due_state": item.get("due_state"),
                    "reason": item.get("reason"),
                    "due_reason": item.get("due_reason"),
                }
            )
    return rows


def show_stage_issue_counts(episodes, show_key):
    counts = {"Critical": 0, "Warning": 0, "Informational": 0}
    for episode in episodes:
        if episode.get("show_key") != show_key:
            continue
        for severity, count in (episode.get("issue_counts") or {}).items():
            counts[severity] = counts.get(severity, 0) + count
    return counts


def grouped_manager_items_by_show(show_keys, rules, episodes, issues, show_diagnostics):
    groups = {
        show_key: {
            "show_key": show_key,
            "show_name": configured_show_name(rules, show_key),
            "ready_episode_count": 0,
            "needs_attention_episode_count": 0,
            "blocked_episode_count": 0,
            "upcoming_episodes": [],
            "due_now_checklist_items": [],
            "overdue_checklist_items": [],
            "fix_first_items": [],
            "configuration_diagnostics": [],
        }
        for show_key in show_keys
    }
    for diagnostic in show_diagnostics or []:
        show_key = diagnostic.get("show_key")
        groups.setdefault(
            show_key,
            {
                "show_key": show_key,
                "show_name": diagnostic.get("show_name") or show_key,
                "ready_episode_count": 0,
                "needs_attention_episode_count": 0,
                "blocked_episode_count": 0,
                "upcoming_episodes": [],
                "due_now_checklist_items": [],
                "overdue_checklist_items": [],
                "fix_first_items": [],
                "configuration_diagnostics": [],
            },
        )
        groups[show_key]["configuration_diagnostics"].append(diagnostic)
    for episode in episodes:
        show_key = episode.get("show_key")
        if show_key not in groups:
            groups[show_key] = {
                "show_key": show_key,
                "show_name": episode.get("show_name") or show_key,
                "ready_episode_count": 0,
                "needs_attention_episode_count": 0,
                "blocked_episode_count": 0,
                "upcoming_episodes": [],
                "due_now_checklist_items": [],
                "overdue_checklist_items": [],
                "fix_first_items": [],
                "configuration_diagnostics": [],
            }
        status = episode.get("production_status")
        if status == "Ready":
            groups[show_key]["ready_episode_count"] += 1
        elif status == "Blocked":
            groups[show_key]["blocked_episode_count"] += 1
        elif status == "Needs Attention":
            groups[show_key]["needs_attention_episode_count"] += 1
        groups[show_key]["upcoming_episodes"].append(episode)
        for item in episode.get("due_now_checklist") or []:
            groups[show_key]["due_now_checklist_items"].append(
                {
                    "episode_time": episode.get("episode_time"),
                    "episode_time_display": episode.get("episode_time_display"),
                    "guest_names": episode.get("guest_names") or [],
                    "checklist_key": item.get("key"),
                    "checklist_label": item.get("label"),
                    "status": item.get("status"),
                    "due_state": item.get("due_state"),
                    "reason": item.get("reason"),
                    "due_reason": item.get("due_reason"),
                }
            )
        for item in episode.get("overdue_checklist") or []:
            groups[show_key]["overdue_checklist_items"].append(
                {
                    "episode_time": episode.get("episode_time"),
                    "episode_time_display": episode.get("episode_time_display"),
                    "guest_names": episode.get("guest_names") or [],
                    "checklist_key": item.get("key"),
                    "checklist_label": item.get("label"),
                    "status": item.get("status"),
                    "due_state": item.get("due_state"),
                    "reason": item.get("reason"),
                    "due_reason": item.get("due_reason"),
                }
            )
    for item in issues or []:
        if item.get("operator_recommendation", {}).get("category") == "Fix First":
            groups.setdefault(
                item.get("show_key"),
                {
                    "show_key": item.get("show_key"),
                    "show_name": item.get("show_name") or item.get("show_key"),
                    "ready_episode_count": 0,
                    "needs_attention_episode_count": 0,
                    "blocked_episode_count": 0,
                    "upcoming_episodes": [],
                    "due_now_checklist_items": [],
                    "overdue_checklist_items": [],
                    "fix_first_items": [],
                    "configuration_diagnostics": [],
                },
            )
            groups[item.get("show_key")]["fix_first_items"].append(item)
    for group in groups.values():
        group["upcoming_episode_count"] = len(group["upcoming_episodes"])
        group["due_now_count"] = len(group["due_now_checklist_items"])
        group["overdue_count"] = len(group["overdue_checklist_items"])
        group["fix_first_count"] = len(group["fix_first_items"])
    return groups


def build_operations_manager_dashboard(report, rules, timeline_rules, now, completion_tracking=None):
    manager = operations_manager_rules(rules)
    upcoming_days = int(manager.get("upcoming_days", 30))
    completed_days = int(manager.get("recently_completed_days", 14))
    episodes = [build_manager_episode(episode, rules, timeline_rules, now) for episode in report.get("episodes") or []]
    health_by_show = {}
    diagnostics_by_show = {
        item.get("show_key"): item
        for item in (report.get("show_configuration_diagnostics") or [])
        if item.get("show_key")
    }
    for show_key, item in (report.get("show_summary") or {}).items():
        show_item = dict(item)
        stage_counts = show_stage_issue_counts(episodes, show_key)
        show_item["stage_adjusted_issue_counts"] = stage_counts
        if show_key in diagnostics_by_show:
            show_item["operational_status"] = "Missing Configuration"
        else:
            show_item["operational_status"] = operational_status_from_counts(stage_counts)
        health_by_show[show_key] = show_item
    upcoming = []
    completed = []
    attention = []
    blocked = []
    ready = []
    needs_attention = []
    configured_keys = configured_show_keys(rules)
    for episode in episodes:
        episode_time = parse_datetime(episode.get("episode_time"))
        if episode_time:
            if now <= episode_time <= now + timedelta(days=upcoming_days):
                upcoming.append(episode)
            if now - timedelta(days=completed_days) <= episode_time < now:
                completed.append(episode)
        if episode.get("production_status") in {"Needs Attention", "Blocked"}:
            attention.append(episode)
        if episode.get("production_status") == "Blocked":
            blocked.append(episode)
        elif episode.get("production_status") == "Needs Attention":
            needs_attention.append(episode)
        elif episode.get("production_status") == "Ready":
            ready.append(episode)
    stage_issue_counts = effective_issue_counts(report.get("issues") or [])
    critical_issues = [item for item in report.get("issues", []) if effective_issue_severity(item) == "Critical"]
    critical_review = build_critical_review(report)
    warnings = [item for item in report.get("issues", []) if effective_issue_severity(item) == "Warning"]
    informational = [item for item in report.get("issues", []) if effective_issue_severity(item) == "Informational"]
    trust_findings = trust_findings_from_issues(report.get("issues") or []) + trust_findings_from_issues(report.get("suppressed_issues") or [])
    trust_buckets = group_trust_findings(trust_findings)
    future_safe_action_findings = [
        item for item in trust_findings if item.get("future_automation_candidate") == "yes"
    ]
    show_groups = grouped_manager_items_by_show(configured_keys, rules, episodes, report.get("issues") or [], report.get("show_configuration_diagnostics") or [])
    for show_key, group in show_groups.items():
        show_item = health_by_show.setdefault(
            show_key,
            {
                "show_name": group.get("show_name") or configured_show_name(rules, show_key),
                "episodes_audited": 0,
                "calendar_matches": 0,
                "production_health_score": None,
                "production_health_label": "No upcoming episodes audited",
                "critical": 0,
                "warning": 0,
                "informational": 0,
                "stage_adjusted_issue_counts": {"Critical": 0, "Warning": 0, "Informational": 0},
                "operational_status": "Ready",
            },
        )
        show_item["ready_episode_count"] = group.get("ready_episode_count", 0)
        show_item["needs_attention_episode_count"] = group.get("needs_attention_episode_count", 0)
        show_item["blocked_episode_count"] = group.get("blocked_episode_count", 0)
        show_item["due_now_count"] = group.get("due_now_count", 0)
        show_item["overdue_count"] = group.get("overdue_count", 0)
        show_item["fix_first_count"] = group.get("fix_first_count", 0)
        if group.get("configuration_diagnostics"):
            show_item["operational_status"] = "Missing Configuration"
    return {
        "generated_at": report.get("generated_at"),
        "read_only": True,
        "source_report": "data/audit/operations_audit_report.json",
        "production_timeline_rules_path": report.get("production_timeline_rules_path"),
        "overall_production_health": report.get("overall_production_health"),
        "overall_production_status": operational_status_from_counts(stage_issue_counts),
        "health_by_show": health_by_show,
        "show_groups": show_groups,
        "show_configuration_diagnostics": report.get("show_configuration_diagnostics") or [],
        "issue_counts": stage_issue_counts,
        "base_issue_counts": report.get("base_severity_counts") or report.get("severity_counts") or {},
        "suppressed_issue_count": report.get("suppressed_issue_count", 0),
        "suppressed_issues": report.get("suppressed_issues") or [],
        "trust_review": report.get("trust_review") or {},
        "trust_summary": (report.get("trust_review") or {}).get("summary") or {},
        "completion_tracking": completion_tracking or {"summary": {"total_claims": 0, "counts_by_status": {}, "completed_today_count": 0}, "claims": [], "completed_today": []},
        "trust_buckets": trust_buckets,
        "confirmed_issue_findings": trust_buckets.get("Confirmed Issues", []),
        "needs_verification_findings": trust_buckets.get("Needs Verification", []),
        "represented_guest_findings": trust_buckets.get("PR Representative Booking / Guest Represented", []),
        "waiting_on_guest_findings": trust_buckets.get("Waiting on Guest", []),
        "waiting_on_guest_topics_findings": trust_buckets.get("Waiting on Guest Topics", []),
        "waiting_on_client_findings": trust_buckets.get("Waiting on Client", []),
        "waiting_on_internal_team_findings": trust_buckets.get("Waiting on Internal Team", []),
        "known_exception_findings": trust_buckets.get("Known Exceptions", []),
        "known_calendar_ownership_exception_findings": trust_buckets.get("Known Calendar Ownership Exception", []),
        "human_confirmed_active_findings": trust_buckets.get("Human Confirmed Active", []),
        "needs_human_follow_up_findings": trust_buckets.get("Needs Human Follow-Up", []),
        "needs_guest_replacement_findings": trust_buckets.get("Needs Guest Replacement", []),
        "not_due_yet_findings": trust_buckets.get("Not Due Yet", []),
        "future_safe_action_findings": future_safe_action_findings,
        "critical_issues": critical_issues,
        "critical_review": critical_review,
        "warnings": warnings,
        "informational_issues": informational,
        "upcoming_days": upcoming_days,
        "recently_completed_days": completed_days,
        "upcoming_episodes": sorted(upcoming, key=lambda item: item.get("episode_time") or ""),
        "represented_guest_matches": [
            {
                "show_name": episode.get("show_name"),
                "episode_time": episode.get("episode_time"),
                **match,
            }
            for episode in episodes
            for match in (episode.get("represented_guest_matches") or [])
        ] + [
            {
                "show_name": item.get("show_name"),
                "episode_time": item.get("episode_time"),
                **represented_guest_summary_from_issues([item]),
            }
            for item in report.get("issues", [])
            if item.get("code") == "pr_representative_booking_guest_represented"
            and represented_guest_summary_from_issues([item]).get("represented_guest")
        ],
        "episodes_requiring_attention": sorted(attention, key=lambda item: ({"Blocked": 0, "Needs Attention": 1}.get(item.get("production_status"), 2), item.get("episode_time") or "")),
        "blocked_episodes": sorted(blocked, key=lambda item: item.get("episode_time") or ""),
        "needs_attention_episodes": sorted(needs_attention, key=lambda item: item.get("episode_time") or ""),
        "ready_episodes": sorted(ready, key=lambda item: item.get("episode_time") or ""),
        "recently_completed_episodes": sorted(completed, key=lambda item: item.get("episode_time") or "", reverse=True),
        "all_episodes": sorted(episodes, key=lambda item: item.get("episode_time") or ""),
        "due_now_checklist_items": aggregate_checklist_bucket(episodes, "due_now_checklist"),
        "overdue_checklist_items": aggregate_checklist_bucket(episodes, "overdue_checklist"),
        "not_yet_due_checklist_items": aggregate_checklist_bucket(episodes, "not_yet_due_checklist"),
        "trend": report.get("change_summary") or {},
        "operator_recommendations": {
            "fix_first": [item for item in report.get("issues", []) if item.get("operator_recommendation", {}).get("category") == "Fix First"],
            "urgent_review": [item for item in report.get("issues", []) if item.get("operator_recommendation", {}).get("category") == "Urgent Review"],
            "fix_today": [item for item in report.get("issues", []) if item.get("operator_recommendation", {}).get("category") == "Fix Today"],
            "monitor": [item for item in report.get("issues", []) if item.get("operator_recommendation", {}).get("category") == "Monitor"],
            "no_action_needed": [
                item for item in episodes if item.get("operator_recommendation", {}).get("category") == "No Action Needed"
            ],
        },
    }


def render_issue_panel(item):
    severity = effective_issue_severity(item)
    panel = item.get("evidence_panel") or {}
    trust = item.get("trust") or {}
    highlevel = panel.get("evidence_from_highlevel") or {}
    calendar = panel.get("evidence_from_google_calendar") or {}
    raw_ids = panel.get("relevant_raw_ids") or {}
    open_attr = " open" if severity == "Critical" else ""
    event_link = html_link(calendar.get("event_url"), "Open Google Calendar event") if calendar.get("event_url") else '<span class="muted">No Google Calendar event link</span>'
    suppressed_note = ""
    if item.get("suppressed"):
        suppression = item.get("suppression") or {}
        suppressed_note = f'<div class="suppression-note">{badge("Suppressed", "info")} {html_text(suppression.get("reason"), 320)}</div>'
    return f"""
<details class="evidence-panel {severity_class(severity)}"{open_attr}>
  <summary>
    {badge(severity, severity_class(severity))}
    <span class="issue-summary">{html_text(item.get('message'), 360)}</span>
  </summary>
  {suppressed_note}
  <div class="evidence-grid">
    <section>
      <h4>Issue</h4>
      <p><strong>Code:</strong> <code>{html_text(item.get('code'), 120)}</code></p>
      <p><strong>Episode:</strong> {html_text(short_date(item.get('episode_time')), 140)}</p>
      <p><strong>Production stage:</strong> {html_text((item.get('production_stage') or {}).get('label'), 160)}</p>
      <p><strong>Stage-adjusted severity:</strong> {badge(item.get('stage_adjusted_severity') or severity, severity_class(item.get('stage_adjusted_severity') or severity))} <span class="muted">Base audit severity: {html_text(item.get('base_severity') or severity, 80)}</span></p>
      <p class="muted">{html_text(item.get('stage_severity_reason'), 360)}</p>
      <p><strong>Confidence:</strong> {html_text(item.get('confidence_label') or item.get('confidence'), 120)}</p>
      <p class="muted">{html_text(item.get('confidence_explanation'), 320)}</p>
      <p><strong>Trust category:</strong> {badge(trust.get('category'), manager_status_class(trust.get('category')))} <span class="muted">{html_text(trust.get('dashboard_bucket'), 120)}</span></p>
      <p><strong>Jessie should verify:</strong> {html_text(trust.get('what_jessie_should_verify'), 360)}</p>
      <p><strong>Operator recommendation:</strong> {badge((item.get('operator_recommendation') or {}).get('category'), manager_status_class((item.get('operator_recommendation') or {}).get('category')))} {html_text((item.get('operator_recommendation') or {}).get('reason'), 280)}</p>
      <p><strong>Future autofix:</strong> {badge((item.get('autofix') or {}).get('classification'), manager_status_class((item.get('autofix') or {}).get('classification')))} {html_text((item.get('autofix') or {}).get('reason'), 280)}</p>
      <p><strong>Recommended action:</strong> {html_text(item.get('recommended_action'), 360)}</p>
    </section>
    <section>
      <h4>Difference Detected</h4>
      <p>{html_text(panel.get('difference_detected'), 520)}</p>
      <h4>Why This Matters</h4>
      <p>{html_text(panel.get('why_this_matters_operationally'), 520)}</p>
    </section>
    <section>
      <h4>HighLevel Evidence</h4>
      <p><strong>Episode:</strong> {html_text(highlevel.get('episode_date_time'), 120)}</p>
      <p><strong>Active guests:</strong></p>
      {render_guest_list(highlevel.get('active_guests') or [])}
      <p><strong>Ignored guests:</strong></p>
      {render_guest_list(highlevel.get('inactive_or_non_actionable_guests_ignored') or [])}
    </section>
    <section>
      <h4>Google Calendar Evidence</h4>
      <p><strong>Event:</strong> {html_text(calendar.get('title') or 'Missing', 240)}</p>
      <p><strong>Start/end:</strong> {html_text(calendar.get('start'), 120)} to {html_text(calendar.get('end'), 120)}</p>
      <p>{event_link}</p>
      <p><strong>Attendees:</strong></p>
      {render_attendee_list(calendar.get('attendee_emails') or [])}
    </section>
    <section>
      <h4>Relevant Raw IDs</h4>
      {render_raw_ids(raw_ids)}
    </section>
    <section>
      <h4>Source JSON</h4>
      {render_source_files(panel.get('source_json_files') or [])}
    </section>
  </div>
</details>
"""


def render_issue_group_sections(issues, heading="Issues By Episode"):
    issue_groups = grouped_issues_by_episode(issues)
    grouped_sections = [f"<h2>{html_escape(heading)}</h2>"]
    if not issue_groups:
        grouped_sections.append('<p class="muted">No issues found.</p>')
        return "\n".join(grouped_sections)
    for episode_time, group in issue_groups.items():
        grouped_sections.append(
            f'<section class="issue-group">'
            f"<h3>{html_text(short_date(episode_time), 160)}</h3>"
            f"{''.join(render_issue_panel(item) for item in group)}"
            "</section>"
        )
    return "\n".join(grouped_sections)


def render_episode_cards(episodes):
    if not episodes:
        return '<p class="muted">No episodes audited.</p>'
    cards = []
    for episode in sorted(episodes, key=episode_sort_key):
        readiness = episode_readiness(episode)
        counts = issue_counts_for_episode(episode)
        health = episode.get("production_health", {})
        first_issue = sorted(episode.get("issues") or [], key=issue_sort_key)[0] if episode.get("issues") else None
        next_action = first_issue.get("recommended_action") if first_issue else "No active issue. Monitor normally."
        event_link = html_link(episode.get("calendar_event_url"), "Open calendar event") if episode.get("calendar_event_url") else ""
        cards.append(
            '<article class="episode-card">'
            f'<div class="episode-card-top">{badge(readiness, readiness_class(readiness))}<span class="score {health_class(health.get("score"))}">{html_escape(health.get("score", "n/a"))}</span></div>'
            f"<h3>{html_text(short_date(episode.get('episode_time')), 160)}</h3>"
            f"<p><strong>{html_text(episode.get('show_name'), 120)}</strong></p>"
            f"<p>{html_text(', '.join(guest_names(episode.get('active_guests'))), 320)}</p>"
            f"<p class=\"muted\">Issues: {counts.get('Critical', 0)} Critical, {counts.get('Warning', 0)} Warning, {counts.get('Informational', 0)} Informational</p>"
            f"<p><strong>Next action:</strong> {html_text(next_action, 320)}</p>"
            f"<p>{event_link}</p>"
            "</article>"
        )
    return '<section class="episode-card-grid">' + "".join(cards) + "</section>"


def render_next_actions(report, limit=5):
    issues = [item for item in report.get("issues", []) if item.get("severity") in {"Critical", "Warning"}]
    if not issues:
        return '<p class="muted">No Critical or Warning next actions.</p>'
    items = []
    for item in sorted(issues, key=issue_sort_key)[:limit]:
        items.append(
            "<li>"
            f"{badge(item.get('severity'), severity_class(item.get('severity')))} "
            f"<strong>{html_text(short_date(item.get('episode_time')), 160)}:</strong> "
            f"{html_text(item.get('recommended_action'), 360)}"
            "</li>"
        )
    return "<ol>" + "".join(items) + "</ol>"


def render_change_summary(change_summary):
    if not change_summary or not change_summary.get("available"):
        return f"<p class=\"muted\">{html_text((change_summary or {}).get('message') or 'No previous audit file exists yet.', 240)}</p>"
    delta = change_summary.get("severity_count_delta") or {}
    health_delta = change_summary.get("health_score_delta")
    return (
        '<div class="card">'
        f"<p><strong>Previous audit:</strong> {html_text(change_summary.get('previous_generated_at'), 140)}</p>"
        f"<p><strong>Health score delta:</strong> {html_text('n/a' if health_delta is None else health_delta, 60)}</p>"
        f"<p><strong>Issue delta:</strong> Critical {delta.get('Critical', 0):+}, Warning {delta.get('Warning', 0):+}, Informational {delta.get('Informational', 0):+}</p>"
        f"<p><strong>New issues:</strong> {len(change_summary.get('new_issues') or [])}; "
        f"<strong>Resolved issues:</strong> {len(change_summary.get('resolved_issues') or [])}; "
        f"<strong>Continuing issues:</strong> {len(change_summary.get('continuing_issues') or [])}; "
        f"<strong>Suppressed delta:</strong> {change_summary.get('suppressed_issue_delta', 0):+}</p>"
        "</div>"
    )


def render_html(report):
    counts = report["severity_counts"]
    suppressed_count = report.get("suppressed_issue_count", len(report.get("suppressed_issues") or []))
    overall = report.get("overall_production_health") or {}
    score = overall.get("score")
    summary = report.get("executive_summary") or build_executive_summary(report)
    fix_first = summary.get("what_should_be_fixed_first") or {}
    change_summary = report.get("change_summary") or {}
    ready_label = "Ready" if counts.get("Critical", 0) == 0 else "Not ready"
    ready_class = "ready" if ready_label == "Ready" else "critical"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reveting Operations Audit Report</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #667085;
      --line: #d9dee8;
      --critical: #b42318;
      --critical-bg: #fff1f0;
      --warning: #946200;
      --warning-bg: #fff7d6;
      --info: #175cd3;
      --info-bg: #eef4ff;
      --ready: #067647;
      --ready-bg: #ecfdf3;
      --shadow: 0 14px 35px rgba(23, 32, 51, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, #e8f1ff 0, transparent 32rem), var(--bg);
      color: var(--ink);
      font: 15px/1.45 "Avenir Next", "Helvetica Neue", Arial, sans-serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 36px 24px 56px; }}
    header.hero {{
      background: linear-gradient(135deg, #172033 0%, #27466f 100%);
      color: white;
      border-radius: 26px;
      padding: 30px;
      box-shadow: var(--shadow);
    }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: clamp(30px, 4vw, 48px); letter-spacing: -0.04em; }}
    h2 {{ font-size: 23px; margin: 28px 0 14px; }}
    h3 {{ font-size: 17px; margin: 22px 0 10px; }}
    .subtitle {{ color: rgba(255,255,255,0.78); margin-top: 8px; }}
    .cards {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin-top: 22px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 20px; padding: 18px; box-shadow: var(--shadow); }}
    .hero .card {{ background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.18); color: white; box-shadow: none; }}
    .metric {{ font-size: 34px; font-weight: 800; letter-spacing: -0.04em; }}
    .label {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
    .hero .label {{ color: rgba(255,255,255,0.72); }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .summary-card {{ min-height: 150px; }}
    .summary-card strong {{ display: block; margin-bottom: 8px; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .badge.critical, .score.critical {{ color: var(--critical); background: var(--critical-bg); }}
    .badge.warning, .score.warning {{ color: var(--warning); background: var(--warning-bg); }}
    .badge.info, .score.info {{ color: var(--info); background: var(--info-bg); }}
    .badge.ready, .score.ready {{ color: var(--ready); background: var(--ready-bg); }}
    .score {{ display: inline-block; border-radius: 12px; padding: 5px 10px; font-weight: 800; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border-radius: 18px; overflow: hidden; box-shadow: var(--shadow); }}
    th, td {{ text-align: left; vertical-align: top; padding: 12px 13px; border-bottom: 1px solid var(--line); }}
    th {{ background: #f0f3f8; color: #344054; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
    tr:last-child td {{ border-bottom: 0; }}
    .muted {{ color: var(--muted); }}
    .issue-group {{ margin-top: 18px; }}
    .episode-card-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .episode-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 20px; padding: 18px; box-shadow: var(--shadow); }}
    .episode-card-top {{ display: flex; justify-content: space-between; gap: 10px; align-items: center; }}
    .evidence-panel {{ background: var(--panel); border: 1px solid var(--line); border-left-width: 7px; border-radius: 18px; margin: 12px 0; box-shadow: var(--shadow); overflow: hidden; }}
    .evidence-panel.critical {{ border-left-color: var(--critical); }}
    .evidence-panel.warning {{ border-left-color: var(--warning); }}
    .evidence-panel.info {{ border-left-color: var(--info); }}
    .evidence-panel.ready {{ border-left-color: var(--ready); }}
    .evidence-panel summary {{ cursor: pointer; list-style: none; padding: 16px 18px; display: flex; gap: 10px; align-items: center; }}
    .evidence-panel summary::-webkit-details-marker {{ display: none; }}
    .issue-summary {{ font-weight: 700; }}
    .evidence-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; padding: 0 18px 18px; }}
    .evidence-grid section {{ background: #fbfcff; border: 1px solid var(--line); border-radius: 14px; padding: 14px; }}
    .evidence-grid h4 {{ margin: 0 0 8px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: #475467; }}
    .suppression-note {{ margin: 0 18px 14px; padding: 10px 12px; background: var(--info-bg); border-radius: 12px; color: var(--info); }}
    dl {{ display: grid; grid-template-columns: 160px 1fr; gap: 8px 12px; }}
    dt {{ color: var(--muted); font-weight: 700; }}
    dd {{ margin: 0; }}
    code {{ background: #eef1f7; border-radius: 7px; padding: 2px 5px; }}
    a {{ color: var(--info); font-weight: 700; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .footer {{ margin-top: 28px; color: var(--muted); font-size: 13px; }}
    @media (max-width: 920px) {{
      .cards, .summary-grid, .episode-card-grid, .evidence-grid {{ grid-template-columns: 1fr 1fr; }}
      main {{ padding: 22px 14px 36px; }}
      table {{ display: block; overflow-x: auto; }}
    }}
    @media (max-width: 620px) {{
      .cards, .summary-grid, .episode-card-grid, .evidence-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="hero">
      <h1>Operations Audit Report</h1>
      <p class="subtitle">Generated {html_text(report.get('generated_at'), 100)}. Read-only audit of {html_text(report.get('calendar_id'), 120)}.</p>
      <div class="cards">
        <div class="card">
          <div class="metric">{html_escape('n/a' if score is None else score)}</div>
          <div class="label">Production health: {html_text(overall.get('label'), 120)}</div>
        </div>
        <div class="card">
          <div class="metric">{html_escape(report.get('episodes_audited'))}</div>
          <div class="label">Episodes audited</div>
        </div>
        <div class="card">
          <div class="metric">{counts.get('Critical', 0)}</div>
          <div class="label">Critical issues</div>
        </div>
        <div class="card">
          <div class="metric">{counts.get('Warning', 0)}</div>
          <div class="label">Warnings</div>
        </div>
        <div class="card">
          <div class="metric">{suppressed_count}</div>
          <div class="label">Suppressed issues</div>
        </div>
      </div>
    </header>

    <h2>Executive Summary</h2>
    <section class="summary-grid">
      <div class="card summary-card">
        <strong>{badge('Ready', 'ready')}</strong>
        <div>{html_text(summary.get('what_is_ready'), 360)}</div>
      </div>
      <div class="card summary-card">
        <strong>{badge(ready_label, ready_class)}</strong>
        <div>{html_text(summary.get('what_needs_action'), 360)}</div>
        <div class="muted">{html_text(summary.get('suppressed_issue_summary'), 180)}</div>
      </div>
      <div class="card summary-card">
        <strong>{badge('Fix first', severity_class(fix_first.get('severity')))}</strong>
        <div><strong>{html_text(fix_first.get('issue'), 320)}</strong></div>
        <div class="muted">{html_text(fix_first.get('recommended_action'), 360)}</div>
      </div>
    </section>

    <h2>Recommended Next Actions</h2>
    <section class="card">
      {render_next_actions(report)}
    </section>

    <h2>What Changed Since Last Audit</h2>
    {render_change_summary(change_summary)}

    <h2>Episode Cards</h2>
    {render_episode_cards(report.get('episodes') or [])}

    <h2>Episode Table</h2>
    <table>
      <thead>
        <tr>
          <th>Status</th>
          <th>Episode</th>
          <th>Show</th>
          <th>Guests</th>
          <th>Pairing</th>
          <th>Health</th>
          <th>Calendar event</th>
          <th>C / W / I</th>
          <th>Event ID</th>
        </tr>
      </thead>
      <tbody>{render_episode_rows(report.get('episodes') or [])}</tbody>
    </table>

    {render_issue_group_sections(report.get('issues') or [], heading='Issues By Episode')}

    {render_issue_group_sections(report.get('suppressed_issues') or [], heading='Suppressed Issues')}

    <h2>All Issues</h2>
    <table class="issues">
      <thead><tr><th>Severity</th><th>Code</th><th>Show</th><th>Episode</th><th>Issue</th><th>Recommended action</th></tr></thead>
      <tbody>{render_issue_rows(report.get('issues') or [])}</tbody>
    </table>

    <p class="footer">Mode: read-only. No Google Calendar, HighLevel, or email changes were made.</p>
  </main>
</body>
</html>
"""


def manager_status_class(status):
    return {
        "Ready": "ready",
        "Needs Attention": "warning",
        "Blocked": "critical",
        "Complete": "ready",
        "Incomplete": "critical",
        "Unknown": "info",
        "Not Applicable": "muted-badge",
        "Upcoming": "info",
        "In Progress": "warning",
        "Fix First": "critical",
        "Fix Today": "warning",
        "Urgent Review": "critical",
        "Due Soon": "warning",
        "Blocked by Guest": "warning",
        "Blocked by Confirmation": "critical",
        "Ready to Create": "warning",
        "Needs Replacement Guest": "critical",
        "Not Due Yet": "info",
        "Monitor": "info",
        "No Action Needed": "ready",
        "Present": "ready",
        "Confirmed": "ready",
        "Human-confirmed active": "ready",
        "Known Exception": "info",
        "Needs Verification": "warning",
        "Missing": "critical",
        "Safe to autofix": "ready",
        "Needs approval": "warning",
        "Never autofix": "critical",
        "Due now": "warning",
        "Overdue": "critical",
        "Not yet due": "info",
        "Not applicable": "muted-badge",
        "Unknown due date": "info",
        "Missing Configuration": "warning",
        "No Discovery Data": "warning",
        "Partial Audit": "warning",
        "Confirmed Issue": "critical",
        "Confirmed Issues": "critical",
        "Needs Human Verification": "warning",
        "Needs Verification": "warning",
        "Known Exception": "info",
        "Known Exceptions": "info",
        "Known Calendar Ownership Exception": "info",
        "Human Confirmed Active": "ready",
        "Waiting on Someone": "warning",
        "Waiting on Guest": "warning",
        "Waiting on Guest Topics": "warning",
        "Waiting on Client": "warning",
        "Waiting on Internal Team": "warning",
        "Needs Human Follow-Up": "warning",
        "Needs Guest Replacement": "critical",
        "Not Due Yet": "info",
        "Ready for Safe Action Later": "ready",
        "Future Safe Actions": "ready",
        "Completed and verified": "ready",
        "Completed but not verified": "warning",
        "Still open": "critical",
        "Needs human review": "warning",
        "low": "ready",
        "medium": "warning",
        "high": "critical",
    }.get(status, "info")


def render_manager_issue_list(issues, empty_label):
    if not issues:
        return f'<p class="muted">{html_escape(empty_label)}</p>'
    items = []
    for item in sorted(issues, key=manager_issue_sort_key):
        recommendation = item.get("operator_recommendation") or {}
        autofix = item.get("autofix") or {}
        event_url = item.get("evidence_panel", {}).get("evidence_from_google_calendar", {}).get("event_url")
        event_link = f" {html_link(event_url, 'Calendar')}" if event_url else ""
        severity = effective_issue_severity(item)
        base_note = ""
        if item.get("base_severity") and item.get("base_severity") != severity:
            base_note = f"; base audit severity: {item.get('base_severity')}"
        items.append(
            "<li>"
            f"{badge(severity, severity_class(severity))} "
            f"{badge(recommendation.get('category', 'Monitor'), manager_status_class(recommendation.get('category', 'Monitor')))} "
            f"<strong>{html_text(short_date(item.get('episode_time')), 140)}</strong> "
            f"{html_text(item.get('message'), 320)} "
            f"<span class=\"muted\">Confidence: {html_text(item.get('confidence_label'), 80)}; Autofix: {html_text(autofix.get('classification'), 80)}{html_text(base_note, 120)}</span>"
            f"<span class=\"muted\">{html_text(item.get('stage_severity_reason'), 260)}</span>"
            f"{event_link}"
            "</li>"
        )
    return "<ul class=\"manager-issue-list\">" + "".join(items) + "</ul>"


def render_trust_finding_list(findings, empty_label):
    if not findings:
        return f'<p class="muted">{html_escape(empty_label)}</p>'
    items = []
    for finding in sorted(
        findings,
        key=lambda item: (
            SEVERITY_ORDER.get(item.get("severity"), 9),
            item.get("episode") or "",
            item.get("show") or "",
            item.get("issue_code") or "",
        ),
    ):
        calendar = finding.get("evidence_from_google_calendar") or {}
        event_url = calendar.get("event_url")
        event_link = f" {html_link(event_url, 'Calendar')}" if event_url else ""
        automation_label = f"automation: {finding.get('future_automation_candidate')}"
        automation_class = manager_status_class(
            "Future Safe Actions" if finding.get("future_automation_candidate") == "yes" else "Never autofix"
        )
        source_files = finding.get("source_json_files") or []
        source_note = ""
        if source_files:
            source_note = f"<span class=\"muted\">Source: {html_text(source_files[0].get('path'), 140)}</span>"
        items.append(
            "<li>"
            f"{badge(finding.get('category'), manager_status_class(finding.get('category')))} "
            f"{badge(finding.get('severity'), severity_class(finding.get('severity')))} "
            f"{badge(automation_label, automation_class)} "
            f"<strong>{html_text(short_date(finding.get('episode')), 140)}</strong> "
            f"{html_text(finding.get('show'), 120)} - {html_text(finding.get('guest'), 220)}"
            f"<span>{html_text(finding.get('issue'), 360)}</span>"
            f"<span class=\"muted\">Operational status: {html_text(finding.get('operational_status'), 180)}</span>"
            f"<span class=\"muted\">Why flagged: {html_text(finding.get('why_it_was_flagged'), 360)}</span>"
            f"<span class=\"muted\">Verify: {html_text(finding.get('what_jessie_should_verify'), 360)}</span>"
            f"<span class=\"muted\">Action: {html_text(finding.get('recommended_human_action'), 360)}</span>"
            f"<span class=\"muted\">Risk: {html_text(finding.get('automation_risk_level'), 60)}; Approval: {html_text(finding.get('approval_required_before_action'), 260)}</span>"
            f"{source_note}{event_link}"
            "</li>"
        )
    return "<ul class=\"manager-issue-list\">" + "".join(items) + "</ul>"


def calendar_export_window(report):
    configured = report.get("calendar_export_window")
    if isinstance(configured, dict):
        return {
            "time_min": configured.get("time_min"),
            "time_max": configured.get("time_max"),
            "event_count": configured.get("event_count"),
            "has_explicit_window": configured.get("has_explicit_window"),
        }
    calendar_path = Path(report.get("calendar_events_path") or "")
    payload = read_json(calendar_path, default={}) if calendar_path.exists() else {}
    return {
        "time_min": payload.get("time_min"),
        "time_max": payload.get("time_max"),
        "event_count": payload.get("event_count"),
        "has_explicit_window": bool(payload.get("time_min") or payload.get("time_max")),
    }


def critical_review_active_guest_names(issue):
    highlevel = issue.get("evidence_from_highlevel") or {}
    guests = highlevel.get("active_guests") or []
    if guests:
        return [guest.get("name") or guest.get("email") or "Unknown guest" for guest in guests]
    evidence = issue.get("evidence") or {}
    return evidence.get("guest_names") or []


def critical_review_active_guest_summary(issue):
    highlevel = issue.get("evidence_from_highlevel") or {}
    guests = highlevel.get("active_guests") or []
    summary = []
    for guest in guests:
        summary.append(
            {
                "name": guest.get("name"),
                "email": guest.get("email"),
                "status": guest.get("status"),
                "appointment_id": guest.get("appointment_id"),
                "contact_id": guest.get("contact_id"),
                "form_submission_ids": guest.get("form_submission_ids") or [],
            }
        )
    return summary


def critical_review_calendar_summary(issue):
    calendar = issue.get("evidence_from_google_calendar") or {}
    return {
        "event_found": bool(calendar.get("event_found")),
        "event_id": calendar.get("event_id"),
        "title": calendar.get("title"),
        "start": calendar.get("start"),
        "end": calendar.get("end"),
        "attendee_emails": calendar.get("attendee_emails") or [],
        "event_url": calendar.get("event_url"),
    }


def build_critical_review(report):
    window = calendar_export_window(report)
    export_min = parse_datetime(window.get("time_min"))
    export_max = parse_datetime(window.get("time_max"))
    reviews = []
    critical_issues = [
        item
        for item in report.get("issues", [])
        if effective_issue_severity(item) == "Critical"
    ]
    for issue in sorted(critical_issues, key=issue_sort_key):
        issue_time = parse_datetime(issue.get("episode_time"))
        highlevel = issue.get("evidence_from_highlevel") or {}
        calendar = critical_review_calendar_summary(issue)
        active_guests = highlevel.get("active_guests") or []
        ignored_guests = highlevel.get("inactive_or_non_actionable_guests_ignored") or []
        active_statuses = sorted({guest.get("status") or "unknown" for guest in active_guests})
        ignored_statuses = sorted({guest.get("status") or "unknown" for guest in ignored_guests})
        stage = issue.get("production_stage") or {}
        days_until_show = stage.get("days_until_show")
        outside_export = bool(issue_time and export_max and issue_time > export_max)
        before_export = bool(issue_time and export_min and issue_time < export_min)
        far_out = isinstance(days_until_show, (int, float)) and days_until_show >= 30
        code = issue.get("code")

        real_problem = "Yes"
        downgrade = "No downgrade recommended from the current evidence."
        status_logic = "No cancellation/reschedule false positive detected."
        config_improvement = "No rule change required from this issue alone."

        if ignored_guests:
            status_logic = (
                "Cancellation/status filtering is active. Ignored guest status(es): "
                f"{', '.join(ignored_statuses)}. Active guest status(es): {', '.join(active_statuses) or 'unknown'}."
            )
        elif active_statuses:
            status_logic = f"Active guest status(es): {', '.join(active_statuses)}."

        if outside_export or before_export:
            real_problem = "Unclear"
            downgrade = (
                "Downgrade candidate: the episode is outside the loaded Google Calendar export window, "
                "so the audit cannot prove the calendar event is missing."
            )
            config_improvement = (
                "Add an audit preflight that compares HighLevel episode times with the Google Calendar export window "
                "and reports out-of-range episodes as export coverage issues instead of Critical missing-calendar issues."
            )
        elif code == "booking_without_calendar_event" and far_out:
            real_problem = "Likely, but not yet urgent Critical"
            downgrade = (
                "Downgrade candidate: this booking is 30+ days out. Treat as Warning/Monitor until the configured "
                "SOP escalation window, then escalate if still missing."
            )
            config_improvement = (
                "Add a stage-aware severity rule for `booking_without_calendar_event`: Warning or Monitor at 30+ days, "
                "Critical inside the 14-day or 7-day production window."
            )
        elif code == "booking_without_calendar_event":
            real_problem = "Yes, if the HighLevel booking remains confirmed."
            config_improvement = (
                "Keep this Critical for near-term confirmed bookings, but improve replacement display when canceled and active guests share a slot."
                if ignored_guests
                else "Keep this Critical for near-term confirmed bookings."
            )
        elif code == "guest_email_not_invited":
            real_problem = "Yes, if the active HighLevel guest is still expected on the episode."
            if ignored_guests:
                status_logic += " The ignored canceled guest is not the missing invitee."
            config_improvement = (
                "If the guest was intentionally removed, cancel/reschedule the HighLevel appointment or add a known-exception suppression. "
                "Otherwise keep active guest invite omissions Critical."
            )

        reviews.append(
            {
                "show_name": issue.get("show_name"),
                "show_key": issue.get("show_key"),
                "episode_time": issue.get("episode_time"),
                "episode_time_display": short_date(issue.get("episode_time")),
                "guest_names": critical_review_active_guest_names(issue),
                "issue_code": code,
                "severity": effective_issue_severity(issue),
                "production_stage": stage,
                "highlevel_evidence": {
                    "active_guests": critical_review_active_guest_summary(issue),
                    "ignored_guests": ignored_guests,
                    "expected_calendar_start": highlevel.get("expected_calendar_start"),
                    "expected_calendar_end": highlevel.get("expected_calendar_end"),
                },
                "google_calendar_evidence": calendar,
                "difference_detected": issue.get("difference_detected"),
                "why_critical": issue.get("why_this_matters_operationally") or issue.get("stage_severity_reason"),
                "real_operational_problem": real_problem,
                "cancellation_or_status_logic": status_logic,
                "recommended_human_action": issue.get("recommended_action"),
                "recommended_rule_or_config_improvement": config_improvement,
                "downgrade_assessment": downgrade,
                "calendar_export_window": window,
                "relevant_raw_ids": issue.get("relevant_raw_ids") or {},
                "confidence": issue.get("confidence_label") or issue.get("confidence"),
            }
        )
    return reviews


def render_critical_review_html(reviews):
    if not reviews:
        return '<p class="muted">No Critical issues to review.</p>'
    cards = []
    for item in reviews:
        highlevel = item.get("highlevel_evidence") or {}
        calendar = item.get("google_calendar_evidence") or {}
        active_guests = highlevel.get("active_guests") or []
        guest_items = []
        for guest in active_guests:
            guest_items.append(
                "<li>"
                f"<strong>{html_text(guest.get('name') or 'Unknown guest', 120)}</strong> "
                f"{html_email(guest.get('email')) if guest.get('email') else ''} "
                f"<span class=\"muted\">status: {html_text(guest.get('status'), 80)}; "
                f"appointment: <code>{html_text(guest.get('appointment_id'), 120)}</code></span>"
                "</li>"
            )
        calendar_event = (
            f"{html_text(calendar.get('title'), 220)} "
            f"{html_link(calendar.get('event_url'), 'Open event') if calendar.get('event_url') else ''}"
            if calendar.get("event_found")
            else "No matching Google Calendar event found in the loaded export."
        )
        cards.append(
            "<article class=\"card\">"
            f"<h3>{html_text(item.get('show_name'), 160)} · {html_text(item.get('episode_time_display'), 160)}</h3>"
            f"<p>{badge(item.get('severity'), severity_class(item.get('severity')))} "
            f"<code>{html_text(item.get('issue_code'), 120)}</code> "
            f"<span class=\"muted\">Confidence: {html_text(item.get('confidence'), 100)}</span></p>"
            f"<p><strong>Guests:</strong> {html_text(', '.join(item.get('guest_names') or []), 260)}</p>"
            f"<p><strong>HighLevel:</strong> expected calendar block {html_text(highlevel.get('expected_calendar_start'), 120)} to {html_text(highlevel.get('expected_calendar_end'), 120)}.</p>"
            f"<ul>{''.join(guest_items) or '<li>No active guest evidence.</li>'}</ul>"
            f"<p><strong>Google Calendar:</strong> {calendar_event}</p>"
            f"<p><strong>Why Critical:</strong> {html_text(item.get('why_critical'), 360)}</p>"
            f"<p><strong>Real operational problem?</strong> {html_text(item.get('real_operational_problem'), 180)}</p>"
            f"<p><strong>Status/cancellation logic:</strong> {html_text(item.get('cancellation_or_status_logic'), 360)}</p>"
            f"<p><strong>Human action:</strong> {html_text(item.get('recommended_human_action'), 420)}</p>"
            f"<p><strong>Rule/config improvement:</strong> {html_text(item.get('recommended_rule_or_config_improvement'), 460)}</p>"
            f"<p><strong>Downgrade assessment:</strong> {html_text(item.get('downgrade_assessment'), 460)}</p>"
            "</article>"
        )
    return "<section class=\"manager-card-grid\">" + "".join(cards) + "</section>"


def render_critical_review_markdown(reviews):
    lines = [
        "# Critical Issues Review",
        "",
        "Read-only review of the current all-shows audit Critical issues. No HighLevel, Google Calendar, Gmail, email, appointment, event, or attendee changes were made.",
        "",
        f"- Critical issues reviewed: {len(reviews)}",
        "",
    ]
    for index, item in enumerate(reviews, 1):
        highlevel = item.get("highlevel_evidence") or {}
        calendar = item.get("google_calendar_evidence") or {}
        lines.extend(
            [
                f"## {index}. {item.get('show_name')} - {item.get('episode_time_display')}",
                "",
                f"- Show name: {item.get('show_name')}",
                f"- Episode date/time: {item.get('episode_time')}",
                f"- Guest name(s): {', '.join(item.get('guest_names') or [])}",
                f"- Issue code: `{item.get('issue_code')}`",
                f"- Confidence: {item.get('confidence')}",
                "",
                "### Evidence From HighLevel",
                "",
                f"- Expected calendar block: {highlevel.get('expected_calendar_start')} to {highlevel.get('expected_calendar_end')}",
            ]
        )
        for guest in highlevel.get("active_guests") or []:
            form_ids = ", ".join(guest.get("form_submission_ids") or []) or "none"
            lines.append(
                f"- Active guest: {guest.get('name')} <{guest.get('email')}>; status `{guest.get('status')}`; appointment `{guest.get('appointment_id')}`; contact `{guest.get('contact_id')}`; form submissions: {form_ids}"
            )
        ignored = highlevel.get("ignored_guests") or []
        if ignored:
            for guest in ignored:
                lines.append(
                    f"- Ignored/non-actionable guest: {guest.get('name')} <{guest.get('email')}>; status `{guest.get('status')}`; appointment `{guest.get('appointment_id')}`"
                )
        else:
            lines.append("- Ignored/non-actionable guests: none")
        lines.extend(["", "### Evidence From Google Calendar", ""])
        if calendar.get("event_found"):
            attendees = ", ".join(calendar.get("attendee_emails") or []) or "none"
            lines.extend(
                [
                    "- Event found: yes",
                    f"- Event title: {calendar.get('title')}",
                    f"- Event start/end: {calendar.get('start')} to {calendar.get('end')}",
                    f"- Attendees: {attendees}",
                    f"- Event ID: `{calendar.get('event_id')}`",
                    f"- Event URL: {calendar.get('event_url')}",
                ]
            )
        else:
            window = item.get("calendar_export_window") or {}
            lines.extend(
                [
                    "- Event found: no matching event in the loaded Google Calendar export",
                    f"- Export window: {window.get('time_min')} to {window.get('time_max')}",
                ]
            )
        lines.extend(
            [
                "",
                "### Assessment",
                "",
                f"- Difference detected: {item.get('difference_detected')}",
                f"- Why it is Critical: {item.get('why_critical')}",
                f"- Real operational problem: {item.get('real_operational_problem')}",
                f"- Cancellation/reschedule/status logic: {item.get('cancellation_or_status_logic')}",
                f"- Recommended human action: {item.get('recommended_human_action')}",
                f"- Recommended rule/config improvement: {item.get('recommended_rule_or_config_improvement')}",
                f"- Downgrade assessment: {item.get('downgrade_assessment')}",
                "",
            ]
        )
    return "\n".join(lines)


def render_checklist(checklist):
    if not checklist:
        return '<p class="muted">No checklist configured.</p>'
    items = []
    for item in checklist:
        status = item.get("status")
        items.append(
            "<li>"
            f"{badge(status, manager_status_class(status))} "
            f"{badge(item.get('due_label'), manager_status_class(item.get('due_label')))} "
            f"<strong>{html_text(item.get('label'), 160)}</strong>"
            f"<span class=\"muted\">{html_text(item.get('reason'), 260)}</span>"
            f"<span class=\"muted\">{html_text(item.get('due_reason'), 260)}</span>"
            "</li>"
        )
    return "<ul class=\"checklist\">" + "".join(items) + "</ul>"


def render_timeline(timeline):
    if not timeline:
        return '<p class="muted">No timeline configured.</p>'
    items = []
    for item in timeline:
        status = item.get("status")
        items.append(
            "<li>"
            f"<span class=\"timeline-dot {manager_status_class(status)}\"></span>"
            f"<div><strong>{html_text(item.get('label'), 160)}</strong>"
            f"<br>{badge(status, manager_status_class(status))} "
            f"<span class=\"muted\">{html_text(item.get('reason'), 240)}</span></div>"
            "</li>"
        )
    return "<ol class=\"timeline\">" + "".join(items) + "</ol>"


def render_progress_bar(value):
    try:
        percentage = max(0, min(100, int(value)))
    except (TypeError, ValueError):
        percentage = 0
    return (
        '<div class="progress-wrap">'
        f'<div class="progress-bar" style="width: {percentage}%"></div>'
        "</div>"
    )


def render_checklist_bucket(items, empty_label):
    if not items:
        return f'<p class="muted">{html_escape(empty_label)}</p>'
    return render_checklist(items)


def render_aggregate_checklist_items(items, empty_label):
    if not items:
        return f'<p class="muted">{html_escape(empty_label)}</p>'
    rows = []
    for item in sorted(items, key=lambda value: (value.get("episode_time") or "", value.get("checklist_label") or ""))[:40]:
        due_label = checklist_due_label(item.get("due_state"))
        rows.append(
            "<li>"
            f"{badge(item.get('status'), manager_status_class(item.get('status')))} "
            f"{badge(due_label, manager_status_class(due_label))} "
            f"<strong>{html_text(item.get('episode_time_display'), 140)}</strong> "
            f"{html_text(item.get('checklist_label'), 180)} "
            f"<span class=\"muted\">{html_text(', '.join(item.get('guest_names') or []), 180)}</span>"
            f"<span class=\"muted\">{html_text(item.get('due_reason') or item.get('reason'), 260)}</span>"
            "</li>"
        )
    if len(items) > 40:
        rows.append(f'<li class="muted">Plus {len(items) - 40} more.</li>')
    return '<ul class="manager-issue-list">' + "".join(rows) + "</ul>"


def render_manager_episode_cards(episodes):
    if not episodes:
        return '<p class="muted">No episodes in this section.</p>'
    cards = []
    for episode in episodes:
        status = episode.get("production_status")
        health = episode.get("production_health") or {}
        recommendation = episode.get("operator_recommendation") or {}
        stage = episode.get("production_stage") or {}
        readiness = episode.get("readiness_percentage")
        event_link = html_link(episode.get("calendar_event_url"), "Open calendar event") if episode.get("calendar_event_url") else ""
        cards.append(
            '<article class="manager-episode-card">'
            '<div class="episode-card-top">'
            f"{badge(status, manager_status_class(status))}"
            f"<span class=\"score {health_class(health.get('score'))}\">{html_escape(health.get('score', 'n/a'))}</span>"
            "</div>"
            f"<h3>{html_text(episode.get('episode_time_display'), 160)}</h3>"
            f"<p><strong>{html_text(episode.get('show_name'), 120)}</strong></p>"
            f"<p>{html_text(', '.join(episode.get('guest_names') or []), 280)}</p>"
            f"<p>{badge(stage.get('label'), 'info')} <span class=\"muted\">{html_text(stage.get('reason'), 260)}</span></p>"
            f"<p><strong>Readiness:</strong> {html_escape('n/a' if readiness is None else str(readiness) + '%')} {render_progress_bar(readiness)}</p>"
            f"<p>{badge(recommendation.get('category'), manager_status_class(recommendation.get('category')))} "
            f"{html_text(recommendation.get('reason'), 300)}</p>"
            f"<p class=\"muted\">Confidence: {html_text((episode.get('confidence') or {}).get('confidence'), 80)}. "
            f"{html_text((episode.get('confidence') or {}).get('reason'), 240)}</p>"
            f"<p>{event_link}</p>"
            "<details>"
            "<summary>Due Now</summary>"
            f"{render_checklist_bucket(episode.get('due_now_checklist') or [], 'No checklist items are due in this stage.')}"
            "</details>"
            "<details>"
            "<summary>Overdue</summary>"
            f"{render_checklist_bucket(episode.get('overdue_checklist') or [], 'No overdue checklist items.')}"
            "</details>"
            "<details>"
            "<summary>Not Yet Due</summary>"
            f"{render_checklist_bucket(episode.get('not_yet_due_checklist') or [], 'No future checklist items remain.')}"
            "</details>"
            "<details>"
            "<summary>Checklist</summary>"
            f"{render_checklist(episode.get('checklist') or [])}"
            "</details>"
            "<details>"
            "<summary>Timeline</summary>"
            f"{render_timeline(episode.get('timeline') or [])}"
            "</details>"
            "</article>"
        )
    return '<section class="manager-card-grid">' + "".join(cards) + "</section>"


def render_manager_episode_table(episodes):
    if not episodes:
        return '<p class="muted">No episodes audited.</p>'
    rows = []
    for episode in sorted(episodes, key=lambda item: item.get("episode_time") or ""):
        health = episode.get("production_health") or {}
        recommendation = episode.get("operator_recommendation") or {}
        confidence = episode.get("confidence") or {}
        counts = episode.get("issue_counts") or {}
        stage = episode.get("production_stage") or {}
        checklist_summary = episode.get("checklist_completion") or {}
        event_link = html_link(episode.get("calendar_event_url"), "Calendar") if episode.get("calendar_event_url") else ""
        rows.append(
            "<tr>"
            f"<td>{badge(episode.get('production_status'), manager_status_class(episode.get('production_status')))}</td>"
            f"<td>{html_text(episode.get('episode_time_display'), 140)}</td>"
            f"<td>{html_text(episode.get('show_name'), 120)}</td>"
            f"<td>{html_text(', '.join(episode.get('guest_names') or []), 260)}</td>"
            f"<td>{badge(stage.get('label'), 'info')}<br><span class=\"muted\">{html_text(stage.get('reason'), 160)}</span></td>"
            f"<td>{html_escape(episode.get('readiness_percentage'))}%<br><span class=\"muted\">{checklist_summary.get('complete_count', 0)} of {checklist_summary.get('required_count', 0)} due items complete</span></td>"
            f"<td><span class=\"score {health_class(health.get('score'))}\">{html_escape('n/a' if health.get('score') is None else health.get('score'))}</span></td>"
            f"<td>{badge(recommendation.get('category'), manager_status_class(recommendation.get('category')))}<br><span class=\"muted\">{html_text(recommendation.get('reason'), 180)}</span></td>"
            f"<td>{html_text(confidence.get('confidence'), 80)}<br><span class=\"muted\">{html_text(confidence.get('reason'), 180)}</span></td>"
            f"<td>{counts.get('Critical', 0)} / {counts.get('Warning', 0)} / {counts.get('Informational', 0)}</td>"
            f"<td>{event_link}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Status</th><th>Episode</th><th>Show</th><th>Guests</th><th>Stage</th><th>Readiness</th><th>Health</th><th>Recommendation</th><th>Confidence</th><th>Stage C/W/I</th><th>Links</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_show_health(health_by_show):
    if not health_by_show:
        return '<p class="muted">No show health data available.</p>'
    rows = []
    for show_key, item in sorted(health_by_show.items(), key=lambda value: value[1].get("show_name", value[0])):
        score = item.get("production_health_score")
        stage_counts = item.get("stage_adjusted_issue_counts") or {}
        rows.append(
            "<tr>"
            f"<td>{html_text(item.get('show_name') or show_key, 160)}</td>"
            f"<td><span class=\"score {health_class(score)}\">{html_escape('n/a' if score is None else score)}</span></td>"
            f"<td>{badge(item.get('operational_status') or operational_status_from_counts(item), manager_status_class(item.get('operational_status') or operational_status_from_counts(item)))}</td>"
            f"<td>{html_text(item.get('production_health_label'), 160)}</td>"
            f"<td>{item.get('episodes_audited', 0)}</td>"
            f"<td>{item.get('ready_episode_count', 0)}</td>"
            f"<td>{item.get('needs_attention_episode_count', 0)}</td>"
            f"<td>{item.get('blocked_episode_count', 0)}</td>"
            f"<td>{item.get('due_now_count', 0)}</td>"
            f"<td>{item.get('overdue_count', 0)}</td>"
            f"<td>{item.get('fix_first_count', 0)}</td>"
            f"<td>{stage_counts.get('Critical', 0)}</td>"
            f"<td>{stage_counts.get('Warning', 0)}</td>"
            f"<td>{stage_counts.get('Informational', 0)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Show</th><th>Health</th><th>Status</th><th>Score Label</th><th>Episodes</th><th>Ready</th><th>Needs Attention</th><th>Blocked</th><th>Due Now</th><th>Overdue</th><th>Fix First</th><th>Critical</th><th>Warnings</th><th>Info</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_configuration_diagnostics(diagnostics):
    if not diagnostics:
        return '<p class="muted">No missing show configuration detected.</p>'
    items = []
    for item in sorted(diagnostics, key=lambda value: value.get("show_name") or value.get("show_key") or ""):
        env_vars = item.get("env_vars") or {}
        missing_files = item.get("missing_files") or []
        file_text = ", ".join(missing_files[:4])
        if len(missing_files) > 4:
            file_text += f", plus {len(missing_files) - 4} more"
        items.append(
            "<li>"
            f"{badge('Missing Configuration', 'warning')} "
            f"<strong>{html_text(item.get('show_name'), 160)}</strong>"
            f"<span>{html_text(item.get('message'), 260)}</span>"
            f"<span><strong>Needed:</strong> {html_text(item.get('what_is_needed'), 320)}</span>"
            f"<span><strong>Env vars:</strong> <code>{html_text(env_vars.get('location_id_env_var'), 120)}</code> <code>{html_text(env_vars.get('token_env_var'), 120)}</code></span>"
            f"<span><strong>Files:</strong> {html_text(file_text or 'No missing files; files are empty.', 360)}</span>"
            f"<span class=\"muted\">{html_text(item.get('how_to_fix'), 420)}</span>"
            "</li>"
        )
    return '<ul class="manager-issue-list">' + "".join(items) + "</ul>"


def render_show_action_groups(show_groups):
    if not show_groups:
        return '<p class="muted">No show groups available.</p>'
    cards = []
    for show_key, group in sorted(show_groups.items(), key=lambda item: item[1].get("show_name") or item[0]):
        diagnostics = group.get("configuration_diagnostics") or []
        cards.append(
            '<article class="manager-episode-card">'
            f"<h3>{html_text(group.get('show_name') or show_key, 180)}</h3>"
            '<div class="show-count-grid">'
            f"<span>{badge('Ready', 'ready')} {group.get('ready_episode_count', 0)}</span>"
            f"<span>{badge('Needs Attention', 'warning')} {group.get('needs_attention_episode_count', 0)}</span>"
            f"<span>{badge('Blocked', 'critical')} {group.get('blocked_episode_count', 0)}</span>"
            f"<span>{badge('Due now', 'warning')} {group.get('due_now_count', 0)}</span>"
            f"<span>{badge('Overdue', 'critical')} {group.get('overdue_count', 0)}</span>"
            f"<span>{badge('Fix First', 'critical')} {group.get('fix_first_count', 0)}</span>"
            "</div>"
            "<details open>"
            "<summary>Upcoming Episodes</summary>"
            f"{render_manager_episode_cards((group.get('upcoming_episodes') or [])[:6])}"
            "</details>"
            "<details>"
            "<summary>Fix First Items</summary>"
            f"{render_manager_issue_list(group.get('fix_first_items') or [], 'No Fix First issues for this show.')}"
            "</details>"
            "<details>"
            "<summary>Due-Now Items</summary>"
            f"{render_aggregate_checklist_items(group.get('due_now_checklist_items') or [], 'No due-now checklist items for this show.')}"
            "</details>"
            "<details>"
            "<summary>Overdue Items</summary>"
            f"{render_aggregate_checklist_items(group.get('overdue_checklist_items') or [], 'No overdue checklist items for this show.')}"
            "</details>"
            "<details>"
            "<summary>Missing Configuration</summary>"
            f"{render_configuration_diagnostics(diagnostics)}"
            "</details>"
            "</article>"
        )
    return '<section class="manager-card-grid show-groups">' + "".join(cards) + "</section>"


def render_trend_issue_briefs(items, empty_label):
    if not items:
        return f'<p class="muted">{html_escape(empty_label)}</p>'
    rows = []
    for item in items[:12]:
        rows.append(
            "<li>"
            f"{badge(item.get('severity'), severity_class(item.get('severity')))} "
            f"<strong>{html_text(short_date(item.get('episode_time')), 120)}</strong> "
            f"<code>{html_text(item.get('code'), 120)}</code> "
            f"{html_text(item.get('message'), 260)}"
            "</li>"
        )
    if len(items) > 12:
        rows.append(f'<li class="muted">Plus {len(items) - 12} more.</li>')
    return '<ul class="manager-issue-list">' + "".join(rows) + "</ul>"


def render_trend_severity_changes(items, empty_label):
    if not items:
        return f'<p class="muted">{html_escape(empty_label)}</p>'
    rows = []
    for item in items[:12]:
        previous = item.get("previous") or {}
        current = item.get("current") or {}
        rows.append(
            "<li>"
            f"<strong>{html_text(short_date(current.get('episode_time') or previous.get('episode_time')), 120)}</strong> "
            f"<code>{html_text(current.get('code') or previous.get('code'), 120)}</code> "
            f"{badge(previous.get('severity'), severity_class(previous.get('severity')))} to "
            f"{badge(current.get('severity'), severity_class(current.get('severity')))} "
            f"{html_text(current.get('message') or previous.get('message'), 260)}"
            "</li>"
        )
    if len(items) > 12:
        rows.append(f'<li class="muted">Plus {len(items) - 12} more.</li>')
    return '<ul class="manager-issue-list">' + "".join(rows) + "</ul>"


def render_trend_detail(trend):
    if not trend or not trend.get("available"):
        return f'<p class="muted">{html_text((trend or {}).get("message") or "No previous audit available.", 240)}</p>'
    delta = trend.get("severity_count_delta") or {}
    return (
        '<div class="trend-grid">'
        f"<div class=\"card\"><strong>Health delta</strong><div class=\"metric small\">{html_text('n/a' if trend.get('health_score_delta') is None else trend.get('health_score_delta'), 60)}</div>"
        f"<p>{'Improved' if trend.get('improved_production_health') else 'No health improvement detected this run.'}</p></div>"
        f"<div class=\"card\"><strong>New issues</strong><div class=\"metric small\">{len(trend.get('new_issues') or [])}</div></div>"
        f"<div class=\"card\"><strong>Resolved issues</strong><div class=\"metric small\">{len(trend.get('resolved_issues') or [])}</div></div>"
        f"<div class=\"card\"><strong>Worsened</strong><div class=\"metric small\">{len(trend.get('worsened_issues') or [])}</div></div>"
        f"<div class=\"card\"><strong>Severity delta</strong><p>Critical {delta.get('Critical', 0):+}, Warning {delta.get('Warning', 0):+}, Info {delta.get('Informational', 0):+}</p></div>"
        "</div>"
        '<div class="trend-detail-grid">'
        f"<section class=\"card\"><h3>New Issue Identities</h3>{render_trend_issue_briefs(trend.get('new_issues') or [], 'No new issue identities.')}</section>"
        f"<section class=\"card\"><h3>Resolved Issue Identities</h3>{render_trend_issue_briefs(trend.get('resolved_issues') or [], 'No resolved issue identities.')}</section>"
        f"<section class=\"card\"><h3>Worsened Issues</h3>{render_trend_severity_changes(trend.get('worsened_issues') or [], 'No issue identities worsened.')}</section>"
        f"<section class=\"card\"><h3>Improved Issues</h3>{render_trend_severity_changes(trend.get('improved_issues') or [], 'No issue identities improved.')}</section>"
        f"<section class=\"card\"><h3>Recently Fixed Items</h3>{render_trend_issue_briefs(trend.get('recently_fixed_items') or [], 'No recently fixed issue identities.')}</section>"
        "</div>"
    )


def render_operations_manager_dashboard_html(dashboard):
    health = dashboard.get("overall_production_health") or {}
    counts = dashboard.get("issue_counts") or {}
    recommendations = dashboard.get("operator_recommendations") or {}
    trust_summary = dashboard.get("trust_summary") or {}
    trust_bucket_counts = trust_summary.get("counts_by_dashboard_bucket") or {}
    completion_tracking = dashboard.get("completion_tracking") or {}
    completion_summary = completion_tracking.get("summary") or {}
    completion_counts = completion_summary.get("counts_by_status") or {}
    score = health.get("score")
    ready_badge = dashboard.get("overall_production_status") or operational_status_from_counts(counts)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reveting Operations Manager</title>
  <style>
    :root {{
      --bg: #f4f1ea;
      --panel: #fffdf8;
      --ink: #18212f;
      --muted: #687083;
      --line: #ded8ca;
      --critical: #b42318;
      --critical-bg: #fff1f0;
      --warning: #946200;
      --warning-bg: #fff7d6;
      --info: #175cd3;
      --info-bg: #edf4ff;
      --ready: #067647;
      --ready-bg: #ecfdf3;
      --shadow: 0 18px 40px rgba(24, 33, 47, 0.09);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: radial-gradient(circle at 12% 0%, #dcecff 0, transparent 34rem), var(--bg); color: var(--ink); font: 15px/1.5 "Avenir Next", "Helvetica Neue", Arial, sans-serif; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 36px 22px 64px; }}
    header {{ background: linear-gradient(135deg, #14213d 0%, #245078 58%, #376f64 100%); color: white; border-radius: 30px; padding: 34px; box-shadow: var(--shadow); }}
    h1 {{ margin: 0; font-size: clamp(34px, 5vw, 58px); letter-spacing: -0.045em; }}
    h2 {{ margin: 34px 0 14px; font-size: 24px; }}
    h3 {{ margin: 12px 0 6px; }}
    .subtitle {{ color: rgba(255,255,255,0.76); margin: 8px 0 0; }}
    .hero-grid, .trend-grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin-top: 24px; }}
    .trend-detail-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 14px; }}
    .task-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin: 12px 0 20px; }}
    .task-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 20px; padding: 16px; box-shadow: var(--shadow); }}
    .task-top {{ display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }}
    .task-top h3 {{ margin-top: 0; }}
    .card, .manager-episode-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 22px; padding: 18px; box-shadow: var(--shadow); }}
    header .card {{ background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.18); color: white; box-shadow: none; }}
    .metric {{ font-size: 36px; font-weight: 850; letter-spacing: -0.045em; }}
    .metric.small {{ font-size: 27px; }}
    .label {{ color: var(--muted); font-size: 13px; }}
    header .label {{ color: rgba(255,255,255,0.7); }}
    .badge {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 10px; font-size: 12px; font-weight: 800; white-space: nowrap; }}
    .badge.critical, .score.critical {{ color: var(--critical); background: var(--critical-bg); }}
    .badge.warning, .score.warning {{ color: var(--warning); background: var(--warning-bg); }}
    .badge.info, .score.info {{ color: var(--info); background: var(--info-bg); }}
    .badge.ready, .score.ready {{ color: var(--ready); background: var(--ready-bg); }}
    .badge.muted-badge {{ color: #667085; background: #eef0f4; }}
    .score {{ display: inline-block; border-radius: 13px; padding: 6px 11px; font-weight: 850; }}
    .progress-wrap {{ height: 10px; border-radius: 999px; background: #e4e7ec; overflow: hidden; margin-top: 6px; }}
    .progress-bar {{ height: 100%; border-radius: inherit; background: linear-gradient(90deg, #2f6f64, #7ba66a); }}
    .manager-card-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
    .show-count-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 12px 0; }}
    .show-groups .manager-card-grid {{ grid-template-columns: 1fr; }}
    .episode-card-top {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
    details {{ margin-top: 12px; }}
    summary {{ cursor: pointer; font-weight: 800; }}
    .checklist, .manager-issue-list {{ padding-left: 0; list-style: none; }}
    .checklist li, .manager-issue-list li {{ margin: 9px 0; display: grid; gap: 5px; }}
    .timeline {{ list-style: none; padding-left: 0; border-left: 2px solid var(--line); margin-left: 9px; }}
    .timeline li {{ display: grid; grid-template-columns: 18px 1fr; gap: 10px; margin: 14px 0 14px -10px; }}
    .timeline-dot {{ width: 18px; height: 18px; border-radius: 99px; margin-top: 4px; border: 3px solid var(--panel); box-shadow: 0 0 0 1px var(--line); }}
    .timeline-dot.critical {{ background: var(--critical); }}
    .timeline-dot.warning {{ background: var(--warning); }}
    .timeline-dot.info {{ background: var(--info); }}
    .timeline-dot.ready {{ background: var(--ready); }}
    .timeline-dot.muted-badge {{ background: #98a2b3; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border-radius: 18px; overflow: hidden; box-shadow: var(--shadow); }}
    th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ background: #ede7db; color: #475467; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
    a {{ color: var(--info); font-weight: 800; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .muted {{ color: var(--muted); }}
    @media (max-width: 980px) {{ .hero-grid, .trend-grid, .trend-detail-grid, .manager-card-grid, .task-grid {{ grid-template-columns: 1fr 1fr; }} table {{ display: block; overflow-x: auto; }} }}
    @media (max-width: 640px) {{ .hero-grid, .trend-grid, .trend-detail-grid, .manager-card-grid, .task-grid {{ grid-template-columns: 1fr; }} main {{ padding: 20px 12px 42px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Operations Manager</h1>
      <p class="subtitle">Primary read-only dashboard generated from normalized audit JSON. No external systems were modified.</p>
      <div class="hero-grid">
        <div class="card"><div class="metric">{html_escape('n/a' if score is None else score)}</div><div class="label">Overall production health. Score label: {html_text(health.get('label'), 120)}</div></div>
        <div class="card"><div class="metric">{badge(ready_badge, manager_status_class(ready_badge))}</div><div class="label">Operational status</div></div>
        <div class="card"><div class="metric">{counts.get('Critical', 0)}</div><div class="label">Critical</div></div>
        <div class="card"><div class="metric">{counts.get('Warning', 0)}</div><div class="label">Warnings</div></div>
        <div class="card"><div class="metric">{dashboard.get('suppressed_issue_count', 0)}</div><div class="label">Suppressed</div></div>
      </div>
    </header>

    <h2>Fix First</h2>
    <section class="card">{render_manager_issue_list(recommendations.get('fix_first') or [], 'No Fix First issues.')}</section>

    <h2>Urgent Review</h2>
    <section class="card">{render_manager_issue_list(recommendations.get('urgent_review') or [], 'No urgent uncertainty inside the 7-day show window.')}</section>

    <h2>Fix Today</h2>
    <section class="card">{render_manager_issue_list(recommendations.get('fix_today') or [], 'No Fix Today issues.')}</section>

    <h2>Completion Verification</h2>
    <section class="trend-grid">
      <div class="card"><div class="metric small">{completion_summary.get('total_claims', 0)}</div><div class="label">Claims reviewed</div></div>
      <div class="card"><div class="metric small">{completion_counts.get('Completed and verified', 0)}</div><div class="label">Completed and verified</div></div>
      <div class="card"><div class="metric small">{completion_counts.get('Completed but not verified', 0)}</div><div class="label">Completed but not verified</div></div>
      <div class="card"><div class="metric small">{completion_counts.get('Still open', 0)}</div><div class="label">Still open</div></div>
      <div class="card"><div class="metric small">{completion_counts.get('Needs human review', 0)}</div><div class="label">Needs human review</div></div>
    </section>
    <section class="card"><p><strong>Completion claims file:</strong> {html_text(completion_tracking.get('completed_tasks_path') or 'data/audit/completed_tasks.json', 220)}</p></section>

    <h2>Completed Today</h2>
    {('<div class="task-grid">' + ''.join(render_completion_claim_html(item) for item in (completion_tracking.get('completed_today') or [])) + '</div>') if (completion_tracking.get('completed_today') or []) else '<section class="card"><p class="muted">No tasks completed and verified today.</p></section>'}

    <h2>Completion Claims</h2>
    {('<div class="task-grid">' + ''.join(render_completion_claim_html(item) for item in (completion_tracking.get('claims') or [])) + '</div>') if (completion_tracking.get('claims') or []) else '<section class="card"><p class="muted">No local completion claims have been recorded yet.</p></section>'}

    <h2>Monitor</h2>
    <section class="card">{render_manager_issue_list(recommendations.get('monitor') or [], 'No Monitor issues.')}</section>

    <h2>Trust Layer</h2>
    <section class="trend-grid">
      <div class="card"><div class="metric small">{trust_bucket_counts.get('Confirmed Issues', 0)}</div><div class="label">Confirmed Issues</div></div>
      <div class="card"><div class="metric small">{trust_bucket_counts.get('Needs Verification', 0)}</div><div class="label">Needs Verification</div></div>
      <div class="card"><div class="metric small">{trust_bucket_counts.get('Waiting on Guest', 0) + trust_bucket_counts.get('Waiting on Guest Topics', 0)}</div><div class="label">Waiting on Guest</div></div>
      <div class="card"><div class="metric small">{trust_bucket_counts.get('Known Exceptions', 0)}</div><div class="label">Known Exceptions</div></div>
      <div class="card"><div class="metric small">{trust_summary.get('future_automation_candidate_count', 0)}</div><div class="label">Future Safe Actions</div></div>
    </section>

    <h2>Confirmed Issues</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('confirmed_issue_findings') or [], 'No confirmed issues.')}</section>

    <h2>Needs Verification</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('needs_verification_findings') or [], 'No findings need human verification.')}</section>

    <h2>Waiting on Guest</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('waiting_on_guest_findings') or [], 'No findings are waiting on guests.')}</section>

    <h2>Waiting on Guest Topics</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('waiting_on_guest_topics_findings') or [], 'No findings are waiting on guest topics.')}</section>

    <h2>Needs Guest Replacement</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('needs_guest_replacement_findings') or [], 'No shows need replacement guests.')}</section>

    <h2>Human Confirmed Active</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('human_confirmed_active_findings') or [], 'No human-confirmed active exceptions matched this audit.')}</section>

    <h2>Known Calendar Ownership Exception</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('known_calendar_ownership_exception_findings') or [], 'No calendar ownership exceptions matched this audit.')}</section>

    <h2>Needs Human Follow-Up</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('needs_human_follow_up_findings') or [], 'No findings need human follow-up.')}</section>

    <h2>Waiting on Client</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('waiting_on_client_findings') or [], 'No findings are waiting on clients.')}</section>

    <h2>Waiting on Internal Team</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('waiting_on_internal_team_findings') or [], 'No findings are waiting on internal team members.')}</section>

    <h2>Known Exceptions</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('known_exception_findings') or [], 'No known exceptions matched this audit.')}</section>

    <h2>Not Due Yet</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('not_due_yet_findings') or [], 'No not-yet-due findings.')}</section>

    <h2>Future Safe Actions</h2>
    <section class="card">{render_trust_finding_list(dashboard.get('future_safe_action_findings') or [], 'No future safe action candidates.')}</section>

    <h2>Health By Show</h2>
    {render_show_health(dashboard.get('health_by_show') or {})}

    <h2>Missing Show Configuration</h2>
    <section class="card">{render_configuration_diagnostics(dashboard.get('show_configuration_diagnostics') or [])}</section>

    <h2>Show Operations</h2>
    {render_show_action_groups(dashboard.get('show_groups') or {})}

    <h2>Blocked Episodes</h2>
    {render_manager_episode_cards(dashboard.get('blocked_episodes') or [])}

    <h2>Ready Episodes</h2>
    {render_manager_episode_cards(dashboard.get('ready_episodes') or [])}

    <h2>Overdue Checklist Items</h2>
    <section class="card">{render_aggregate_checklist_items(dashboard.get('overdue_checklist_items') or [], 'No overdue checklist items.')}</section>

    <h2>Due-Now Checklist Items</h2>
    <section class="card">{render_aggregate_checklist_items(dashboard.get('due_now_checklist_items') or [], 'No checklist items are due in the current stage.')}</section>

    <h2>Not-Yet-Due Checklist Items</h2>
    <section class="card">{render_aggregate_checklist_items(dashboard.get('not_yet_due_checklist_items') or [], 'No future checklist items remain.')}</section>

    <h2>Upcoming Episodes: Next {dashboard.get('upcoming_days')} Days</h2>
    {render_manager_episode_cards(dashboard.get('upcoming_episodes') or [])}

    <h2>Episodes Requiring Attention</h2>
    {render_manager_episode_cards(dashboard.get('episodes_requiring_attention') or [])}

    <h2>Recently Completed Episodes</h2>
    {render_manager_episode_cards(dashboard.get('recently_completed_episodes') or [])}

    <h2>All Audited Episodes</h2>
    {render_manager_episode_table(dashboard.get('all_episodes') or [])}

    <h2>Trend Compared To Previous Audit</h2>
    {render_trend_detail(dashboard.get('trend') or {})}

    <h2>Critical Review</h2>
    {render_critical_review_html(dashboard.get('critical_review') or [])}

    <h2>Critical Issues</h2>
    <section class="card">{render_manager_issue_list(dashboard.get('critical_issues') or [], 'No Critical issues.')}</section>

    <h2>Warnings</h2>
    <section class="card">{render_manager_issue_list(dashboard.get('warnings') or [], 'No Warnings.')}</section>

    <h2>Informational Issues</h2>
    <section class="card">{render_manager_issue_list(dashboard.get('informational_issues') or [], 'No Informational issues.')}</section>

    <h2>Suppressed Issues</h2>
    <section class="card">{render_manager_issue_list(dashboard.get('suppressed_issues') or [], 'No suppressed issues.')}</section>
  </main>
</body>
</html>
"""


def render_markdown(report):
    counts = report["severity_counts"]
    summary = report.get("executive_summary") or build_executive_summary(report)
    fix_first = summary.get("what_should_be_fixed_first") or {}
    change_summary = report.get("change_summary") or {}
    lines = [
        "# Operations Audit Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Calendar audited: `{report['calendar_id']}`",
        f"- Calendar events loaded: {report['calendar_events_loaded']}",
        f"- Episodes audited: {report['episodes_audited']}",
        f"- Production health: {report.get('overall_production_health', {}).get('score', 'n/a')} - {report.get('overall_production_health', {}).get('label', 'unknown')}",
        f"- Issues: {len(report['issues'])} ({counts.get('Critical', 0)} Critical, {counts.get('Warning', 0)} Warning, {counts.get('Informational', 0)} Informational)",
        f"- Suppressed issues: {report.get('suppressed_issue_count', 0)}",
        "- Mode: read-only; no Google Calendar, HighLevel, or email changes were made",
        "",
        "## Executive Summary",
        "",
        f"- Ready: {summary.get('what_is_ready')}",
        f"- Needs action: {summary.get('what_needs_action')}",
        f"- Suppressed: {summary.get('suppressed_issue_summary')}",
        f"- Fix first: {fix_first.get('issue')} Recommended action: {fix_first.get('recommended_action')}",
        "",
        "## What Changed Since Last Audit",
        "",
    ]
    if change_summary.get("available"):
        delta = change_summary.get("severity_count_delta") or {}
        lines.extend(
            [
                f"- Previous audit: {change_summary.get('previous_generated_at')}",
                f"- Health score delta: {change_summary.get('health_score_delta')}",
                f"- Issue delta: Critical {delta.get('Critical', 0):+}, Warning {delta.get('Warning', 0):+}, Informational {delta.get('Informational', 0):+}",
                f"- New issues: {len(change_summary.get('new_issues') or [])}",
                f"- Resolved issues: {len(change_summary.get('resolved_issues') or [])}",
                f"- Continuing issues: {len(change_summary.get('continuing_issues') or [])}",
                "",
            ]
        )
    else:
        lines.extend([f"- {change_summary.get('message') or 'No previous audit file exists yet.'}", ""])
    lines.extend(
        [
        "## Show Summary",
        "",
        "| Show | Health | Episodes | Calendar matches | Critical | Warning | Informational |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in sorted(report["show_summary"].values(), key=lambda row: row["show_name"]):
        health = item.get("production_health_score")
        health_text = "n/a" if health is None else f"{health} - {item.get('production_health_label')}"
        lines.append(
            f"| {md_escape(item['show_name'])} | {md_escape(health_text)} | {item['episodes_audited']} | {item['calendar_matches']} | "
            f"{item['critical']} | {item['warning']} | {item['informational']} |"
        )
    lines.extend(["", "## Issues", ""])
    if not report["issues"]:
        lines.append("No issues found.")
    else:
        lines.extend(
            [
                "| Severity | Confidence | Show | Episode Time | Code | Issue | Recommended Action |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in report["issues"]:
            lines.append(
                f"| {item['severity']} | {md_escape(item.get('confidence'))} | {md_escape(item['show_name'])} | {md_escape(item.get('episode_time'))} | "
                f"{md_escape(item['code'])} | {md_escape(item['message'])} | {md_escape(item['recommended_action'])} |"
            )
    lines.extend(["", "## Audited Episodes", ""])
    lines.extend(
        [
            "| Show | Episode Time | Health | Guests | Calendar Event | Issue Count |",
            "| --- | --- | ---: | ---: | --- | ---: |",
        ]
    )
    for episode in report["episodes"]:
        event_label = episode.get("calendar_event_title") or "Missing"
        if episode.get("calendar_event_id"):
            event_label = f"{event_label} ({episode['calendar_event_id']})"
        health = episode.get("production_health", {}).get("score")
        health_text = "n/a" if health is None else f"{health}"
        lines.append(
            f"| {md_escape(episode['show_name'])} | {md_escape(episode['episode_time'])} | {health_text} | {episode['guest_count']} | "
            f"{md_escape(event_label)} | {len(episode.get('issues') or [])} |"
        )
    lines.append("")
    return "\n".join(lines)


def trust_finding_markdown_lines(finding):
    highlevel = finding.get("evidence_from_highlevel") or {}
    calendar = finding.get("evidence_from_google_calendar") or {}
    active_guests = []
    for guest in highlevel.get("active_guests") or []:
        name = guest.get("name")
        email = guest.get("email")
        if name and email:
            active_guests.append(f"{name} <{email}>")
        elif name or email:
            active_guests.append(name or email)
    attendee_emails = calendar.get("attendee_emails") or []
    source_files = ", ".join(item.get("path") for item in finding.get("source_json_files") or [] if item.get("path"))
    return [
        f"### {md_escape(finding.get('show'))} - {md_escape(short_date(finding.get('episode')))}",
        "",
        f"- Guest(s): {md_escape(finding.get('guest'))}",
        f"- Issue: `{md_escape(finding.get('issue_code'))}` - {md_escape(finding.get('issue'))}",
        f"- Category: {md_escape(finding.get('category'))}",
        f"- Operational status: {md_escape(finding.get('operational_status'))}",
        f"- Severity: {md_escape(finding.get('severity'))}",
        f"- Confidence: {md_escape(finding.get('confidence'))}",
        f"- Why it was flagged: {md_escape(finding.get('why_it_was_flagged'))}",
        f"- HighLevel evidence: {md_escape('; '.join(active_guests) if active_guests else 'No direct active guest evidence in this finding.')}",
        f"- Google Calendar evidence: {md_escape(calendar.get('title') or 'No matched calendar event')} ({md_escape(calendar.get('start'))}); attendees: {md_escape(', '.join(attendee_emails[:8]) if attendee_emails else 'none in evidence')}",
        f"- Difference detected: {md_escape(finding.get('difference_detected'))}",
        f"- Jessie should verify: {md_escape(finding.get('what_jessie_should_verify'))}",
        f"- Recommended human action: {md_escape(finding.get('recommended_human_action'))}",
        f"- Future automation candidate: {md_escape(finding.get('future_automation_candidate'))}",
        f"- Automation risk level: {md_escape(finding.get('automation_risk_level'))}",
        f"- Approval required before action: {md_escape(finding.get('approval_required_before_action'))}",
        f"- Source JSON: {md_escape(source_files or 'not listed')}",
        "",
    ]


def render_trust_finding_section(title, findings, empty_label):
    lines = [f"## {title}", ""]
    if not findings:
        lines.extend([empty_label, ""])
        return lines
    for finding in findings:
        lines.extend(trust_finding_markdown_lines(finding))
    return lines


def render_known_context_section(context_items):
    lines = ["## Known Context From Config", ""]
    if not context_items:
        lines.extend(["No known context entries are configured.", ""])
        return lines
    for item in context_items:
        lines.append(
            f"- {md_escape(item.get('show_key'))} {md_escape(item.get('episode_date'))}: "
            f"{md_escape(item.get('guest_name'))} - {md_escape(item.get('context'))}"
        )
    lines.append("")
    return lines


def render_trust_review_markdown(trust_review):
    summary = trust_review.get("summary") or {}
    health = trust_review.get("overall_production_health") or {}
    counts_by_category = summary.get("counts_by_category") or {}
    counts_by_bucket = summary.get("counts_by_dashboard_bucket") or {}
    readiness = trust_review.get("automation_readiness") or {}
    completion_tracking = trust_review.get("completion_tracking") or {}
    completion_summary = completion_tracking.get("summary") or {}
    lines = [
        "# Trust Review",
        "",
        f"- Generated at: {trust_review.get('generated_at')}",
        f"- Production health: {health.get('score', 'n/a')} - {health.get('label', 'unknown')}",
        f"- Total findings reviewed: {summary.get('total_findings', 0)}",
        "- Mode: read-only; no HighLevel, Google Calendar, Gmail, Google Drive, or email changes were made",
        "",
        "## Trust Summary",
        "",
    ]
    for category, count in sorted(counts_by_category.items()):
        lines.append(f"- {md_escape(category)}: {count}")
    lines.extend(["", "## Dashboard Buckets", ""])
    for bucket in TRUST_BUCKETS:
        count = summary.get("future_automation_candidate_count", 0) if bucket == "Future Safe Actions" else counts_by_bucket.get(bucket, 0)
        lines.append(f"- {bucket}: {count}")
    lines.append("")
    lines.extend(
        [
            "## Completion Verification",
            "",
            f"- Total completion claims reviewed: {completion_summary.get('total_claims', 0)}",
            f"- Completed and verified: {(completion_summary.get('counts_by_status') or {}).get('Completed and verified', 0)}",
            f"- Completed but not verified: {(completion_summary.get('counts_by_status') or {}).get('Completed but not verified', 0)}",
            f"- Still open: {(completion_summary.get('counts_by_status') or {}).get('Still open', 0)}",
            f"- Needs human review: {(completion_summary.get('counts_by_status') or {}).get('Needs human review', 0)}",
            f"- Completed today: {completion_summary.get('completed_today_count', 0)}",
            "",
        ]
    )
    completed_today = completion_tracking.get("completed_today") or []
    if completed_today:
        for item in completed_today:
            lines.append(
                f"- Completed today: {md_escape(item.get('task_label') or 'Claimed completed task')} - "
                f"{md_escape(item.get('verification_status'))} - {md_escape(item.get('explanation'))}"
            )
        lines.append("")
    else:
        lines.extend(["No tasks completed and verified today.", ""])
    lines.extend(
        render_trust_finding_section(
            "What The System Is Highly Confident About",
            trust_review.get("what_the_system_is_highly_confident_about") or [],
            "No high-confidence confirmed issues are active.",
        )
    )
    lines.extend(
        render_trust_finding_section(
            "What Needs Human Verification",
            trust_review.get("what_needs_human_verification") or [],
            "No findings currently need human verification.",
        )
    )
    lines.extend(
        render_trust_finding_section(
            "Waiting On Someone",
            trust_review.get("what_is_waiting_on_someone") or [],
            "No findings are currently waiting on guests, clients, or internal team members.",
        )
    )
    lines.extend(
        render_trust_finding_section(
            "Waiting On Guest Topics",
            trust_review.get("waiting_on_guest_topics") or [],
            "No findings are currently waiting on guest topics.",
        )
    )
    lines.extend(
        render_trust_finding_section(
            "Needs Guest Replacement",
            trust_review.get("needs_guest_replacement") or [],
            "No shows currently need replacement guests.",
        )
    )
    lines.extend(
        render_trust_finding_section(
            "Human Confirmed Active",
            trust_review.get("human_confirmed_active") or [],
            "No human-confirmed active exceptions matched this audit.",
        )
    )
    lines.extend(
        render_trust_finding_section(
            "Known Calendar Ownership Exceptions",
            trust_review.get("known_calendar_ownership_exceptions") or [],
            "No calendar ownership exceptions matched this audit.",
        )
    )
    lines.extend(
        render_trust_finding_section(
            "Needs Human Follow-Up",
            trust_review.get("needs_human_follow_up") or [],
            "No findings currently need human follow-up.",
        )
    )
    lines.extend(
        render_trust_finding_section(
            "Known Exceptions",
            trust_review.get("known_exceptions") or [],
            "No configured known exceptions matched this audit.",
        )
    )
    lines.extend(render_known_context_section(trust_review.get("known_context_from_config") or []))
    lines.extend(
        render_trust_finding_section(
            "Not Due Yet",
            trust_review.get("not_due_yet") or [],
            "No findings are classified as not due yet.",
        )
    )
    lines.extend(
        render_trust_finding_section(
            "Could Eventually Be Safely Automated",
            trust_review.get("future_safe_actions") or [],
            "No current findings are classified as future safe-action candidates.",
        )
    )
    lines.extend(
        [
            "## Automation Readiness",
            "",
            "### Could Eventually Be Safe After Approval",
            "",
        ]
    )
    for item in readiness.get("could_eventually_be_safe_after_approval") or []:
        lines.append(f"- {md_escape(item)}")
    lines.extend(["", "### Should Never Be Automated Without Human Approval", ""])
    for item in readiness.get("requires_human_approval") or []:
        lines.append(f"- {md_escape(item)}")
    lines.extend(["", f"Current mode: {md_escape(readiness.get('current_mode'))}", ""])
    return "\n".join(lines)


def knowledge_payload(knowledge, key):
    return ((knowledge.get("files") or {}).get(key) or {}).get("payload") or {}


def known_exceptions_from_knowledge(knowledge):
    return rule_list(knowledge_payload(knowledge, "known_exceptions"), "exceptions")


def known_decisions_from_knowledge(knowledge):
    return rule_list(knowledge_payload(knowledge, "known_decisions"), "decisions")


def known_patterns_from_knowledge(knowledge):
    return rule_list(knowledge_payload(knowledge, "known_patterns"), "patterns")


def linkedin_events_from_knowledge(knowledge):
    return rule_list(knowledge_payload(knowledge, "linkedin_events"), "events")


def knowledge_operational_records(knowledge):
    records = []
    for source, items in (
        ("known_exception", known_exceptions_from_knowledge(knowledge)),
        ("known_decision", known_decisions_from_knowledge(knowledge)),
        ("known_pattern", known_patterns_from_knowledge(knowledge)),
    ):
        for item in items:
            if isinstance(item, dict):
                enriched = dict(item)
                enriched["knowledge_source"] = source
                records.append(enriched)
    return records


def knowledge_record_matches_issue(record, item, now=None):
    if not isinstance(record, dict):
        return False
    show_key = record.get("show_key")
    if show_key and show_key != "*" and show_key != item.get("show_key"):
        return False
    issue_codes = record.get("issue_codes") or record.get("observed_issue_codes") or []
    if issue_codes and item.get("code") not in issue_codes and "*" not in issue_codes:
        return False
    episode_date = record.get("episode_date") or record.get("episode_time")
    if episode_date and len(str(episode_date)) >= 10 and date_key(episode_date) != date_key(item.get("episode_time")):
        return False
    calendar_event_id = record.get("calendar_event_id")
    if calendar_event_id and calendar_event_id != item.get("calendar_event_id"):
        return False
    appointment_id = record.get("appointment_id")
    if appointment_id and appointment_id not in (item.get("appointment_ids") or []):
        return False
    guest_name = normalize_text(record.get("guest_name"))
    guest_email = normalize_email(record.get("guest_email"))
    if guest_name or guest_email:
        tokens = issue_guest_tokens(item)
        search_text = normalize_text(
            " ".join(
                [
                    item.get("message") or "",
                    ((item.get("evidence_panel") or {}).get("evidence_from_google_calendar") or {}).get("title") or "",
                    json.dumps(item.get("details") or {}, ensure_ascii=True),
                ]
            )
        )
        if guest_name and guest_name not in tokens:
            if guest_name not in search_text:
                return False
        if guest_email and guest_email not in tokens:
            return False
    return True


def knowledge_record_affects_issue_output(record):
    return any(
        record.get(key) not in (None, "", False)
        for key in (
            "status_category",
            "operational_status",
            "trust_category",
            "trust_dashboard_bucket",
            "suppress_matching_issues",
            "convert_to_issue_code",
            "alert_issue_code",
        )
    )


def knowledge_suppression_reason(record):
    return record.get("operator_guidance") or record.get("decision_summary") or record.get("summary") or "Suppressed by human-confirmed knowledge record."


def apply_knowledge_record_to_issue(item, record):
    item["knowledge_decision"] = {
        "id": record.get("id"),
        "source": record.get("knowledge_source"),
        "decision_outcome": record.get("decision_outcome"),
        "status_category": record.get("status_category"),
        "guest_status": record.get("guest_status"),
        "summary": record.get("decision_summary") or record.get("summary"),
        "operator_guidance": record.get("operator_guidance"),
        "suggested_rule_update": record.get("suggested_rule_update"),
    }
    if record.get("trust_category"):
        item["knowledge_trust_category"] = record.get("trust_category")
    if record.get("trust_dashboard_bucket"):
        item["knowledge_trust_dashboard_bucket"] = record.get("trust_dashboard_bucket")
    if record.get("operational_status"):
        item["operational_status"] = record.get("operational_status")
    if record.get("recommended_action"):
        item["recommended_action"] = record.get("recommended_action")
    if record.get("convert_to_issue_code"):
        item["code"] = record["convert_to_issue_code"]
    if record.get("severity"):
        item["severity"] = record["severity"]
    if record.get("message"):
        item["message"] = record["message"]
    details = item.get("details") or {}
    knowledge_details = record.get("details") if isinstance(record.get("details"), dict) else {}
    item["details"] = {
        **details,
        **knowledge_details,
        "knowledge_status": record.get("status_category") or record.get("guest_status"),
        "knowledge_record_id": record.get("id"),
    }
    item["evidence"] = item["details"]
    panel = item.get("evidence_panel")
    if isinstance(panel, dict):
        panel["issue_code"] = item.get("code")
        panel["severity"] = item.get("severity")
        panel["recommended_action"] = item.get("recommended_action")
        panel["difference_detected"] = difference_for_issue(item)
        item["difference_detected"] = panel["difference_detected"]
    return item


def apply_knowledge_to_issue_sets(active_issues, suppressed_issues, knowledge, now):
    records = knowledge_operational_records(knowledge)
    active = []
    suppressed = list(suppressed_issues or [])
    for item in active_issues or []:
        matched = None
        for record in records:
            if not knowledge_record_affects_issue_output(record):
                continue
            if knowledge_record_matches_issue(record, item, now):
                matched = record
                break
        if matched:
            apply_knowledge_record_to_issue(item, matched)
            if matched.get("suppress_matching_issues"):
                item["suppressed"] = True
                item["suppression"] = {
                    "reason": knowledge_suppression_reason(matched),
                    "expires_on": matched.get("expires_on"),
                    "configured_rule": {
                        key: matched.get(key)
                        for key in ("id", "show_key", "episode_date", "guest_name", "issue_codes", "status_category")
                        if matched.get(key) not in (None, "")
                    },
                }
                suppressed.append(item)
                continue
        active.append(item)
    for item in suppressed:
        for record in records:
            if not knowledge_record_affects_issue_output(record):
                continue
            if knowledge_record_matches_issue(record, item, now):
                apply_knowledge_record_to_issue(item, record)
                if item.get("suppression"):
                    item["suppression"]["reason"] = knowledge_suppression_reason(record)
                break
    return active, suppressed


def knowledge_record_event_start(record, event=None):
    if event and event.get("start"):
        return event.get("start")
    return parse_datetime(record.get("episode_time") or record.get("episode_date"))


def find_event_for_knowledge_record(record, calendar_events, rules):
    calendar_event_id = record.get("calendar_event_id")
    episode_date = record.get("episode_date")
    show_name = configured_show_name(rules, record.get("show_key")) if record.get("show_key") else None
    guest_name = record.get("guest_name")
    for event in calendar_events or []:
        if calendar_event_id and event.get("id") == calendar_event_id:
            return event
    for event in calendar_events or []:
        if episode_date and date_key(event.get("start")) != date_key(episode_date):
            continue
        event_text = event_full_text(event)
        if show_name and not has_show_signal(event, show_name):
            continue
        if guest_name and normalize_text(guest_name) not in normalize_text(event_text):
            continue
        return event
    return None


def show_needs_guest_replacement_records(knowledge):
    return [
        record
        for record in knowledge_operational_records(knowledge)
        if record.get("alert_issue_code") == "show_needs_guest_replacement"
        or record.get("status_category") in {"needs_guest_replacement", "needs_human_follow_up"}
    ]


def build_knowledge_alert_issues(calendar_events, existing_issues, options, knowledge):
    alerts = []
    rules = options["rules"]
    now = options["now"]
    max_time = now + timedelta(days=30)
    existing_keys = {
        (item.get("show_key"), date_key(item.get("episode_time")), item.get("code"))
        for item in existing_issues or []
    }
    for record in show_needs_guest_replacement_records(knowledge):
        event = find_event_for_knowledge_record(record, calendar_events, rules)
        event_start = knowledge_record_event_start(record, event)
        if not event_start:
            continue
        status_category = record.get("status_category")
        if status_category != "needs_guest_replacement":
            max_time = now + timedelta(days=options["days_ahead"] or DEFAULT_DAYS_AHEAD)
        if event_start < now or event_start > max_time:
            continue
        show_key = record.get("show_key") or "unknown"
        issue_code = record.get("alert_issue_code")
        if not issue_code:
            issue_code = "show_needs_guest_replacement" if status_category == "needs_guest_replacement" else "needs_human_follow_up"
        issue_key = (show_key, date_key(event_start), issue_code)
        if issue_key in existing_keys:
            continue
        show_name = record.get("show_name") or configured_show_name(rules, show_key) or show_key
        calendar_status = record.get("calendar_status") or ("Calendar event exists" if event else "No matching calendar event found")
        highlevel_status = record.get("highlevel_status") or "Unknown HighLevel status"
        guest_status = record.get("guest_status") or record.get("status_category") or "No confirmed active guest"
        recommended_action = record.get("recommended_action")
        if not recommended_action and show_key == "cherry-willow":
            recommended_action = "Write PR pitch / find replacement guest."
        recommended_action = recommended_action or "Confirm guest status and find a replacement guest if no active guest is confirmed."
        default_message = (
            f"{show_name} needs a confirmed guest or replacement for this upcoming episode."
            if issue_code == "show_needs_guest_replacement"
            else f"{show_name} needs human follow-up to reconcile guest status."
        )
        item = issue(
            severity=record.get("severity") or "Warning",
            code=issue_code,
            show_key=show_key,
            show_name=show_name,
            episode_time=event_start.isoformat(),
            calendar_event_id=event.get("id") if event else record.get("calendar_event_id"),
            message=record.get("message") or default_message,
            recommended_action=recommended_action,
            details={
                "show_name": show_name,
                "calendar_status": calendar_status,
                "highlevel_status": highlevel_status,
                "guest_status": guest_status,
                "pitch_or_replacement_outreach_needed": bool(record.get("pitch_or_replacement_outreach_needed", True)),
                "knowledge_record_id": record.get("id"),
                "guest_name": record.get("guest_name"),
            },
            confidence=record.get("confidence") or "high",
        )
        apply_knowledge_record_to_issue(item, record)
        build_issue_evidence_panel(
            item,
            show_key,
            {"episode_date_time": event_start.isoformat()},
            [],
            [],
            event,
            [],
            None,
            None,
            options,
        )
        alerts.append(item)
    return alerts


def build_linkedin_manual_evidence_issues(calendar_events, existing_issues, options, knowledge):
    issues = []
    existing_keys = {
        (item.get("calendar_event_id"), item.get("code"))
        for item in existing_issues or []
    }
    for record in linkedin_events_from_knowledge(knowledge):
        if not isinstance(record, dict):
            continue
        event = find_event_for_knowledge_record(record, calendar_events, options["rules"])
        if not event:
            continue
        if extract_linkedin_urls(calendar_text_for_brief(event)):
            continue
        key = (event.get("id"), "linkedin_event_exists_calendar_needs_update")
        if key in existing_keys:
            continue
        show_key = record.get("show_key") or "unknown"
        show_name = configured_show_name(options["rules"], show_key) or show_key
        issues.append(
            issue(
                severity="Warning",
                code="linkedin_event_exists_calendar_needs_update",
                show_key=show_key,
                show_name=show_name,
                episode_time=(event.get("start").isoformat() if event.get("start") else record.get("episode_date")),
                calendar_event_id=event.get("id"),
                message="A verified LinkedIn event exists, but the Google Calendar event still needs the LinkedIn URL added.",
                recommended_action="Add the verified LinkedIn event URL to the Google Calendar description after review, then send or schedule the SOP emails that depend on the event link.",
                details={
                    "guest_name": record.get("guest_name"),
                    "linkedin_event_url": record.get("linkedin_event_url"),
                    "source": record.get("source"),
                    "verified_by": record.get("verified_by"),
                    "verified_at": record.get("verified_at"),
                    "notes": record.get("notes"),
                    "calendar_needs_update": True,
                },
                confidence="high",
            )
        )
    return issues


def show_preferences_from_knowledge(knowledge):
    shows = rule_dict(knowledge_payload(knowledge, "show_preferences"), "shows")
    preferences = []
    for show_key, show in shows.items():
        for item in show.get("preferences") or []:
            enriched = dict(item)
            enriched["show_key"] = show_key
            enriched["show_name"] = show.get("show_name") or show_key
            preferences.append(enriched)
    return preferences


def confirmation_count(item):
    try:
        return int(item.get("confirmation_count") or 0)
    except (TypeError, ValueError):
        return 0


def rule_recommendation_threshold(item):
    try:
        return int(item.get("minimum_confirmations_for_rule_recommendation") or item.get("rule_recommendation_threshold") or 2)
    except (TypeError, ValueError):
        return 2


def learning_recommendation_status(item):
    count = confirmation_count(item)
    threshold = rule_recommendation_threshold(item)
    if count >= threshold:
        return "Ready for Jessie approval"
    return f"Keep learning ({count}/{threshold} confirmations)"


def learning_item_brief(item, item_type):
    return {
        "id": item.get("id"),
        "type": item_type,
        "show_key": item.get("show_key"),
        "show_name": item.get("show_name"),
        "episode_date": item.get("episode_date"),
        "guest_name": item.get("guest_name"),
        "decision_outcome": item.get("decision_outcome"),
        "summary": item.get("decision_summary") or item.get("summary"),
        "operator_guidance": item.get("operator_guidance"),
        "issue_codes": item.get("issue_codes") or item.get("observed_issue_codes") or [],
        "confirmation_count": confirmation_count(item),
        "recommendation_status": learning_recommendation_status(item),
        "suggested_rule_update": item.get("suggested_rule_update"),
        "last_confirmed_at": item.get("last_confirmed_at"),
    }


def issue_code_counter(findings):
    counts = {}
    for item in findings or []:
        code = item.get("issue_code")
        if code:
            counts[code] = counts.get(code, 0) + 1
    return counts


def previous_trust_counts(previous_report):
    if not isinstance(previous_report, dict):
        return {}
    return ((previous_report.get("trust_review") or {}).get("summary") or {}).get("counts_by_category") or {}


def build_confidence_improvement_summary(report, previous_report):
    current_counts = ((report.get("trust_review") or {}).get("summary") or {}).get("counts_by_category") or {}
    previous_counts = previous_trust_counts(previous_report)
    if not previous_counts:
        return {
            "available": False,
            "message": "No previous Trust Mode counts were available for comparison.",
            "current_needs_human_verification": current_counts.get("Needs Human Verification", 0),
            "current_known_exceptions": current_counts.get("Known Exception", 0),
        }
    previous_needs = previous_counts.get("Needs Human Verification", 0)
    current_needs = current_counts.get("Needs Human Verification", 0)
    previous_known = previous_counts.get("Known Exception", 0)
    current_known = current_counts.get("Known Exception", 0)
    return {
        "available": True,
        "previous_needs_human_verification": previous_needs,
        "current_needs_human_verification": current_needs,
        "needs_human_verification_delta": current_needs - previous_needs,
        "previous_known_exceptions": previous_known,
        "current_known_exceptions": current_known,
        "known_exceptions_delta": current_known - previous_known,
        "interpretation": "Lower Needs Human Verification and higher documented Known Exceptions generally indicate the system is learning approved operating patterns.",
    }


def build_learning_report(report, previous_report, knowledge):
    decisions = known_decisions_from_knowledge(knowledge)
    exceptions = known_exceptions_from_knowledge(knowledge)
    patterns = known_patterns_from_knowledge(knowledge)
    preferences = show_preferences_from_knowledge(knowledge)
    current_findings = trust_findings_from_issues(report.get("issues") or []) + trust_findings_from_issues(report.get("suppressed_issues") or [])
    new_sops = [
        learning_item_brief(item, "decision")
        for item in decisions
        if item.get("decision_outcome") == "new SOP discovered"
    ]
    new_sops.extend(
        learning_item_brief(item, "pattern")
        for item in patterns
        if item.get("decision_outcome") == "new SOP discovered"
    )
    new_sops.extend(
        learning_item_brief(item, "show_preference")
        for item in preferences
        if item.get("decision_outcome") == "new SOP discovered"
    )
    recurring_decisions = [
        learning_item_brief(item, "decision")
        for item in decisions
        if item.get("decision_outcome")
    ]
    recurring_false_positives = [
        learning_item_brief(item, "decision")
        for item in decisions
        if item.get("decision_outcome") in {"audit was incorrect", "intentional business exception", "audit was partially correct"}
    ]
    recurring_false_positives.extend(
        learning_item_brief(item, "known_exception")
        for item in exceptions
        if item.get("decision_outcome") in {"audit was incorrect", "intentional business exception", "audit was partially correct"}
    )
    recurring_confirmed_issues = [
        learning_item_brief(item, "decision")
        for item in decisions
        if item.get("decision_outcome") == "audit was correct"
    ]
    recurring_confirmed_issues.extend(
        {
            "id": item.get("finding_id"),
            "type": "current_trust_finding",
            "show_key": item.get("show_key"),
            "show_name": item.get("show"),
            "episode_date": date_key(item.get("episode")),
            "guest_name": item.get("guest"),
            "decision_outcome": "current confirmed issue",
            "summary": item.get("issue"),
            "operator_guidance": item.get("recommended_human_action"),
            "issue_codes": [item.get("issue_code")] if item.get("issue_code") else [],
            "confirmation_count": 0,
            "recommendation_status": "Current audit evidence only",
            "suggested_rule_update": "No rule update recommended until Jessie confirms this outcome.",
            "last_confirmed_at": None,
        }
        for item in current_findings
        if item.get("category") == "Confirmed Issue"
    )
    recommendation_sources = []
    for item_type, items in (
        ("decision", decisions),
        ("known_exception", exceptions),
        ("pattern", patterns),
        ("show_preference", preferences),
    ):
        for item in items:
            if item.get("suggested_rule_update"):
                recommendation_sources.append(learning_item_brief(item, item_type))
    return {
        "generated_at": report.get("generated_at"),
        "read_only": True,
        "knowledge_dir": knowledge.get("path"),
        "knowledge_files": {
            key: {"path": value.get("path"), "exists": value.get("exists")}
            for key, value in (knowledge.get("files") or {}).items()
        },
        "summary": {
            "known_exception_count": len(exceptions),
            "known_decision_count": len(decisions),
            "known_pattern_count": len(patterns),
            "show_preference_count": len(preferences),
            "current_needs_human_verification": ((report.get("trust_review") or {}).get("summary") or {}).get("counts_by_category", {}).get("Needs Human Verification", 0),
            "current_finding_issue_codes": issue_code_counter(current_findings),
        },
        "new_sops_learned": new_sops,
        "recurring_human_decisions": recurring_decisions,
        "recurring_false_positives": recurring_false_positives,
        "recurring_confirmed_issues": recurring_confirmed_issues,
        "suggested_rule_improvements": recommendation_sources,
        "confidence_improvements_since_previous_audit": build_confidence_improvement_summary(report, previous_report),
        "policy": {
            "automatic_rule_changes": "disabled",
            "operator_approval_required": True,
            "goal": "Reduce Needs Human Verification findings over time by promoting repeated human decisions into Jessie-approved SOP rules.",
        },
    }


def render_learning_items(items, empty_label):
    if not items:
        return [empty_label, ""]
    lines = []
    for item in items:
        title_parts = [item.get("show_name") or item.get("show_key") or "Unknown show"]
        if item.get("episode_date"):
            title_parts.append(str(item.get("episode_date")))
        if item.get("guest_name"):
            title_parts.append(str(item.get("guest_name")))
        lines.extend(
            [
                f"### {md_escape(' - '.join(title_parts))}",
                "",
                f"- Outcome: {md_escape(item.get('decision_outcome'))}",
                f"- Type: {md_escape(item.get('type'))}",
                f"- Summary: {md_escape(item.get('summary'))}",
                f"- Operator guidance: {md_escape(item.get('operator_guidance'))}",
                f"- Issue codes: {md_escape(', '.join(item.get('issue_codes') or []))}",
                f"- Confirmations: {item.get('confirmation_count', 0)}",
                f"- Recommendation status: {md_escape(item.get('recommendation_status'))}",
                f"- Suggested rule improvement: {md_escape(item.get('suggested_rule_update'))}",
                "",
            ]
        )
    return lines


def render_learning_report_markdown(learning_report):
    summary = learning_report.get("summary") or {}
    confidence = learning_report.get("confidence_improvements_since_previous_audit") or {}
    lines = [
        "# Learning Report",
        "",
        f"- Generated at: {learning_report.get('generated_at')}",
        f"- Knowledge directory: `{learning_report.get('knowledge_dir')}`",
        f"- Known exceptions: {summary.get('known_exception_count', 0)}",
        f"- Known decisions: {summary.get('known_decision_count', 0)}",
        f"- Known patterns: {summary.get('known_pattern_count', 0)}",
        f"- Show preferences: {summary.get('show_preference_count', 0)}",
        f"- Current Needs Human Verification findings: {summary.get('current_needs_human_verification', 0)}",
        "- Mode: read-only; no external systems or audit rules were modified",
        "",
        "## New SOPs Learned",
        "",
    ]
    lines.extend(render_learning_items(learning_report.get("new_sops_learned") or [], "No new SOPs have been recorded yet."))
    lines.extend(["## Recurring Human Decisions", ""])
    lines.extend(render_learning_items(learning_report.get("recurring_human_decisions") or [], "No human decisions have been recorded yet."))
    lines.extend(["## Recurring False Positives Or Business Exceptions", ""])
    lines.extend(render_learning_items(learning_report.get("recurring_false_positives") or [], "No recurring false positives or business exceptions are recorded yet."))
    lines.extend(["## Recurring Confirmed Issues", ""])
    lines.extend(render_learning_items(learning_report.get("recurring_confirmed_issues") or [], "No recurring confirmed issues are recorded yet."))
    lines.extend(["## Suggested Rule Improvements For Jessie Approval", ""])
    lines.extend(render_learning_items(learning_report.get("suggested_rule_improvements") or [], "No rule improvements are suggested yet."))
    lines.extend(["## Confidence Improvements Since Previous Audit", ""])
    if confidence.get("available"):
        lines.extend(
            [
                f"- Previous Needs Human Verification: {confidence.get('previous_needs_human_verification')}",
                f"- Current Needs Human Verification: {confidence.get('current_needs_human_verification')}",
                f"- Needs Human Verification delta: {confidence.get('needs_human_verification_delta'):+}",
                f"- Previous Known Exceptions: {confidence.get('previous_known_exceptions')}",
                f"- Current Known Exceptions: {confidence.get('current_known_exceptions')}",
                f"- Known Exceptions delta: {confidence.get('known_exceptions_delta'):+}",
                f"- Interpretation: {md_escape(confidence.get('interpretation'))}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"- {md_escape(confidence.get('message'))}",
                f"- Current Needs Human Verification: {confidence.get('current_needs_human_verification')}",
                f"- Current Known Exceptions: {confidence.get('current_known_exceptions')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Knowledge Policy",
            "",
            "- Knowledge records are advisory and do not automatically suppress, downgrade, or create audit rules.",
            "- Repeated human decisions should become rule recommendations, not automatic rule changes.",
            "- Jessie must approve any permanent SOP or audit-rule change before implementation.",
            "",
        ]
    )
    return "\n".join(lines)


def rule_queue_name(item):
    name = item.get("id") or "-".join(
        str(part)
        for part in (
            item.get("show_key"),
            item.get("episode_date"),
            item.get("guest_name"),
            ",".join(item.get("issue_codes") or []),
        )
        if part
    )
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(name)).strip("-").lower() or "suggested-rule-improvement"


def rule_queue_risk_level(item):
    issue_codes = set(item.get("issue_codes") or [])
    summary_text = normalize_text(" ".join([item.get("summary") or "", item.get("suggested_rule_update") or ""]))
    if issue_codes & {"guest_email_not_invited", "title_missing_guest", "guest_topics_pending"}:
        return "high"
    if "email" in summary_text or "guest-facing" in summary_text or "calendar description" in summary_text:
        return "high"
    if issue_codes & {"booking_without_calendar_event", "calendar_event_without_booking", "calendar_event_needs_confirmation"}:
        return "medium"
    if issue_codes & {"calendar_missing_preshow_block", "sop_required_assets_missing", "guest_confirmation_pitch_follow_up", "guest_rsvp_acceptance_risk"}:
        return "medium"
    return "low"


def rule_queue_reduces_false_positives(item):
    outcome = item.get("decision_outcome")
    if outcome in {"audit was partially correct", "audit was incorrect", "intentional business exception", "new SOP discovered"}:
        return True
    return False


def rule_queue_affects_guest_facing(item):
    text = normalize_text(" ".join([item.get("summary") or "", item.get("suggested_rule_update") or ""]))
    issue_codes = set(item.get("issue_codes") or [])
    guest_facing_terms = {"guest", "email", "calendar description", "title", "invite", "linkedin", "streamyard"}
    if any(term in text for term in guest_facing_terms):
        return True
    return bool(issue_codes & {"guest_email_not_invited", "title_missing_guest", "sop_required_assets_missing", "guest_topics_pending"})


def rule_queue_recommended_status(item):
    if normalize_text(item.get("suggested_rule_update")).startswith("no automatic rule change"):
        return "reject"
    if confirmation_count(item) >= rule_recommendation_threshold(item) and rule_queue_risk_level(item) == "low":
        return "approve"
    return "needs Jessie decision"


def rule_queue_proposed_config_change(item):
    suggested = item.get("suggested_rule_update") or "No specific config change proposed yet."
    show_key = item.get("show_key") or "global"
    issue_codes = item.get("issue_codes") or []
    return {
        "target": "config/operations_rules.json or config/production_timeline_rules.json after Jessie approval",
        "show_key": show_key,
        "issue_codes": issue_codes,
        "proposal": suggested,
        "not_applied": True,
    }


def rule_queue_expected_impact(item):
    if rule_queue_reduces_false_positives(item):
        return "Should reduce repeated Needs Human Verification findings by teaching the audit a human-confirmed operating pattern after approval."
    if item.get("decision_outcome") == "audit was correct":
        return "Should improve confidence labeling for future confirmed issues without suppressing legitimate warnings."
    return "Should clarify future audit output if Jessie approves the proposed SOP or configuration change."


def build_rule_approval_queue(learning_report):
    suggestions = learning_report.get("suggested_rule_improvements") or []
    queue = []
    for index, item in enumerate(suggestions, start=1):
        risk = rule_queue_risk_level(item)
        reduces_false_positive = rule_queue_reduces_false_positives(item)
        affects_guest_facing = rule_queue_affects_guest_facing(item)
        queue.append(
            {
                "queue_id": f"rule-{index:03d}",
                "suggested_rule_name": rule_queue_name(item),
                "show_affected": item.get("show_name") or item.get("show_key") or "Global",
                "show_key": item.get("show_key"),
                "current_problem": item.get("summary") or "A recurring human decision suggests the audit could become more precise.",
                "evidence": {
                    "source_type": item.get("type"),
                    "decision_outcome": item.get("decision_outcome"),
                    "issue_codes": item.get("issue_codes") or [],
                    "episode_date": item.get("episode_date"),
                    "guest_name": item.get("guest_name"),
                    "operator_guidance": item.get("operator_guidance"),
                    "confirmation_count": confirmation_count(item),
                    "recommendation_status": item.get("recommendation_status"),
                    "last_confirmed_at": item.get("last_confirmed_at"),
                },
                "proposed_config_change": rule_queue_proposed_config_change(item),
                "expected_impact": rule_queue_expected_impact(item),
                "risk_level": risk,
                "reduces_false_positives": reduces_false_positive,
                "affects_guest_facing_operations": affects_guest_facing,
                "recommended_approval_status": rule_queue_recommended_status(item),
                "approval_notes": "No changes have been applied. Jessie approval is required before this can become a rule.",
            }
        )
    return {
        "generated_at": learning_report.get("generated_at"),
        "read_only": True,
        "source_learning_report": learning_report.get("path") or "data/audit/learning_report.md",
        "automation_enabled": False,
        "status_values": ["approve", "reject", "needs Jessie decision"],
        "total_suggestions": len(queue),
        "items": queue,
    }


def render_rule_queue_markdown(queue):
    items = queue.get("items") or []
    status_counts = {}
    for item in items:
        status = item.get("recommended_approval_status")
        status_counts[status] = status_counts.get(status, 0) + 1
    lines = [
        "# Rule Approval Queue",
        "",
        f"- Generated at: {queue.get('generated_at')}",
        f"- Source: `{queue.get('source_learning_report')}`",
        f"- Suggested improvements: {queue.get('total_suggestions', 0)}",
        f"- Automation enabled: {queue.get('automation_enabled')}",
        "- Mode: read-only; no audit rules or external systems were modified",
        "",
        "## Status Summary",
        "",
    ]
    for status in queue.get("status_values") or []:
        lines.append(f"- {status}: {status_counts.get(status, 0)}")
    lines.extend(["", "## Approval Items", ""])
    if not items:
        lines.extend(["No suggested rule improvements are queued.", ""])
        return "\n".join(lines)
    for item in items:
        evidence = item.get("evidence") or {}
        proposed = item.get("proposed_config_change") or {}
        lines.extend(
            [
                f"### {md_escape(item.get('queue_id'))}: {md_escape(item.get('suggested_rule_name'))}",
                "",
                f"- Show affected: {md_escape(item.get('show_affected'))}",
                f"- Current problem: {md_escape(item.get('current_problem'))}",
                f"- Evidence: {md_escape(evidence.get('decision_outcome'))}; issue codes: {md_escape(', '.join(evidence.get('issue_codes') or []))}; confirmations: {evidence.get('confirmation_count', 0)}; source: {md_escape(evidence.get('source_type'))}",
                f"- Proposed config change: {md_escape(proposed.get('proposal'))}",
                f"- Config target: {md_escape(proposed.get('target'))}",
                f"- Expected impact: {md_escape(item.get('expected_impact'))}",
                f"- Risk level: {md_escape(item.get('risk_level'))}",
                f"- Reduces false positives: {item.get('reduces_false_positives')}",
                f"- Affects guest-facing operations: {item.get('affects_guest_facing_operations')}",
                f"- Recommended approval status: {md_escape(item.get('recommended_approval_status'))}",
                f"- Approval notes: {md_escape(item.get('approval_notes'))}",
                "",
            ]
        )
    lines.extend(
        [
            "## Apply Safety",
            "",
            "`python3 scripts/operations-audit.py --apply-approved-rules` is intentionally disabled and fails with: Rule automation is not enabled yet.",
            "",
        ]
    )
    return "\n".join(lines)


def action_plan_items(report):
    issues = report.get("issues") or []
    prioritized = []
    wanted_buckets = {
        "Confirmed Issues",
        "Waiting on Guest Topics",
        "Needs Guest Replacement",
        "Needs Human Follow-Up",
        "Waiting on Client",
        "Waiting on Guest",
        "Needs Verification",
    }
    for item in issues:
        trust = item.get("trust") or {}
        if effective_issue_severity(item) in {"Critical", "Warning"} or trust.get("dashboard_bucket") in wanted_buckets:
            prioritized.append(item)
    return sorted(
        prioritized,
        key=lambda item: (
            {
                "Needs Guest Replacement": 0,
                "Confirmed Issues": 1,
                "Waiting on Guest Topics": 2,
                "Needs Human Follow-Up": 3,
                "Waiting on Client": 4,
                "Waiting on Guest": 5,
                "Needs Verification": 6,
            }.get((item.get("trust") or {}).get("dashboard_bucket"), 9),
            0 if (item.get("operator_recommendation") or {}).get("category") == "Urgent Review" else 1,
            SEVERITY_ORDER.get(effective_issue_severity(item), 9),
            item.get("episode_time") or "",
            item.get("show_name") or "",
        ),
    )


def clean_url(value):
    url = unescape(str(value or "").strip())
    return url.rstrip(".,;:!?)]}'\"")


def extract_urls_from_text(value):
    seen = set()
    urls = []
    for match in RAW_URL_RE.findall(str(value or "")):
        url = clean_url(match)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def extract_linkedin_urls(value):
    return [
        url
        for url in extract_urls_from_text(value)
        if linkedin_url_is_promotion(url)
    ]


def extract_streamyard_urls(value):
    return [
        url
        for url in extract_urls_from_text(value)
        if "streamyard.com/" in url.lower()
    ]


def linkedin_url_is_promotion(url):
    lowered = str(url or "").lower()
    if "linkedin.com/" not in lowered:
        return False
    promotion_markers = (
        "/events/",
        "/feed/update/",
        "/posts/",
        "/video/live",
        "/live/",
        "urn:li:activity",
    )
    return any(marker in lowered for marker in promotion_markers)


def daily_now(now_value=None):
    parsed = parse_datetime(now_value) if now_value else datetime.now(timezone.utc)
    if not parsed:
        parsed = datetime.now(timezone.utc)
    return parsed.astimezone(LOCAL_TIMEZONE)


def path_from_report(value):
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def show_aliases_for_daily_brief(report, rules):
    aliases = {}
    show_keys = configured_show_keys(rules)
    overly_broad_aliases = {"reveting"}
    for show_key in show_keys:
        config = show_rule(rules, show_key)
        names = [
            show_key,
            show_key.replace("-", " "),
            config.get("show_name"),
        ]
        client_alias = normalize_text(config.get("client_name"))
        if client_alias and client_alias not in overly_broad_aliases:
            names.append(config.get("client_name"))
        summary = (report.get("show_summary") or {}).get(show_key) or {}
        names.append(summary.get("show_name"))
        if show_key == "cherry-willow":
            names.extend(["Cherry Willow", "Cherry Willow Livestream"])
        if show_key == "david-daily":
            names.extend(["David Daily", "David Daily Show"])
        aliases[show_key] = sorted({normalize_text(name) for name in names if normalize_text(name)}, key=len, reverse=True)
    return aliases


def show_key_for_calendar_event(event, aliases):
    title_text = normalize_text(event.get("title") or "")
    full_text = event_full_text(event)
    for show_key, show_aliases in aliases.items():
        for alias in show_aliases:
            if alias and alias in title_text:
                return show_key
    for show_key, show_aliases in aliases.items():
        for alias in show_aliases:
            if alias and alias in full_text:
                return show_key
    return None


def display_guests_from_title(title, show_aliases=None):
    text = compact(title, limit=260)
    if not text:
        return []
    lowered = text.lower()
    if " with " in lowered:
        after_with = text[lowered.rfind(" with ") + len(" with "):]
        cleaned = re.sub(r"\s+", " ", after_with).strip(" -:")
        parts = re.split(r"\s+(?:and|&)\s+|,\s*", cleaned)
        return [part.strip() for part in parts if part.strip()]
    cleaned = text
    for alias in show_aliases or []:
        if not alias:
            continue
        cleaned = re.sub(re.escape(alias), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(livestream|podcast|episode|show)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:")
    return [cleaned] if cleaned else []


def display_guests_for_brief(item, show_aliases=None):
    title_guests = display_guests_from_title(item.get("calendar_event_title") or "", show_aliases)
    if title_guests:
        return title_guests
    guests = list(item.get("guest_names") or [])
    for issue in item.get("issues") or []:
        details = issue.get("details") or issue.get("evidence") or {}
        replacement = details.get("replacement_guest")
        if replacement and replacement not in guests:
            guests.append(replacement)
    return guests


def represented_guest_summary_from_issues(issues):
    for issue in issues or []:
        details = issue.get("details") or {}
        if details.get("represented_guest"):
            return {
                "highlevel_submitter_contact": details.get("highlevel_submitter_contact"),
                "highlevel_submitter_email": details.get("highlevel_submitter_email"),
                "represented_guest": details.get("represented_guest"),
                "represented_guest_email": details.get("represented_guest_email"),
                "confidence": details.get("represented_guest_confidence"),
                "evidence": details.get("represented_guest_evidence") or [],
            }
    return {}


def linkedin_event_summary_from_issues(issues):
    for issue in issues or []:
        details = issue.get("details") or {}
        if details.get("linkedin_event_url"):
            return {
                "linkedin_event_url": details.get("linkedin_event_url"),
                "source": details.get("source"),
                "verified_by": details.get("verified_by"),
                "verified_at": details.get("verified_at"),
                "notes": details.get("notes"),
                "calendar_needs_update": bool(details.get("calendar_needs_update")),
            }
    return {}


def calendar_text_for_brief(event):
    if not event:
        return ""
    raw = event.get("raw_event_payload") or {}
    parts = [
        event.get("description"),
        event.get("location"),
        raw.get("description"),
        raw.get("location"),
        raw.get("meeting_link"),
        raw.get("hangoutLink"),
        raw.get("hangout_link"),
    ]
    conference = raw.get("conferenceData") or raw.get("conference_data") or {}
    if isinstance(conference, dict):
        for entry in conference.get("entryPoints") or conference.get("entry_points") or []:
            if isinstance(entry, dict):
                parts.append(entry.get("uri"))
    return "\n".join(str(part) for part in parts if part)


def has_complete_checklist_item(episode, key):
    for item in episode.get("checklist") or []:
        if item.get("key") == key and item.get("status") == "Complete":
            return True
    return False


def brief_issue_bucket(issue):
    trust = issue.get("trust") or {}
    return trust.get("dashboard_bucket") or issue.get("trust_dashboard_bucket")


def schedule_days_until(item, now_local):
    item_time = parse_datetime(item.get("date_time") or item.get("episode_time"))
    if not item_time:
        return None
    return (item_time.astimezone(LOCAL_TIMEZONE) - now_local).total_seconds() / 86400


def item_issue_codes(item):
    return {issue.get("code") for issue in item.get("issues") or []}


def item_issue_text(item):
    return normalize_text(" ".join([issue.get("message") or "" for issue in item.get("issues") or []]))


def item_has_issue_bucket(item, *bucket_names):
    wanted = set(bucket_names)
    return any(brief_issue_bucket(issue) in wanted for issue in item.get("issues") or [])


def item_has_confirmed_guest(item):
    if item.get("highlevel_status") in {"Yes", "Human-confirmed active", "Known exception", "PR Representative Booking / Guest Represented"}:
        return True
    if item.get("guest_status") in {"Confirmed", "Human-confirmed active", "PR Representative Booking / Guest Represented"}:
        return True
    return False


def guest_status_for_schedule(item):
    codes = item_issue_codes(item)
    text = item_issue_text(item)
    if "pr_representative_booking_guest_represented" in codes:
        return "PR Representative Booking / Guest Represented"
    if "show_needs_guest_replacement" in codes:
        return "Needs Replacement Guest"
    if "guest_rsvp_acceptance_risk" in codes:
        return "Blocked by Confirmation"
    if "guest_confirmation_pitch_follow_up" in codes or "calendar_event_needs_confirmation" in codes:
        return "Blocked by Confirmation"
    if item.get("highlevel_status") == "PR Representative Booking / Guest Represented":
        return "Confirmed"
    if item.get("highlevel_status") == "Human-confirmed active":
        return "Human-confirmed active"
    if item.get("highlevel_status") == "Known exception":
        return "Known Exception"
    if item.get("highlevel_status") == "Yes":
        return "Confirmed"
    if "guest confirmation" in text:
        return "Blocked by Confirmation"
    return "Needs Verification" if item.get("highlevel_status") == "No" else "Unknown"


def topics_status_for_schedule(item, days_until):
    codes = item_issue_codes(item)
    text = item_issue_text(item)
    if "guest_topics_pending" in codes or "topics pending" in text or "waiting on guest topics" in text:
        return "Blocked by Guest"
    if "required_custom_fields_missing_from_description" in codes:
        if days_until is not None and days_until < DAILY_BRIEF_NEXT_DAYS:
            return "Urgent Review"
        return "Due Soon"
    return "Present or not blocking"


def calendar_status_for_schedule(item):
    if not item.get("calendar_event_found"):
        return "Missing"
    if any(issue.get("code") == "calendar_event_without_booking" for issue in item.get("issues") or []):
        return "Needs Verification"
    return "Present"


def highlevel_status_for_schedule(item):
    status = item.get("highlevel_status") or ("Yes" if item.get("highlevel_booking_found") else "No")
    if "pr_representative_booking_guest_represented" in item_issue_codes(item):
        return "PR Representative Booking / Guest Represented"
    if status == "No":
        return "Needs Verification"
    return status


def linkedin_status_for_schedule(item, days_until):
    if (item.get("linkedin_event_summary") or {}).get("calendar_needs_update"):
        return "Exists - Calendar Needs Update"
    if item.get("linkedin_urls"):
        return "Present"
    if item.get("topics_status") == "Blocked by Guest":
        return "Blocked by Guest"
    if item.get("guest_status") in {"Needs Replacement Guest", "Blocked by Confirmation"}:
        return "Blocked by Confirmation"
    if days_until is not None and days_until < DAILY_BRIEF_NEXT_DAYS:
        return "Urgent Review"
    if days_until is not None and days_until < 14:
        return "Due Soon"
    return "Not Due Yet"


def streamyard_status_for_schedule(item, days_until):
    if item.get("streamyard_urls"):
        return "Present"
    if item.get("topics_status") == "Blocked by Guest":
        return "Blocked by Guest"
    if item.get("guest_status") in {"Needs Replacement Guest", "Blocked by Confirmation"}:
        return "Blocked by Confirmation"
    if days_until is not None and days_until < 2 and item_has_confirmed_guest(item):
        return "Critical"
    if days_until is not None and days_until < DAILY_BRIEF_NEXT_DAYS:
        return "Urgent Review"
    if days_until is not None and days_until < 14:
        return "Due Soon"
    if item_has_confirmed_guest(item):
        return "Ready to Create"
    return "Monitor"


def production_blockers_for_schedule(item):
    blockers = []
    if item.get("guest_status") == "Needs Replacement Guest":
        blockers.append("Needs replacement guest")
    if item.get("guest_status") == "Blocked by Confirmation":
        blockers.append("Guest confirmation unclear")
    if item.get("topics_status") == "Blocked by Guest":
        blockers.append("Guest topics missing")
    if item.get("calendar_status") in {"Missing", "Needs Verification"}:
        blockers.append("Calendar status needs verification")
    if item.get("highlevel_status_display") == "Needs Verification":
        blockers.append("HighLevel/calendar mismatch")
    if item.get("linkedin_status") == "Exists - Calendar Needs Update":
        blockers.append("Google Calendar needs LinkedIn URL added")
    elif item.get("linkedin_status") in {"Urgent Review", "Ready to Create"}:
        blockers.append("LinkedIn production URL not ready")
    if item.get("streamyard_status") == "Blocked by Guest":
        blockers.append("StreamYard blocked by missing guest topics/confirmation")
    elif item.get("streamyard_status") == "Blocked by Confirmation":
        blockers.append("StreamYard blocked by missing guest topics/confirmation")
    elif item.get("streamyard_status") in {"Critical", "Urgent Review", "Ready to Create"}:
        blockers.append("StreamYard link not ready")
    return blockers or ["No active production blocker found"]


def next_human_action_for_schedule(item):
    codes = item_issue_codes(item)
    if "pr_representative_booking_guest_represented" in codes:
        return "No mismatch cleanup needed. Use the represented guest for production context and keep the submitter/contact noted in the booking record."
    if item.get("linkedin_status") == "Exists - Calendar Needs Update":
        return "Add the verified LinkedIn event URL to the Google Calendar description, then send or schedule the SOP emails after review."
    if "show_needs_guest_replacement" in codes:
        return "Write PR pitch / source replacement guest."
    if item.get("topics_status") == "Blocked by Guest":
        return "Follow up for guest topics; after topics arrive, update calendar, LinkedIn, StreamYard, and emails."
    if item.get("guest_status") == "Blocked by Confirmation":
        return "Confirm guest status and RSVP/attendance before treating the episode as ready."
    if item.get("highlevel_status_display") == "Needs Verification":
        return "Verify whether the Google Calendar event is intentional, manually booked, or disconnected from HighLevel."
    if item.get("streamyard_status") in {"Critical", "Urgent Review", "Ready to Create"}:
        return "Create or locate the StreamYard link manually and add it to the production source of truth after review."
    if item.get("linkedin_status") in {"Urgent Review", "Ready to Create"}:
        return "Create or locate the LinkedIn promotion URL manually and add it to the production source of truth after review."
    for issue in item.get("issues") or []:
        if effective_issue_severity(issue) in {"Critical", "Warning"}:
            return issue.get("recommended_action") or "Review the issue evidence and decide the next human action."
    return "Monitor; no immediate human action is required."


def finalize_schedule_item(item, now_local):
    days_until = schedule_days_until(item, now_local)
    item["days_until"] = days_until
    item["guest_status"] = guest_status_for_schedule(item)
    item["topics_status"] = topics_status_for_schedule(item, days_until)
    item["calendar_status"] = calendar_status_for_schedule(item)
    item["highlevel_status_display"] = highlevel_status_for_schedule(item)
    if item["highlevel_status_display"] == "PR Representative Booking / Guest Represented":
        item["highlevel_status"] = item["highlevel_status_display"]
    item["linkedin_status"] = linkedin_status_for_schedule(item, days_until)
    item["streamyard_status"] = streamyard_status_for_schedule(item, days_until)
    item["production_blockers"] = production_blockers_for_schedule(item)
    item["next_human_action"] = next_human_action_for_schedule(item)
    item["flags"] = brief_item_flags(item)
    item["current_production_status"] = brief_item_status(item)
    return item


WORK_QUEUE_LANES = ("Today's Work", "This Week", "Blocked", "Waiting On")
WORK_QUEUE_GROUPS = ("Guest Follow-up", "Calendar", "Production", "PR", "Marketing", "Post Production")


def task_time_text(minutes):
    if minutes is None:
        return "Unknown"
    return f"{minutes} minute{'s' if int(minutes) != 1 else ''}"


def task_key(*parts):
    return "|".join(normalize_text(part) for part in parts if part)


def add_work_task(tasks, task):
    key = task.get("task_id") or task_key(task.get("show_name"), task.get("episode_time"), task.get("title"))
    if not key:
        return
    if key in tasks:
        existing = tasks[key]
        existing["source_issue_codes"] = sorted(set(existing.get("source_issue_codes") or []) | set(task.get("source_issue_codes") or []))
        existing["checklist"] = sorted(set(existing.get("checklist") or []) | set(task.get("checklist") or []))
        return
    task["task_id"] = key
    task.setdefault("group", "Production")
    task.setdefault("lane", "Today's Work")
    task.setdefault("status", "Needs Attention")
    task.setdefault("estimated_minutes", 8)
    task.setdefault("business_impact", "Medium")
    task.setdefault("checklist", [])
    task.setdefault("source_issue_codes", [])
    tasks[key] = task


def schedule_guest_label(item):
    return ", ".join(item.get("guest_names") or []) or "Unknown guest"


def schedule_task_title(item, suffix):
    guest = schedule_guest_label(item)
    return f"{guest}: {suffix}" if guest != "Unknown guest" else suffix


def schedule_source_codes(item):
    return sorted({issue.get("code") for issue in item.get("issues") or [] if issue.get("code")})


def task_from_guest_topics(item):
    guest = schedule_guest_label(item)
    return {
        "task_kind": "guest_topics",
        "title": schedule_task_title(item, "Waiting on Topics"),
        "group": "Guest Follow-up",
        "lane": "Today's Work",
        "status": "Waiting On",
        "show_key": item.get("show_key"),
        "show_name": item.get("show_name"),
        "episode_time": item.get("date_time") or item.get("episode_time"),
        "guest": guest,
        "why_seen": "This episode is inside the 7-day show window and guest topics are blocking final production prep.",
        "blocking": "Waiting on guest topics.",
        "next_action": "Follow up for topics. When topics arrive, finish the production prep sequence.",
        "estimated_minutes": 12,
        "business_impact": "High",
        "blocked": True,
        "waiting_on": True,
        "ignored_risk": "The team may not have final calendar copy, LinkedIn promotion, guest email copy, or StreamYard logistics ready before the show.",
        "checklist": [
            "Update calendar description",
            "Create LinkedIn event or promotion URL",
            "Schedule guest email",
            "Finalize StreamYard",
        ],
        "calendar_event_url": item.get("calendar_event_url"),
        "source_issue_codes": schedule_source_codes(item),
    }


def task_from_guest_confirmation(item):
    guest = schedule_guest_label(item)
    return {
        "task_kind": "guest_confirmation",
        "title": schedule_task_title(item, "Confirm Guest Status"),
        "group": "Guest Follow-up",
        "lane": "Today's Work",
        "status": "Blocked by Confirmation",
        "show_key": item.get("show_key"),
        "show_name": item.get("show_name"),
        "episode_time": item.get("date_time") or item.get("episode_time"),
        "guest": guest,
        "why_seen": "The show is less than 7 days away and guest confirmation or RSVP status is unclear.",
        "blocking": "Guest-side confirmation/RSVP status is not fully trusted yet.",
        "next_action": item.get("next_human_action") or "Confirm the guest is still expected and review RSVP status.",
        "estimated_minutes": 7,
        "business_impact": "High",
        "blocked": True,
        "waiting_on": True,
        "ignored_risk": "Production may prepare for a guest who is not actually confirmed, or a confirmed guest may miss key logistics.",
        "checklist": [
            "Review attendee RSVP status",
            "Confirm guest-side acceptance",
            "Decide whether production links can be finalized",
        ],
        "calendar_event_url": item.get("calendar_event_url"),
        "source_issue_codes": schedule_source_codes(item),
    }


def task_from_calendar_mismatch(item):
    return {
        "task_kind": "calendar_mismatch",
        "title": schedule_task_title(item, "Resolve Calendar / HighLevel Mismatch"),
        "group": "Calendar",
        "lane": "Today's Work",
        "status": "Urgent Review",
        "show_key": item.get("show_key"),
        "show_name": item.get("show_name"),
        "episode_time": item.get("date_time") or item.get("episode_time"),
        "guest": schedule_guest_label(item),
        "why_seen": "There is a show-like Google Calendar event inside 7 days without a trusted matching active HighLevel booking.",
        "blocking": "The system cannot tell whether this is a real manually-booked episode, a stale event, or a disconnected booking.",
        "next_action": item.get("next_human_action") or "Verify whether the event is intentional and reconcile it manually if needed.",
        "estimated_minutes": 8,
        "business_impact": "High",
        "blocked": True,
        "waiting_on": False,
        "ignored_risk": "The operator may prepare a stale event or miss the actual active booking source of truth.",
        "checklist": [
            "Confirm whether the calendar event is real",
            "Check HighLevel booking context",
            "Decide whether production should proceed",
        ],
        "calendar_event_url": item.get("calendar_event_url"),
        "source_issue_codes": schedule_source_codes(item),
    }


PRODUCTION_LINKEDIN_OPEN_STATUSES = {"Exists - Calendar Needs Update", "Urgent Review", "Ready to Create", "Due Soon"}
PRODUCTION_STREAMYARD_OPEN_STATUSES = {"Critical", "Urgent Review", "Ready to Create", "Due Soon"}


def explicit_sop_email_tracking(item):
    tracked_keys = {"sop_email_sent", "sop_emails_sent", "sop_email_scheduled", "sop_emails_scheduled"}
    for checklist_item in item.get("checklist_statuses") or []:
        key = checklist_item.get("key")
        if key in tracked_keys:
            return checklist_item
    return None


def production_links_close_criteria(item):
    criteria = []
    if item.get("linkedin_status") == "Present":
        criteria.append("LinkedIn URL present in Google Calendar")
    elif item.get("linkedin_status") == "Exists - Calendar Needs Update":
        criteria.append("Add the verified LinkedIn event URL to Google Calendar")
    else:
        criteria.append("LinkedIn URL present")
    if item.get("streamyard_status") == "Present":
        criteria.append("StreamYard URL present in Google Calendar")
    else:
        criteria.append("StreamYard URL present")
    sop_email_status = explicit_sop_email_tracking(item)
    if sop_email_status:
        criteria.append(f"SOP email status updated ({sop_email_status.get('label')}: {sop_email_status.get('status')})")
    else:
        criteria.append("SOP email status is not currently tracked in normalized audit data")
    return criteria


def production_links_task_needed(item):
    return item.get("linkedin_status") in PRODUCTION_LINKEDIN_OPEN_STATUSES or item.get("streamyard_status") in PRODUCTION_STREAMYARD_OPEN_STATUSES


def task_from_production_links(item):
    missing = []
    if item.get("linkedin_status") == "Exists - Calendar Needs Update":
        missing.append("LinkedIn URL in Google Calendar")
    elif item.get("linkedin_status") in PRODUCTION_LINKEDIN_OPEN_STATUSES:
        missing.append("LinkedIn promotion URL")
    if item.get("streamyard_status") in PRODUCTION_STREAMYARD_OPEN_STATUSES:
        missing.append("StreamYard link")
    label = "Finalize Production Links" if len(missing) > 1 else f"Finalize {missing[0]}" if missing else "Finalize Production Links"
    if item.get("linkedin_status") == "Exists - Calendar Needs Update" and item.get("streamyard_status") in PRODUCTION_STREAMYARD_OPEN_STATUSES:
        next_action = "Add the verified LinkedIn event URL to the Google Calendar description, verify the StreamYard URL is present, then rerun the audit to confirm the task can close."
    elif item.get("linkedin_status") == "Exists - Calendar Needs Update":
        next_action = "Add the verified LinkedIn event URL to the Google Calendar description, then rerun the audit to confirm the task closes."
    elif len(missing) > 1:
        next_action = "Create or locate the LinkedIn promotion URL and StreamYard link, then add them to the production source of truth after review."
    else:
        next_action = item.get("next_human_action") or "Create or locate the production link and add it to the source of truth after review."
    return {
        "task_kind": "production_links",
        "title": schedule_task_title(item, label),
        "group": "Production",
        "lane": "Today's Work" if item.get("current_production_status") == "Urgent Review" or (item.get("days_until") is not None and item.get("days_until") < DAILY_BRIEF_NEXT_DAYS) else "This Week",
        "status": item.get("current_production_status") or "Needs Attention",
        "show_key": item.get("show_key"),
        "show_name": item.get("show_name"),
        "episode_time": item.get("date_time") or item.get("episode_time"),
        "guest": schedule_guest_label(item),
        "why_seen": "A confirmed or human-confirmed episode is approaching and one or more production links are not ready.",
        "blocking": "No guest blocker is detected; this appears ready for human production prep.",
        "next_action": next_action,
        "estimated_minutes": 12 if len(missing) > 1 else 7,
        "business_impact": "High",
        "blocked": False,
        "waiting_on": False,
        "ignored_risk": "Guests and operators may not have the live-room or promotion link before the show.",
        "checklist": missing or ["Review production links"],
        "close_when": production_links_close_criteria(item),
        "calendar_event_url": item.get("calendar_event_url"),
        "source_issue_codes": schedule_source_codes(item),
    }


def task_from_replacement_finding(finding):
    guest = finding.get("guest") or "Replacement guest"
    return {
        "task_kind": "replacement_guest",
        "title": f"{guest}: Source Replacement Guest",
        "group": "PR",
        "lane": "This Week",
        "status": "Needs Replacement Guest",
        "show_key": finding.get("show_key"),
        "show_name": finding.get("show"),
        "episode_time": finding.get("episode"),
        "guest": guest,
        "why_seen": "A show inside the planning window has a canceled or missing confirmed guest.",
        "blocking": "A replacement guest has not been confirmed.",
        "next_action": finding.get("recommended_human_action") or "Write PR pitch / source replacement guest.",
        "estimated_minutes": 25,
        "business_impact": "High",
        "blocked": True,
        "waiting_on": False,
        "ignored_risk": "The show may not have a guest in time to produce the episode.",
        "checklist": [
            "Write PR pitch",
            "Source replacement guest",
            "Confirm booking path once guest is found",
        ],
        "calendar_event_url": (finding.get("raw_ids") or {}).get("google_calendar_event_url"),
        "source_issue_codes": [finding.get("issue_code")] if finding.get("issue_code") else [],
    }


def task_from_follow_up_finding(finding):
    guest = finding.get("guest") or "Guest status"
    return {
        "task_kind": "follow_up",
        "title": f"{guest}: Reconcile Guest Status",
        "group": "Guest Follow-up",
        "lane": "This Week",
        "status": "Needs Human Follow-Up",
        "show_key": finding.get("show_key"),
        "show_name": finding.get("show"),
        "episode_time": finding.get("episode"),
        "guest": guest,
        "why_seen": "The audit found a known mismatch or unclear guest status that still needs human follow-up.",
        "blocking": "Guest/client status is not reconciled between operational sources.",
        "next_action": finding.get("recommended_human_action") or "Follow up and reconcile HighLevel vs Google Calendar status.",
        "estimated_minutes": 8,
        "business_impact": "Medium",
        "blocked": True,
        "waiting_on": True,
        "ignored_risk": "The team may continue carrying uncertainty into future production planning.",
        "checklist": [
            "Confirm intended guest",
            "Check source-of-truth status",
            "Record the human decision for future audits",
        ],
        "calendar_event_url": (finding.get("raw_ids") or {}).get("google_calendar_event_url"),
        "source_issue_codes": [finding.get("issue_code")] if finding.get("issue_code") else [],
    }


def work_queue_sort_key(task):
    lane_order = {"Today's Work": 0, "This Week": 1, "Blocked": 2, "Waiting On": 3}
    impact_order = {"High": 0, "Medium": 1, "Low": 2}
    return (
        lane_order.get(task.get("lane"), 9),
        impact_order.get(task.get("business_impact"), 9),
        task.get("episode_time") or "",
        task.get("group") or "",
        task.get("title") or "",
    )


def build_work_queue(brief):
    tasks = {}
    for item in brief.get("next_7_days_schedule") or []:
        if item.get("topics_status") == "Blocked by Guest":
            add_work_task(tasks, task_from_guest_topics(item))
            continue
        if item.get("guest_status") == "Blocked by Confirmation":
            add_work_task(tasks, task_from_guest_confirmation(item))
            continue
        if item.get("calendar_status") == "Needs Verification" or item.get("highlevel_status_display") == "Needs Verification":
            add_work_task(tasks, task_from_calendar_mismatch(item))
            continue
        if production_links_task_needed(item):
            add_work_task(tasks, task_from_production_links(item))
    for finding in brief.get("guest_replacement_needed") or []:
        add_work_task(tasks, task_from_replacement_finding(finding))
    for finding in brief.get("follow_up_needed") or []:
        if finding.get("issue_code") in {"guest_rsvp_acceptance_risk", "guest_confirmation_pitch_follow_up"}:
            continue
        add_work_task(tasks, task_from_follow_up_finding(finding))

    task_list = sorted(tasks.values(), key=work_queue_sort_key)
    by_lane = {lane: [] for lane in WORK_QUEUE_LANES}
    by_group = {group: [] for group in WORK_QUEUE_GROUPS}
    for task in task_list:
        by_lane.setdefault(task.get("lane") or "Today's Work", []).append(task)
        by_group.setdefault(task.get("group") or "Production", []).append(task)
        if task.get("blocked") and task not in by_lane["Blocked"]:
            by_lane["Blocked"].append(task)
        if task.get("waiting_on") and task not in by_lane["Waiting On"]:
            by_lane["Waiting On"].append(task)
    return {
        "tasks": task_list,
        "by_lane": by_lane,
        "by_group": by_group,
        "total_estimated_minutes": sum(int(task.get("estimated_minutes") or 0) for task in task_list if task.get("lane") == "Today's Work"),
        "total_task_count": len(task_list),
    }


def completion_claim_guest(claim):
    return claim.get("guest_name") or claim.get("guest") or ""


def completion_claim_date(claim):
    return date_key(claim.get("episode_time") or claim.get("episode_date"))


def completion_claim_marked_at(claim):
    return parse_datetime(claim.get("marked_complete_at") or claim.get("completed_at") or claim.get("recorded_at"))


def guest_matches_claim(guest_name, guest_names):
    if not guest_name:
        return True
    expected = normalize_text(guest_name)
    values = [normalize_text(item) for item in guest_names or []]
    return any(expected == value or expected in value or value in expected for value in values if value)


def claim_matches_schedule_item(claim, item):
    claim_show_key = claim.get("show_key")
    if claim_show_key and normalize_text(claim_show_key) != normalize_text(item.get("show_key")):
        return False
    claim_show_name = claim.get("show_name")
    if claim_show_name and normalize_text(claim_show_name) != normalize_text(item.get("show_name")):
        return False
    claim_date = completion_claim_date(claim)
    if claim_date and claim_date != date_key(item.get("episode_time") or item.get("date_time")):
        return False
    return guest_matches_claim(completion_claim_guest(claim), item.get("guest_names") or [])


def claim_matches_task(claim, task):
    claim_task_id = claim.get("task_id")
    if claim_task_id:
        return normalize_text(claim_task_id) == normalize_text(task.get("task_id"))
    claim_task_kind = claim.get("task_kind")
    if claim_task_kind and normalize_text(claim_task_kind) != normalize_text(task.get("task_kind")):
        return False
    claim_show_key = claim.get("show_key")
    if claim_show_key and normalize_text(claim_show_key) != normalize_text(task.get("show_key")):
        return False
    claim_show_name = claim.get("show_name")
    if claim_show_name and normalize_text(claim_show_name) != normalize_text(task.get("show_name")):
        return False
    claim_date = completion_claim_date(claim)
    if claim_date and claim_date != date_key(task.get("episode_time")):
        return False
    return guest_matches_claim(completion_claim_guest(claim), [task.get("guest")])


def source_verified_linkedin_in_calendar(item):
    return bool(item.get("calendar_linkedin_urls"))


def source_verified_linkedin_any(item):
    return source_verified_linkedin_in_calendar(item) or bool((item.get("linkedin_event_summary") or {}).get("linkedin_event_url"))


def source_verified_streamyard(item):
    return bool(item.get("streamyard_urls"))


def completion_missing_for_production_links(item):
    verified = []
    missing = []
    not_tracked = []
    if source_verified_streamyard(item):
        verified.append("StreamYard URL present in Google Calendar location or description")
    else:
        missing.append("StreamYard URL is not yet present in Google Calendar location or description")
    if source_verified_linkedin_in_calendar(item):
        verified.append("LinkedIn URL present in Google Calendar description")
    elif (item.get("linkedin_event_summary") or {}).get("linkedin_event_url"):
        verified.append("LinkedIn event verified from known LinkedIn evidence")
        missing.append("Google Calendar description still needs the LinkedIn event URL")
    else:
        missing.append("LinkedIn URL is not yet present in Google Calendar description or known LinkedIn evidence")
    sop_email_status = explicit_sop_email_tracking(item)
    if sop_email_status:
        if sop_email_status.get("status") == "Complete":
            verified.append(f"{sop_email_status.get('label')} tracked as complete")
        else:
            missing.append(f"{sop_email_status.get('label')} is tracked as {sop_email_status.get('status')}")
    else:
        not_tracked.append("SOP email status is not currently tracked in normalized audit data")
    return verified, missing, not_tracked


def completion_result_sort_key(item):
    marked_at = completion_claim_marked_at(item.get("claim") or {})
    return (
        0 if marked_at else 1,
        "" if not marked_at else marked_at.isoformat(),
        item.get("show_name") or "",
        item.get("episode_time") or "",
        item.get("task_label") or "",
    )


def build_completion_verification(completed_tasks_payload, schedule, work_queue, now_local):
    claims = (completed_tasks_payload or {}).get("tasks") or []
    open_tasks = work_queue.get("tasks") or []
    results = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        matching_schedule = [item for item in schedule if claim_matches_schedule_item(claim, item)]
        matching_open_tasks = [task for task in open_tasks if claim_matches_task(claim, task)]
        marked_at = completion_claim_marked_at(claim)
        result = {
            "claim": claim,
            "task_id": claim.get("task_id"),
            "task_kind": claim.get("task_kind") or (matching_open_tasks[0].get("task_kind") if len(matching_open_tasks) == 1 else ""),
            "task_label": claim.get("task_label") or claim.get("title") or (matching_open_tasks[0].get("title") if len(matching_open_tasks) == 1 else "Claimed completed task"),
            "show_key": claim.get("show_key") or (matching_schedule[0].get("show_key") if len(matching_schedule) == 1 else ""),
            "show_name": claim.get("show_name") or (matching_schedule[0].get("show_name") if len(matching_schedule) == 1 else ""),
            "episode_time": claim.get("episode_time") or (matching_schedule[0].get("episode_time") if len(matching_schedule) == 1 else ""),
            "episode_date": completion_claim_date(claim) or (date_key(matching_schedule[0].get("episode_time")) if len(matching_schedule) == 1 else ""),
            "guest_name": completion_claim_guest(claim) or (", ".join(matching_schedule[0].get("guest_names") or []) if len(matching_schedule) == 1 else ""),
            "marked_complete_at": marked_at.isoformat() if marked_at else claim.get("marked_complete_at") or claim.get("completed_at") or claim.get("recorded_at"),
            "marked_complete_by": claim.get("marked_complete_by") or claim.get("completed_by") or claim.get("recorded_by"),
            "claimed_actions": claim.get("claimed_actions") or [],
            "notes": claim.get("notes"),
            "verification_status": "Needs human review",
            "verified_checks": [],
            "still_missing": [],
            "not_tracked": [],
            "related_work_queue_item_removed": False,
            "current_task_title": matching_open_tasks[0].get("title") if len(matching_open_tasks) == 1 else None,
            "current_task_status": matching_open_tasks[0].get("status") if len(matching_open_tasks) == 1 else None,
            "explanation": "The completion claim needs human review before the system can confirm it.",
        }
        if len(matching_schedule) > 1 or len(matching_open_tasks) > 1:
            result["verification_status"] = "Needs human review"
            result["explanation"] = "Multiple matching episodes or work queue items were found, so the completion claim could not be verified safely."
            results.append(result)
            continue
        current_task = matching_open_tasks[0] if len(matching_open_tasks) == 1 else None
        current_schedule = matching_schedule[0] if len(matching_schedule) == 1 else None
        if result["task_kind"] == "production_links" and current_schedule:
            verified, missing, not_tracked = completion_missing_for_production_links(current_schedule)
            result["verified_checks"] = verified
            result["still_missing"] = missing
            result["not_tracked"] = not_tracked
            result["related_work_queue_item_removed"] = not production_links_task_needed(current_schedule)
            if not missing and result["related_work_queue_item_removed"]:
                result["verification_status"] = "Completed and verified"
                result["explanation"] = "The fresh audit confirms the production links are present and the related work queue item is no longer open."
            elif current_task:
                result["verification_status"] = "Still open"
                result["current_task_title"] = current_task.get("title")
                result["current_task_status"] = current_task.get("status")
                result["explanation"] = "The fresh audit still shows the related production-links task as open."
            else:
                result["verification_status"] = "Completed but not verified"
                result["explanation"] = "The claim no longer appears as an open work queue item, but at least one requested completion check is still missing from source data."
            results.append(result)
            continue
        if current_task:
            result["verification_status"] = "Still open"
            result["still_missing"] = list(current_task.get("checklist") or [])
            result["not_tracked"] = list(current_task.get("close_when") or [])
            result["explanation"] = current_task.get("next_action") or "The fresh audit still shows the related work queue item as open."
            results.append(result)
            continue
        if current_schedule or result.get("show_key") or result.get("show_name"):
            result["verification_status"] = "Completed and verified"
            result["related_work_queue_item_removed"] = True
            result["explanation"] = "The fresh audit no longer shows a matching work queue item for this claim."
        else:
            result["verification_status"] = "Completed but not verified"
            result["explanation"] = "The claim was recorded locally, but the fresh audit could not match it to current source-backed episode data."
        results.append(result)

    results = sorted(results, key=completion_result_sort_key, reverse=True)
    counts = {status: 0 for status in COMPLETION_STATUSES}
    for item in results:
        counts[item.get("verification_status")] = counts.get(item.get("verification_status"), 0) + 1
    today_key = now_local.date().isoformat()
    completed_today = [
        item
        for item in results
        if item.get("verification_status") == "Completed and verified"
        and date_key(item.get("marked_complete_at")) == today_key
    ]
    return {
        "completed_tasks_path": str(DEFAULT_COMPLETED_TASKS_PATH),
        "claims": results,
        "completed_today": completed_today,
        "summary": {
            "total_claims": len(results),
            "counts_by_status": counts,
            "completed_today_count": len(completed_today),
        },
    }


def brief_item_flags(item):
    flags = []
    if not item.get("calendar_event_found"):
        flags.append("Calendar status unclear")
    if item.get("highlevel_status_display") == "Needs Verification":
        flags.append("HighLevel/calendar mismatch")
    if item.get("guest_status") in {"Needs Replacement Guest", "Blocked by Confirmation", "Urgent Review"}:
        flags.append(item["guest_status"])
    if item.get("topics_status") == "Blocked by Guest":
        flags.append("Blocked by Guest")
    if item.get("linkedin_status") in {"Exists - Calendar Needs Update", "Urgent Review", "Ready to Create", "Blocked by Guest", "Blocked by Confirmation"}:
        flags.append(f"LinkedIn {item['linkedin_status']}")
    if item.get("streamyard_status") in {"Critical", "Urgent Review", "Ready to Create", "Blocked by Guest", "Blocked by Confirmation"}:
        flags.append(f"StreamYard {item['streamyard_status']}")
    return flags


def brief_item_status(item):
    issues = item.get("issues") or []
    if any(effective_issue_severity(issue) == "Critical" for issue in issues):
        return "Blocked"
    flags = set(item.get("flags") or [])
    if {"Needs Replacement Guest", "StreamYard Critical"} & flags:
        return "Blocked"
    if any("Urgent Review" in flag for flag in flags):
        return "Urgent Review"
    if any(effective_issue_severity(issue) == "Warning" for issue in issues) or flags:
        return "Needs Attention"
    return item.get("production_status") or "Ready"


def brief_issue_sort_key(item):
    return (
        SEVERITY_ORDER.get(effective_issue_severity(item), 9),
        item.get("episode_time") or "",
        item.get("show_name") or "",
        item.get("code") or "",
    )


def issue_list_by_event_id(report):
    grouped = {}
    for issue in report.get("issues") or []:
        event_id = issue.get("calendar_event_id") or ((issue.get("relevant_raw_ids") or {}).get("google_calendar_event_id"))
        if event_id:
            grouped.setdefault(event_id, []).append(issue)
    for values in grouped.values():
        values.sort(key=brief_issue_sort_key)
    return grouped


def issue_list_by_episode_key(report):
    grouped = {}
    for issue in report.get("issues") or []:
        key = (issue.get("show_key"), issue.get("episode_time"))
        if key[0] and key[1]:
            grouped.setdefault(key, []).append(issue)
    for values in grouped.values():
        values.sort(key=brief_issue_sort_key)
    return grouped


def finding_event_ids(manager_dashboard, key):
    event_ids = set()
    for finding in manager_dashboard.get(key) or []:
        raw_ids = finding.get("raw_ids") or {}
        event_id = raw_ids.get("google_calendar_event_id")
        if event_id:
            event_ids.add(event_id)
    return event_ids


def daily_issue_needs_action_today(issue, now_local):
    if effective_issue_severity(issue) == "Critical":
        return True
    if (issue.get("operator_recommendation") or {}).get("category") == "Urgent Review":
        return True
    bucket = brief_issue_bucket(issue)
    code = issue.get("code")
    issue_time = parse_datetime(issue.get("episode_time"))
    days_until = None
    if issue_time:
        days_until = (issue_time.astimezone(LOCAL_TIMEZONE) - now_local).total_seconds() / 86400
    near_term = days_until is not None and -1 <= days_until <= DAILY_BRIEF_NEXT_DAYS
    replacement_window = days_until is not None and -1 <= days_until <= DAILY_BRIEF_REPLACEMENT_DAYS
    if code == "show_needs_guest_replacement":
        return replacement_window
    if code in {"guest_topics_pending", "guest_rsvp_acceptance_risk", "needs_human_follow_up"}:
        return near_term or replacement_window
    if bucket in {"Waiting on Guest", "Waiting on Guest Topics", "Needs Human Follow-Up", "Confirmed Issues"}:
        return near_term
    if code in {"sop_required_assets_missing", "calendar_event_without_booking"}:
        return near_term
    return False


def dedupe_issues(issues):
    seen = set()
    deduped = []
    for issue in issues or []:
        key = issue_identity_key(issue)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def build_daily_schedule(report, manager_dashboard, calendar_events, rules, now_local):
    aliases = show_aliases_for_daily_brief(report, rules)
    events_by_id = {event.get("id"): event for event in calendar_events if event.get("id")}
    issues_by_event = issue_list_by_event_id(report)
    issues_by_episode = issue_list_by_episode_key(report)
    represented_guest_event_ids = finding_event_ids(manager_dashboard, "represented_guest_findings")
    human_confirmed_event_ids = finding_event_ids(manager_dashboard, "human_confirmed_active_findings")
    known_exception_event_ids = finding_event_ids(manager_dashboard, "known_exception_findings")
    window_end = now_local + timedelta(days=DAILY_BRIEF_NEXT_DAYS)
    schedule = []
    included_event_ids = set()

    for episode in manager_dashboard.get("all_episodes") or []:
        episode_time = parse_datetime(episode.get("episode_time"))
        if not episode_time:
            continue
        local_time = episode_time.astimezone(LOCAL_TIMEZONE)
        if local_time < now_local or local_time > window_end:
            continue
        event_id = episode.get("calendar_event_id")
        event = events_by_id.get(event_id)
        if event_id:
            included_event_ids.add(event_id)
        event_text = calendar_text_for_brief(event)
        issue_candidates = dedupe_issues(
            list(episode.get("issues") or [])
            + list(issues_by_event.get(event_id, []))
            + list(issues_by_episode.get((episode.get("show_key"), episode.get("episode_time")), []))
        )
        item = {
            "source": "HighLevel discovery",
            "show_key": episode.get("show_key"),
            "show_name": episode.get("show_name"),
            "episode_title": episode.get("calendar_event_title") or "Untitled episode",
            "episode_time": episode.get("episode_time"),
            "date_time": (event.get("start") if event else episode_time).isoformat() if (event or episode_time) else None,
            "guest_names": episode.get("guest_names") or [],
            "calendar_event_found": bool(event_id),
            "calendar_event_title": episode.get("calendar_event_title"),
            "calendar_event_url": episode.get("calendar_event_url") or (event or {}).get("url"),
            "calendar_event_id": event_id,
            "highlevel_booking_found": has_complete_checklist_item(episode, "highlevel_booking"),
            "highlevel_status": "PR Representative Booking / Guest Represented"
            if event_id in represented_guest_event_ids
            else "Yes"
            if has_complete_checklist_item(episode, "highlevel_booking")
            else "No",
            "production_status": episode.get("production_status"),
            "readiness_percentage": episode.get("readiness_percentage"),
            "issues": issue_candidates,
            "checklist_statuses": episode.get("checklist_statuses") or [],
            "timeline": episode.get("timeline") or [],
            "linkedin_urls": extract_linkedin_urls(event_text),
            "calendar_linkedin_urls": extract_linkedin_urls(event_text),
            "streamyard_urls": extract_streamyard_urls(event_text),
            "represented_guest_summary": represented_guest_summary_from_issues(issue_candidates) or (
                (episode.get("represented_guest_matches") or [None])[0] or {}
            ),
            "linkedin_event_summary": linkedin_event_summary_from_issues(issue_candidates),
        }
        if item["linkedin_event_summary"].get("linkedin_event_url") and item["linkedin_event_summary"]["linkedin_event_url"] not in item["linkedin_urls"]:
            item["linkedin_urls"].append(item["linkedin_event_summary"]["linkedin_event_url"])
        item["guest_names"] = display_guests_for_brief(item, aliases.get(item.get("show_key")))
        item = finalize_schedule_item(item, now_local)
        schedule.append(item)

    for event in calendar_events:
        event_start = event.get("start")
        if not event_start:
            continue
        local_time = event_start.astimezone(LOCAL_TIMEZONE)
        if local_time < now_local or local_time > window_end:
            continue
        if event.get("id") in included_event_ids:
            continue
        show_key = show_key_for_calendar_event(event, aliases)
        if not show_key:
            continue
        event_text = calendar_text_for_brief(event)
        issues = dedupe_issues(issues_by_event.get(event.get("id"), []))
        item = {
            "source": "Google Calendar export",
            "show_key": show_key,
            "show_name": configured_show_name(rules, show_key),
            "episode_title": event.get("title") or "Untitled episode",
            "episode_time": event_start.isoformat(),
            "date_time": event_start.isoformat(),
            "guest_names": display_guests_from_title(event.get("title"), aliases.get(show_key)),
            "calendar_event_found": True,
            "calendar_event_title": event.get("title"),
            "calendar_event_url": event.get("url"),
            "calendar_event_id": event.get("id"),
            "highlevel_booking_found": False,
            "highlevel_status": "PR Representative Booking / Guest Represented"
            if event.get("id") in represented_guest_event_ids
            else "Human-confirmed active"
            if event.get("id") in human_confirmed_event_ids
            else "Known exception"
            if event.get("id") in known_exception_event_ids
            else "No",
            "production_status": operational_status_from_counts(effective_issue_counts(issues)),
            "readiness_percentage": None,
            "issues": issues,
            "checklist_statuses": [],
            "timeline": [],
            "linkedin_urls": extract_linkedin_urls(event_text),
            "calendar_linkedin_urls": extract_linkedin_urls(event_text),
            "streamyard_urls": extract_streamyard_urls(event_text),
            "represented_guest_summary": represented_guest_summary_from_issues(issues),
            "linkedin_event_summary": linkedin_event_summary_from_issues(issues),
        }
        if item["linkedin_event_summary"].get("linkedin_event_url") and item["linkedin_event_summary"]["linkedin_event_url"] not in item["linkedin_urls"]:
            item["linkedin_urls"].append(item["linkedin_event_summary"]["linkedin_event_url"])
        item = finalize_schedule_item(item, now_local)
        schedule.append(item)

    schedule.sort(key=lambda item: item.get("date_time") or item.get("episode_time") or "")
    return schedule


def brief_findings(manager_dashboard, key, limit=None):
    findings = manager_dashboard.get(key) or []
    if limit is not None:
        return findings[:limit]
    return findings


def brief_finding_line(finding):
    guest = finding.get("guest")
    guest_text = f" ({guest})" if guest else ""
    action = finding.get("recommended_human_action") or finding.get("recommended_action")
    return f"{finding.get('show')} - {short_date(finding.get('episode'))}{guest_text}: {finding.get('issue')} Action: {action}"


def brief_issue_line(issue):
    action = issue.get("recommended_action")
    return f"{issue.get('show_name')} - {short_date(issue.get('episode_time'))}: {issue.get('message')} Action: {action}"


def brief_schedule_issue_summary(item):
    labels = []
    for issue in item.get("issues") or []:
        labels.append(f"{issue.get('code')}: {issue.get('message')}")
    return labels


def md_brief(value, limit=900):
    return compact(value, limit=limit).replace("|", "\\|").replace("\n", " ")


def build_daily_brief_payload(report, manager_dashboard, calendar_events, rules, now_local, completed_tasks_payload=None, completed_tasks_path=None):
    health = manager_dashboard.get("overall_production_health") or report.get("overall_production_health") or {}
    issue_counts = manager_dashboard.get("issue_counts") or report.get("severity_counts") or {}
    trust_summary = manager_dashboard.get("trust_summary") or {}
    bucket_counts = trust_summary.get("counts_by_dashboard_bucket") or {}
    health_by_show = manager_dashboard.get("health_by_show") or report.get("show_summary") or {}
    shows_needing_attention = [
        value.get("show_name") or key
        for key, value in health_by_show.items()
        if key != "unknown" and (value.get("operational_status") == "Needs Attention" or (value.get("warning") or 0) > 0 or (value.get("critical") or 0) > 0)
    ]
    schedule = build_daily_schedule(report, manager_dashboard, calendar_events, rules, now_local)
    waiting_on = {
        "guest": brief_findings(manager_dashboard, "waiting_on_guest_findings") + brief_findings(manager_dashboard, "waiting_on_guest_topics_findings"),
        "client": brief_findings(manager_dashboard, "waiting_on_client_findings"),
        "internal_team": brief_findings(manager_dashboard, "waiting_on_internal_team_findings"),
        "confirmation": brief_findings(manager_dashboard, "needs_human_follow_up_findings"),
    }
    replacement = brief_findings(manager_dashboard, "needs_guest_replacement_findings")
    follow_up = (
        brief_findings(manager_dashboard, "needs_human_follow_up_findings")
        + brief_findings(manager_dashboard, "waiting_on_guest_findings")
    )
    known_exceptions = (
        brief_findings(manager_dashboard, "known_exception_findings")
        + brief_findings(manager_dashboard, "known_calendar_ownership_exception_findings")
        + brief_findings(manager_dashboard, "human_confirmed_active_findings")
    )
    future_safe_actions = brief_findings(manager_dashboard, "future_safe_action_findings", limit=10)
    linkedin_watch = [item for item in schedule if item.get("linkedin_status") != "Present"]
    streamyard_watch = [item for item in schedule if item.get("streamyard_status") != "Present"]
    urgent_review = sorted(
        [
            issue
            for issue in report.get("issues") or []
            if (issue.get("operator_recommendation") or {}).get("category") == "Urgent Review"
        ],
        key=brief_issue_sort_key,
    )
    fix_today = sorted(
        dedupe_issues(issue for issue in report.get("issues") or [] if daily_issue_needs_action_today(issue, now_local)),
        key=brief_issue_sort_key,
    )
    safe_to_ignore = {
        "not_due_yet": len(manager_dashboard.get("not_due_yet_findings") or []),
        "known_exceptions": len(known_exceptions),
        "human_confirmed_active": len(manager_dashboard.get("human_confirmed_active_findings") or []),
    }
    represented_lookup = {}
    for issue in list(report.get("issues") or []) + list(report.get("suppressed_issues") or []):
        details = issue.get("details") or {}
        if not details.get("represented_guest"):
            continue
        key = issue.get("calendar_event_id") or issue.get("episode_time")
        represented_lookup[key] = details
    represented_guest_matches = []
    for finding in manager_dashboard.get("represented_guest_findings") or []:
        raw_ids = finding.get("raw_ids") or {}
        details = represented_lookup.get(raw_ids.get("google_calendar_event_id")) or {}
        event_time = parse_datetime(finding.get("episode"))
        if not event_time:
            continue
        local_time = event_time.astimezone(LOCAL_TIMEZONE)
        if local_time < now_local or local_time > now_local + timedelta(days=DAILY_BRIEF_NEXT_DAYS):
            continue
        represented_guest_matches.append(
            {
                "show_name": finding.get("show"),
                "date_time": finding.get("episode"),
                "represented_guest_summary": {
                    "highlevel_submitter_contact": details.get("highlevel_submitter_contact") or finding.get("guest"),
                    "represented_guest": details.get("represented_guest") or finding.get("guest"),
                    "confidence": details.get("represented_guest_confidence") or finding.get("confidence"),
                    "evidence": details.get("represented_guest_evidence") or [],
                },
            }
        )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today": now_local.date().isoformat(),
        "read_only": True,
        "source_report": str(DEFAULT_OUTPUT_DIR / "operations_audit_report.json"),
        "source_dashboard": str(DEFAULT_OUTPUT_DIR / "operations_manager_dashboard.json"),
        "health": health,
        "issue_counts": issue_counts,
        "shows_needing_attention": sorted(set(shows_needing_attention)),
        "safe_to_ignore_today": safe_to_ignore,
        "trust_bucket_counts": bucket_counts,
        "next_7_days_schedule": schedule,
        "represented_guest_matches": represented_guest_matches,
        "linkedin_event_manual_evidence": [
            item for item in schedule if (item.get("linkedin_event_summary") or {}).get("linkedin_event_url")
        ],
        "urgent_review": urgent_review,
        "fix_today": fix_today,
        "waiting_on": waiting_on,
        "guest_replacement_needed": replacement,
        "follow_up_needed": follow_up,
        "not_due_yet_summary": {
            "count": len(manager_dashboard.get("not_due_yet_findings") or []),
            "message": "These items are required later by the production timeline and should not be treated as problems today.",
        },
        "known_exceptions": known_exceptions,
        "future_safe_actions": future_safe_actions,
        "missing_linkedin_url": linkedin_watch,
        "missing_streamyard_url": streamyard_watch,
        "linkedin_status_watch": linkedin_watch,
        "streamyard_status_watch": streamyard_watch,
        "critical_issues": manager_dashboard.get("critical_issues") or [],
    }
    payload["work_queue"] = build_work_queue(payload)
    payload["completion_tracking"] = build_completion_verification(completed_tasks_payload or COMPLETED_TASKS_DEFAULT, payload.get("next_7_days_schedule") or [], payload["work_queue"], now_local)
    if completed_tasks_path:
        payload["completion_tracking"]["completed_tasks_path"] = str(completed_tasks_path)
    return payload


def render_brief_finding_lines(findings, empty_label):
    if not findings:
        return [empty_label]
    return [f"- {md_brief(brief_finding_line(item))}" for item in findings]


def render_brief_issue_lines(issues, empty_label):
    if not issues:
        return [empty_label]
    return [f"- {md_brief(brief_issue_line(item))}" for item in issues]


def render_work_task_markdown(task):
    lines = [
        f"### {md_brief(task.get('title'), 180)}",
        "",
        f"- Group: {md_brief(task.get('group'))}",
        f"- Status: {md_brief(task.get('status'))}",
        f"- Show: {md_brief(task.get('show_name'))}",
        f"- Episode: {md_brief(short_date(task.get('episode_time')))}",
        f"- Why am I seeing this? {md_brief(task.get('why_seen'))}",
        f"- What is blocking it? {md_brief(task.get('blocking'))}",
        f"- Next action: {md_brief(task.get('next_action'))}",
        f"- Estimated time: {task_time_text(task.get('estimated_minutes'))}",
        f"- Business impact: {md_brief(task.get('business_impact'))}",
        f"- What happens if I ignore it? {md_brief(task.get('ignored_risk'))}",
    ]
    checklist = task.get("checklist") or []
    if checklist:
        lines.append(f"- Checklist: {md_brief('; '.join(checklist), 520)}")
    close_when = task.get("close_when") or []
    if close_when:
        lines.append(f"- Close when: {md_brief('; '.join(close_when), 520)}")
    if task.get("calendar_event_url"):
        lines.append(f"- Calendar: {task.get('calendar_event_url')}")
    return lines + [""]


def render_completion_claim_markdown(item):
    lines = [
        f"### {md_brief(item.get('task_label') or 'Claimed completed task', 180)}",
        "",
        f"- Status: {md_brief(item.get('verification_status'))}",
        f"- Show: {md_brief(item.get('show_name') or item.get('show_key') or 'Unknown')}",
        f"- Episode: {md_brief(short_date(item.get('episode_time') or item.get('episode_date')))}",
        f"- Guest: {md_brief(item.get('guest_name') or 'Unknown')}",
        f"- Marked complete by: {md_brief(item.get('marked_complete_by') or 'Unknown')}",
        f"- Marked complete at: {md_brief(item.get('marked_complete_at') or 'Unknown')}",
        f"- Explanation: {md_brief(item.get('explanation'))}",
    ]
    claimed_actions = item.get("claimed_actions") or []
    if claimed_actions:
        lines.append(f"- Claimed actions: {md_brief('; '.join(claimed_actions), 520)}")
    verified_checks = item.get("verified_checks") or []
    if verified_checks:
        lines.append(f"- Verified: {md_brief('; '.join(verified_checks), 520)}")
    still_missing = item.get("still_missing") or []
    if still_missing:
        lines.append(f"- Still missing: {md_brief('; '.join(still_missing), 520)}")
    not_tracked = item.get("not_tracked") or []
    if not_tracked:
        lines.append(f"- Not tracked: {md_brief('; '.join(not_tracked), 520)}")
    if item.get("notes"):
        lines.append(f"- Notes: {md_brief(item.get('notes'), 520)}")
    return lines + [""]


def render_completion_claim_html(item):
    claimed_actions = item.get("claimed_actions") or []
    verified_checks = item.get("verified_checks") or []
    still_missing = item.get("still_missing") or []
    not_tracked = item.get("not_tracked") or []
    return (
        '<article class="task-card">'
        f"<div class=\"task-top\"><h3>{html_text(item.get('task_label') or 'Claimed completed task', 180)}</h3>{badge(item.get('verification_status'), manager_status_class(item.get('verification_status')))}</div>"
        f"<p><strong>Show:</strong> {html_text(item.get('show_name') or item.get('show_key') or 'Unknown', 120)} <strong>Guest:</strong> {html_text(item.get('guest_name') or 'Unknown', 140)}</p>"
        f"<p><strong>Episode:</strong> {html_text(short_date(item.get('episode_time') or item.get('episode_date')), 120)}</p>"
        f"<p><strong>Marked complete by:</strong> {html_text(item.get('marked_complete_by') or 'Unknown', 120)} <strong>At:</strong> {html_text(item.get('marked_complete_at') or 'Unknown', 140)}</p>"
        f"<p><strong>Explanation:</strong> {html_text(item.get('explanation'), 420)}</p>"
        + (f"<p><strong>Claimed actions:</strong> {html_text('; '.join(claimed_actions), 520)}</p>" if claimed_actions else "")
        + (f"<p><strong>Verified:</strong> {html_text('; '.join(verified_checks), 520)}</p>" if verified_checks else "")
        + (f"<p><strong>Still missing:</strong> {html_text('; '.join(still_missing), 520)}</p>" if still_missing else "")
        + (f"<p><strong>Not tracked:</strong> {html_text('; '.join(not_tracked), 520)}</p>" if not_tracked else "")
        + (f"<p><strong>Notes:</strong> {html_text(item.get('notes'), 520)}</p>" if item.get("notes") else "")
        + "</article>"
    )


def render_work_queue_markdown(queue):
    lines = [
        "## Operations Copilot Work Queue",
        "",
        f"- Tasks: {queue.get('total_task_count', 0)}",
        f"- Estimated today's work: {task_time_text(queue.get('total_estimated_minutes', 0))}",
        "- Mode: read-only recommendations only; no automation will run.",
        "",
    ]
    by_lane = queue.get("by_lane") or {}
    for lane in WORK_QUEUE_LANES:
        tasks = by_lane.get(lane) or []
        lines.extend([f"## {lane}", ""])
        if not tasks:
            lines.extend([f"No {lane.lower()} tasks.", ""])
            continue
        for task in tasks:
            lines.extend(render_work_task_markdown(task))
    lines.extend(["## Work By Group", ""])
    by_group = queue.get("by_group") or {}
    for group in WORK_QUEUE_GROUPS:
        tasks = by_group.get(group) or []
        if not tasks:
            lines.append(f"- {group}: none")
        else:
            labels = "; ".join(task.get("title") for task in tasks)
            lines.append(f"- {group}: {len(tasks)} task(s) - {md_brief(labels, 700)}")
    lines.append("")
    return lines


def render_daily_brief_markdown(brief):
    health = brief.get("health") or {}
    counts = brief.get("issue_counts") or {}
    schedule = brief.get("next_7_days_schedule") or []
    work_queue = brief.get("work_queue") or {}
    completion_tracking = brief.get("completion_tracking") or {}
    completion_summary = completion_tracking.get("summary") or {}
    lines = [
        "# Daily Operations Brief",
        "",
        f"- Generated at: {brief.get('generated_at')}",
        f"- Today: {brief.get('today')}",
        "- Mode: read-only; generated from local audit outputs only",
        "",
        "## Today's Production Status",
        "",
        f"- Overall health: {health.get('score', 'n/a')} - {health.get('label', 'unknown')}",
        f"- Critical issues: {counts.get('Critical', 0)}",
        f"- Shows needing attention: {md_escape(', '.join(brief.get('shows_needing_attention') or []) or 'None')}",
        f"- Safe to ignore today: {brief.get('safe_to_ignore_today', {}).get('not_due_yet', 0)} not-yet-due findings, {brief.get('safe_to_ignore_today', {}).get('known_exceptions', 0)} known exceptions/human-confirmed items",
        "",
    ]
    lines.extend(render_work_queue_markdown(work_queue))
    lines.extend(
        [
            "## Completion Verification",
            "",
            f"- Total completion claims reviewed: {completion_summary.get('total_claims', 0)}",
            f"- Completed and verified: {(completion_summary.get('counts_by_status') or {}).get('Completed and verified', 0)}",
            f"- Completed but not verified: {(completion_summary.get('counts_by_status') or {}).get('Completed but not verified', 0)}",
            f"- Still open: {(completion_summary.get('counts_by_status') or {}).get('Still open', 0)}",
            f"- Needs human review: {(completion_summary.get('counts_by_status') or {}).get('Needs human review', 0)}",
            f"- Completion claims file: {md_escape((completion_tracking.get('completed_tasks_path') or 'data/audit/completed_tasks.json'))}",
            "",
            "## Completed Today",
            "",
        ]
    )
    completed_today = completion_tracking.get("completed_today") or []
    if not completed_today:
        lines.extend(["No tasks completed and verified today.", ""])
    else:
        for item in completed_today:
            lines.extend(render_completion_claim_markdown(item))
    lines.extend(["## Completion Claims", ""])
    all_claims = completion_tracking.get("claims") or []
    if not all_claims:
        lines.extend(["No local completion claims have been recorded yet.", ""])
    else:
        for item in all_claims:
            lines.extend(render_completion_claim_markdown(item))
    lines.extend(["## Next 7 Days Show Schedule", ""])
    if not schedule:
        lines.extend(["No configured show episodes are scheduled in the next 7 days.", ""])
    else:
        lines.extend(
            [
                "| Date/Time | Show | Guest(s) | Guest Status | Topics Status | LinkedIn URL Status | StreamYard URL Status | Calendar Status | HighLevel Status | Blocking Production | Next Human Action |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in schedule:
            calendar_label = item.get("calendar_status") or "Unknown"
            if item.get("calendar_event_url"):
                calendar_label = f"{calendar_label}: [{item.get('calendar_event_title') or 'Open event'}]({item.get('calendar_event_url')})"
            linkedin_label = item.get("linkedin_status") or "Unknown"
            if item.get("linkedin_urls"):
                prefix = item.get("linkedin_status") or "Present"
                if prefix == "Present":
                    linkedin_label = f"Present: {', '.join(item.get('linkedin_urls') or [])}"
                else:
                    linkedin_label = f"{prefix}: {', '.join(item.get('linkedin_urls') or [])}"
            streamyard_label = item.get("streamyard_status") or "Unknown"
            if item.get("streamyard_urls"):
                streamyard_label = f"Present: {', '.join(item.get('streamyard_urls') or [])}"
            lines.append(
                f"| {md_escape(short_date(item.get('date_time')))} | {md_escape(item.get('show_name'))} | "
                f"{md_escape(', '.join(item.get('guest_names') or []) or 'Unknown')} | "
                f"{md_escape(item.get('guest_status'))} | {md_escape(item.get('topics_status'))} | "
                f"{md_escape(linkedin_label)} | {md_escape(streamyard_label)} | {calendar_label} | "
                f"{md_escape(item.get('highlevel_status_display') or item.get('highlevel_status'))} | "
                f"{md_escape('; '.join(item.get('production_blockers') or []) or 'None')} | "
                f"{md_escape(item.get('next_human_action'))} |"
            )
        lines.append("")
    lines.extend(["", "## Not Due Yet", ""])
    not_due = brief.get("not_due_yet_summary") or {}
    lines.append(f"- {not_due.get('count', 0)} items are not due yet. {md_escape(not_due.get('message'))}")
    lines.extend(["", "## Known Exceptions", ""])
    known = brief.get("known_exceptions") or []
    if known:
        lines.append(f"- {len(known)} active known exception or human-confirmed context item(s) are being tracked.")
    else:
        lines.append("- No active known exceptions.")
    lines.extend(["", "## LinkedIn Event Evidence", ""])
    manual_linkedin = brief.get("linkedin_event_manual_evidence") or []
    if manual_linkedin:
        for item in manual_linkedin:
            summary = item.get("linkedin_event_summary") or {}
            lines.append(f"- {md_escape(item.get('show_name'))} - {md_escape(short_date(item.get('date_time')))} - {md_escape(', '.join(item.get('guest_names') or []) or 'Unknown')}")
            lines.append(f"  LinkedIn event exists: {summary.get('linkedin_event_url')}")
            lines.append(f"  Source: {md_escape(summary.get('source') or 'Unknown')}")
            lines.append(f"  Verified by: {md_escape(summary.get('verified_by') or 'Unknown')}")
            lines.append(f"  Notes: {md_escape(summary.get('notes') or 'None')}")
    else:
        lines.append("- No external/manual LinkedIn event evidence is recorded for the next 7 days.")
    lines.extend(["", "## PR Representative Bookings", ""])
    represented = brief.get("represented_guest_matches") or []
    if represented:
        for item in represented:
            summary = item.get("represented_guest_summary") or {}
            lines.append(f"- Show: {md_escape(item.get('show_name'))} - {md_escape(short_date(item.get('date_time')))}")
            lines.append(f"  HighLevel submitter/contact: {md_escape(summary.get('highlevel_submitter_contact') or 'Unknown')}")
            lines.append(f"  Represented guest: {md_escape(summary.get('represented_guest') or 'Unknown')}")
            lines.append(f"  Confidence: {md_escape(summary.get('confidence') or 'Unknown')}")
            lines.append(f"  Evidence: {md_escape(', '.join(summary.get('evidence') or []) or 'None recorded')}")
    else:
        lines.append("- No PR representative bookings were inferred in the next 7 days.")
    lines.extend(["", "## Future Safe Actions", ""])
    future = brief.get("future_safe_actions") or []
    if future:
        lines.append(f"- {len(future)} future safe action candidate(s) exist, but automation remains disabled.")
    else:
        lines.append("- No future safe action candidates are ready to review.")
    lines.extend(["", "## Production Links To Watch", ""])
    lines.append(f"- LinkedIn URL statuses needing attention in next 7 days: {len(brief.get('linkedin_status_watch') or [])}")
    for item in brief.get("linkedin_status_watch") or []:
        lines.append(f"- LinkedIn {md_escape(item.get('linkedin_status'))}: {md_escape(item.get('show_name'))} - {md_escape(short_date(item.get('date_time')))} - {md_escape(item.get('episode_title'))}")
    lines.append(f"- StreamYard URL statuses needing attention in next 7 days: {len(brief.get('streamyard_status_watch') or [])}")
    for item in brief.get("streamyard_status_watch") or []:
        lines.append(f"- StreamYard {md_escape(item.get('streamyard_status'))}: {md_escape(item.get('show_name'))} - {md_escape(short_date(item.get('date_time')))} - {md_escape(item.get('episode_title'))}")
    lines.append("")
    return "\n".join(lines)


def html_brief_list(items, empty_label):
    if not items:
        return f"<p class=\"muted\">{html_text(empty_label)}</p>"
    return "<ul>" + "".join(f"<li>{html_text(item, 420)}</li>" for item in items) + "</ul>"


def html_brief_finding_list(findings, empty_label):
    return html_brief_list([brief_finding_line(item) for item in findings], empty_label)


def html_brief_issue_list(issues, empty_label):
    return html_brief_list([brief_issue_line(item) for item in issues], empty_label)


def render_work_task_html(task):
    checklist = task.get("checklist") or []
    checklist_html = ""
    if checklist:
        checklist_html = "<p><strong>Checklist:</strong> " + html_text("; ".join(checklist), 520) + "</p>"
    close_when = task.get("close_when") or []
    close_when_html = ""
    if close_when:
        close_when_html = "<p><strong>Close when:</strong> " + html_text("; ".join(close_when), 520) + "</p>"
    calendar_html = ""
    if task.get("calendar_event_url"):
        calendar_html = f"<p>{html_link(task.get('calendar_event_url'), 'Open calendar event')}</p>"
    return (
        '<article class="task-card">'
        f"<div class=\"task-top\"><h3>{html_text(task.get('title'), 180)}</h3>{badge(task.get('status'), manager_status_class(task.get('status')))}</div>"
        f"<p><strong>Group:</strong> {html_text(task.get('group'), 80)} <strong>Show:</strong> {html_text(task.get('show_name'), 120)}</p>"
        f"<p><strong>Episode:</strong> {html_text(short_date(task.get('episode_time')), 120)}</p>"
        f"<p><strong>Why am I seeing this?</strong> {html_text(task.get('why_seen'), 420)}</p>"
        f"<p><strong>What is blocking it?</strong> {html_text(task.get('blocking'), 420)}</p>"
        f"<p><strong>Next action:</strong> {html_text(task.get('next_action'), 420)}</p>"
        f"<p><strong>Estimated time:</strong> {html_text(task_time_text(task.get('estimated_minutes')), 80)} <strong>Business impact:</strong> {html_text(task.get('business_impact'), 80)}</p>"
        f"<p><strong>If ignored:</strong> {html_text(task.get('ignored_risk'), 420)}</p>"
        f"{checklist_html}{close_when_html}{calendar_html}"
        "</article>"
    )


def render_work_queue_html(queue):
    by_lane = queue.get("by_lane") or {}
    lane_sections = []
    for lane in WORK_QUEUE_LANES:
        tasks = by_lane.get(lane) or []
        body = '<p class="muted">No tasks in this lane.</p>' if not tasks else '<div class="task-grid">' + "".join(render_work_task_html(task) for task in tasks) + "</div>"
        lane_sections.append(f"<h3>{html_text(lane, 80)}</h3>{body}")
    group_rows = []
    by_group = queue.get("by_group") or {}
    for group in WORK_QUEUE_GROUPS:
        tasks = by_group.get(group) or []
        group_rows.append(
            "<tr>"
            f"<td>{html_text(group, 80)}</td>"
            f"<td>{len(tasks)}</td>"
            f"<td>{html_text('; '.join(task.get('title') for task in tasks) or 'None', 700)}</td>"
            "</tr>"
        )
    return (
        "<section class=\"card\">"
        f"<p><strong>Tasks:</strong> {queue.get('total_task_count', 0)} "
        f"<strong>Estimated today's work:</strong> {html_text(task_time_text(queue.get('total_estimated_minutes', 0)), 80)}</p>"
        "<p class=\"muted\">Read-only recommendations only. No automation will run.</p>"
        "</section>"
        + "".join(lane_sections)
        + "<h3>Work By Group</h3>"
        + "<table><thead><tr><th>Group</th><th>Tasks</th><th>Work</th></tr></thead>"
        + f"<tbody>{''.join(group_rows)}</tbody></table>"
    )


def render_daily_schedule_html(schedule):
    if not schedule:
        return '<p class="muted">No configured show episodes are scheduled in the next 7 days.</p>'
    rows = []
    for item in schedule:
        calendar = badge(item.get("calendar_status"), manager_status_class(item.get("calendar_status")))
        if item.get("calendar_event_url"):
            calendar += f"<br>{html_link(item.get('calendar_event_url'), item.get('calendar_event_title') or 'Open event')}"
        linkedin = badge(item.get("linkedin_status"), manager_status_class(item.get("linkedin_status")))
        if item.get("linkedin_urls"):
            linkedin += "<br>" + "<br>".join(html_link(url, "LinkedIn") for url in item.get("linkedin_urls") or [])
        streamyard = badge(item.get("streamyard_status"), manager_status_class(item.get("streamyard_status")))
        if item.get("streamyard_urls"):
            streamyard += "<br>" + "<br>".join(html_link(url, "StreamYard") for url in item.get("streamyard_urls") or [])
        blockers = "; ".join(item.get("production_blockers") or []) or "None"
        status_class = manager_status_class(item.get("current_production_status"))
        rows.append(
            "<tr>"
            f"<td>{html_text(short_date(item.get('date_time')), 90)}</td>"
            f"<td>{html_text(item.get('show_name'), 120)}</td>"
            f"<td>{html_text(', '.join(item.get('guest_names') or []) or 'Unknown', 180)}</td>"
            f"<td>{badge(item.get('guest_status'), manager_status_class(item.get('guest_status')))}</td>"
            f"<td>{badge(item.get('topics_status'), manager_status_class(item.get('topics_status')))}</td>"
            f"<td>{linkedin}</td>"
            f"<td>{streamyard}</td>"
            f"<td>{calendar}</td>"
            f"<td>{badge(item.get('highlevel_status_display') or item.get('highlevel_status'), manager_status_class(item.get('highlevel_status_display') or item.get('highlevel_status')))}</td>"
            f"<td>{badge(item.get('current_production_status'), status_class)}</td>"
            f"<td>{html_text(blockers, 320)}</td>"
            f"<td>{html_text(item.get('next_human_action'), 360)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Date/Time</th><th>Show</th><th>Guest(s)</th><th>Guest Status</th>"
        "<th>Topics Status</th><th>LinkedIn URL Status</th><th>StreamYard URL Status</th><th>Calendar Status</th>"
        "<th>HighLevel Status</th><th>Production Status</th><th>Blocking Production</th><th>Next Human Action</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_daily_operations_brief_html(brief):
    health = brief.get("health") or {}
    counts = brief.get("issue_counts") or {}
    waiting = brief.get("waiting_on") or {}
    safe = brief.get("safe_to_ignore_today") or {}
    completion_tracking = brief.get("completion_tracking") or {}
    completion_summary = completion_tracking.get("summary") or {}
    completion_counts = completion_summary.get("counts_by_status") or {}
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Operations Brief</title>
  <style>
    :root {{
      --bg: #f6f3ec;
      --panel: #fffdf8;
      --ink: #18212f;
      --muted: #667085;
      --line: #ded8ca;
      --ready: #067647;
      --ready-bg: #ecfdf3;
      --warning: #946200;
      --warning-bg: #fff7d6;
      --critical: #b42318;
      --critical-bg: #fff1f0;
      --info: #175cd3;
      --info-bg: #edf4ff;
      --shadow: 0 18px 40px rgba(24, 33, 47, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: radial-gradient(circle at top left, #d7ece5 0, transparent 34rem), var(--bg); color: var(--ink); font: 15px/1.5 "Avenir Next", "Helvetica Neue", Arial, sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 34px 20px 58px; }}
    header {{ background: linear-gradient(135deg, #203047, #25665f); color: white; border-radius: 28px; padding: 30px; box-shadow: var(--shadow); }}
    h1 {{ margin: 0; font-size: clamp(34px, 5vw, 56px); letter-spacing: -0.045em; }}
    h2 {{ margin: 30px 0 12px; }}
    h3 {{ margin: 16px 0 8px; }}
    .subtitle {{ color: rgba(255,255,255,0.78); }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 22px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 22px; padding: 17px; box-shadow: var(--shadow); }}
    .task-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin: 12px 0 20px; }}
    .task-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 20px; padding: 16px; box-shadow: var(--shadow); }}
    .task-top {{ display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }}
    .task-top h3 {{ margin-top: 0; }}
    header .card {{ background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.18); box-shadow: none; }}
    .metric {{ font-size: 34px; font-weight: 850; letter-spacing: -0.04em; }}
    .label, .muted {{ color: var(--muted); }}
    header .label {{ color: rgba(255,255,255,0.72); }}
    .badge {{ display: inline-flex; border-radius: 999px; padding: 4px 10px; font-size: 12px; font-weight: 800; }}
    .badge.critical {{ color: var(--critical); background: var(--critical-bg); }}
    .badge.warning {{ color: var(--warning); background: var(--warning-bg); }}
    .badge.info {{ color: var(--info); background: var(--info-bg); }}
    .badge.ready {{ color: var(--ready); background: var(--ready-bg); }}
    .badge.muted-badge {{ color: #667085; background: #eef0f4; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border-radius: 18px; overflow: hidden; box-shadow: var(--shadow); }}
    th, td {{ text-align: left; padding: 11px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ background: #ede7db; color: #475467; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
    a {{ color: var(--info); font-weight: 800; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .missing {{ color: var(--critical); font-weight: 850; }}
    ul {{ margin-top: 8px; }}
    li {{ margin: 7px 0; }}
    @media (max-width: 900px) {{ .grid, .task-grid {{ grid-template-columns: 1fr 1fr; }} table {{ display: block; overflow-x: auto; }} }}
    @media (max-width: 620px) {{ .grid, .task-grid {{ grid-template-columns: 1fr; }} main {{ padding: 20px 12px 42px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Daily Operations Brief</h1>
      <p class="subtitle">Short read-only operator brief generated from local audit outputs. No external systems were modified.</p>
      <div class="grid">
        <div class="card"><div class="metric">{html_text(health.get('score', 'n/a'), 30)}</div><div class="label">{html_text(health.get('label', 'Production health'), 100)}</div></div>
        <div class="card"><div class="metric">{counts.get('Critical', 0)}</div><div class="label">Critical issues</div></div>
        <div class="card"><div class="metric">{len(brief.get('shows_needing_attention') or [])}</div><div class="label">Shows needing attention</div></div>
        <div class="card"><div class="metric">{safe.get('not_due_yet', 0)}</div><div class="label">Safe to ignore today</div></div>
      </div>
    </header>

    <h2>Operations Copilot Work Queue</h2>
    {render_work_queue_html(brief.get('work_queue') or {})}

    <h2>Completion Verification</h2>
    <section class="grid">
      <div class="card"><div class="metric">{completion_summary.get('total_claims', 0)}</div><div class="label">Completion claims reviewed</div></div>
      <div class="card"><div class="metric">{completion_counts.get('Completed and verified', 0)}</div><div class="label">Completed and verified</div></div>
      <div class="card"><div class="metric">{completion_counts.get('Still open', 0)}</div><div class="label">Still open</div></div>
      <div class="card"><div class="metric">{completion_counts.get('Needs human review', 0)}</div><div class="label">Needs human review</div></div>
    </section>
    <section class="card"><p><strong>Completion claims file:</strong> {html_text(completion_tracking.get('completed_tasks_path') or 'data/audit/completed_tasks.json', 220)}</p></section>

    <h2>Completed Today</h2>
    {('<div class="task-grid">' + ''.join(render_completion_claim_html(item) for item in (completion_tracking.get('completed_today') or [])) + '</div>') if (completion_tracking.get('completed_today') or []) else '<section class="card"><p class="muted">No tasks completed and verified today.</p></section>'}

    <h2>Completion Claims</h2>
    {('<div class="task-grid">' + ''.join(render_completion_claim_html(item) for item in (completion_tracking.get('claims') or [])) + '</div>') if (completion_tracking.get('claims') or []) else '<section class="card"><p class="muted">No local completion claims have been recorded yet.</p></section>'}

    <h2>Next 7 Days Show Schedule</h2>
    {render_daily_schedule_html(brief.get('next_7_days_schedule') or [])}

    <h2>Known Exceptions</h2>
    <section class="card"><p>{len(brief.get('known_exceptions') or [])} active known exception or human-confirmed context item(s) are being tracked.</p></section>
    <section class="card"><p>{len(brief.get('linkedin_event_manual_evidence') or [])} episode(s) have LinkedIn event evidence from read-only/manual sources outside Google Calendar.</p></section>

    <h2>Future Safe Actions</h2>
    <section class="card"><p>{len(brief.get('future_safe_actions') or [])} future safe action candidate(s) exist, but automation remains disabled.</p></section>

    <h2>Not Due Yet</h2>
    <section class="card"><p>{brief.get('not_due_yet_summary', {}).get('count', 0)} items are not due yet. {html_text(brief.get('not_due_yet_summary', {}).get('message'), 220)}</p></section>

    <h2>Production Links To Watch</h2>
    <section class="card">
      <p><strong>LinkedIn URL statuses needing attention:</strong> {len(brief.get('linkedin_status_watch') or [])}</p>
      <p><strong>StreamYard URL statuses needing attention:</strong> {len(brief.get('streamyard_status_watch') or [])}</p>
    </section>
  </main>
</body>
</html>
"""


def load_daily_brief_sources(args):
    output_dir = Path(args.output_dir)
    report_path = output_dir / "operations_audit_report.json"
    dashboard_path = output_dir / "operations_manager_dashboard.json"
    completed_tasks_path = output_dir / "completed_tasks.json"
    if not report_path.exists():
        raise RuntimeError(f"Missing audit report: {report_path}. Run the all-shows audit first.")
    if not dashboard_path.exists():
        raise RuntimeError(f"Missing operations manager dashboard JSON: {dashboard_path}. Run the all-shows audit first.")
    report = read_json(report_path, default={})
    manager_dashboard = read_json(dashboard_path, default={})
    completed_tasks = load_completed_tasks(completed_tasks_path)
    rules = load_rules(Path(args.rules))
    calendar_events = []
    calendar_path = path_from_report(report.get("calendar_events_path"))
    if calendar_path and calendar_path.exists():
        calendar_payload = load_calendar_payload(calendar_path)
        calendar_events = [normalize_calendar_event(event) for event in flatten_calendar_payload(calendar_payload)]
    return report, manager_dashboard, calendar_events, rules, completed_tasks, completed_tasks_path


def generate_daily_brief(args):
    output_dir = Path(args.output_dir)
    report, manager_dashboard, calendar_events, rules, completed_tasks, completed_tasks_path = load_daily_brief_sources(args)
    now_local = daily_now(args.now)
    brief = build_daily_brief_payload(report, manager_dashboard, calendar_events, rules, now_local, completed_tasks, completed_tasks_path)
    md_path = output_dir / "daily_operations_brief.md"
    html_path = output_dir / "daily_operations_brief.html"
    md_path.write_text(render_daily_brief_markdown(brief), encoding="utf-8")
    html_path.write_text(render_daily_operations_brief_html(brief), encoding="utf-8")
    return brief, md_path, html_path


def render_operator_action_plan(report):
    health = report.get("overall_production_health") or {}
    issues = action_plan_items(report)
    lines = [
        "# Operator Action Plan",
        "",
        f"- Generated at: {report.get('generated_at')}",
        f"- Production health: {health.get('score', 'n/a')} - {health.get('label', 'unknown')}",
        f"- Action items: {len(issues)}",
        "- Mode: read-only; no external systems were modified",
        "",
        "## Priority Actions",
        "",
    ]
    if not issues:
        lines.extend(["No priority action items found.", ""])
        return "\n".join(lines)
    for item in issues:
        trust = item.get("trust") or {}
        details = item.get("details") or {}
        lines.extend(
            [
                f"### {md_escape(item.get('show_name'))} - {md_escape(short_date(item.get('episode_time')))}",
                "",
                f"- Issue: `{md_escape(item.get('code'))}` - {md_escape(item.get('message'))}",
                f"- Severity: {md_escape(effective_issue_severity(item))}",
                f"- Trust category: {md_escape(trust.get('category'))}",
                f"- Operational status: {md_escape(trust.get('operational_status') or item.get('operational_status'))}",
                f"- Guest/status details: {md_escape(details.get('guest_status') or details.get('calendar_guest') or details.get('guest_name') or trust.get('guest'))}",
                f"- Current calendar status: {md_escape(details.get('calendar_status') or (trust.get('evidence_from_google_calendar') or {}).get('title'))}",
                f"- Current HighLevel status: {md_escape(details.get('highlevel_status') or 'See HighLevel evidence in audit JSON.')}",
                f"- Recommended human action: {md_escape(item.get('recommended_action'))}",
                f"- Evidence summary: {md_escape(trust.get('difference_detected') or item.get('difference_detected') or item.get('reason'))}",
                "",
            ]
        )
    return "\n".join(lines)


def write_issue_csv(path, issues):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "severity",
        "base_severity",
        "stage_adjusted_severity",
        "production_stage",
        "code",
        "show_key",
        "show_name",
        "episode_time",
        "calendar_event_id",
        "appointment_ids",
        "message",
        "reason",
        "evidence",
        "difference_detected",
        "relevant_raw_ids",
        "why_this_matters_operationally",
        "confidence",
        "trust_category",
        "trust_dashboard_bucket",
        "future_automation_candidate",
        "automation_risk_level",
        "approval_required_before_action",
        "recommended_action",
        "explanation",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in issues:
            writer.writerow(
                {
                    field: json.dumps(item.get(field), ensure_ascii=True)
                    if field in {"appointment_ids", "evidence", "relevant_raw_ids", "production_stage"}
                    else item.get(field)
                    for field in fields
                }
            )


def top_operational_risks(issues, limit=10):
    severity_order = {"Critical": 0, "Warning": 1, "Informational": 2}
    return [
        {
            "severity": item.get("severity"),
            "confidence": item.get("confidence"),
            "show_name": item.get("show_name"),
            "episode_time": item.get("episode_time"),
            "code": item.get("code"),
            "message": item.get("message"),
            "recommended_action": item.get("recommended_action"),
        }
        for item in sorted(
            issues,
            key=lambda value: (
                severity_order.get(value.get("severity"), 9),
                value.get("episode_time") or "",
                value.get("show_name") or "",
            ),
        )[:limit]
    ]


def previous_health_score(previous_report):
    if not isinstance(previous_report, dict):
        return None
    dashboard = previous_report.get("dashboard")
    if isinstance(dashboard, dict):
        score = dashboard.get("overall_production_health", {}).get("score")
        if score is not None:
            return score
    health = previous_report.get("overall_production_health")
    if isinstance(health, dict):
        return health.get("score")
    return None


def issue_fingerprint(item):
    appointment_ids = ",".join(sorted(str(value) for value in item.get("appointment_ids") or []))
    return "|".join(
        [
            str(item.get("show_key") or ""),
            str(item.get("episode_time") or ""),
            str(item.get("code") or ""),
            str(item.get("calendar_event_id") or ""),
            appointment_ids,
            normalize_text(item.get("message") or ""),
        ]
    )


def issue_identity_key(item):
    appointment_ids = ",".join(sorted(str(value) for value in item.get("appointment_ids") or []))
    return "|".join(
        [
            str(item.get("show_key") or ""),
            str(item.get("episode_time") or ""),
            str(item.get("code") or ""),
            str(item.get("calendar_event_id") or ""),
            appointment_ids,
        ]
    )


def issue_brief(item):
    return {
        "severity": item.get("severity"),
        "code": item.get("code"),
        "show_name": item.get("show_name"),
        "episode_time": item.get("episode_time"),
        "message": item.get("message"),
        "recommended_action": item.get("recommended_action"),
    }


def build_change_summary(previous_report, current_report):
    if not isinstance(previous_report, dict):
        return {
            "available": False,
            "message": "No previous audit file exists yet.",
            "new_issues": [],
            "resolved_issues": [],
            "continuing_issues": [],
            "worsened_issues": [],
            "improved_issues": [],
            "recently_fixed_items": [],
            "health_score_delta": None,
            "improved_production_health": False,
            "severity_count_delta": {},
            "suppressed_issue_delta": None,
        }
    previous_issues = previous_report.get("issues") or []
    current_issues = current_report.get("issues") or []
    previous_by_key = {issue_fingerprint(item): item for item in previous_issues}
    current_by_key = {issue_fingerprint(item): item for item in current_issues}
    previous_by_identity = {issue_identity_key(item): item for item in previous_issues}
    current_by_identity = {issue_identity_key(item): item for item in current_issues}
    previous_keys = set(previous_by_key)
    current_keys = set(current_by_key)
    previous_identity_keys = set(previous_by_identity)
    current_identity_keys = set(current_by_identity)
    previous_score = previous_health_score(previous_report)
    current_score = current_report.get("overall_production_health", {}).get("score")
    severity_delta = {}
    previous_counts = previous_report.get("severity_counts") or {}
    current_counts = current_report.get("severity_counts") or {}
    for severity in ("Critical", "Warning", "Informational"):
        severity_delta[severity] = current_counts.get(severity, 0) - previous_counts.get(severity, 0)
    previous_suppressed = len(previous_report.get("suppressed_issues") or [])
    current_suppressed = len(current_report.get("suppressed_issues") or [])
    worsened = []
    improved = []
    for key in sorted(previous_identity_keys & current_identity_keys):
        previous_item = previous_by_identity[key]
        current_item = current_by_identity[key]
        previous_rank = severity_rank(previous_item.get("severity"))
        current_rank = severity_rank(current_item.get("severity"))
        if current_rank < previous_rank:
            worsened.append(
                {
                    "previous": issue_brief(previous_item),
                    "current": issue_brief(current_item),
                }
            )
        elif current_rank > previous_rank:
            improved.append(
                {
                    "previous": issue_brief(previous_item),
                    "current": issue_brief(current_item),
                }
            )
    return {
        "available": True,
        "message": "Compared with the previous local audit report.",
        "previous_generated_at": previous_report.get("generated_at"),
        "new_issues": [issue_brief(current_by_key[key]) for key in sorted(current_keys - previous_keys)],
        "resolved_issues": [issue_brief(previous_by_key[key]) for key in sorted(previous_keys - current_keys)],
        "continuing_issues": [issue_brief(current_by_key[key]) for key in sorted(current_keys & previous_keys)],
        "worsened_issues": worsened,
        "improved_issues": improved,
        "recently_fixed_items": [issue_brief(previous_by_key[key]) for key in sorted(previous_keys - current_keys)],
        "health_score_delta": None if previous_score is None or current_score is None else round(current_score - previous_score, 1),
        "improved_production_health": bool(previous_score is not None and current_score is not None and current_score > previous_score),
        "severity_count_delta": severity_delta,
        "suppressed_issue_delta": current_suppressed - previous_suppressed,
    }


def dashboard_trend(previous_report, current_score):
    previous_score = previous_health_score(previous_report)
    if previous_score is None or current_score is None:
        return {
            "available": False,
            "message": "No previous audit snapshot found for comparison.",
        }
    delta = round(current_score - previous_score, 1)
    return {
        "available": True,
        "previous_score": previous_score,
        "current_score": current_score,
        "delta": delta,
        "direction": "improved" if delta > 0 else "declined" if delta < 0 else "unchanged",
        "previous_generated_at": previous_report.get("generated_at"),
    }


def build_dashboard(report, previous_report, rules):
    episode_health_items = [
        episode["production_health"]
        for episode in report["episodes"]
        if episode.get("production_health", {}).get("score") is not None
    ]
    overall_health = aggregate_health(episode_health_items, rules)
    per_show_health = []
    for show_key, summary in sorted(report["show_summary"].items(), key=lambda item: item[1]["show_name"]):
        score = summary.get("production_health_score")
        per_show_health.append(
            {
                "show_key": show_key,
                "show_name": summary.get("show_name"),
                "score": score,
                "label": summary.get("production_health_label"),
                "episodes_audited": summary.get("episodes_audited"),
                "critical": summary.get("critical"),
                "warning": summary.get("warning"),
                "informational": summary.get("informational"),
            }
        )
    critical_issues = [item for item in report["issues"] if effective_issue_severity(item) == "Critical"]
    warnings = [item for item in report["issues"] if effective_issue_severity(item) == "Warning"]
    ready_shows = [
        item for item in per_show_health if item.get("score") is not None and item.get("score") >= 90 and not item.get("critical")
    ]
    attention_shows = [
        item for item in per_show_health if item.get("score") is not None and (item.get("score") < 90 or item.get("critical"))
    ]
    return {
        "generated_at": report["generated_at"],
        "read_only": True,
        "overall_production_health": overall_health,
        "per_show_health": per_show_health,
        "upcoming_episodes": [
            {
                "show_key": episode.get("show_key"),
                "show_name": episode.get("show_name"),
                "episode_time": episode.get("episode_time"),
                "guest_count": episode.get("guest_count"),
                "calendar_event_found": episode.get("calendar_event_found"),
                "production_health": episode.get("production_health"),
                "critical_issue_count": sum(1 for item in episode.get("issues", []) if effective_issue_severity(item) == "Critical"),
                "warning_count": sum(1 for item in episode.get("issues", []) if effective_issue_severity(item) == "Warning"),
            }
            for episode in report["episodes"]
        ],
        "critical_issues": critical_issues,
        "warnings": warnings,
        "ready_for_production": ready_shows,
        "shows_requiring_attention": attention_shows,
        "top_operational_risks": top_operational_risks(report["issues"]),
        "trend": dashboard_trend(previous_report, overall_health.get("score")),
    }


def run_audit(args):
    discovery_dir = Path(args.discovery_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rules = load_rules(Path(args.rules))
    timeline_rules = load_production_timeline_rules(Path(args.production_timeline_rules))
    knowledge = load_knowledge(Path(args.knowledge_dir))
    completed_tasks_path = output_dir / "completed_tasks.json"
    completed_tasks_payload = load_completed_tasks(completed_tasks_path)
    rules["_loaded_knowledge"] = knowledge
    calendar_payload = load_calendar_payload(Path(args.calendar_events))
    calendar_export_window = calendar_export_window_from_payload(calendar_payload)
    calendar_events = [normalize_calendar_event(event) for event in flatten_calendar_payload(calendar_payload)]
    now = parse_datetime(args.now) if args.now else datetime.now(timezone.utc)
    if not now:
        raise RuntimeError(f"Could not parse --now value: {args.now}")
    options = {
        "now": now,
        "preshow_minutes": args.preshow_minutes,
        "tolerance_minutes": args.time_tolerance_minutes,
        "days_ahead": args.days_ahead,
        "include_past": args.include_past,
        "rules": rules,
        "knowledge": knowledge,
        "match_threshold": int(rules.get("calendar_match_threshold", 45)),
        "discovery_dir": discovery_dir,
        "calendar_events_path": Path(args.calendar_events),
        "calendar_export_window": calendar_export_window,
    }
    show_keys = configured_show_keys(rules) if args.show_key in (None, "all") else [args.show_key]
    audited_episodes = []
    all_issues = []
    all_suppressed_issues = []
    show_diagnostics = []
    show_names = set()
    show_contexts = {}

    for show_key in show_keys:
        episodes, appointments_by_id, submissions_by_id, custom_field_map_by_id = load_show_context(show_key, discovery_dir)
        show_contexts[show_key] = {
            "episodes": episodes,
            "appointments_by_id": appointments_by_id,
            "submissions_by_id": submissions_by_id,
            "custom_field_map_by_id": custom_field_map_by_id,
        }
        diagnostic = discovery_diagnostic(show_key, discovery_dir, rules, episodes, appointments_by_id, submissions_by_id)
        if diagnostic:
            show_diagnostics.append(diagnostic)
        for episode in episodes:
            if episode.get("show_name"):
                show_names.add(episode["show_name"])
            audited = audit_episode(show_key, episode, appointments_by_id, submissions_by_id, custom_field_map_by_id, calendar_events, options)
            if audited is None:
                continue
            audited_episodes.append(audited)
            all_issues.extend(audited["issues"])
            all_suppressed_issues.extend(audited.get("suppressed_issues") or [])

    options["show_contexts"] = show_contexts

    orphan_issues = find_calendar_events_without_bookings(calendar_events, audited_episodes, show_names, options)
    orphan_active_issues, orphan_suppressed_issues = apply_suppression_rules(orphan_issues, rules, now)
    orphan_active_issues, orphan_suppressed_issues = apply_knowledge_to_issue_sets(
        orphan_active_issues,
        orphan_suppressed_issues,
        knowledge,
        now,
    )
    all_issues.extend(orphan_active_issues)
    all_suppressed_issues.extend(orphan_suppressed_issues)
    all_issues.extend(build_knowledge_alert_issues(calendar_events, all_issues, options, knowledge))
    all_issues.extend(build_linkedin_manual_evidence_issues(calendar_events, all_issues + all_suppressed_issues, options, knowledge))
    apply_metadata_to_issues(all_issues, rules)
    apply_metadata_to_issues(all_suppressed_issues, rules)
    attach_issue_decisions(all_issues, rules, now)
    attach_issue_decisions(all_suppressed_issues, rules, now)
    attach_stage_decisions(all_issues, timeline_rules, now)
    attach_stage_decisions(all_suppressed_issues, timeline_rules, now)
    attach_trust_layer(all_issues, rules)
    attach_trust_layer(all_suppressed_issues, rules)
    for episode in audited_episodes:
        episode["production_health"] = production_health(episode.get("issues") or [], rules)

    all_issues.sort(key=issue_sort_key)
    all_suppressed_issues.sort(key=issue_sort_key)
    json_path = output_dir / "operations_audit_report.json"
    md_path = output_dir / "operations_audit_report.md"
    html_path = output_dir / "operations_audit_report.html"
    csv_path = output_dir / "operations_audit_issues.csv"
    critical_review_path = output_dir / "critical_issues_review.md"
    trust_review_path = output_dir / "trust_review.md"
    learning_report_path = output_dir / "learning_report.md"
    rule_queue_json_path = output_dir / "rule_approval_queue.json"
    rule_queue_md_path = output_dir / "rule_approval_queue.md"
    operator_action_plan_path = output_dir / "operator_action_plan.md"
    dashboard_path = output_dir / "operations_dashboard.json"
    manager_dashboard_path = output_dir / "operations_manager_dashboard.json"
    manager_dashboard_html_path = output_dir / "operations_manager_dashboard.html"
    previous_report = read_json(json_path, default=None)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "calendar_id": args.calendar_id,
        "calendar_events_path": str(Path(args.calendar_events)),
        "calendar_export_window": calendar_export_window,
        "discovery_dir": str(discovery_dir),
        "rules_path": str(Path(args.rules)),
        "production_timeline_rules_path": str(Path(args.production_timeline_rules)),
        "knowledge_dir": str(Path(args.knowledge_dir)),
        "rules_version": rules.get("version"),
        "production_timeline_rules_version": timeline_rules.get("version"),
        "calendar_events_loaded": len(calendar_events),
        "episodes_audited": len(audited_episodes),
        "severity_counts": severity_counts(all_issues),
        "base_severity_counts": base_severity_counts(all_issues),
        "suppressed_issue_count": len(all_suppressed_issues),
        "suppressed_severity_counts": severity_counts(all_suppressed_issues),
        "suppressed_base_severity_counts": base_severity_counts(all_suppressed_issues),
        "show_summary": show_summary(audited_episodes, all_issues, rules, show_diagnostics),
        "show_configuration_diagnostics": show_diagnostics,
        "episodes": audited_episodes,
        "issues": all_issues,
        "suppressed_issues": all_suppressed_issues,
        "read_only": True,
    }
    dashboard = build_dashboard(report, previous_report, rules)
    report["overall_production_health"] = dashboard["overall_production_health"]
    report["dashboard"] = {
        "path": str(dashboard_path),
        "overall_production_health": dashboard["overall_production_health"],
        "trend": dashboard["trend"],
    }
    report["change_summary"] = build_change_summary(previous_report, report)
    report["executive_summary"] = build_executive_summary(report)
    report["trust_review"] = build_trust_review(report, rules)
    report["learning_report"] = build_learning_report(report, previous_report, knowledge)
    report["learning_report"]["path"] = str(learning_report_path)
    report["rule_approval_queue"] = build_rule_approval_queue(report["learning_report"])
    report["rule_approval_queue"]["json_path"] = str(rule_queue_json_path)
    report["rule_approval_queue"]["markdown_path"] = str(rule_queue_md_path)
    manager_dashboard = build_operations_manager_dashboard(report, rules, timeline_rules, now)
    completion_preview = build_daily_brief_payload(
        report,
        manager_dashboard,
        calendar_events,
        rules,
        now.astimezone(LOCAL_TIMEZONE),
        completed_tasks_payload,
        completed_tasks_path,
    ).get("completion_tracking") or {}
    report["trust_review"] = build_trust_review(report, rules, completion_preview)
    report["trust_review"]["path"] = str(trust_review_path)
    manager_dashboard = build_operations_manager_dashboard(report, rules, timeline_rules, now, completion_preview)
    critical_review = manager_dashboard.get("critical_review") or []
    report["critical_review"] = {
        "path": str(critical_review_path),
        "issues": critical_review,
    }
    report["operations_manager_dashboard"] = {
        "json_path": str(manager_dashboard_path),
        "html_path": str(manager_dashboard_html_path),
        "completed_tasks_path": str(completed_tasks_path),
    }

    write_json(json_path, report)
    write_json(dashboard_path, dashboard)
    write_json(manager_dashboard_path, manager_dashboard)
    write_json(rule_queue_json_path, report["rule_approval_queue"])
    md_path.write_text(render_markdown(report), encoding="utf-8")
    critical_review_path.write_text(render_critical_review_markdown(critical_review), encoding="utf-8")
    trust_review_path.write_text(render_trust_review_markdown(report["trust_review"]), encoding="utf-8")
    learning_report_path.write_text(render_learning_report_markdown(report["learning_report"]), encoding="utf-8")
    rule_queue_md_path.write_text(render_rule_queue_markdown(report["rule_approval_queue"]), encoding="utf-8")
    operator_action_plan_path.write_text(render_operator_action_plan(report), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    manager_dashboard_html_path.write_text(render_operations_manager_dashboard_html(manager_dashboard), encoding="utf-8")
    write_issue_csv(csv_path, all_issues)
    return report, json_path, md_path, html_path, csv_path, dashboard_path, manager_dashboard_path, manager_dashboard_html_path, trust_review_path, learning_report_path, rule_queue_json_path, rule_queue_md_path, operator_action_plan_path


def main():
    initial_rules = load_rules(DEFAULT_RULES_PATH)
    parser = argparse.ArgumentParser(description="Read-only Reveting Operations Audit")
    parser.add_argument("--calendar-events", default=str(DEFAULT_CALENDAR_EVENTS_PATH), help="Path to Google Calendar events JSON export")
    parser.add_argument("--calendar-id", default=configured_calendar_id(initial_rules), help="Calendar ID represented by the export")
    parser.add_argument("--discovery-dir", default=str(DISCOVERY_DIR), help="Path to HighLevel Discovery V1 artifacts")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Where audit reports should be written")
    parser.add_argument("--rules", default=str(DEFAULT_RULES_PATH), help="Path to configurable operations audit rules JSON")
    parser.add_argument("--production-timeline-rules", default=str(DEFAULT_PRODUCTION_TIMELINE_RULES_PATH), help="Path to configurable production timeline/readiness rules JSON")
    parser.add_argument("--knowledge-dir", default=str(DEFAULT_KNOWLEDGE_DIR), help="Path to read-only knowledge files used for learning reports")
    parser.add_argument("--show-key", choices=configured_show_keys(initial_rules) + ["all"], help="Limit audit to one show, or use `all` for every configured show")
    parser.add_argument("--preshow-minutes", type=int, default=int(initial_rules.get("preshow_offset_minutes", DEFAULT_PRESHOW_MINUTES)), help="Minutes before HighLevel start that Google Calendar should reserve")
    parser.add_argument("--time-tolerance-minutes", type=int, default=int(initial_rules.get("time_tolerance_minutes", DEFAULT_TIME_TOLERANCE_MINUTES)), help="Allowed clock drift before a mismatch is reported")
    parser.add_argument("--days-ahead", type=int, default=int(initial_rules.get("audit_window_days_ahead", DEFAULT_DAYS_AHEAD)), help="Only audit episodes up to this many days ahead")
    parser.add_argument("--include-past", action="store_true", help="Include past episodes/events in the audit")
    parser.add_argument("--now", help="Override current time with an ISO timestamp for repeatable audits")
    parser.add_argument("--daily-brief", action="store_true", help="Generate the Daily Operations Brief from existing local audit outputs only.")
    parser.add_argument("--apply-approved-rules", action="store_true", help="Future stub. Currently disabled and fails safely.")
    args = parser.parse_args()

    if args.apply_approved_rules:
        print("Rule automation is not enabled yet.", file=sys.stderr)
        sys.exit(1)

    if args.daily_brief:
        try:
            brief, md_path, html_path = generate_daily_brief(args)
        except RuntimeError as exc:
            print(f"Daily brief failed: {exc}", file=sys.stderr)
            sys.exit(1)
        counts = brief.get("issue_counts") or {}
        print("Daily operations brief complete.")
        print(f"  Overall health: {brief.get('health', {}).get('score', 'n/a')} - {brief.get('health', {}).get('label', 'unknown')}")
        print(f"  Critical issues: {counts.get('Critical', 0)}")
        print(f"  Next 7 days: {len(brief.get('next_7_days_schedule') or [])} scheduled show item(s)")
        work_queue = brief.get("work_queue") or {}
        completion_summary = (brief.get("completion_tracking") or {}).get("summary") or {}
        print(f"  Work queue tasks: {work_queue.get('total_task_count', 0)}")
        print(f"  Estimated today's work: {task_time_text(work_queue.get('total_estimated_minutes', 0))}")
        print(f"  Completion claims reviewed: {completion_summary.get('total_claims', 0)}")
        print(f"  Completed today: {completion_summary.get('completed_today_count', 0)}")
        print(f"  Markdown: {md_path}")
        print(f"  HTML: {html_path}")
        print("  Mode: read-only; generated from existing local audit outputs only.")
        return

    try:
        report, json_path, md_path, html_path, csv_path, dashboard_path, manager_dashboard_path, manager_dashboard_html_path, trust_review_path, learning_report_path, rule_queue_json_path, rule_queue_md_path, operator_action_plan_path = run_audit(args)
    except RuntimeError as exc:
        print(f"Audit failed: {exc}", file=sys.stderr)
        sys.exit(1)

    counts = report["severity_counts"]
    print("Operations audit complete.")
    print(f"  Episodes audited: {report['episodes_audited']}")
    print(f"  Calendar events loaded: {report['calendar_events_loaded']}")
    print(
        "  Issues: "
        f"{counts.get('Critical', 0)} Critical, "
        f"{counts.get('Warning', 0)} Warning, "
        f"{counts.get('Informational', 0)} Informational"
    )
    completion_summary = ((report.get("trust_review") or {}).get("completion_tracking") or {}).get("summary") or {}
    print(f"  Completion claims reviewed: {completion_summary.get('total_claims', 0)}")
    print(f"  Completed today: {completion_summary.get('completed_today_count', 0)}")
    print(f"  Markdown: {md_path}")
    print(f"  HTML: {html_path}")
    print(f"  JSON: {json_path}")
    print(f"  CSV: {csv_path}")
    print(f"  Dashboard: {dashboard_path}")
    print(f"  Operations Manager JSON: {manager_dashboard_path}")
    print(f"  Operations Manager HTML: {manager_dashboard_html_path}")
    print(f"  Trust Review: {trust_review_path}")
    print(f"  Learning Report: {learning_report_path}")
    print(f"  Rule Approval Queue JSON: {rule_queue_json_path}")
    print(f"  Rule Approval Queue Markdown: {rule_queue_md_path}")
    print(f"  Operator Action Plan: {operator_action_plan_path}")
    print("  Mode: read-only; no external systems were modified.")


if __name__ == "__main__":
    main()
