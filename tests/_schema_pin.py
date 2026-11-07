# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Compare historical schema0 byte pins while explicitly requiring the current schema 1.1 (c0462)."""

from __future__ import annotations

import json

from fenolite import __version__

PIN_VERSION = "0.7.0.dev0"
"""The tool version the byte pins were reviewed at; the release only renames it (c0469)."""


def pinned_version(data: bytes) -> bytes:
    """``data`` with the running Fenolite version written as the pins' :data:`PIN_VERSION`."""
    if __version__ == PIN_VERSION:
        return data
    return data.replace(__version__.encode("utf-8"), PIN_VERSION.encode("utf-8"))


def legacy_meta_bytes(data: bytes) -> bytes:
    """Restore only the deliberately changed marker in a copy; every other byte is kept."""
    data = pinned_version(data)
    meta = json.loads(data)
    assert meta["schema_version"] == "1.1"
    current = b'"schema_version": "1.1"'
    assert data.count(current) == 1
    legacy = data.replace(current, b'"schema_version": "0"', 1)
    assert json.loads(legacy) == {**meta, "schema_version": "0"}
    return legacy
