#!/usr/bin/env python3
"""
Build or apply Google Sheets updates from a client operating-system folder.

Examples:
  python3 scripts/sync_client_workbook.py --client ridgeback-network-defense --preview
  python3 scripts/sync_client_workbook.py --client ridgeback-network-defense --write --service-account /path/to/key.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build


REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass
class ClientPaths:
    root: Path
    manifest: Path
    workbook_content: Path
    episodes_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True, help="Client slug under clients/")
    parser.add_argument("--preview", action="store_true", help="Print the generated workbook payload.")
    parser.add_argument("--write", action="store_true", help="Apply the generated payload to Google Sheets.")
    parser.add_argument("--service-account", help="Path to a Google service-account JSON key.")
    parser.add_argument("--output-json", help="Optional path for the generated payload.")
    args = parser.parse_args()
    if not args.preview and not args.write:
        args.preview = True
    return args


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def client_paths(client_slug: str) -> ClientPaths:
    root = CLIENTS_DIR / client_slug
    return ClientPaths(
        root=root,
        manifest=root / "automation" / "workbook-manifest.yaml",
        workbook_content=root / "automation" / "workbook-content.yaml",
        episodes_dir=root / "episodes",
    )


def require_paths(paths: ClientPaths) -> None:
    required = [paths.root, paths.manifest, paths.workbook_content, paths.episodes_dir]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Missing required client files:\n- " + "\n- ".join(missing))


def load_episode_records(episodes_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(episodes_dir.glob("episode-*/episode.yaml")):
        payload = load_yaml(path)
        payload["_source_path"] = str(path)
        records.append(payload)
    return sorted(records, key=lambda item: int(item["episode_number"]))


def to_multiline(items: list[str]) -> str:
    return "\n".join(items)


def date_formula(iso_date: str) -> str:
    year, month, day = iso_date.split("-")
    return f"=DATE({year},{int(month)},{int(day)})"


def build_event_row(episode: dict[str, Any]) -> list[Any]:
    links = episode.get("links") or {}
    guests = episode.get("guests") or []
    guest_name = "pending" if not guests else ", ".join(guest.get("name", "") for guest in guests)
    guest_linkedin = "pending" if not guests else ", ".join(
        guest.get("linkedin_url", "") for guest in guests if guest.get("linkedin_url")
    )
    return [
        "",
        date_formula(str(episode["recording_date"])),
        int(episode["episode_number"]),
        episode["working_title"],
        to_multiline([f"{index}. {topic}" for index, topic in enumerate(episode.get("public_topics") or [], start=1)])
        + "\n4. Breaking Threat Brief: "
        + str(((episode.get("breaking_threat_brief") or {}).get("prompt")) or ""),
        ", ".join(episode.get("hosts") or []),
        guest_name,
        guest_linkedin,
        bool(episode["published"]),
        links.get("event", ""),
        "",
        links.get("spotify", ""),
        links.get("full_download", ""),
        links.get("streamyard", ""),
    ]


def build_ridgeback_rows(workbook_content: dict[str, Any]) -> list[list[Any]]:
    tab = workbook_content["ridgeback_tab"]
    rows: list[list[Any]] = [[tab["title"]], ["Section", "Details"]]
    for section in tab.get("sections") or []:
        rows.append([section["section"], section["details"]])
    rows.append(["Content Pillar", "Purpose", "Core Audience", "Sample Topics", "Appropriate CTA", "Potential Content Formats"])
    for pillar in tab.get("content_pillars") or []:
        rows.append(
            [
                pillar["pillar"],
                pillar["purpose"],
                pillar["core_audience"],
                to_multiline(pillar.get("sample_topics") or []),
                pillar["cta"],
                to_multiline(pillar.get("formats") or []),
            ]
        )
    return rows


def build_social_rows(workbook_content: dict[str, Any]) -> list[list[Any]]:
    tab = workbook_content["social_schedule_tab"]
    rows: list[list[Any]] = [
        [tab["title"]],
        ["Workbook Purpose", tab["workbook_purpose"]],
        [],
        [
            "Day",
            "Content Slot",
            "Goal",
            "Focus",
            "Suggested Formats",
            "Content Pillar",
            "Platform",
            "Owner",
            "Asset Needed",
            "Draft Status",
            "Approval Status",
            "Scheduled Date",
            "Published Link",
            "Repurposing Status",
        ],
    ]
    for row in tab.get("rows") or []:
        rows.append(
            [
                row["day"],
                row["content_slot"],
                row["goal"],
                row["focus"],
                to_multiline(row.get("suggested_formats") or []),
                row["content_pillar"],
                row["platform"],
                row["owner"],
                row["asset_needed"],
                row["draft_status"],
                row["approval_status"],
                row["scheduled_date"],
                row["published_link"],
                row["repurposing_status"],
            ]
        )
    rows.extend([[], ["Event Publishing Strategy"], ["Rule", "Guidance"]])
    for record in tab.get("event_publishing_strategy") or []:
        rows.append([record["rule"], record["guidance"]])
    rows.extend([[], ["Status Standards"]])
    for label, values in (tab.get("status_standards") or {}).items():
        rows.append([label.replace("_", " ").title(), to_multiline(values)])
    return rows


def build_payload(manifest: dict[str, Any], workbook_content: dict[str, Any], episodes: list[dict[str, Any]]) -> dict[str, Any]:
    tabs = {tab["purpose"]: tab for tab in manifest["workbook"]["tabs"]}
    return {
        "spreadsheet_id": manifest["workbook"]["spreadsheet_id"],
        "event_details": {
            "sheet_name": "Event Details ",
            "rows": [build_event_row(episode) for episode in episodes],
        },
        "ridgeback": {
            "sheet_name": "Ridgeback",
            "clear_range": "A1:F120",
            "rows": build_ridgeback_rows(workbook_content),
        },
        "social_schedule": {
            "sheet_name": "Social Schedule",
            "clear_range": "A1:N160",
            "rows": build_social_rows(workbook_content),
        },
    }


def get_service(service_account_path: str):
    credentials = service_account.Credentials.from_service_account_file(service_account_path, scopes=SCOPES)
    return build("sheets", "v4", credentials=credentials)


def existing_event_rows(service, spreadsheet_id: str, sheet_name: str) -> dict[int, int]:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A2:N1000", valueRenderOption="UNFORMATTED_VALUE")
        .execute()
    )
    mapping: dict[int, int] = {}
    rows = result.get("values", [])
    for offset, row in enumerate(rows, start=2):
        if len(row) < 3:
            continue
        value = row[2]
        try:
            mapping[int(value)] = offset
        except (TypeError, ValueError):
            continue
    return mapping


def update_tab_block(service, spreadsheet_id: str, sheet_name: str, clear_range: str, rows: list[list[Any]]) -> None:
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!{clear_range}",
        body={},
    ).execute()
    end_column = chr(ord("A") + max(len(row) for row in rows) - 1)
    end_row = len(rows)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1:{end_column}{end_row}",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()


def update_event_rows(service, spreadsheet_id: str, rows: list[list[Any]]) -> list[dict[str, Any]]:
    sheet_name = "Event Details "
    mapping = existing_event_rows(service, spreadsheet_id, sheet_name)
    last_row = max(mapping.values(), default=1)
    operations: list[dict[str, Any]] = []
    for row in rows:
        episode_number = int(row[2])
        target_row = mapping.get(episode_number)
        if target_row is None:
            last_row += 1
            target_row = last_row
        range_name = f"'{sheet_name}'!A{target_row}:N{target_row}"
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
        operations.append({"episode_number": episode_number, "range": range_name})
    return operations


def write_payload(payload: dict[str, Any], service_account_path: str) -> dict[str, Any]:
    service = get_service(service_account_path)
    spreadsheet_id = payload["spreadsheet_id"]
    update_tab_block(service, spreadsheet_id, payload["ridgeback"]["sheet_name"], payload["ridgeback"]["clear_range"], payload["ridgeback"]["rows"])
    update_tab_block(
        service,
        spreadsheet_id,
        payload["social_schedule"]["sheet_name"],
        payload["social_schedule"]["clear_range"],
        payload["social_schedule"]["rows"],
    )
    event_ops = update_event_rows(service, spreadsheet_id, payload["event_details"]["rows"])
    return {"spreadsheet_id": spreadsheet_id, "event_updates": event_ops}


def main() -> None:
    args = parse_args()
    paths = client_paths(args.client)
    require_paths(paths)
    manifest = load_yaml(paths.manifest)
    workbook_content = load_yaml(paths.workbook_content)
    episodes = load_episode_records(paths.episodes_dir)
    payload = build_payload(manifest, workbook_content, episodes)
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.preview:
        print(json.dumps(payload, indent=2))
    if args.write:
        if not args.service_account:
            raise SystemExit("--write requires --service-account")
        result = write_payload(payload, args.service_account)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
