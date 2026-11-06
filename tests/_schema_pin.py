# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Compare historical schema0 byte pins while explicitly requiring the current schema 1.1 (c0462)."""

from __future__ import annotations

import json


def legacy_meta_bytes(data: bytes) -> bytes:
    """Restore only the deliberately changed marker in a copy; every other byte is kept."""
    meta = json.loads(data)
    assert meta["schema_version"] == "1.1"
    current = b'"schema_version": "1.1"'
    assert data.count(current) == 1
    legacy = data.replace(current, b'"schema_version": "0"', 1)
    assert json.loads(legacy) == {**meta, "schema_version": "0"}
    return legacy
