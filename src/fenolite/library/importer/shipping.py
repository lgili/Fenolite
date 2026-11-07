# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Local download data cannot become a shipped catalog or library item (c0264)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from fenolite.catalog.records import DeviceRecord, Header, ImportOrigin, Record


def shippable(record: Record | Header | Mapping[str, object]) -> bool:
    """False for a local-import origin or its fixed source-terms licence, including raw TOML maps."""
    if isinstance(record, DeviceRecord) and record.device.provenance is not None:
        if record.device.provenance.tool == "fenolite catalog import":
            return False
    if isinstance(record, Header):
        return record.licence != "see source terms" and not isinstance(record.origin, ImportOrigin)
    if isinstance(record, Mapping):
        data = record
        origin = data.get("origin")
        provenance = data.get("provenance")
        if (
            isinstance(provenance, Mapping)
            and cast("Mapping[str, object]", provenance).get("tool") == "fenolite catalog import"
        ):
            return False
        return data.get("licence") != "see source terms" and not (
            isinstance(origin, Mapping) and cast("Mapping[str, object]", origin).get("shippable") is False
        )
    return shippable(record.header)


__all__ = ["shippable"]
