#!/usr/bin/env python3
"""
Show Launch Automation — Main Orchestrator
Takes a GHL appointment record and generates all show assets.

Usage:
  python3 scripts/show-launch.py --input appointment.json --dry-run
  python3 scripts/show-launch.py --input appointment.json --execute
  python3 scripts/show-launch.py --ghl-pull --show-key winsday --dry-run
  python3 scripts/show-launch.py --discover-highlevel
  python3 scripts/show-launch.py --test-highlevel-auth --show-key winsday
"""

import argparse
import csv
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

# ── Config ────────────────────────────────────────────────────
DEFAULT_GHL_API_BASE = "https://services.leadconnectorhq.com"
DEFAULT_GHL_API_VERSION = "2021-04-15"
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)

REPO_ROOT = Path(__file__).parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "shows.json"
EXAMPLES_DIR = REPO_ROOT / "examples"
DISCOVERY_DIR = REPO_ROOT / "data" / "discovery"
DOTENV_PATH = REPO_ROOT / ".env"

SHOW_HIGHLEVEL_CONFIGS = [
    {
        "key": "cherry-willow",
        "env_var": "HIGHLEVEL_TOKEN_CHERRY_WILLOW",
        "location_env_var": "HIGHLEVEL_LOCATION_ID_CHERRY_WILLOW",
        "client_name": "Cherry Willow",
        "show_name": "Apparel with Purpose",
        "location_name_hint": "Cherry Willow",
        "calendar_name_hint": "Cherry Willow's apparel with Purpose",
        "calendar_id_hint": "Dyx2Z4FZH1QrIyUrMHIz",
        "form_name_hint": "Application Form",
    },
    {
        "key": "david-daily",
        "env_var": "HIGHLEVEL_TOKEN_DAVID_DAILY",
        "location_env_var": "HIGHLEVEL_LOCATION_ID_DAVID_DAILY",
        "client_name": "David Daily",
        "show_name": "The David Daily Show",
        "location_name_hint": "David Daily",
        "calendar_name_hint": "The David Daily Show",
        "calendar_id_hint": "tfyAt3M4UCqJwOKpSBry",
        "form_name_hint": "The David Daily Show - Guest Booking Calendar Form",
    },
    {
        "key": "beyond-the-cart",
        "env_var": "HIGHLEVEL_TOKEN_BEYOND_THE_CART",
        "location_env_var": "HIGHLEVEL_LOCATION_ID_BEYOND_THE_CART",
        "client_name": "Beyond the Cart / OmniRocket LLC",
        "show_name": "Beyond the Cart",
        "location_name_hint": "Beyond the Cart | OmniRocket LLC",
        "calendar_name_hint": "Beyond The Cart Podcast",
        "calendar_id_hint": "SgvRnzc0z5hw1t71I3TL",
        "form_name_hint": "Beyond The Cart",
    },
    {
        "key": "deconstructing-data",
        "env_var": "HIGHLEVEL_TOKEN_DECONSTRUCTING_DATA",
        "location_env_var": "HIGHLEVEL_LOCATION_ID_DECONSTRUCTING_DATA",
        "client_name": "BDEX",
        "show_name": "Deconstructing Data",
        "location_name_hint": "BDEX",
        "calendar_name_hint": "Deconstructing Data Live Broadcast and Podcast",
        "calendar_id_hint": "xQf69sfGMyYK9PXapHq6",
        "form_name_hint": "Deconstructing Data Live Broadcast and Podcast",
    },
    {
        "key": "winsday",
        "env_var": "HIGHLEVEL_TOKEN_WINSDAY",
        "location_env_var": "HIGHLEVEL_LOCATION_ID_WINSDAY",
        "client_name": "Reveting",
        "show_name": "WinsDay",
        "location_name_hint": "Reveting",
        "calendar_name_hint": "WinsDay Livestream & Podcast",
        "calendar_id_hint": "Pc2uJPYPLs8UT0LIfF5k",
        "form_name_hint": "WinsDay Podcast",
    },
]

SHOW_CONFIG_BY_KEY = {config["key"]: config for config in SHOW_HIGHLEVEL_CONFIGS}
DEFAULT_DISCOVERY_LOOKBACK_DAYS = 90
DEFAULT_DISCOVERY_LOOKAHEAD_DAYS = 180
HIGHLEVEL_API_PROFILES = [
    {
        "name": "leadconnector-services-v2021-04-15",
        "base_url": DEFAULT_GHL_API_BASE,
        "default_headers": {
            "Version": DEFAULT_GHL_API_VERSION,
            "Accept": "application/json",
        },
        "auth_probe": {
            "label": "search contacts",
            "method": "POST",
            "path": "/contacts/search",
            "json": {"locationId": "{location_id}", "pageLimit": 1},
        },
    }
]


def load_project_env():
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError(
            "python-dotenv is required. Install dependencies with: pip install -r requirements.txt"
        ) from exc
    load_dotenv(dotenv_path=DOTENV_PATH, override=False)


def use_relay_transport():
    mode = os.environ.get("HIGHLEVEL_TRANSPORT", "").strip().lower()
    if mode == "relay":
        return True
    return False


def relay_base_url():
    base_url = os.environ.get("HIGHLEVEL_RELAY_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError(
            "HIGHLEVEL_RELAY_BASE_URL is required for relay transport. "
            "Point it at the deployed HighLevel relay service."
        )
    return base_url


def relay_headers():
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    shared_secret = os.environ.get("HIGHLEVEL_RELAY_SHARED_SECRET", "").strip()
    if shared_secret:
        headers["Authorization"] = f"Bearer {shared_secret}"
    return headers


def relay_post(path, payload):
    url = f"{relay_base_url()}{path}"
    raw_payload = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=raw_payload, headers=relay_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_body = resp.read().decode(errors="replace")
            try:
                response_payload = json.loads(raw_body)
            except json.JSONDecodeError:
                response_payload = {"raw": raw_body}
            return {
                "ok": True,
                "status": resp.status,
                "url": url,
                "payload": response_payload,
            }
    except urllib.error.HTTPError as e:
        body = redact_known_secrets(e.read().decode(errors="replace"))
        return {
            "ok": False,
            "status": e.code,
            "url": url,
            "error": body[:1200],
        }
    except Exception as e:
        return {
            "ok": False,
            "status": None,
            "url": url,
            "error": redact_known_secrets(e),
        }


def redact_known_secrets(value):
    text = str(value)
    for config in SHOW_HIGHLEVEL_CONFIGS:
        token = os.environ.get(config["env_var"])
        if token:
            text = text.replace(token, "[REDACTED]")
    return text


def log_error(message):
    print(redact_known_secrets(message), file=sys.stderr)


def require_highlevel_tokens(configs=None):
    configs = configs or SHOW_HIGHLEVEL_CONFIGS
    if use_relay_transport():
        return {config["key"]: None for config in configs}
    missing = [config["env_var"] for config in configs if not os.environ.get(config["env_var"])]
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            "Missing required HighLevel token environment variables: "
            f"{missing_list}. Add them to your local .env before running discovery."
        )
    return {config["key"]: os.environ[config["env_var"]] for config in configs}


def resolve_location_id(show_config, required=False):
    location_id = os.environ.get(show_config["location_env_var"]) or show_config.get("location_id") or show_config.get("location_id_hint")
    if use_relay_transport() and not location_id:
        location_id = show_config.get("location_id_hint")
    if required and not location_id:
        raise RuntimeError(
            f"Missing required HighLevel location ID for {show_config['show_name']}. "
            f"Set {show_config['location_env_var']} in your local .env."
        )
    return location_id


def iso_range(days_back=DEFAULT_DISCOVERY_LOOKBACK_DAYS, days_ahead=DEFAULT_DISCOVERY_LOOKAHEAD_DAYS):
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00.000Z")
    end_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%dT23:59:59.999Z")
    return start_date, end_date


def iso_to_epoch_millis(value):
    normalized = value.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp() * 1000)


def upcoming_iso_range(days_ahead):
    now = datetime.now(timezone.utc)
    start_date = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%dT23:59:59.999Z")
    return start_date, end_date

# ── GHL API ──────────────────────────────────────────────────
def ghl_headers(token, location_id=None, extra_headers=None, profile=None):
    if not token:
        raise RuntimeError("Missing HighLevel token for the requested show.")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if profile:
        headers.update(profile.get("default_headers", {}))
    if location_id:
        headers["Location-Id"] = location_id
    if extra_headers:
        headers.update(extra_headers)
    return headers


def sanitize_response_for_output(payload, limit=1200):
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=True)
    return redact_known_secrets(text)[:limit]


def curl_json_request(url, *, method="GET", headers=None, json_body=None, timeout=30):
    config_lines = [
        "silent",
        "show-error",
        f"request = {json.dumps(method)}",
        f"url = {json.dumps(url)}",
        f"max-time = {timeout}",
        'write-out = "\\n%{http_code}"',
    ]
    for key, value in (headers or {}).items():
        config_lines.append(f"header = {json.dumps(f'{key}: {value}')}")
    if json_body is not None:
        config_lines.append(f"data = {json.dumps(json.dumps(json_body))}")
    config_blob = "\n".join(config_lines) + "\n"
    result = subprocess.run(
        ["curl", "--config", "-"],
        input=config_blob,
        text=True,
        capture_output=True,
        timeout=timeout + 5,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"curl exited with status {result.returncode}")
    if "\n" not in result.stdout:
        raise RuntimeError("curl response did not include an HTTP status code")
    body, status_text = result.stdout.rsplit("\n", 1)
    try:
        status_code = int(status_text.strip())
    except ValueError as exc:
        raise RuntimeError(f"Could not parse curl status code from: {status_text!r}") from exc
    return status_code, body

def render_template_value(value, show_config, location_id):
    if isinstance(value, str):
        return value.format(location_id=location_id, show_key=show_config["key"])
    if isinstance(value, dict):
        return {key: render_template_value(item, show_config, location_id) for key, item in value.items()}
    return value


def ghl_request(
    path,
    token,
    *,
    profile=None,
    params=None,
    context=None,
    location_id=None,
    extra_headers=None,
    show_config=None,
    method="GET",
    json_body=None,
):
    if use_relay_transport():
        if not show_config:
            raise RuntimeError("Relay transport requires show_config for HighLevel requests.")
        relay_result = relay_post(
            "/highlevel/proxy",
            {
                "show_key": show_config["key"],
                "path": path,
                "params": params or {},
                "method": method,
                "json": json_body,
                "context": context,
                "profile_name": (profile or HIGHLEVEL_API_PROFILES[0])["name"],
            },
        )
        if not relay_result["ok"]:
            return {
                "ok": False,
                "status": relay_result["status"],
                "url": relay_result["url"],
                "profile": "relay",
                "error": f"Relay request failed: {relay_result['error']}",
            }
        return relay_result["payload"]

    active_profile = profile or HIGHLEVEL_API_PROFILES[0]
    url = f"{active_profile['base_url']}{path}"
    if params:
        qs = urlencode(params, doseq=True)
        url += f"?{qs}"
    raw_body = None
    if json_body is not None:
        raw_body = json.dumps(json_body).encode("utf-8")
    headers = ghl_headers(token, location_id=location_id, extra_headers=extra_headers, profile=active_profile)
    try:
        status_code, response_body = curl_json_request(
            url,
            method=method,
            headers=headers,
            json_body=json_body,
        )
        try:
            payload = json.loads(response_body)
        except json.JSONDecodeError:
            payload = {"raw": response_body}
        if 200 <= status_code < 300:
            return {
                "ok": True,
                "status": status_code,
                "url": url,
                "profile": active_profile["name"],
                "payload": payload,
            }
        label = f" for {context}" if context else ""
        body = redact_known_secrets(response_body)
        return {
            "ok": False,
            "status": status_code,
            "url": url,
            "profile": active_profile["name"],
            "error": f"GHL API error {status_code}{label}: {body[:300]}",
            "body": body[:300],
        }
    except Exception as e:
        label = f" for {context}" if context else ""
        return {
            "ok": False,
            "status": None,
            "url": url,
            "profile": active_profile["name"],
            "error": f"Request failed{label}: {redact_known_secrets(e)}",
        }


def ghl_get(path, token, params=None, context=None, location_id=None, profile=None, extra_headers=None, show_config=None):
    result = ghl_request(
        path,
        token,
        profile=profile,
        params=params,
        context=context,
        location_id=location_id,
        extra_headers=extra_headers,
        show_config=show_config,
    )
    if not result.get("ok", True):
        log_error(f"  ⚠️ {result['error']}")
        return None
    return result.get("payload", result)


def ghl_post(path, token, json_body=None, params=None, context=None, location_id=None, profile=None, extra_headers=None, show_config=None):
    result = ghl_request(
        path,
        token,
        profile=profile,
        params=params,
        context=context,
        location_id=location_id,
        extra_headers=extra_headers,
        show_config=show_config,
        method="POST",
        json_body=json_body,
    )
    if not result.get("ok", True):
        log_error(f"  ⚠️ {result['error']}")
        return None
    return result.get("payload", result)

def extract_items(payload, preferred_keys=None):
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in preferred_keys or []:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        for value in payload.values():
            if isinstance(value, list):
                return value
    return []


def unwrap_contact_payload(payload):
    if not isinstance(payload, dict):
        return {}
    contact = payload.get("contact")
    if isinstance(contact, dict):
        return contact
    return payload


def contact_display_name(contact):
    if not contact:
        return ""
    full_name = contact.get("fullName") or contact.get("contactName") or contact.get("name")
    if full_name:
        return str(full_name).strip()
    first_name = contact.get("firstName") or contact.get("first_name") or ""
    last_name = contact.get("lastName") or contact.get("last_name") or ""
    return f"{first_name} {last_name}".strip()


def extract_emails(value):
    if value is None:
        return []
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=True)
    return sorted(set(EMAIL_RE.findall(str(value))))


def get_contact(contact_id, token, *, show_config, profile, location_id, cache):
    if not contact_id:
        return {}
    if contact_id in cache:
        return cache[contact_id]
    payload = ghl_get(
        f"/contacts/{contact_id}",
        token,
        context=f"contact {contact_id}",
        location_id=location_id,
        profile=profile,
        show_config=show_config,
    )
    contact = unwrap_contact_payload(payload)
    cache[contact_id] = contact
    return contact


def normalize_appointment(event, *, show_config, location_id, contact=None):
    contact = contact or {}
    contact_id = event.get("contactId") or event.get("contact_id")
    raw_payload = event
    return {
        "show_key": show_config["key"],
        "show_name": show_config["show_name"],
        "highlevel_location_id": location_id,
        "highlevel_calendar_id": event.get("calendarId") or event.get("calendar_id"),
        "appointment_id": event.get("id") or event.get("_id") or event.get("appointmentId"),
        "contact_id": contact_id,
        "guest_name": contact_display_name(contact) or event.get("contactName") or event.get("title") or "",
        "guest_email": contact.get("email") or event.get("email") or event.get("contactEmail") or "",
        "start_time": event.get("startTime") or event.get("start_time"),
        "end_time": event.get("endTime") or event.get("end_time"),
        "calendar_id": event.get("calendarId") or event.get("calendar_id"),
        "assigned_user_id": event.get("assignedUserId") or event.get("assigned_user_id"),
        "status": event.get("appointmentStatus") or event.get("appoinmentStatus") or event.get("status"),
        "linked_form_submission_ids": [],
        "possible_related_form_submissions": [],
        "enriched_contact_payload": contact or None,
        "raw_appointment_payload": raw_payload,
        "raw_payload": raw_payload,
    }


def calendar_event_filter(matched_calendar, show_config):
    matched_calendar = matched_calendar or {}
    group_id = matched_calendar.get("groupId") or matched_calendar.get("group_id")
    calendar_id = matched_calendar.get("id") or matched_calendar.get("_id") or show_config.get("calendar_id_hint")
    if group_id:
        return "groupId", group_id
    if calendar_id:
        return "calendarId", calendar_id
    team_members = matched_calendar.get("teamMembers") or []
    for member in team_members:
        user_id = member.get("userId")
        if user_id:
            return "userId", user_id
    return None, None


def submission_others(submission):
    others = submission.get("others") if isinstance(submission, dict) else {}
    return others if isinstance(others, dict) else {}


def submission_id(submission):
    others = submission_others(submission)
    return submission.get("id") or others.get("submissionId")


def submission_selected_slot(submission):
    others = submission_others(submission)
    return submission.get("selectedSlot") or others.get("selectedSlot")


def parse_datetime(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def same_instant(value_a, value_b, tolerance_seconds=300):
    date_a = parse_datetime(value_a)
    date_b = parse_datetime(value_b)
    if not date_a or not date_b:
        return False
    return abs((date_a.astimezone(timezone.utc) - date_b.astimezone(timezone.utc)).total_seconds()) <= tolerance_seconds


def short_value(value, limit=500):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=True)
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def form_value_items(submission):
    values = {}
    for key in ("name", "email", "phone"):
        if submission.get(key):
            values[key] = submission.get(key)
    for key, value in submission_others(submission).items():
        if key in {
            "formId",
            "sessionId",
            "eventData",
            "Timezone",
            "formAction",
            "calendarName",
            "dateFieldDetails",
            "internalSource",
            "source",
            "locationId",
            "selectedTimezone",
            "selectedSlot",
            "fieldsOriSequance",
            "submissionId",
            "signatureHash",
            "ip",
        }:
            continue
        values[key] = value
    return values


def default_field_metadata(field_key):
    defaults = {
        "name": {"name": "Name", "fieldKey": "contact.name", "dataType": "TEXT"},
        "full_name": {"name": "Full Name", "fieldKey": "contact.full_name", "dataType": "TEXT"},
        "fullName": {"name": "Full Name", "fieldKey": "contact.full_name", "dataType": "TEXT"},
        "first_name": {"name": "First Name", "fieldKey": "contact.first_name", "dataType": "TEXT"},
        "last_name": {"name": "Last Name", "fieldKey": "contact.last_name", "dataType": "TEXT"},
        "email": {"name": "Email", "fieldKey": "contact.email", "dataType": "EMAIL"},
        "phone": {"name": "Phone", "fieldKey": "contact.phone", "dataType": "PHONE"},
    }
    if field_key in defaults:
        return {
            "id": field_key,
            "standard": True,
            "documentType": "default_field",
            **defaults[field_key],
        }
    return {
        "id": field_key,
        "name": field_key,
        "fieldKey": field_key,
        "dataType": None,
        "standard": False,
        "documentType": "observed_submission_field",
    }


def infer_field_flags(field_label, field_key, sample_values):
    context = " ".join([str(field_label or ""), str(field_key or ""), " ".join(map(str, sample_values or []))]).lower()
    has_email_signal = "email" in context or any(extract_emails(value) for value in sample_values or [])
    pr_signal = any(term in context for term in ("pr", "publicist", "marketing rep", "marketing representative", "media contact"))
    assistant_signal = any(term in context for term in ("assistant", "assist@", "ea ", "scheduler", "coordinator"))
    alternate_signal = any(term in context for term in ("alternate", "additional", "calendar invite", "invite email", "cc ", "copy"))
    notes_signal = any(term in context for term in ("notes", "instruction", "calendar invite", "calendar description", "include on", "planning email"))
    guest_signal = has_email_signal and not (pr_signal or assistant_signal or alternate_signal)
    return {
        "appears_to_contain_guest_email": guest_signal,
        "appears_to_contain_pr_email": has_email_signal and pr_signal,
        "appears_to_contain_assistant_email": has_email_signal and assistant_signal,
        "appears_to_contain_alternate_calendar_invite_email": has_email_signal and alternate_signal,
        "appears_to_contain_calendar_invite_notes": notes_signal,
    }


def field_record(field_key, custom_field_by_id, submissions):
    metadata = custom_field_by_id.get(field_key) or default_field_metadata(field_key)
    sample_values = []
    for submission in submissions:
        values = form_value_items(submission)
        if field_key in values:
            value = short_value(values[field_key])
            if value and value not in sample_values:
                sample_values.append(value)
        if len(sample_values) >= 5:
            break
    label = metadata.get("name") or metadata.get("label") or field_key
    field_name = metadata.get("fieldKey") or metadata.get("key") or metadata.get("name") or field_key
    flags = infer_field_flags(label, field_name, sample_values)
    return {
        "field_id": metadata.get("id") or field_key,
        "form_field_key": field_key,
        "field_label": label,
        "field_key_or_name": field_name,
        "field_type": metadata.get("dataType") or metadata.get("type"),
        "required": metadata.get("required") or metadata.get("isRequired"),
        "sample_values": sample_values,
        **flags,
        "raw_field_metadata": metadata,
    }


def custom_field_items(payload):
    return extract_items(payload, preferred_keys=["customFields", "fields"])


def fetch_custom_fields(show_config, token, *, profile, location_id):
    payload = ghl_get(
        f"/locations/{location_id}/customFields",
        token,
        context=f"custom fields for {show_config['show_name']}",
        location_id=location_id,
        profile=profile,
        show_config=show_config,
    )
    return custom_field_items(payload)


def normalize_form_submission(show_config, location_id, submission, custom_field_by_id):
    values = form_value_items(submission)
    field_values = []
    for key, value in values.items():
        metadata = custom_field_by_id.get(key) or default_field_metadata(key)
        label = metadata.get("name") or metadata.get("label") or key
        field_name = metadata.get("fieldKey") or metadata.get("key") or metadata.get("name") or key
        flags = infer_field_flags(label, field_name, [value])
        field_values.append(
            {
                "field_id": metadata.get("id") or key,
                "form_field_key": key,
                "field_label": label,
                "field_key_or_name": field_name,
                "field_type": metadata.get("dataType") or metadata.get("type"),
                "value": value,
                "emails_found": extract_emails(value),
                **flags,
                "raw_field_metadata": metadata,
            }
        )
    return {
        "show_key": show_config["key"],
        "show_name": show_config["show_name"],
        "highlevel_location_id": location_id,
        "submission_id": submission_id(submission),
        "contact_id": submission.get("contactId"),
        "form_id": submission.get("formId") or submission_others(submission).get("formId"),
        "guest_name": submission.get("name") or submission_others(submission).get("fullName") or "",
        "guest_email": submission.get("email") or submission_others(submission).get("email") or "",
        "selected_slot": submission_selected_slot(submission),
        "created_at": submission.get("createdAt"),
        "field_values": field_values,
        "raw_submission_payload": submission,
    }


def submission_summary(submission):
    return {
        "submission_id": submission.get("submission_id") or submission_id(submission),
        "contact_id": submission.get("contact_id") or submission.get("contactId"),
        "form_id": submission.get("form_id") or submission.get("formId"),
        "guest_name": submission.get("guest_name") or submission.get("name"),
        "guest_email": submission.get("guest_email") or submission.get("email"),
        "selected_slot": submission.get("selected_slot") or submission_selected_slot(submission),
    }


def attach_submission_links(appointments, submissions):
    for appointment in appointments:
        linked = []
        possible = []
        for submission in submissions:
            contact_matches = (
                appointment.get("contact_id")
                and appointment.get("contact_id") == submission.get("contact_id")
            )
            slot_matches = same_instant(appointment.get("start_time"), submission.get("selected_slot"))
            if contact_matches:
                linked.append(submission.get("submission_id"))
            elif slot_matches:
                related = submission_summary(submission)
                related["link_reason"] = "same selected slot as appointment start"
                possible.append(related)
        appointment["linked_form_submission_ids"] = [item for item in linked if item]
        appointment["possible_related_form_submissions"] = possible
    return appointments


def calendar_relevant_field_values(submission):
    values = []
    for field in submission.get("field_values", []):
        if any(
            field.get(flag)
            for flag in (
                "appears_to_contain_pr_email",
                "appears_to_contain_assistant_email",
                "appears_to_contain_alternate_calendar_invite_email",
                "appears_to_contain_calendar_invite_notes",
            )
        ):
            values.append(
                {
                    "field_id": field["field_id"],
                    "field_label": field["field_label"],
                    "value": field["value"],
                    "emails_found": field["emails_found"],
                    "classification": {
                        "pr_email": field["appears_to_contain_pr_email"],
                        "assistant_email": field["appears_to_contain_assistant_email"],
                        "alternate_calendar_invite_email": field["appears_to_contain_alternate_calendar_invite_email"],
                        "calendar_invite_notes": field["appears_to_contain_calendar_invite_notes"],
                    },
                }
            )
    return values


def episode_key_from_time(value):
    parsed = parse_datetime(value)
    if not parsed:
        return str(value or "")
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_episode_structure(show_config, appointments, submissions):
    grouped = {}
    for appointment in appointments:
        key = episode_key_from_time(appointment.get("start_time"))
        grouped.setdefault(
            key,
            {
                "show_key": show_config["key"],
                "show_name": show_config["show_name"],
                "episode_date_time": appointment.get("start_time"),
                "appointment_id": appointment.get("appointment_id"),
                "appointment_ids": [],
                "guests": [],
                "unclear_fields_needing_human_review": [],
            },
        )
        grouped[key]["appointment_ids"].append(appointment.get("appointment_id"))
        grouped[key]["guests"].append(
            {
                "appointment_id": appointment.get("appointment_id"),
                "contact_id": appointment.get("contact_id"),
                "name": appointment.get("guest_name"),
                "email": appointment.get("guest_email"),
                "form_submission_ids": appointment.get("linked_form_submission_ids", []),
                "possible_form_submissions": appointment.get("possible_related_form_submissions", []),
                "pr_assistant_alternate_emails": [],
            }
        )
    for submission in submissions:
        key = episode_key_from_time(submission.get("selected_slot"))
        if key not in grouped:
            continue
        linked_to_guest = False
        for guest in grouped[key]["guests"]:
            if submission.get("contact_id") and submission.get("contact_id") == guest.get("contact_id"):
                guest["form_submission_ids"].append(submission.get("submission_id"))
                guest["pr_assistant_alternate_emails"].extend(calendar_relevant_field_values(submission))
                linked_to_guest = True
        if not linked_to_guest:
            grouped[key]["guests"].append(
                {
                    "appointment_id": None,
                    "contact_id": submission.get("contact_id"),
                    "name": submission.get("guest_name"),
                    "email": submission.get("guest_email"),
                    "form_submission_ids": [submission.get("submission_id")],
                    "possible_form_submissions": [],
                    "pr_assistant_alternate_emails": calendar_relevant_field_values(submission),
                }
            )
            grouped[key]["unclear_fields_needing_human_review"].append(
                "Submission matched the episode slot but did not match an appointment contact ID."
            )
    episodes = []
    for episode in grouped.values():
        episode["guest_count"] = len(episode["guests"])
        episode["appears_to_support_multiple_guests"] = len(episode["guests"]) > 1
        if episode["guests"]:
            episode["guest_1_name"] = episode["guests"][0].get("name")
            episode["guest_1_email"] = episode["guests"][0].get("email")
            episode["guest_1_form_submission"] = episode["guests"][0].get("form_submission_ids")
        if len(episode["guests"]) > 1:
            episode["guest_2_name"] = episode["guests"][1].get("name")
            episode["guest_2_email"] = episode["guests"][1].get("email")
            episode["guest_2_form_submission"] = episode["guests"][1].get("form_submission_ids")
        episodes.append(episode)
    return sorted(episodes, key=lambda item: item.get("episode_date_time") or "")


def form_field_order(form_submissions):
    order = []
    for submission in form_submissions:
        fields = submission_others(submission.get("raw_submission_payload", submission)).get("fieldsOriSequance") or []
        for field in fields:
            if field != "button" and field not in order:
                order.append(field)
    return order


def build_form_discovery(show_config, location_id, form_items, custom_fields, raw_submissions):
    custom_field_by_id = {field.get("id"): field for field in custom_fields if field.get("id")}
    normalized_submissions = [
        normalize_form_submission(show_config, location_id, submission, custom_field_by_id)
        for submission in raw_submissions
    ]
    normalized_by_raw_id = {item["submission_id"]: item for item in normalized_submissions}
    form_records = []
    form_fields = []
    for form in form_items:
        form_id = form.get("id") or form.get("_id")
        form_submissions = [item for item in normalized_submissions if item.get("form_id") == form_id]
        raw_for_form = [
            item["raw_submission_payload"]
            for item in form_submissions
            if item.get("raw_submission_payload")
        ]
        field_keys = form_field_order(form_submissions)
        for submission in raw_for_form:
            for key in form_value_items(submission):
                if key not in field_keys:
                    field_keys.append(key)
        fields = [
            field_record(key, custom_field_by_id, raw_for_form)
            for key in field_keys
        ]
        form_records.append(
            {
                "show_key": show_config["key"],
                "show_name": show_config["show_name"],
                "highlevel_location_id": location_id,
                "form_id": form_id,
                "form_name": form.get("name"),
                "submission_count": len(form_submissions),
                "raw_form_metadata": form,
            }
        )
        form_fields.append(
            {
                "show_key": show_config["key"],
                "show_name": show_config["show_name"],
                "highlevel_location_id": location_id,
                "form_id": form_id,
                "form_name": form.get("name"),
                "fields": fields,
            }
        )
    observed_keys = []
    for submission in raw_submissions:
        for key in form_value_items(submission):
            if key not in observed_keys:
                observed_keys.append(key)
    for custom_field in custom_fields:
        key = custom_field.get("id")
        if key and key not in observed_keys:
            observed_keys.append(key)
    custom_field_map = [
        field_record(key, custom_field_by_id, raw_submissions)
        for key in observed_keys
    ]
    return form_records, form_fields, normalized_submissions, custom_field_map, normalized_by_raw_id


def try_discovery_endpoints(token, endpoint_specs, context, *, show_config, profile, location_id):
    for spec in endpoint_specs:
        path = render_template_value(spec["path"], show_config, location_id)
        params = render_template_value(spec.get("params"), show_config, location_id)
        json_body = render_template_value(spec.get("json"), show_config, location_id)
        method = spec.get("method", "GET").upper()
        if method == "POST":
            data = ghl_post(
                path,
                token,
                json_body=json_body,
                params=params,
                context=f"{context} via {path}",
                location_id=location_id,
                profile=profile,
                extra_headers=spec.get("headers"),
                show_config=show_config,
            )
        else:
            data = ghl_get(
                path,
                token,
                params=params,
                context=f"{context} via {path}",
                location_id=location_id,
                profile=profile,
                extra_headers=spec.get("headers"),
                show_config=show_config,
            )
        if data is not None:
            return data, path
    return None, None


def normalized_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def item_name(item):
    return str(item.get("name") or item.get("title") or item.get("calendarName") or "")


def item_id(item):
    return str(item.get("id") or item.get("_id") or item.get("calendarId") or item.get("locationId") or "")


def calendar_form_id(calendar):
    return (calendar or {}).get("formId") or (calendar or {}).get("form_id")


def calendar_active_status(calendar):
    if not calendar:
        return None
    if "isActive" in calendar:
        return bool(calendar.get("isActive"))
    if "active" in calendar:
        return bool(calendar.get("active"))
    return None


def calendar_summary(calendar):
    calendar = calendar or {}
    return {
        "calendar_id": item_id(calendar),
        "calendar_name": item_name(calendar),
        "active": calendar_active_status(calendar),
        "calendar_type": calendar.get("calendarType") or calendar.get("type"),
        "event_type": calendar.get("eventType"),
        "event_title": calendar.get("eventTitle"),
        "widget_slug": calendar.get("widgetSlug"),
        "form_id": calendar_form_id(calendar),
        "group_id": calendar.get("groupId") or calendar.get("group_id"),
        "team_member_user_ids": [
            member.get("userId")
            for member in (calendar.get("teamMembers") or [])
            if isinstance(member, dict) and member.get("userId")
        ],
    }


def appointment_status_counts(events):
    counts = {}
    for event in events:
        status = event.get("appointmentStatus") or event.get("appoinmentStatus") or event.get("status") or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def best_match(items, *, name_hint=None, id_hint=None):
    if not items:
        return None

    if id_hint:
        for item in items:
            if item_id(item) == id_hint:
                return item
    if name_hint:
        for item in items:
            if item_name(item).strip().lower() == name_hint.strip().lower():
                return item
    return items[0]


def fetch_calendar_event_candidates(show_config, token, *, profile, location_id, start_date, end_date, calendar):
    filter_name, filter_value = calendar_event_filter(calendar, show_config)
    if not filter_name:
        return {
            "ok": False,
            "status": None,
            "url": None,
            "events": [],
            "error": "No calendarId, groupId, or userId available for this calendar.",
            "filter_name": None,
            "filter_value": None,
        }
    result = ghl_request(
        "/calendars/events",
        token,
        params={
            "locationId": location_id,
            filter_name: filter_value,
            "startTime": iso_to_epoch_millis(start_date),
            "endTime": iso_to_epoch_millis(end_date),
        },
        context=f"appointment probe for {show_config['show_name']} calendar {filter_value}",
        location_id=location_id,
        profile=profile,
        show_config=show_config,
    )
    payload = result.get("payload") if result.get("ok") else {}
    events = extract_items(payload, preferred_keys=["events", "appointments", "bookings"])
    return {
        "ok": bool(result.get("ok")),
        "status": result.get("status"),
        "url": result.get("url"),
        "events": events,
        "error": result.get("error"),
        "filter_name": filter_name,
        "filter_value": filter_value,
    }


def score_calendar_candidate(candidate):
    score = 0
    reasons = []
    if candidate["config_id_match"]:
        score += 120
        reasons.append("calendar ID matches config")
    if candidate["config_name_match"]:
        score += 80
        reasons.append("calendar name matches config")
    if candidate["form_association"]:
        score += 90
        reasons.append("calendar uses the matched booking form")
    if candidate["appointment_count"] > 0:
        score += 200 + min(candidate["appointment_count"], 25) * 4
        reasons.append(f"{candidate['appointment_count']} appointment(s) found")
    if candidate["name_signal"]:
        score += 25
        reasons.append("calendar name matches show/form language")
    if candidate["active"] is True:
        score += 10
        reasons.append("calendar is active")
    if candidate["endpoint_ok"]:
        score += 5
    else:
        score -= 50
        reasons.append("appointment endpoint failed for this calendar")
    if candidate["active"] is False:
        score -= 25
        reasons.append("calendar is inactive")
    candidate["confidence_score"] = score
    candidate["rank_reasons"] = reasons
    return candidate


def build_calendar_candidate(
    show_config,
    token,
    *,
    profile,
    location_id,
    calendar,
    matched_form,
    start_date,
    end_date,
):
    form_id = item_id(matched_form or {})
    calendar_id = item_id(calendar)
    calendar_name = item_name(calendar)
    config_id_hint = show_config.get("calendar_id_hint") or ""
    config_name_hint = show_config.get("calendar_name_hint") or ""
    name_parts = [
        show_config.get("show_name"),
        show_config.get("form_name_hint"),
        config_name_hint,
        calendar.get("eventTitle"),
        calendar.get("widgetSlug"),
    ]
    normalized_calendar_text = normalized_text(" ".join(str(part or "") for part in [calendar_name, calendar.get("eventTitle"), calendar.get("widgetSlug")]))
    name_signal = any(
        normalized_text(part) and normalized_text(part) in normalized_calendar_text
        for part in name_parts
    )
    probe = fetch_calendar_event_candidates(
        show_config,
        token,
        profile=profile,
        location_id=location_id,
        start_date=start_date,
        end_date=end_date,
        calendar=calendar,
    )
    candidate = {
        **calendar_summary(calendar),
        "config_id_hint": config_id_hint,
        "config_name_hint": config_name_hint,
        "config_id_match": bool(config_id_hint and calendar_id == config_id_hint),
        "config_name_match": bool(config_name_hint and normalized_text(calendar_name) == normalized_text(config_name_hint)),
        "form_association": bool(form_id and calendar_form_id(calendar) == form_id),
        "matched_form_id": form_id or None,
        "matched_form_name": item_name(matched_form or {}) or None,
        "name_signal": name_signal,
        "appointment_count": len(probe["events"]),
        "appointment_status_counts": appointment_status_counts(probe["events"]),
        "endpoint_ok": probe["ok"],
        "endpoint_status": probe["status"],
        "endpoint_url": probe["url"],
        "endpoint_error": redact_known_secrets(probe["error"]) if probe.get("error") else None,
        "filter_name": probe["filter_name"],
        "filter_value": probe["filter_value"],
        "events": probe["events"],
    }
    return score_calendar_candidate(candidate)


def public_calendar_candidate(candidate):
    return {
        key: value
        for key, value in candidate.items()
        if key not in {"events"}
    }


def select_calendar_for_discovery(
    show_config,
    token,
    *,
    profile,
    location_id,
    calendar_items,
    matched_form,
    start_date,
    end_date,
    verbose=True,
):
    candidates = [
        build_calendar_candidate(
            show_config,
            token,
            profile=profile,
            location_id=location_id,
            calendar=calendar,
            matched_form=matched_form,
            start_date=start_date,
            end_date=end_date,
        )
        for calendar in calendar_items
    ]
    candidates.sort(
        key=lambda item: (
            item["confidence_score"],
            item["appointment_count"],
            int(item["config_id_match"]),
            int(item["config_name_match"]),
            int(item["form_association"]),
        ),
        reverse=True,
    )
    selected = candidates[0] if candidates else None
    warnings = []
    config_mismatches = []
    config_id_hint = show_config.get("calendar_id_hint")
    config_name_hint = show_config.get("calendar_name_hint")
    if config_id_hint and not any(candidate["config_id_match"] for candidate in candidates):
        message = f"Configured calendar ID `{config_id_hint}` was not found in the HighLevel location; it may be invalid or stale."
        warnings.append(message)
        config_mismatches.append(message)
    if config_name_hint and not any(candidate["config_name_match"] for candidate in candidates):
        message = f"Configured calendar name `{config_name_hint}` was not found as an exact HighLevel calendar name."
        warnings.append(message)
        config_mismatches.append(message)
    if selected and config_id_hint and selected["calendar_id"] != config_id_hint:
        config_mismatches.append(
            f"Selected calendar `{selected['calendar_id']}` differs from configured calendar ID `{config_id_hint}`."
        )
    if selected and config_name_hint and normalized_text(selected["calendar_name"]) != normalized_text(config_name_hint):
        config_mismatches.append(
            f"Selected calendar `{selected['calendar_name']}` differs from configured calendar name `{config_name_hint}`."
        )
    if selected and selected["appointment_count"] == 0:
        warnings.append(
            "Selected calendar returned 0 appointments; all available calendars were probed before concluding no upcoming bookings were found."
        )
    if not selected:
        warnings.append("No calendars were returned for this HighLevel location.")

    confidence = "Low"
    if selected:
        if selected["appointment_count"] > 0 and (
            selected["config_id_match"] or selected["form_association"] or selected["config_name_match"]
        ):
            confidence = "High"
        elif selected["appointment_count"] > 0:
            confidence = "Medium"
        elif selected["endpoint_ok"] and (
            selected["config_id_match"] or selected["form_association"] or selected["config_name_match"]
        ):
            confidence = "Medium"

    selected_reason = "No calendar selected."
    if selected:
        selected_reason = "Selected highest-ranked calendar: " + (
            "; ".join(selected.get("rank_reasons") or ["no specific ranking evidence"])
        )

    if verbose:
        if selected:
            print(
                f"   Selected calendar: {selected['calendar_name']} "
                f"({selected['calendar_id']}) — {selected['appointment_count']} appointment(s)"
            )
            print(f"   Discovery confidence: {confidence}")
            print(f"   Selection reason: {selected_reason}")
        for warning in warnings:
            print(f"  ⚠️ {warning}")
        if warnings or (selected and selected["appointment_count"] == 0):
            print("   Available HighLevel calendars:")
            for candidate in candidates:
                active_label = "active" if candidate["active"] is True else "inactive" if candidate["active"] is False else "active unknown"
                print(
                    "    - "
                    f"{candidate['calendar_id']} | {candidate['calendar_name']} | "
                    f"{active_label} | appointments: {candidate['appointment_count']} | "
                    f"form: {candidate.get('form_id') or 'none'}"
                )

    return {
        "selected_calendar": selected,
        "selected_calendar_public": public_calendar_candidate(selected) if selected else None,
        "selected_calendar_raw": next(
            (calendar for calendar in calendar_items if selected and item_id(calendar) == selected["calendar_id"]),
            None,
        ),
        "selected_events": selected.get("events", []) if selected else [],
        "candidate_calendars": [public_calendar_candidate(candidate) for candidate in candidates],
        "confidence": confidence,
        "selected_reason": selected_reason,
        "warnings": warnings,
        "config_mismatches": config_mismatches,
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def read_json_if_exists(path, fallback=None):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def discovery_artifact_count(show_key, suffix):
    data = read_json_if_exists(DISCOVERY_DIR / f"{show_key}_{suffix}.json", fallback=[])
    return len(data) if isinstance(data, list) else 0


def discovery_metadata_record(
    *,
    show_config,
    location_id,
    profile,
    location_verified,
    matched_form,
    form_count,
    contact_count,
    appointment_count,
    calendar_selection,
    appointment_discovery_succeeded,
):
    selected = calendar_selection.get("selected_calendar_public") or {}
    return {
        "show_key": show_config["key"],
        "show_name": show_config["show_name"],
        "client_name": show_config["client_name"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_successful_discovery": datetime.now(timezone.utc).isoformat() if appointment_discovery_succeeded else None,
        "highlevel_profile": profile["name"],
        "location_id": location_id,
        "location_verified": location_verified,
        "selected_calendar": selected,
        "selected_calendar_id": selected.get("calendar_id"),
        "selected_calendar_name": selected.get("calendar_name"),
        "selected_calendar_active": selected.get("active"),
        "selected_calendar_form_id": selected.get("form_id"),
        "configured_calendar_id": show_config.get("calendar_id_hint"),
        "configured_calendar_name": show_config.get("calendar_name_hint"),
        "calendar_id_matches_config": bool(selected.get("config_id_match")),
        "calendar_name_matches_config": bool(selected.get("config_name_match")),
        "booking_form": {
            "form_id": item_id(matched_form or {}) or None,
            "form_name": item_name(matched_form or {}) or None,
            "found": matched_form is not None,
        },
        "form_count": form_count,
        "contact_count": contact_count,
        "appointment_count": appointment_count,
        "appointment_status_counts": selected.get("appointment_status_counts", {}),
        "appointment_endpoint_returning_data": appointment_count > 0,
        "appointment_discovery_succeeded": appointment_discovery_succeeded,
        "discovery_confidence": calendar_selection.get("confidence", "Low"),
        "selected_reason": calendar_selection.get("selected_reason"),
        "alternate_calendars_considered": calendar_selection.get("candidate_calendars", []),
        "warnings": calendar_selection.get("warnings", []),
        "configuration_mismatches": calendar_selection.get("config_mismatches", []),
    }


def health_badge_class(value):
    normalized = normalized_text(value)
    if normalized == "high":
        return "ready"
    if normalized == "medium":
        return "warning"
    if normalized == "low":
        return "critical"
    return "info"


def write_discovery_health_report(updated_records=None):
    updated_by_key = {record["show_key"]: record for record in (updated_records or [])}
    records = []
    for show_config in SHOW_HIGHLEVEL_CONFIGS:
        show_key = show_config["key"]
        metadata_path = DISCOVERY_DIR / f"{show_key}_discovery_metadata.json"
        record = updated_by_key.get(show_key) or read_json_if_exists(metadata_path, fallback={}) or {}
        if record:
            record.setdefault("show_key", show_key)
            record.setdefault("show_name", show_config["show_name"])
            record.setdefault("client_name", show_config["client_name"])
        else:
            record = {
                "show_key": show_key,
                "show_name": show_config["show_name"],
                "client_name": show_config["client_name"],
                "generated_at": None,
                "last_successful_discovery": None,
                "selected_calendar_name": None,
                "selected_calendar_id": None,
                "appointment_count": discovery_artifact_count(show_key, "appointments"),
                "form_count": discovery_artifact_count(show_key, "forms"),
                "contact_count": 0,
                "discovery_confidence": "Low",
                "warnings": ["Discovery metadata is not available yet. Rerun HighLevel discovery for this show."],
                "configuration_mismatches": [],
                "alternate_calendars_considered": [],
            }
        record["appointment_count"] = record.get("appointment_count", discovery_artifact_count(show_key, "appointments"))
        record["form_count"] = record.get("form_count", discovery_artifact_count(show_key, "forms"))
        records.append(record)

    write_json(DISCOVERY_DIR / "discovery_health.json", records)

    generated_at = datetime.now(timezone.utc).isoformat()
    rows = []
    detail_cards = []
    for record in records:
        warnings = record.get("warnings") or []
        mismatches = record.get("configuration_mismatches") or []
        confidence = record.get("discovery_confidence") or "Low"
        rows.append(
            "<tr>"
            f"<td>{html.escape(record.get('show_name') or record['show_key'])}</td>"
            f"<td>{html.escape(record.get('selected_calendar_name') or 'Not selected')}</td>"
            f"<td><code>{html.escape(str(record.get('selected_calendar_id') or ''))}</code></td>"
            f"<td>{html.escape(str(record.get('appointment_count', 0)))}</td>"
            f"<td>{html.escape(str(record.get('form_count', 0)))}</td>"
            f"<td>{html.escape(str(record.get('contact_count', 0)))}</td>"
            f"<td>{html.escape(str(record.get('last_successful_discovery') or 'Unknown'))}</td>"
            f"<td><span class=\"badge {health_badge_class(confidence)}\">{html.escape(confidence)}</span></td>"
            f"<td>{html.escape('; '.join(warnings + mismatches) or 'None')}</td>"
            "</tr>"
        )
        candidate_items = []
        for candidate in record.get("alternate_calendars_considered") or []:
            candidate_items.append(
                "<li>"
                f"<code>{html.escape(str(candidate.get('calendar_id') or ''))}</code> "
                f"{html.escape(candidate.get('calendar_name') or 'Unnamed calendar')} "
                f"<span class=\"muted\">appointments: {html.escape(str(candidate.get('appointment_count', 0)))}; "
                f"active: {html.escape(str(candidate.get('active')))}; "
                f"form: {html.escape(str(candidate.get('form_id') or 'none'))}</span>"
                "</li>"
            )
        detail_cards.append(
            "<article class=\"card\">"
            f"<h2>{html.escape(record.get('show_name') or record['show_key'])}</h2>"
            f"<p><strong>Selected calendar:</strong> {html.escape(record.get('selected_calendar_name') or 'Not selected')} "
            f"<code>{html.escape(str(record.get('selected_calendar_id') or ''))}</code></p>"
            f"<p><strong>Confidence:</strong> <span class=\"badge {health_badge_class(confidence)}\">{html.escape(confidence)}</span></p>"
            f"<p><strong>Why selected:</strong> {html.escape(record.get('selected_reason') or 'No selection reason available.')}</p>"
            f"<p><strong>Warnings:</strong> {html.escape('; '.join(warnings) or 'None')}</p>"
            f"<p><strong>Configuration mismatches:</strong> {html.escape('; '.join(mismatches) or 'None')}</p>"
            "<details><summary>Alternate Calendars Considered</summary>"
            f"<ul>{''.join(candidate_items) or '<li>No alternate calendar evidence recorded.</li>'}</ul>"
            "</details>"
            "</article>"
        )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HighLevel Discovery Health</title>
  <style>
    :root {{
      --ink: #102033;
      --muted: #637083;
      --paper: #f7f4ec;
      --card: #fffaf0;
      --line: #d9cfbd;
      --ready: #19784a;
      --warning: #a66b00;
      --critical: #b3261e;
      --info: #2f5f9f;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: linear-gradient(135deg, #f7f4ec 0%, #eef4f7 100%);
      color: var(--ink);
    }}
    header, main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px;
    }}
    header {{
      padding-top: 42px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(32px, 5vw, 56px);
      letter-spacing: -0.04em;
    }}
    .muted {{
      color: var(--muted);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: rgba(255, 250, 240, 0.88);
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      background: #efe6d5;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 18px;
      margin-top: 24px;
    }}
    .card {{
      background: rgba(255, 250, 240, 0.92);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
      box-shadow: 0 18px 45px rgba(16, 32, 51, 0.08);
    }}
    .badge {{
      display: inline-block;
      padding: 4px 9px;
      border-radius: 999px;
      color: white;
      font-size: 12px;
      font-weight: 700;
    }}
    .ready {{ background: var(--ready); }}
    .warning {{ background: var(--warning); }}
    .critical {{ background: var(--critical); }}
    .info {{ background: var(--info); }}
  </style>
</head>
<body>
  <header>
    <h1>HighLevel Discovery Health</h1>
    <p class="muted">Generated {html.escape(generated_at)}. Read-only report: no HighLevel, Google Calendar, Gmail, appointment, event, attendee, or email changes are made.</p>
  </header>
  <main>
    <table>
      <thead>
        <tr>
          <th>Show</th>
          <th>Selected Calendar</th>
          <th>Calendar ID</th>
          <th>Appointments</th>
          <th>Forms</th>
          <th>Contacts</th>
          <th>Last Successful Discovery</th>
          <th>Confidence</th>
          <th>Warnings / Mismatches</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    <section class="grid">
      {''.join(detail_cards)}
    </section>
  </main>
</body>
</html>
"""
    (DISCOVERY_DIR / "discovery_health.html").write_text(html_doc, encoding="utf-8")


def write_review_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["show_key", "show_name", "severity", "area", "message"])
        writer.writeheader()
        writer.writerows(rows)


def test_highlevel_auth(show_config, token, *, verbose=True):
    if use_relay_transport():
        relay_result = relay_post("/highlevel/auth-test", {"show_key": show_config["key"]})
        if not relay_result["ok"]:
            raise RuntimeError(f"HighLevel relay auth test failed: {relay_result['error']}")
        payload = relay_result["payload"]
        if verbose:
            print(f"\n🔐 Testing HighLevel auth for {show_config['show_name']}")
            print(f"   Transport: relay")
            print(f"   Relay endpoint: {relay_result['url']}")
            if payload.get("ok"):
                print("  ✅ Auth OK through deployed relay")
                print(f"     Status: {payload['status']}")
                print(f"     Working endpoint: {payload['url']}")
                print(f"     Response body: {json.dumps(payload.get('payload', {}), ensure_ascii=True)[:1200]}")
            else:
                print("  ❌ Relay auth test failed")
                print(f"     Status: {payload.get('status')}")
                print(f"     Working endpoint: {payload.get('url')}")
                print(f"     Response body: {payload.get('error')}")
        if not payload.get("ok"):
            raise RuntimeError(
                f"Could not validate the HighLevel private integration token for {show_config['show_name']} through the deployed relay."
            )
        return {
            "profile": {"name": payload.get("profile", "relay")},
            "path": payload.get("path"),
            "params": payload.get("params"),
            "result": payload,
        }

    location_id = resolve_location_id(show_config, required=True)
    if verbose:
        print(f"\n🔐 Testing HighLevel auth for {show_config['show_name']}")
        print(f"   Location ID source: {show_config['location_env_var']}")
    profile = HIGHLEVEL_API_PROFILES[0]
    probe = profile["auth_probe"]
    path = render_template_value(probe["path"], show_config, location_id)
    json_body = render_template_value(probe.get("json"), show_config, location_id)
    result = ghl_request(
        path,
        token,
        profile=profile,
        context=f"auth probe {probe['label']}",
        location_id=location_id,
        extra_headers=probe.get("headers"),
        show_config=show_config,
        method=probe.get("method", "POST"),
        json_body=json_body,
    )
    if verbose:
        print(f"   API base: {profile['base_url']}")
        print(f"   API version: {profile['default_headers'].get('Version')}")
        print(f"   Endpoint: {result['url']}")
        print(f"   Method: {probe.get('method', 'POST')}")
        print(f"   Request body: {json.dumps(json_body, ensure_ascii=True)}")
        if result["ok"]:
            print("  ✅ Auth OK with documented location-scoped endpoint")
            print(f"     Status: {result['status']}")
            print(f"     Response body: {sanitize_response_for_output(result['payload'])}")
        else:
            print("  ❌ Auth failed")
            print(f"     Status: {result.get('status')}")
            print(f"     Response body: {sanitize_response_for_output(result.get('body') or result.get('error'))}")
    if result["ok"]:
        return {
            "profile": profile,
            "path": path,
            "json": json_body,
            "result": result,
        }
    raise RuntimeError(
        f"Could not validate the HighLevel private integration token for {show_config['show_name']} "
        f"with the documented POST {path} location-scoped auth check."
    )


def validation_line(ok, label, detail="", fix=""):
    marker = "✓" if ok else "✗"
    print(f"  {marker} {label}: {detail}")
    if not ok and fix:
        print(f"     Fix: {fix}")
    return {
        "label": label,
        "ok": ok,
        "detail": detail,
        "fix": fix,
    }


def validate_discovery(show_key=None, days_ahead=90):
    selected_configs = [SHOW_CONFIG_BY_KEY[show_key]] if show_key else SHOW_HIGHLEVEL_CONFIGS
    start_date, end_date = upcoming_iso_range(days_ahead)
    validation_results = []
    metadata_output = []
    any_failed = False

    for show_config in selected_configs:
        show_key_value = show_config["key"]
        show_name = show_config["show_name"]
        print(f"\n🔎 Validating discovery for {show_name}")
        checks = []
        token = os.environ.get(show_config["env_var"])
        location_id = resolve_location_id(show_config, required=False)

        if not token:
            any_failed = True
            checks.append(
                validation_line(
                    False,
                    "Token valid",
                    f"{show_config['env_var']} is missing",
                    f"Add {show_config['env_var']} to `.env`.",
                )
            )
            validation_results.append({"show_key": show_key_value, "show_name": show_name, "checks": checks})
            continue
        if not location_id:
            any_failed = True
            checks.append(
                validation_line(
                    False,
                    "Location valid",
                    f"{show_config['location_env_var']} is missing",
                    f"Add {show_config['location_env_var']} to `.env`.",
                )
            )
            validation_results.append({"show_key": show_key_value, "show_name": show_name, "checks": checks})
            continue

        try:
            auth_state = test_highlevel_auth(show_config, token, verbose=False)
            profile = auth_state["profile"]
            checks.append(
                validation_line(
                    True,
                    "Token valid",
                    f"POST {auth_state['path']} returned {auth_state['result']['status']}",
                )
            )
        except RuntimeError as exc:
            any_failed = True
            checks.append(
                validation_line(
                    False,
                    "Token valid",
                    redact_known_secrets(exc),
                    "Confirm the private integration token belongs to this HighLevel sub-account and has read scopes.",
                )
            )
            validation_results.append({"show_key": show_key_value, "show_name": show_name, "checks": checks})
            continue

        location_payload, _location_endpoint = try_discovery_endpoints(
            token,
            [
                {"path": "/locations/{location_id}"},
                {"path": "/locations/{location_id}/"},
            ],
            context=f"location validation for {show_name}",
            show_config=show_config,
            profile=profile,
            location_id=location_id,
        )
        location_verified = bool(location_payload)
        checks.append(
            validation_line(
                location_verified,
                "Location valid",
                f"Location ID {location_id} {'was verified' if location_verified else 'could not be verified'}",
                f"Confirm {show_config['location_env_var']} belongs to {show_name}.",
            )
        )

        calendars_payload, _calendars_endpoint = try_discovery_endpoints(
            token,
            [
                {"path": "/calendars/", "params": {"locationId": "{location_id}"}},
                {"path": "/calendars", "params": {"locationId": "{location_id}"}},
            ],
            context=f"calendar validation for {show_name}",
            show_config=show_config,
            profile=profile,
            location_id=location_id,
        )
        calendar_items = extract_items(calendars_payload, preferred_keys=["calendars"])

        forms_payload, _forms_endpoint = try_discovery_endpoints(
            token,
            [
                {"path": "/forms/", "params": {"locationId": "{location_id}"}},
                {"path": "/forms", "params": {"locationId": "{location_id}"}},
            ],
            context=f"form validation for {show_name}",
            show_config=show_config,
            profile=profile,
            location_id=location_id,
        )
        form_items = extract_items(forms_payload, preferred_keys=["forms"])
        matched_form = best_match(form_items, name_hint=show_config.get("form_name_hint"))

        calendar_selection = select_calendar_for_discovery(
            show_config,
            token,
            profile=profile,
            location_id=location_id,
            calendar_items=calendar_items,
            matched_form=matched_form,
            start_date=start_date,
            end_date=end_date,
            verbose=False,
        )
        selected_calendar = calendar_selection.get("selected_calendar_public") or {}
        calendar_exists = bool(selected_calendar)
        calendar_id_matches = bool(selected_calendar.get("config_id_match"))
        booking_form_found = matched_form is not None
        appointment_endpoint_returning_data = selected_calendar.get("appointment_count", 0) > 0
        confidence = calendar_selection.get("confidence", "Low")

        checks.extend(
            [
                validation_line(
                    calendar_exists,
                    "Calendar exists",
                    (
                        f"{selected_calendar.get('calendar_name')} ({selected_calendar.get('calendar_id')})"
                        if calendar_exists
                        else "No calendars returned for this location"
                    ),
                    "Confirm the HighLevel location ID and calendar scopes, then rerun discovery.",
                ),
                validation_line(
                    calendar_id_matches,
                    "Calendar ID matches config",
                    (
                        f"Configured {show_config.get('calendar_id_hint')} matches selected calendar"
                        if calendar_id_matches
                        else f"Configured {show_config.get('calendar_id_hint')} does not match selected {selected_calendar.get('calendar_id')}"
                    ),
                    "Update `calendar_id_hint` and `calendar_name_hint` in `scripts/show-launch.py` to the selected booking calendar.",
                ),
                validation_line(
                    booking_form_found,
                    "Booking form found",
                    (
                        f"{item_name(matched_form)} ({item_id(matched_form)})"
                        if booking_form_found
                        else f"No form matched `{show_config.get('form_name_hint')}`"
                    ),
                    "Update the form hint or confirm the booking form still exists in HighLevel.",
                ),
                validation_line(
                    appointment_endpoint_returning_data,
                    "Appointment endpoint returning data",
                    f"{selected_calendar.get('appointment_count', 0)} appointment(s) found in the validation range",
                    "If bookings exist, check whether the configured booking calendar is stale or whether bookings live on another calendar.",
                ),
                validation_line(
                    confidence in {"High", "Medium"},
                    "Discovery confidence",
                    confidence,
                    "Review candidate calendars and update calendar hints before trusting this show's audit.",
                ),
            ]
        )

        contacts_payload, _contacts_endpoint = try_discovery_endpoints(
            token,
            [
                {"method": "POST", "path": "/contacts/search", "json": {"locationId": "{location_id}", "pageLimit": 25}},
            ],
            context=f"contact validation for {show_name}",
            show_config=show_config,
            profile=profile,
            location_id=location_id,
        )
        contact_items = extract_items(contacts_payload, preferred_keys=["contacts"])

        if any(not check["ok"] for check in checks):
            any_failed = True

        metadata_record = discovery_metadata_record(
            show_config=show_config,
            location_id=location_id,
            profile=profile,
            location_verified=location_verified,
            matched_form=matched_form,
            form_count=len(form_items),
            contact_count=len(contact_items),
            appointment_count=selected_calendar.get("appointment_count", 0),
            calendar_selection=calendar_selection,
            appointment_discovery_succeeded=bool(selected_calendar.get("endpoint_ok")),
        )
        metadata_output.append(metadata_record)
        write_json(DISCOVERY_DIR / f"{show_key_value}_discovery_metadata.json", metadata_record)
        validation_results.append(
            {
                "show_key": show_key_value,
                "show_name": show_name,
                "checks": checks,
                "calendar_selection": {
                    "selected_calendar": selected_calendar,
                    "confidence": confidence,
                    "warnings": calendar_selection.get("warnings", []),
                    "configuration_mismatches": calendar_selection.get("config_mismatches", []),
                    "alternate_calendars_considered": calendar_selection.get("candidate_calendars", []),
                },
            }
        )

    write_json(DISCOVERY_DIR / "discovery_validation.json", validation_results)
    write_discovery_health_report(metadata_output)

    if any_failed:
        raise RuntimeError(
            "Discovery validation found one or more issues. Review the failed checks above and `data/discovery/discovery_health.html`."
        )
    print(f"\n✅ Discovery validation passed for {len(selected_configs)} show(s).")


def pull_appointments(
    show_config,
    token,
    start_date=None,
    end_date=None,
    matched_calendar=None,
    profile=None,
    preloaded_events=None,
):
    """Pull appointments from GHL calendar."""
    location_id = resolve_location_id(show_config, required=True)
    if profile is None:
        auth_state = test_highlevel_auth(show_config, token, verbose=False)
        profile = auth_state["profile"]

    if not start_date:
        start_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00.000Z")
    if not end_date:
        end_date = (datetime.now(timezone.utc) + timedelta(days=90)).strftime("%Y-%m-%dT23:59:59.999Z")

    print(f"\n📋 Pulling appointments from GHL for {show_config['show_name']}...")
    print(f"   Range: {start_date[:10]} → {end_date[:10]}")

    if preloaded_events is not None:
        events = preloaded_events
    else:
        probe = fetch_calendar_event_candidates(
            show_config,
            token,
            profile=profile,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date,
            calendar=matched_calendar,
        )
        if not probe["ok"]:
            print("  ❌ Failed to fetch appointments")
            if probe.get("error"):
                log_error(f"  ⚠️ {probe['error']}")
            return [], False
        events = probe["events"]
    contact_cache = {}
    appointments = []
    for event in events:
        contact_id = event.get("contactId") or event.get("contact_id")
        contact = get_contact(
            contact_id,
            token,
            show_config=show_config,
            profile=profile,
            location_id=location_id,
            cache=contact_cache,
        )
        appointments.append(
            normalize_appointment(
                event,
                show_config=show_config,
                location_id=location_id,
                contact=contact,
            )
        )
    print(f"  ✅ Found {len(appointments)} appointment(s)")
    return appointments, True


def discover_highlevel(days_back=DEFAULT_DISCOVERY_LOOKBACK_DAYS, days_ahead=DEFAULT_DISCOVERY_LOOKAHEAD_DAYS, show_key=None):
    selected_configs = [SHOW_CONFIG_BY_KEY[show_key]] if show_key else SHOW_HIGHLEVEL_CONFIGS
    tokens = require_highlevel_tokens(selected_configs)
    start_date, end_date = iso_range(days_back=days_back, days_ahead=days_ahead)

    locations_output = []
    calendars_output = []
    calendar_settings_output = []
    forms_output = []
    form_fields_output = []
    submissions_output = []
    appointments_output = []
    contacts_output = []
    metadata_output = []
    review_rows = []
    summary_lines = [
        "# HighLevel Discovery Summary",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Date range: {start_date[:10]} to {end_date[:10]}",
        f"- Scoped sub-accounts: {len(selected_configs)}",
        "",
    ]

    for show_config in selected_configs:
        token = tokens[show_config["key"]]
        show_name = show_config["show_name"]
        client_name = show_config["client_name"]
        try:
            location_id = resolve_location_id(show_config, required=True)
        except RuntimeError as exc:
            error_message = str(exc)
            log_error(f"  ⚠️ Skipping {show_name}: {error_message}")
            review_rows.append(
                {
                    "show_key": show_config["key"],
                    "show_name": show_name,
                    "severity": "high",
                    "area": "configuration",
                    "message": error_message,
                }
            )
            for suffix in (
                "appointments",
                "forms",
                "form_fields",
                "form_submissions",
                "custom_field_map",
                "episodes",
            ):
                write_json(DISCOVERY_DIR / f"{show_config['key']}_{suffix}.json", [])
            summary_lines.extend(
                [
                    f"## {show_name}",
                    "",
                    "- Discovery status: failed",
                    f"- Client: {client_name}",
                    f"- Env var: `{show_config['env_var']}`",
                    f"- Location env var: `{show_config['location_env_var']}`",
                    f"- Failure reason: {error_message}",
                    f"- Appointments discovered: 0",
                    f"- Form submissions discovered: 0",
                    f"- Custom fields discovered: 0",
                    "- Appointment/submission linking: not linked",
                    "- Multiple-guest support detected: unknown",
                    "- Calendar-relevant fields: none detected",
                    "- Missing field categories: unknown until location ID is configured",
                    "- Human review items: 1",
                    "",
                ]
            )
            continue
        auth_state = test_highlevel_auth(show_config, token, verbose=False)
        profile = auth_state["profile"]
        print(f"\n🔎 Discovering HighLevel data for {show_name} ({client_name})")
        print(f"   Using HighLevel profile: {profile['name']}")

        location_payload, location_endpoint = try_discovery_endpoints(
            token,
            [
                {"path": "/locations/{location_id}"},
                {"path": "/locations/{location_id}/"},
            ],
            context=f"location for {show_name}",
            show_config=show_config,
            profile=profile,
            location_id=location_id,
        )
        location_record = location_payload if isinstance(location_payload, dict) else {}
        show_config["location_id"] = location_id
        location_verified = bool(location_record)

        locations_output.append(
            {
                "show_key": show_config["key"],
                "show_name": show_name,
                "client_name": client_name,
                "env_var": show_config["env_var"],
                "location_env_var": show_config["location_env_var"],
                "location_id": location_id,
                "discovery_endpoint": location_endpoint,
                "location_verified": location_verified,
                "location_hint_name": show_config.get("location_name_hint"),
                "location_hint_id": show_config.get("location_id_hint"),
                "location": location_record,
            }
        )
        if not location_verified:
            review_rows.append(
                {
                    "show_key": show_config["key"],
                    "show_name": show_name,
                    "severity": "high",
                    "area": "location",
                    "message": "Could not verify the expected HighLevel location via API; review location scope and endpoint support.",
                }
            )

        calendars_payload, calendars_endpoint = try_discovery_endpoints(
            token,
            [
                {"path": "/calendars/", "params": {"locationId": "{location_id}"}},
                {"path": "/calendars", "params": {"locationId": "{location_id}"}},
            ],
            context=f"calendars for {show_name}",
            show_config=show_config,
            profile=profile,
            location_id=location_id,
        )
        calendar_items = extract_items(calendars_payload, preferred_keys=["calendars"])

        forms_payload, forms_endpoint = try_discovery_endpoints(
            token,
            [
                {"path": "/forms/", "params": {"locationId": "{location_id}"}},
                {"path": "/forms", "params": {"locationId": "{location_id}"}},
            ],
            context=f"forms for {show_name}",
            show_config=show_config,
            profile=profile,
            location_id=location_id,
        )
        form_items = extract_items(forms_payload, preferred_keys=["forms"])
        matched_form = best_match(form_items, name_hint=show_config.get("form_name_hint"))
        forms_output.append(
            {
                "show_key": show_config["key"],
                "show_name": show_name,
                "client_name": client_name,
                "discovery_endpoint": forms_endpoint,
                "form_hint_name": show_config.get("form_name_hint"),
                "form_verified": matched_form is not None,
                "form": matched_form,
                "raw_forms_sample": form_items[:20],
            }
        )
        if matched_form is None:
            review_rows.append(
                {
                    "show_key": show_config["key"],
                    "show_name": show_name,
                    "severity": "medium",
                    "area": "form",
                    "message": "Could not verify the expected HighLevel form via API; review form naming and endpoint support.",
                }
            )

        appointment_start_date, appointment_end_date = upcoming_iso_range(days_ahead)
        calendar_selection = select_calendar_for_discovery(
            show_config,
            token,
            profile=profile,
            location_id=location_id,
            calendar_items=calendar_items,
            matched_form=matched_form,
            start_date=appointment_start_date,
            end_date=appointment_end_date,
            verbose=True,
        )
        matched_calendar = calendar_selection.get("selected_calendar_raw")
        selected_calendar_public = calendar_selection.get("selected_calendar_public") or {}
        calendars_output.append(
            {
                "show_key": show_config["key"],
                "show_name": show_name,
                "client_name": client_name,
                "discovery_endpoint": calendars_endpoint,
                "calendar_hint_name": show_config.get("calendar_name_hint"),
                "calendar_hint_id": show_config.get("calendar_id_hint"),
                "calendar_verified": matched_calendar is not None,
                "calendar": matched_calendar,
                "selected_calendar": selected_calendar_public,
                "selection_reason": calendar_selection.get("selected_reason"),
                "discovery_confidence": calendar_selection.get("confidence"),
                "warnings": calendar_selection.get("warnings", []),
                "configuration_mismatches": calendar_selection.get("config_mismatches", []),
                "candidate_calendars": calendar_selection.get("candidate_calendars", []),
                "raw_calendars_sample": calendar_items[:20],
            }
        )
        calendar_settings_output.append(
            {
                "show_key": show_config["key"],
                "show_name": show_name,
                "calendar_id_hint": show_config.get("calendar_id_hint"),
                "calendar_verified": matched_calendar is not None,
                "settings_source": calendars_endpoint,
                "calendar_settings": matched_calendar or {},
                "selected_calendar": selected_calendar_public,
                "selection_reason": calendar_selection.get("selected_reason"),
                "discovery_confidence": calendar_selection.get("confidence"),
                "candidate_calendars": calendar_selection.get("candidate_calendars", []),
                "add_guests": (
                    (matched_calendar or {}).get("allowGuests")
                    if matched_calendar
                    else None
                ),
            }
        )
        if matched_calendar is None:
            review_rows.append(
                {
                    "show_key": show_config["key"],
                    "show_name": show_name,
                    "severity": "high",
                    "area": "calendar",
                    "message": "Could not verify the expected HighLevel calendar via API; review calendar hints and endpoint support.",
                }
            )
        for message in calendar_selection.get("warnings", []):
            review_rows.append(
                {
                    "show_key": show_config["key"],
                    "show_name": show_name,
                    "severity": "medium",
                    "area": "calendar",
                    "message": message,
                }
            )
        for message in calendar_selection.get("config_mismatches", []):
            review_rows.append(
                {
                    "show_key": show_config["key"],
                    "show_name": show_name,
                    "severity": "medium",
                    "area": "calendar_configuration",
                    "message": message,
                }
            )

        submissions_payload, submissions_endpoint = try_discovery_endpoints(
            token,
            [
                {"path": "/forms/submissions/", "params": {"locationId": "{location_id}", "limit": 100}},
                {"path": "/forms/submissions", "params": {"locationId": "{location_id}", "limit": 100}},
            ],
            context=f"recent submissions for {show_name}",
            show_config=show_config,
            profile=profile,
            location_id=location_id,
        )
        submission_items = extract_items(submissions_payload, preferred_keys=["submissions", "results"])

        custom_field_items_for_show = fetch_custom_fields(show_config, token, profile=profile, location_id=location_id)
        (
            show_form_records,
            show_form_fields,
            normalized_submissions,
            custom_field_map,
            _normalized_submission_by_id,
        ) = build_form_discovery(show_config, location_id, form_items, custom_field_items_for_show, submission_items)
        write_json(DISCOVERY_DIR / f"{show_config['key']}_forms.json", show_form_records)
        write_json(DISCOVERY_DIR / f"{show_config['key']}_form_fields.json", show_form_fields)
        write_json(DISCOVERY_DIR / f"{show_config['key']}_form_submissions.json", normalized_submissions)
        write_json(DISCOVERY_DIR / f"{show_config['key']}_custom_field_map.json", custom_field_map)
        form_fields_output.extend(show_form_fields)
        submissions_output.append(
            {
                "show_key": show_config["key"],
                "show_name": show_name,
                "client_name": client_name,
                "discovery_endpoint": submissions_endpoint,
                "submission_count": len(normalized_submissions),
                "recent_submissions": normalized_submissions[:100],
            }
        )

        if matched_calendar:
            appointment_items, appointment_discovery_succeeded = pull_appointments(
                show_config,
                token,
                start_date=appointment_start_date,
                end_date=appointment_end_date,
                matched_calendar=matched_calendar,
                profile=profile,
                preloaded_events=calendar_selection.get("selected_events", []),
            )
        else:
            appointment_items = []
            appointment_discovery_succeeded = False
        appointment_items = attach_submission_links(appointment_items, normalized_submissions)
        episode_items = build_episode_structure(show_config, appointment_items, normalized_submissions)
        write_json(DISCOVERY_DIR / f"{show_config['key']}_appointments.json", appointment_items)
        write_json(DISCOVERY_DIR / f"{show_config['key']}_episodes.json", episode_items)
        appointments_output.append(
            {
                "show_key": show_config["key"],
                "show_name": show_name,
                "client_name": client_name,
                "location_id": location_id,
                "calendar_id": selected_calendar_public.get("calendar_id") or show_config.get("calendar_id_hint"),
                "selected_calendar": selected_calendar_public,
                "selection_reason": calendar_selection.get("selected_reason"),
                "discovery_confidence": calendar_selection.get("confidence"),
                "alternate_calendars_considered": calendar_selection.get("candidate_calendars", []),
                "warnings": calendar_selection.get("warnings", []),
                "configuration_mismatches": calendar_selection.get("config_mismatches", []),
                "appointment_discovery_succeeded": appointment_discovery_succeeded,
                "appointment_start_date": appointment_start_date,
                "appointment_end_date": appointment_end_date,
                "appointments": appointment_items[:100],
                "appointment_count": len(appointment_items),
                "episodes": episode_items[:100],
                "episode_count": len(episode_items),
            }
        )
        if not appointment_discovery_succeeded:
            review_rows.append(
                {
                    "show_key": show_config["key"],
                    "show_name": show_name,
                    "severity": "high",
                    "area": "appointments",
                    "message": "Could not discover upcoming HighLevel appointments for the matched calendar.",
                }
            )

        contacts_payload, contacts_endpoint = try_discovery_endpoints(
            token,
            [
                {"method": "POST", "path": "/contacts/search", "json": {"locationId": "{location_id}", "pageLimit": 25}},
            ],
            context=f"contacts for {show_name}",
            show_config=show_config,
            profile=profile,
            location_id=location_id,
        )
        contact_items = extract_items(contacts_payload, preferred_keys=["contacts"])
        contacts_output.append(
            {
                "show_key": show_config["key"],
                "show_name": show_name,
                "client_name": client_name,
                "discovery_endpoint": contacts_endpoint,
                "contact_count": len(contact_items),
                "contacts": contact_items[:25],
            }
        )

        metadata_record = discovery_metadata_record(
            show_config=show_config,
            location_id=location_id,
            profile=profile,
            location_verified=location_verified,
            matched_form=matched_form,
            form_count=len(form_items),
            contact_count=len(contact_items),
            appointment_count=len(appointment_items),
            calendar_selection=calendar_selection,
            appointment_discovery_succeeded=appointment_discovery_succeeded,
        )
        metadata_output.append(metadata_record)
        write_json(DISCOVERY_DIR / f"{show_config['key']}_discovery_metadata.json", metadata_record)

        exact_link_count = sum(1 for item in appointment_items if item.get("linked_form_submission_ids"))
        possible_link_count = sum(1 for item in appointment_items if item.get("possible_related_form_submissions"))
        if exact_link_count:
            linking_status = "exact contact link available"
        elif possible_link_count:
            linking_status = "possible slot-based link available"
        else:
            linking_status = "not linked"
        multiple_guest_supported = any(item.get("appears_to_support_multiple_guests") for item in episode_items)
        calendar_relevant_fields = [
            item["field_label"]
            for item in custom_field_map
            if item.get("appears_to_contain_pr_email")
            or item.get("appears_to_contain_assistant_email")
            or item.get("appears_to_contain_alternate_calendar_invite_email")
            or item.get("appears_to_contain_calendar_invite_notes")
        ]
        missing_field_categories = []
        field_category_checks = {
            "guest email": "appears_to_contain_guest_email",
            "PR email": "appears_to_contain_pr_email",
            "assistant email": "appears_to_contain_assistant_email",
            "alternate calendar invite email": "appears_to_contain_alternate_calendar_invite_email",
            "calendar invite notes/instructions": "appears_to_contain_calendar_invite_notes",
        }
        for label, flag in field_category_checks.items():
            if not any(item.get(flag) for item in custom_field_map):
                missing_field_categories.append(label)
        human_review_items = sum(len(item.get("unclear_fields_needing_human_review", [])) for item in episode_items)

        summary_lines.extend(
            [
                f"## {show_name}",
                "",
                "- Discovery status: succeeded",
                f"- Client: {client_name}",
                f"- Env var: `{show_config['env_var']}`",
                f"- Location env var: `{show_config['location_env_var']}`",
                f"- HighLevel profile: `{profile['name']}`",
                f"- Location verified: {'yes' if location_verified else 'no'}",
                f"- Calendar verified: {'yes' if matched_calendar else 'no'}",
                f"- Selected calendar: {selected_calendar_public.get('calendar_name') or 'none'}",
                f"- Selected calendar ID: {selected_calendar_public.get('calendar_id') or 'none'}",
                f"- Calendar selection reason: {calendar_selection.get('selected_reason')}",
                f"- Discovery confidence: {calendar_selection.get('confidence')}",
                f"- Alternate calendars considered: {len(calendar_selection.get('candidate_calendars', []))}",
                f"- Calendar warnings: {'; '.join(calendar_selection.get('warnings', [])) if calendar_selection.get('warnings') else 'none'}",
                f"- Configuration mismatches: {'; '.join(calendar_selection.get('config_mismatches', [])) if calendar_selection.get('config_mismatches') else 'none'}",
                f"- Form verified: {'yes' if matched_form else 'no'}",
                f"- Appointment discovery succeeded: {'yes' if appointment_discovery_succeeded else 'no'}",
                f"- Appointments discovered: {len(appointment_items)}",
                f"- Form submissions discovered: {len(normalized_submissions)}",
                f"- Custom fields discovered: {len(custom_field_map)}",
                f"- Appointment/submission linking: {linking_status} ({exact_link_count} exact, {possible_link_count} possible)",
                f"- Multiple-guest support detected: {'yes' if multiple_guest_supported else 'no'}",
                f"- Calendar-relevant fields: {', '.join(calendar_relevant_fields[:12]) if calendar_relevant_fields else 'none detected'}",
                f"- Missing field categories: {', '.join(missing_field_categories) if missing_field_categories else 'none detected'}",
                f"- Human review items: {human_review_items}",
                f"- Contact sample size: {len(contact_items)}",
                "",
            ]
        )

    write_json(DISCOVERY_DIR / "highlevel_locations.json", locations_output)
    write_json(DISCOVERY_DIR / "highlevel_calendars.json", calendars_output)
    write_json(DISCOVERY_DIR / "highlevel_calendar_settings.json", calendar_settings_output)
    write_json(DISCOVERY_DIR / "highlevel_forms.json", forms_output)
    write_json(DISCOVERY_DIR / "highlevel_form_fields.json", form_fields_output)
    write_json(DISCOVERY_DIR / "highlevel_recent_submissions.json", submissions_output)
    write_json(DISCOVERY_DIR / "highlevel_appointments.json", appointments_output)
    write_json(DISCOVERY_DIR / "highlevel_contacts_sample.json", contacts_output)
    write_json(DISCOVERY_DIR / "highlevel_discovery_metadata.json", metadata_output)
    write_discovery_health_report(metadata_output)
    write_review_rows(DISCOVERY_DIR / "review_needed.csv", review_rows)
    (DISCOVERY_DIR / "discovery_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"\n✅ HighLevel discovery complete. Outputs written to {DISCOVERY_DIR}")

# ── Appointment Parser ───────────────────────────────────────
def parse_appointment(raw):
    """Parse a raw GHL event into a standardized appointment dict."""
    # Handle both raw GHL API format and our example JSON format
    if "appointment" in raw:
        raw = raw["appointment"]

    guest = raw.get("guest", raw.get("contact", {}))
    episode = raw.get("episode", {})
    start = raw.get("start_time", raw.get("startTime", ""))
    end = raw.get("end_time", raw.get("endTime", ""))
    description = raw.get("description", raw.get("calendar_description", ""))

    # Parse topics
    topics = raw.get("topics") or episode.get("topics") or []
    if not topics:
        for line in description.split("\n"):
            if line.strip().startswith(("1.", "2.", "3.", "•", "-")):
                topics.append(line.strip().lstrip("123.•- "))
    if not topics:
        topics = ["Topic 1", "Topic 2", "Topic 3"]

    first_name = guest.get("first_name", guest.get("firstName", ""))
    last_name = guest.get("last_name", guest.get("lastName", ""))
    show_name = raw.get("show_name", raw.get("calendar", "The David Daily Show"))
    title = (
        raw.get("episode_title")
        or episode.get("title")
        or raw.get("title", "").replace(f"{show_name} with ", "").strip()
    )
    date = raw.get("date", raw.get("event_date", start[:10] if start else ""))

    return {
        "guest_name": f"{first_name} {last_name}".strip() or raw.get("event_name", "Guest"),
        "guest_first_name": first_name,
        "guest_last_name": last_name,
        "guest_email": guest.get("email", ""),
        "guest_phone": guest.get("phone", ""),
        "guest_linkedin": guest.get("linkedin_url", guest.get("linkedinUrl", "")),
        "guest_linkedin_followers": guest.get("linkedin_followers", 0),
        "show_name": show_name,
        "episode_number": episode.get("number", raw.get("episode_number", "")),
        "episode_title": title,
        "date": date,
        "start_time": start,
        "end_time": end,
        "topics": topics[:4],
        "status": raw.get("status", "confirmed"),
        "location": raw.get("location", "StreamYard URL TBD"),
        "description": description,
        "calendar_description": raw.get("calendar_description", description),
        "signature": raw.get("signature", ""),
    }

# ── Asset Generators ─────────────────────────────────────────
def generate_banner_thumbnail(appointment, output_dir):
    """Generate a LinkedIn event banner using Pillow (no Canva needed)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  ⚠️ Pillow not installed. Run: pip3 install Pillow")
        return None

    show_name = appointment.get("show_name", "The David Daily Show")
    guest_name = appointment.get("guest_name", "Guest")
    episode_title = appointment.get("episode_title", "")
    date_str = appointment.get("date", "")
    topics = appointment.get("topics", [])

    # LinkedIn event banner: 1920×1080
    img = Image.new("RGB", (1920, 1080), color=(13, 27, 62))
    draw = ImageDraw.Draw(img)

    # Gold accent bar at top
    draw.rectangle([0, 0, 1920, 8], fill=(245, 166, 35))

    # Gold accent bar at bottom
    draw.rectangle([0, 1072, 1920, 1080], fill=(245, 166, 35))

    # Try to load fonts, fall back to default
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
        name_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        topic_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except (OSError, IOError):
        title_font = ImageFont.load_default()
        name_font = ImageFont.load_default()
        topic_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Show name (top area)
    draw.text((100, 60), show_name.upper(), fill=(245, 166, 35), font=title_font)

    # Episode title
    draw.text((100, 200), episode_title, fill=(255, 255, 255), font=name_font)

    # Guest name
    draw.text((100, 320), f"with {guest_name}", fill=(245, 166, 35), font=name_font)

    # Date
    draw.text((100, 440), date_str, fill=(138, 155, 181), font=small_font)

    # Topics
    y = 520
    for i, topic in enumerate(topics):
        draw.text((120, y + i * 55), f"• {topic}", fill=(245, 255, 255), font=topic_font)

    # Brand mark (bottom right)
    draw.text((1500, 980), "gotech.ai", fill=(138, 155, 181), font=small_font)

    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "banner.png"
    img.save(str(output_path), "PNG")
    print(f"  ✅ Banner saved: {output_path}")
    return str(output_path)

def generate_ical_event(appointment, output_dir):
    """Generate a .ics calendar event."""
    try:
        from icalendar import Calendar, Event, vText, vDatetime
    except ImportError:
        print("  ⚠️ icalendar not installed. Run: pip3 install icalendar")
        return None

    cal = Calendar()
    cal.add("prodid", "-//Go Technology Solutions//Show Launch//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    event = Event()
    event.add("summary", f"{appointment['show_name']} with {appointment['guest_name']}")
    event.add("description", (
        f"Thank you for submitting your topics. We will format them to fit the show "
        f"and then email them before updating this calendar description.\n\n"
        f"Guest: {appointment['guest_name']}\n"
        f"LinkedIn: {appointment.get('guest_linkedin', '')}\n"
        f"Logistics: Login 15 minutes early. Go live at {appointment.get('start_time', '')}.\n\n"
        f"Original booking submission:\n{appointment.get('calendar_description', '')}"
    ))
    event.add("location", vText("StreamYard URL TBD"))
    event.add("status", "CONFIRMED")

    # Parse date/time
    date_str = appointment.get("date", "")
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            event.add("dtstart", dt.replace(hour=10, minute=45))
            event.add("dtend", dt.replace(hour=12, minute=0))
        except ValueError:
            pass

    event["uid"] = f"{appointment.get('guest_last_name', 'guest').lower()}-{date_str}@reveting.com"
    cal.add_component(event)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "episode.ics"
    with open(output_path, "wb") as f:
        f.write(cal.to_ical())
    print(f"  ✅ Calendar event saved: {output_path}")
    return str(output_path)

def generate_email_sequence(appointment, output_dir):
    """Generate the SOP guest email cadence with known variables filled."""
    emails = {}
    first_name = appointment.get("guest_first_name") or appointment.get("guest_name", "there")
    show_name = appointment.get("show_name", "[SHOW_NAME]")
    date = appointment.get("date", "[EPISODE_DATE]")
    start_time = appointment.get("start_time", "[GOLIVE_TIME_ET/CT/PT]")
    title = appointment.get("episode_title") or "[EPISODE_TITLE]"
    topics = appointment.get("topics", [])
    topics_list = "\n".join(f"{i+1}. {topic}" for i, topic in enumerate(topics))
    topics_block = topics_list or "1. [TOPIC_1]\n2. [TOPIC_2]\n3. [TOPIC_3]"
    signature = appointment.get("signature") or "[SIGNATURE_BLOCK]"

    emails["01-t14-activation"] = (
        f"Subject: Your {show_name} appearance is coming up\n\n"
        f"Hi {first_name},\n\n"
        f"We're excited to have you on {show_name} on {date}.\n\n"
        f"Because this is a live LinkedIn broadcast, the best conversations happen "
        f"when both sides bring their audience into the room.\n\n"
        f"Please share a LinkedIn post, invite a few people directly to join live, "
        f"and be ready to engage in the comments. If anything comes up, please give "
        f"as much notice as possible, ideally 3+ weeks.\n\n"
        f"Looking forward to a great conversation.\n\n"
        f"{signature}"
    )

    emails["02-event-published"] = (
        f"Subject: Your {show_name} Appearance Details\n\n"
        f"Hi {first_name},\n\n"
        f"Thank you for booking the {date} episode of {show_name}. "
        f"We're anticipating a great discussion.\n\n"
        f"Event title:\n{title}\n\n"
        f"Topics:\n{topics_block}\n\n"
        f"Show Details:\n"
        f"Please join the StreamYard link at [PRESHOW_TIME_ET/CT/PT] for a pre-show tech check. "
        f"We go live at {start_time}. Join link: [STREAMYARD_GUEST_LINK].\n\n"
        f"PROMOTE:\n"
        f"LinkedIn: [LINKEDIN_EVENT_URL]\n"
        f"Facebook: [FACEBOOK_EVENT_URL]\n"
        f"YouTube: [YOUTUBE_EVENT_URL]\n"
        f"Twitch: [TWITCH_EVENT_URL]\n"
        f"Instagram: [INSTAGRAM_CHANNEL_URL]\n\n"
        f"LinkedIn event invites drive real engagement. Please use the walkthrough link "
        f"and remember LinkedIn allows 1,000 invites per week.\n\n"
        f"{signature}"
    )

    emails["03-one-week"] = (
        f"Subject: Your {show_name} livestream is coming up\n\n"
        f"Hey {first_name},\n\n"
        f"We're about a week away from your {show_name} livestream and podcast "
        f"appearance on {date}.\n\n"
        f"Please join us for pre-show at [PRESHOW_TIME_ET/CT/PT]. "
        f"The show goes live at {start_time}.\n\n"
        f"Right now is a great time to invite your audience on LinkedIn. "
        f"Here is the event link: [LINKEDIN_EVENT_URL].\n\n"
        f"{signature}"
    )

    emails["04-day-before"] = (
        f"Subject: Your Appearance Tomorrow on {show_name}\n\n"
        f"Hi {first_name},\n\n"
        f"We're looking forward to having you on {show_name} tomorrow. "
        f"Here is everything you need:\n\n"
        f"- Pre-show tech check: [PRESHOW_TIME_ET/CT/PT]\n"
        f"- We go live: {start_time}\n"
        f"- StreamYard link: [STREAMYARD_GUEST_LINK]\n\n"
        f"During pre-show, we'll check camera, mic, lighting, and help you connect "
        f"your social channels if you'd like to livestream to your audience.\n\n"
        f"Please bring a good mic or headphones, decent lighting, and optional social "
        f"media credentials. If you have not already, today is a great time to send "
        f"LinkedIn event invites.\n\n"
        f"{signature}"
    )

    emails["05-day-of"] = (
        f"Subject: You're live today on {show_name}\n\n"
        f"Hi {first_name},\n\n"
        f"We're going live today for your {show_name} appearance. Join us here:\n\n"
        f"[STREAMYARD_GUEST_LINK]\n\n"
        f"Timing:\n"
        f"- Pre-show tech check: [PRESHOW_TIME_ET/CT/PT]\n"
        f"- We go live: {start_time}\n\n"
        f"Please join right at pre-show time so we can get you set up comfortably.\n\n"
        f"{signature}"
    )

    emails["06-postshow-one-hour"] = (
        f"Subject: Your first {show_name} clip and recording files\n\n"
        f"Hi {first_name},\n\n"
        f"That conversation was strong, and now you have a video clip ready to post.\n\n"
        f"Find the following in the Google Drive link below:\n"
        f"- AI-generated highlight clip\n"
        f"- Full episode recording\n"
        f"- Full transcript\n"
        f"- Organized episode files\n\n"
        f"[AI_CLIPS_DRIVE_LINK]\n\n"
        f"Right now is the best window to share while it is fresh. If you post the clip "
        f"and tag us, we'll support it on our end.\n\n"
        f"{signature}"
    )

    emails["07-postproduction-24-36h"] = (
        f"Subject: Your {show_name} Episode Assets Are Ready\n\n"
        f"Hi {first_name},\n\n"
        f"Thank you again for coming on {show_name}. Your episode is officially live "
        f"on the podcast platforms and your post-production assets are ready.\n\n"
        f"{title}\n"
        f"{show_name}\n\n"
        f"Listen here:\n"
        f"Spotify: [SPOTIFY_EPISODE_LINK]\n"
        f"Apple Podcasts: [APPLE_EPISODE_LINK]\n\n"
        f"Video clips and files: [HUMAN_EDITED_CLIPS_LINK]\n\n"
        f"You can continue promoting the full episode and replays here:\n"
        f"- LinkedIn: [LINKEDIN_EVENT_URL]\n"
        f"- YouTube: [YOUTUBE_EVENT_URL]\n"
        f"- Other active channels: [OTHER_REPLAY_LINKS]\n\n"
        f"{signature}"
    )

    # Save all emails
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in emails.items():
        path = output_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        print(f"  ✅ Email saved: {path}")

    return emails

# ── Main Pipeline ────────────────────────────────────────────
def launch_show(appointment, dry_run=True):
    """Run the full show launch pipeline."""
    guest_name = appointment.get("guest_name", "Guest")
    show_name = appointment.get("show_name", "The David Daily Show")
    date_str = appointment.get("date", "unknown")

    print(f"\n{'='*60}")
    print(f"  SHOW LAUNCH: {show_name}")
    print(f"  Guest: {guest_name}")
    print(f"  Date: {date_str}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"{'='*60}")

    safe_name = guest_name.lower().replace(" ", "-")
    output_dir = REPO_ROOT / "assets" / safe_name

    if dry_run:
        print(f"\n  📋 Would generate:")
        print(f"     • Banner image → {output_dir}/banner.png")
        print(f"     • Calendar event → {output_dir}/episode.ics")
        print(f"     • Email sequence → {output_dir}/emails/ (7 SOP emails)")
        print(f"     • PPTX deck → {output_dir}/episode.pptx")
        print(f"\n  ℹ️  Run with --execute to actually generate assets")
        return

    # Step 1: Banner
    print(f"\n  🎨 Generating banner...")
    generate_banner_thumbnail(appointment, output_dir)

    # Step 2: Calendar event
    print(f"\n  📅 Generating calendar event...")
    generate_ical_event(appointment, output_dir)

    # Step 3: Email sequence
    print(f"\n  📧 Generating email sequence...")
    generate_email_sequence(appointment, output_dir / "emails")

    # Step 4: PPTX
    print(f"\n  📊 Generating PPTX deck...")
    print(f"     Run: python3 presentations/reveting-show-flow.py --guest \"{guest_name}\"")

    print(f"\n  ✅ All assets generated in: {output_dir}")

# ── CLI ──────────────────────────────────────────────────────
def main():
    load_project_env()
    parser = argparse.ArgumentParser(description="Show Launch Automation")
    parser.add_argument("--input", "-i", help="Path to GHL appointment JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no changes")
    parser.add_argument("--execute", action="store_true", help="Actually generate assets")
    parser.add_argument("--discover-highlevel", action="store_true", help="Run HighLevel discovery for all configured sub-accounts")
    parser.add_argument("--test-highlevel-auth", action="store_true", help="Verify which HighLevel endpoint works for a configured private integration token")
    parser.add_argument("--validate-discovery", action="store_true", help="Validate HighLevel discovery configuration and calendar selection evidence")
    parser.add_argument("--ghl-pull", action="store_true", help="Pull appointments from GHL API")
    parser.add_argument("--show-key", choices=sorted(SHOW_CONFIG_BY_KEY.keys()), help="Limit GHL pull to a single configured show")
    parser.add_argument("--days-back", type=int, default=DEFAULT_DISCOVERY_LOOKBACK_DAYS, help="How many days back to use for discovery")
    parser.add_argument("--days-ahead", type=int, default=90, help="How many days ahead to pull")
    args = parser.parse_args()

    dry_run = not args.execute

    try:
        if args.test_highlevel_auth:
            if not args.show_key:
                raise RuntimeError("--test-highlevel-auth requires --show-key.")
            show_config = SHOW_CONFIG_BY_KEY[args.show_key]
            token = require_highlevel_tokens([show_config])[show_config["key"]]
            test_highlevel_auth(show_config, token, verbose=True)
            return
        if args.discover_highlevel:
            discover_highlevel(days_back=args.days_back, days_ahead=args.days_ahead, show_key=args.show_key)
            return
        if args.validate_discovery:
            validate_discovery(show_key=args.show_key, days_ahead=args.days_ahead)
            return
        if args.ghl_pull:
            selected_configs = [SHOW_CONFIG_BY_KEY[args.show_key]] if args.show_key else SHOW_HIGHLEVEL_CONFIGS
            tokens = require_highlevel_tokens(selected_configs)
            start_date, end_date = iso_range(days_back=0, days_ahead=args.days_ahead)

            any_events = False
            for show_config in selected_configs:
                events, _ = pull_appointments(show_config, tokens[show_config["key"]], start_date=start_date, end_date=end_date)
                for evt in events:
                    evt.setdefault("show_name", show_config["show_name"])
                    appt = parse_appointment(evt.get("raw_payload", evt))
                    launch_show(appt, dry_run=dry_run)
                any_events = any_events or bool(events)

            if not any_events:
                print("  No appointments found.")
            return
        if args.input:
            input_path = Path(args.input)
            if not input_path.exists():
                print(f"  ❌ File not found: {input_path}")
                sys.exit(1)
            with open(input_path) as f:
                data = json.load(f)
            appointment = parse_appointment(data)
            launch_show(appointment, dry_run=dry_run)
            return

        # Default: use the Daniel Burrus example
        example_path = EXAMPLES_DIR / "appointments" / "daniel-burrus.json"
        if example_path.exists():
            with open(example_path) as f:
                data = json.load(f)
            appointment = parse_appointment(data)
            launch_show(appointment, dry_run=dry_run)
        else:
            print("  ❌ No input file specified. Use --input, --ghl-pull, or --discover-highlevel")
            sys.exit(1)
    except RuntimeError as exc:
        log_error(f"  ❌ {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
