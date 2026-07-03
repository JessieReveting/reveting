#!/usr/bin/env python3
"""
Minimal HighLevel private-token smoke test.

Uses one documented endpoint exactly as shown in HighLevel's official docs:
POST /contacts/search
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent.parent
DOTENV_PATH = REPO_ROOT / ".env"
API_BASE = "https://services.leadconnectorhq.com"
API_VERSION = "2021-04-15"

SHOW_ENV_MAP = {
    "cherry-willow": (
        "HIGHLEVEL_TOKEN_CHERRY_WILLOW",
        "HIGHLEVEL_LOCATION_ID_CHERRY_WILLOW",
    ),
    "david-daily": (
        "HIGHLEVEL_TOKEN_DAVID_DAILY",
        "HIGHLEVEL_LOCATION_ID_DAVID_DAILY",
    ),
    "beyond-the-cart": (
        "HIGHLEVEL_TOKEN_BEYOND_THE_CART",
        "HIGHLEVEL_LOCATION_ID_BEYOND_THE_CART",
    ),
    "deconstructing-data": (
        "HIGHLEVEL_TOKEN_DECONSTRUCTING_DATA",
        "HIGHLEVEL_LOCATION_ID_DECONSTRUCTING_DATA",
    ),
    "winsday": (
        "HIGHLEVEL_TOKEN_WINSDAY",
        "HIGHLEVEL_LOCATION_ID_WINSDAY",
    ),
}


def redact_known_secrets(text, secrets):
    value = str(text)
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return value


def curl_request(url, *, headers, json_body, timeout=30):
    config_lines = [
        "silent",
        "show-error",
        'request = "POST"',
        f"url = {json.dumps(url)}",
        f"max-time = {timeout}",
        'write-out = "\\n%{http_code}"',
    ]
    for key, value in headers.items():
        config_lines.append(f"header = {json.dumps(f'{key}: {value}')}")
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
    return int(status_text.strip()), body


def main():
    load_dotenv(dotenv_path=DOTENV_PATH, override=False)

    parser = argparse.ArgumentParser(description="Minimal HighLevel direct auth smoke test")
    parser.add_argument("--show-key", choices=sorted(SHOW_ENV_MAP.keys()), required=True)
    args = parser.parse_args()

    token_env_var, location_env_var = SHOW_ENV_MAP[args.show_key]
    token = os.environ.get(token_env_var, "").strip()
    location_id = os.environ.get(location_env_var, "").strip()

    if not token:
        print(f"Missing required environment variable: {token_env_var}", file=sys.stderr)
        sys.exit(1)
    if not location_id:
        print(f"Missing required environment variable: {location_env_var}", file=sys.stderr)
        sys.exit(1)

    url = f"{API_BASE}/contacts/search"
    body = {"locationId": location_id, "pageLimit": 1}
    headers = {
        "Authorization": f"Bearer {token}",
        "Version": API_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    secrets = [token]

    try:
        status_code, payload = curl_request(url, headers=headers, json_body=body)
        print(f"ENDPOINT={url}")
        print("METHOD=POST")
        print(f"STATUS={status_code}")
        print(f"REQUEST_BODY={json.dumps(body, ensure_ascii=True)}")
        print(f"RESPONSE_BODY={redact_known_secrets(payload[:1200], secrets)}")
    except Exception as exc:
        print(f"ENDPOINT={url}")
        print("METHOD=POST")
        print("STATUS=request-failed")
        print(f"REQUEST_BODY={json.dumps(body, ensure_ascii=True)}")
        print(f"RESPONSE_BODY={redact_known_secrets(exc, secrets)}")
        sys.exit(1)
    if not 200 <= status_code < 300:
        sys.exit(1)


if __name__ == "__main__":
    main()
