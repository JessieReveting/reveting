#!/usr/bin/env python3
"""
HighLevel relay service.

Run this in a deployed/server environment that can make supported outbound
requests to HighLevel. The desktop script calls this relay instead of calling
HighLevel directly.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

APP = FastAPI(title="Reveting HighLevel Relay")

SHOW_HIGHLEVEL_CONFIGS = {
    "cherry-willow": {
        "env_var": "HIGHLEVEL_TOKEN_CHERRY_WILLOW",
        "location_env_var": "HIGHLEVEL_LOCATION_ID_CHERRY_WILLOW",
    },
    "david-daily": {
        "env_var": "HIGHLEVEL_TOKEN_DAVID_DAILY",
        "location_env_var": "HIGHLEVEL_LOCATION_ID_DAVID_DAILY",
    },
    "beyond-the-cart": {
        "env_var": "HIGHLEVEL_TOKEN_BEYOND_THE_CART",
        "location_env_var": "HIGHLEVEL_LOCATION_ID_BEYOND_THE_CART",
    },
    "deconstructing-data": {
        "env_var": "HIGHLEVEL_TOKEN_DECONSTRUCTING_DATA",
        "location_env_var": "HIGHLEVEL_LOCATION_ID_DECONSTRUCTING_DATA",
    },
    "winsday": {
        "env_var": "HIGHLEVEL_TOKEN_WINSDAY",
        "location_env_var": "HIGHLEVEL_LOCATION_ID_WINSDAY",
    },
}

HIGHLEVEL_API_PROFILES = {
    "leadconnector-services": {
        "base_url": "https://services.leadconnectorhq.com",
        "default_headers": {
            "Version": "2021-07-28",
            "Accept": "application/json",
        },
        "auth_probes": [
            {"label": "location by id", "path": "/locations/{location_id}"},
            {"label": "contacts by location", "path": "/contacts/", "params": {"locationId": "{location_id}", "limit": 1}},
            {"label": "calendars by location", "path": "/calendars/", "params": {"locationId": "{location_id}"}},
            {"label": "forms by location", "path": "/forms/", "params": {"locationId": "{location_id}"}},
        ],
    },
    "gohighlevel-rest-v1": {
        "base_url": "https://rest.gohighlevel.com/v1",
        "default_headers": {
            "Accept": "application/json",
        },
        "auth_probes": [
            {"label": "location by id", "path": "/locations/{location_id}"},
            {"label": "contacts by location", "path": "/contacts/", "params": {"locationId": "{location_id}", "limit": 1}},
        ],
    },
}


class AuthTestRequest(BaseModel):
    show_key: str


class ProxyRequest(BaseModel):
    show_key: str
    path: str
    params: Optional[Dict[str, Any]] = None
    context: Optional[str] = None
    profile_name: Optional[str] = None


def redact(text: Any) -> str:
    value = str(text)
    for config in SHOW_HIGHLEVEL_CONFIGS.values():
        token = os.environ.get(config["env_var"])
        if token:
            value = value.replace(token, "[REDACTED]")
    return value


def verify_relay_secret(authorization: Optional[str]):
    required_secret = os.environ.get("HIGHLEVEL_RELAY_SHARED_SECRET", "").strip()
    if not required_secret:
        return
    if authorization != f"Bearer {required_secret}":
        raise HTTPException(status_code=401, detail="Invalid relay authorization.")


def show_credentials(show_key: str):
    if show_key not in SHOW_HIGHLEVEL_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Unknown show_key: {show_key}")
    config = SHOW_HIGHLEVEL_CONFIGS[show_key]
    token = os.environ.get(config["env_var"], "").strip()
    location_id = os.environ.get(config["location_env_var"], "").strip()
    if not token:
        raise HTTPException(status_code=500, detail=f"Missing server env var: {config['env_var']}")
    if not location_id:
        raise HTTPException(status_code=500, detail=f"Missing server env var: {config['location_env_var']}")
    return token, location_id


def render(value: Any, location_id: str):
    if isinstance(value, str):
        return value.format(location_id=location_id)
    if isinstance(value, dict):
        return {key: render(item, location_id) for key, item in value.items()}
    return value


def highlevel_request(show_key: str, path: str, *, params=None, profile_name=None, context=None):
    token, location_id = show_credentials(show_key)
    profile_name = profile_name or "leadconnector-services"
    if profile_name not in HIGHLEVEL_API_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown profile_name: {profile_name}")
    profile = HIGHLEVEL_API_PROFILES[profile_name]
    url = f"{profile['base_url']}{path}"
    if params:
        url += f"?{urlencode(params, doseq=True)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Location-Id": location_id,
    }
    headers.update(profile["default_headers"])

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_body = resp.read().decode(errors="replace")
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                payload = {"raw": raw_body}
            return {
                "ok": True,
                "status": resp.status,
                "url": url,
                "profile": profile_name,
                "path": path,
                "params": params or {},
                "payload": payload,
            }
    except urllib.error.HTTPError as exc:
        body = redact(exc.read().decode(errors="replace"))
        return {
            "ok": False,
            "status": exc.code,
            "url": url,
            "profile": profile_name,
            "path": path,
            "params": params or {},
            "error": f"GHL API error {exc.code}{f' for {context}' if context else ''}: {body[:1200]}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "url": url,
            "profile": profile_name,
            "path": path,
            "params": params or {},
            "error": f"Request failed{f' for {context}' if context else ''}: {redact(exc)}",
        }


@APP.get("/healthz")
def healthz():
    return {"ok": True}


@APP.post("/highlevel/auth-test")
def auth_test(payload: AuthTestRequest, authorization: Optional[str] = Header(default=None)):
    verify_relay_secret(authorization)
    _, location_id = show_credentials(payload.show_key)
    last_failure = None
    for profile_name, profile in HIGHLEVEL_API_PROFILES.items():
        for probe in profile["auth_probes"]:
            path = render(probe["path"], location_id)
            params = render(probe.get("params"), location_id)
            result = highlevel_request(
                payload.show_key,
                path,
                params=params,
                profile_name=profile_name,
                context=f"auth probe {probe['label']}",
            )
            if result["ok"]:
                return result
            last_failure = result
    return last_failure or {"ok": False, "error": "No auth probes configured."}


@APP.post("/highlevel/proxy")
def proxy(payload: ProxyRequest, authorization: Optional[str] = Header(default=None)):
    verify_relay_secret(authorization)
    return highlevel_request(
        payload.show_key,
        payload.path,
        params=payload.params or {},
        profile_name=payload.profile_name,
        context=payload.context,
    )
