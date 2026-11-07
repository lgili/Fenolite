# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Static supplier discovery; safe to read without importing provider code (change c0267)."""

from __future__ import annotations

import importlib.metadata
import os
from collections.abc import Mapping
from typing import Any

SUPPLIER_ISSUE_CODES = {
    "supplier.proposed": "info",
    "supplier.row-incomplete": "info",
    "supplier.no-results": "info",
    "supplier.rate-limited": "warning",
    "supplier.unmapped": "info",
}

POLICIES: dict[str, dict[str, Any]] = {
    "digikey": {
        "title": "DigiKey",
        "terms": ("S-1221",),
        "sources": ("S-1100", "S-1101", "S-1102", "S-1220"),
        "credentials": ("CLIENT_ID", "CLIENT_SECRET"),
        "hosts": ("api.digikey.com",),
        "per_minute": 120,
        "per_day": 1000,
        "reason": (
            "the API agreement restricts creating an information database; "
            "durable identity-proposal permission is unverified"
        ),
    },
    "mouser": {
        "title": "Mouser",
        "terms": ("S-1222",),
        "sources": ("S-1103", "S-1104", "S-1222"),
        "credentials": ("API_KEY",),
        "hosts": ("api.mouser.com",),
        "per_minute": 30,
        "per_day": 1000,
        "reason": (
            "primary API terms prohibit storing content; durable identity-proposal permission is unverified"
        ),
    },
    "nexar": {
        "title": "Nexar",
        "terms": ("S-1107",),
        "sources": ("S-1105", "S-1106", "S-1223", "S-1224", "S-1225", "S-1226", "S-1227"),
        "credentials": ("CLIENT_ID", "CLIENT_SECRET"),
        "hosts": ("identity.nexar.com", "api.nexar.com"),
        "per_minute": 1,
        "per_day": None,
        "reason": (
            "the current API-terms body, quotas and durable identity-proposal permission are unverified"
        ),
    },
    "farnell": {
        "title": "Farnell",
        "terms": ("S-1109",),
        "sources": ("S-1108",),
        "credentials": ("API_KEY",),
        "hosts": ("api.element14.com",),
        "per_minute": 1,
        "per_day": None,
        "reason": (
            "partner terms prohibit recording API content; durable identity-proposal permission is unverified"
        ),
    },
}
"""Source facts: docs/formats/suppliers/*.md. Unknown quotas use a conservative client choice, not a claim."""


def metadata(name: str) -> dict[str, Any]:
    source = POLICIES[name]
    return {
        "name": name,
        "title": source["title"],
        "terms": source["terms"],
        "attribution": f"{source['title']} (source acknowledgement; required wording is unverified)",
        "cache": "none",
        "max_age_s": 0,
        "terms_max_age_s": None,
        "rate": {"per_minute": source["per_minute"], "per_day": source["per_day"]},
        "sends": ("canonical query keywords", "own account credentials"),
        "persist": (),
        "evidence": "UNVERIFIED",
        "ready": False,
        "reason": source["reason"],
        "hosts": source["hosts"],
        "credentials": source["credentials"],
    }


def capabilities(
    entries: Mapping[str, importlib.metadata.EntryPoint], *, brief: bool = False
) -> list[dict[str, Any]]:
    try:
        importlib.metadata.version("keyring")
        extra = True
    except importlib.metadata.PackageNotFoundError:
        extra = False
    present = set(os.environ)
    entries_out = [
        {
            **{key: value for key, value in metadata(name).items() if key not in ("hosts", "credentials")},
            "available": False,
            "credential_env_present": all(
                f"FENOLITE_{name.upper()}_{key}" in present for key in POLICIES[name]["credentials"]
            ),
            "sends_data_offsite": True,
            "extra_installed": extra,
        }
        for name in sorted(entries)
        if name in POLICIES
    ]

    if brief:
        keys = {
            "name",
            "available",
            "ready",
            "reason",
            "credential_env_present",
            "sends_data_offsite",
            "sends",
            "cache",
            "extra_installed",
        }
        return [{key: value for key, value in entry.items() if key in keys} for entry in entries_out]
    return entries_out
