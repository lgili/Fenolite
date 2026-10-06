# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Extension bags of imported entities (capability altium-import, "Extension bags"; change c0043): the key
table is closed, and each key is a row of the fact page."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from fenolite.backends.altium.adapter import EXT_KEYS, import_board
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.model.base import Entity, ExtBag
from fenolite.model.design import iter_entities

ROOT = Path(__file__).resolve().parents[5]
DATA = ROOT / "tests" / "data" / "altium"
PAGE = ROOT / "docs" / "formats" / "altium" / "import.md"
NEEDED = (
    "u", "deg", "layer_id", "altium_name", "plane_net", "origin", "stack_mode", "corner_percent", "paste",
    "mask", "plated", "via_layers", "net", "pour_index", "hatch_style", "component_kind", "part_ids",
    "source_designator", "source_lib_reference", "electrical", "pin_symbols", "alias", "classes", "label",
    "harness_type", "scope1", "scope2", "rule_kind",
)  # fmt: skip
DOCUMENTS = sorted(p for p in DATA.rglob("*") if p.suffix.lower() == ".pcbdoc")


def bags(value: object) -> list[tuple[Entity, ExtBag]]:
    return [(entity, entity.ext["altium"]) for entity in iter_entities(value) if "altium" in entity.ext]


def check_closed(value: object) -> int:
    found = bags(value)
    for entity, bag in found:
        assert set(entity.ext) == {"altium"} and bag.min_version is None
        for key, text in bag.payload:
            assert key in EXT_KEYS, (entity.id, key)
            assert isinstance(text, str), (entity.id, key)
        order = [EXT_KEYS.index(key) for key, _ in bag.payload]
        assert order == sorted(order), entity.id
    return len(found)


def test_closed_key_table_holds_the_needed_keys_and_each_is_a_row_of_the_page() -> None:
    assert set(NEEDED) <= set(EXT_KEYS) and len(set(EXT_KEYS)) == len(EXT_KEYS)
    rows = set(re.findall(r"^\| `([a-z_0-9]+)` \|", PAGE.read_text(encoding="utf-8"), re.MULTILINE))
    assert set(EXT_KEYS) <= rows, sorted(set(EXT_KEYS) - rows)


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_closed_on_the_authored_documents(path: Path) -> None:
    data = path.read_bytes()
    design = import_board(read_pcbdoc(data), file=path.name, sha256=hashlib.sha256(data).hexdigest())
    assert check_closed(design.board) + check_closed(design.circuit) + check_closed(design.rules) > 0
