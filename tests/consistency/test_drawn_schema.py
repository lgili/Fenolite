# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``schemas/fenolite.drawn-schematic.v0.json`` and ``docs/drawn-schematic.md`` follow the reader's closed key
sets (capability drawn-schematic, "Drawn schematic documentation"; change c0276)."""

from __future__ import annotations

import json
from pathlib import Path

from fenolite.lens.drawn import CLOSED_KEYS

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "fenolite.drawn-schematic.v0.json"
PAGE = ROOT / "docs" / "drawn-schematic.md"


def test_schema_tables_have_the_closed_keys() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["$id"] == "fenolite.drawn-schematic.v0"
    assert list(schema["properties"]) == list(CLOSED_KEYS["root"])
    for kind, keys in CLOSED_KEYS.items():
        if kind == "root":
            continue
        table = schema["$defs"][kind]
        assert list(table["properties"]) == list(keys), kind
        assert table["additionalProperties"] is False


def test_page_names_every_key() -> None:
    """Scenario "Pages cover the names": every key of the reader's closed sets is on the page."""
    page = PAGE.read_text(encoding="utf-8")
    for kind, keys in CLOSED_KEYS.items():
        for key in keys:
            assert f"`{key}`" in page, (kind, key)
