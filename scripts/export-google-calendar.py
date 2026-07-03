#!/usr/bin/env python3
"""
Read-only Google Calendar exporter for Reveting operations audits.

Exports upcoming events from ww@reveting.com into data/calendar/ww_reveting_events.json.
This script only uses Google Calendar read APIs.
"""

import argparse
import json
import os
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
DOTENV_PATH = REPO_ROOT / ".env"
DEFAULT_CALENDAR_ID = "ww@reveting.com"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "calendar" / "ww_reveting_events.json"
DEFAULT_OAUTH_CLIENT_PATH = REPO_ROOT / "secrets" / "google-calendar-oauth-client.json"
DEFAULT_OAUTH_TOKEN_PATH = REPO_ROOT / "secrets" / "google-calendar-token.json"
DEFAULT_DAYS_AHEAD = 180
READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
AUTH_MODES = ("auto", "oauth", "service-account")

warnings.filterwarnings(
    "ignore",
    message=r"You are using a Python version .* past its end of life\.",
    category=FutureWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+",
)


def load_project_env():
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError(
            "python-dotenv is required. Install dependencies with: pip install -r requirements.txt"
        ) from exc
    load_dotenv(dotenv_path=DOTENV_PATH, override=False)


def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RuntimeError(f"Could not parse datetime: {value}") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def iso_utc(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_repo_path(value, default=None):
    text = str(value or "").strip()
    if not text:
        if default is None:
            return None
        path = Path(default)
    else:
        path = Path(text).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def event_datetime(value):
    if isinstance(value, dict):
        return value.get("dateTime") or value.get("date")
    return value


def attendee_emails(event):
    emails = []
    for attendee in event.get("attendees") or []:
        email = attendee.get("email") if isinstance(attendee, dict) else None
        if email:
            emails.append(email.strip().lower())
    return sorted(set(emails))


def conference_link(event):
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    conference_data = event.get("conferenceData") or {}
    for entry_point in conference_data.get("entryPoints") or []:
        uri = entry_point.get("uri")
        if uri:
            return uri
    return None


def normalize_event(event, calendar_id):
    return {
        "id": event.get("id"),
        "event_id": event.get("id"),
        "calendar_id": calendar_id,
        "summary": event.get("summary"),
        "title": event.get("summary"),
        "start": event_datetime(event.get("start")),
        "end": event_datetime(event.get("end")),
        "attendees": event.get("attendees") or [],
        "attendee_emails": attendee_emails(event),
        "organizer": event.get("organizer"),
        "creator": event.get("creator"),
        "description": event.get("description"),
        "location": event.get("location"),
        "meeting_link": conference_link(event),
        "hangout_link": event.get("hangoutLink"),
        "conference_data": event.get("conferenceData"),
        "html_link": event.get("htmlLink"),
        "url": event.get("htmlLink"),
        "status": event.get("status"),
        "recurring_event_id": event.get("recurringEventId"),
        "original_start_time": event_datetime(event.get("originalStartTime")),
        "raw_event_payload": event,
    }


def flatten_calendar_payload(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("items", "events", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def service_account_credentials():
    credentials_path = resolve_repo_path(os.environ.get("GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON"))
    delegated_user = os.environ.get("GOOGLE_CALENDAR_DELEGATED_USER", "").strip()
    if not credentials_path:
        raise RuntimeError(
            "GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON is required for API export. "
            "Set it to a service account JSON key path in your local .env, or use a manual Google Calendar JSON export."
        )
    if not credentials_path.exists():
        raise RuntimeError(f"Google Calendar service account JSON was not found: {credentials_path}")
    try:
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError(
            "google-auth is required for Google Calendar export. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=[READONLY_SCOPE],
    )
    if delegated_user:
        credentials = credentials.with_subject(delegated_user)
    return credentials


def oauth_credentials():
    client_path = resolve_repo_path(
        os.environ.get("GOOGLE_CALENDAR_OAUTH_CLIENT_JSON"),
        default=DEFAULT_OAUTH_CLIENT_PATH,
    )
    token_path = resolve_repo_path(
        os.environ.get("GOOGLE_CALENDAR_OAUTH_TOKEN_JSON"),
        default=DEFAULT_OAUTH_TOKEN_PATH,
    )
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "OAuth export requires google-auth-oauthlib. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    credentials = None
    if token_path.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(token_path), [READONLY_SCOPE])
        except ValueError:
            credentials = None
    if credentials and not credentials.has_scopes([READONLY_SCOPE]):
        credentials = None

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception:
            credentials = None

    if not credentials or not credentials.valid:
        if not client_path.exists():
            raise RuntimeError(
                "Google Calendar OAuth client JSON was not found: "
                f"{client_path}. Create an OAuth Desktop app credential in Google Cloud, "
                "download the JSON, and save it at that path."
            )
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_path), [READONLY_SCOPE])
            credentials = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
            )
        except ValueError as exc:
            raise RuntimeError(
                "Could not load the OAuth client JSON. Make sure it is an OAuth client for a Desktop app, "
                "not an API key or service-account key."
            ) from exc

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json() + "\n", encoding="utf-8")
    return credentials


def effective_auth_mode(auth_mode):
    mode = (auth_mode or os.environ.get("GOOGLE_CALENDAR_AUTH_MODE") or "auto").strip().lower()
    if mode not in AUTH_MODES:
        raise RuntimeError(f"Unsupported GOOGLE_CALENDAR_AUTH_MODE: {mode}. Use one of: {', '.join(AUTH_MODES)}")
    if mode == "auto":
        if os.environ.get("GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON", "").strip():
            return "service-account"
        return "oauth"
    return mode


def google_calendar_credentials(auth_mode):
    mode = effective_auth_mode(auth_mode)
    if mode == "service-account":
        return service_account_credentials(), mode
    return oauth_credentials(), mode


def calendar_service(auth_mode):
    credentials, mode = google_calendar_credentials(auth_mode)
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "google-api-python-client is required for Google Calendar export. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc
    return build("calendar", "v3", credentials=credentials, cache_discovery=False), mode


def export_events(calendar_id, time_min, time_max, auth_mode):
    service, mode = calendar_service(auth_mode)
    events = []
    page_token = None
    while True:
        response = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=2500,
                pageToken=page_token,
                showDeleted=False,
            )
            .execute()
        )
        events.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return events, mode


def write_export(path, calendar_id, time_min, time_max, raw_events):
    normalized_events = [normalize_event(event, calendar_id) for event in raw_events]
    payload = {
        "calendar_id": calendar_id,
        "exported_at": iso_utc(datetime.now(timezone.utc)),
        "time_min": time_min,
        "time_max": time_max,
        "event_count": len(normalized_events),
        "events": normalized_events,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def main():
    load_project_env()
    parser = argparse.ArgumentParser(description="Export ww@reveting.com Google Calendar events for read-only audit")
    parser.add_argument("--calendar-id", default=os.environ.get("GOOGLE_CALENDAR_ID", DEFAULT_CALENDAR_ID))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--input", help="Normalize a manually exported Google Calendar API JSON response instead of calling the API")
    parser.add_argument("--time-min", help="RFC3339 start timestamp. Defaults to now.")
    parser.add_argument("--time-max", help="RFC3339 end timestamp. Defaults to --days-ahead from now.")
    parser.add_argument("--days-ahead", type=int, default=int(os.environ.get("GOOGLE_CALENDAR_EXPORT_DAYS_AHEAD", DEFAULT_DAYS_AHEAD)))
    parser.add_argument(
        "--auth-mode",
        choices=AUTH_MODES,
        default=os.environ.get("GOOGLE_CALENDAR_AUTH_MODE", "auto"),
        help="Google Calendar auth mode for API export. Defaults to auto: service account if configured, otherwise OAuth Desktop.",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    time_min = iso_utc(parse_datetime(args.time_min) if args.time_min else now)
    time_max = iso_utc(parse_datetime(args.time_max) if args.time_max else now + timedelta(days=args.days_ahead))
    mode = "manual-input"
    try:
        if args.input:
            input_payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
            raw_events = flatten_calendar_payload(input_payload)
        else:
            raw_events, mode = export_events(args.calendar_id, time_min, time_max, args.auth_mode)
        payload = write_export(Path(args.output), args.calendar_id, time_min, time_max, raw_events)
    except RuntimeError as exc:
        print(f"Google Calendar export failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Google Calendar export complete.")
    print(f"  Calendar: {args.calendar_id}")
    print(f"  Range: {time_min} to {time_max}")
    print(f"  Events exported: {payload['event_count']}")
    print(f"  Output: {Path(args.output)}")
    print(f"  Auth mode: {mode}")
    print("  Mode: read-only; no Google Calendar events were modified.")


if __name__ == "__main__":
    main()
