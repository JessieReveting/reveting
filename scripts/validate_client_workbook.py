#!/usr/bin/env python3
"""
Validate a client operating-system folder before workbook sync.

Example:
  python3 scripts/validate_client_workbook.py --client ridgeback-network-defense
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True, help="Client slug under clients/")
    return parser.parse_args()


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def fail(message: str) -> None:
    raise SystemExit(message)


def validate_status(value: str, allowed: set[str], field_name: str, source: str) -> None:
    if value not in allowed:
        fail(f"{source}: invalid {field_name!r} value {value!r}. Allowed: {sorted(allowed)}")


def main() -> None:
    args = parse_args()
    root = CLIENTS_DIR / args.client
    manifest_path = root / "automation" / "workbook-manifest.yaml"
    content_path = root / "automation" / "workbook-content.yaml"
    episodes_dir = root / "episodes"
    if not manifest_path.exists() or not content_path.exists() or not episodes_dir.exists():
        fail("Client folder is missing required automation or episode files.")

    manifest = load_yaml(manifest_path)
    workbook_content = load_yaml(content_path)
    if manifest["client"]["slug"] != args.client:
        fail("Manifest client slug does not match --client.")

    dropdowns = manifest["workbook"]["status_dropdowns"]
    content_status = set(dropdowns["content_status"])
    repurposing_status = set(dropdowns["repurposing_status"])
    episode_status = set(dropdowns["episode_status"])

    rows = workbook_content["social_schedule_tab"]["rows"]
    for index, row in enumerate(rows, start=1):
        source = f"social_schedule_tab.rows[{index}]"
        validate_status(row["draft_status"], content_status, "draft_status", source)
        if row["approval_status"] not in content_status and row["approval_status"] != "Not Started":
            fail(f"{source}: approval_status must be 'Not Started' or a content status value.")
        validate_status(row["repurposing_status"], repurposing_status, "repurposing_status", source)

    episode_files = sorted(episodes_dir.glob("episode-*/episode.yaml"))
    if not episode_files:
        fail("No episode YAML files found.")
    for path in episode_files:
        episode = load_yaml(path)
        required_fields = ["episode_number", "recording_date", "working_title", "hosts", "published", "status"]
        missing = [field for field in required_fields if field not in episode]
        if missing:
            fail(f"{path}: missing fields {missing}")
        if not episode.get("hosts"):
            fail(f"{path}: hosts list cannot be empty.")
        validate_status(episode["status"]["episode_status"], episode_status, "episode_status", str(path))
        validate_status(episode["status"]["repurposing_status"], repurposing_status, "repurposing_status", str(path))

    print(f"Validated client workbook inputs for {args.client}.")
    print(f"- Episode files: {len(episode_files)}")
    print(f"- Social schedule rows: {len(rows)}")
    print(f"- Spreadsheet ID: {manifest['workbook']['spreadsheet_id']}")


if __name__ == "__main__":
    main()
