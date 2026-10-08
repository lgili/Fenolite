# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The visibility bits of the pins that Altium saved (change c0148, S-0614, ``H-A-SCHLIB-PINBITS``).

Every pin of the public schematic documents and libraries holds bit 0x20 of ``PINCONGLOMERATE``, and the
split by bits 0x08 and 0x10 and by the size of the owning component is the table of
``docs/evidence/altium-schematic.md``, "Pin visibility bits" (measured on 2026-10-08).
"""

from __future__ import annotations

import re
from collections import Counter

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.read import sch, schlib
from fenolite.backends.altium.read.sch.records import SHOW_FLAGS, Pin

pytestmark = pytest.mark.needs_corpus
SCH = [i for i in manifest_items("altium") if re.fullmatch(r"altium-third-party-schdoc-\d+", i.id)]
LIB = [i for i in manifest_items("altium") if re.fullmatch(r"altium-third-party-schlib-\d+", i.id)]
DOCUMENT_SPLIT = {
    ("small", False, False): 1233,
    ("small", False, True): 105,
    ("small", True, False): 17,
    ("small", True, True): 12,
    ("large", False, False): 47,
    ("large", False, True): 77,
    ("large", True, False): 69,
    ("large", True, True): 1414,
}
"""(owner of at most 3 pins or more, 0x08 set, 0x10 set) → pins, in the 38 public documents."""


def _document_pins(item: CorpusItem) -> list[Pin]:
    document = sch.read_schematic(require(item).read_bytes(), file=item.id)
    return [r for r in document.records if isinstance(r, Pin)]


def _library_pins(item: CorpusItem) -> list[Pin]:
    library = schlib.read_schlib(require(item).read_bytes(), file=item.id)
    return [p for component in library.components for p in component.pins]


@pytest.mark.parametrize("item", SCH + LIB, ids=lambda i: i.id)
def test_every_saved_pin_holds_bit_0x20(item: CorpusItem) -> None:
    pins = _document_pins(item) if item in SCH else _library_pins(item)
    assert all(p.conglomerate & SHOW_FLAGS for p in pins), item.id


def test_document_split_by_component_size() -> None:
    if len(SCH) != 38 or any(i.heavy for i in SCH):
        pytest.skip("the table was measured on the 38 light rows altium-third-party-schdoc-01 to -38")
    found: Counter[tuple[str, bool, bool]] = Counter()
    for item in SCH:
        owners: dict[int | None, list[int]] = {}
        for pin in _document_pins(item):
            owners.setdefault(pin.owner_index, []).append(pin.conglomerate)
        for values in owners.values():
            size = "small" if len(values) <= 3 else "large"
            found.update((size, bool(v & 0x08), bool(v & 0x10)) for v in values)
    assert dict(found) == DOCUMENT_SPLIT
