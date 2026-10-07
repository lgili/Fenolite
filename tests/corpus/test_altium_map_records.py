# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Which map records (record 47) the footprint models of the public project sets hold
(``H-A-SCHX-PINMAP-FORM``; change c0135). Only counts are printed; no content of a corpus file is kept."""

from __future__ import annotations

from collections import Counter

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.read.sch import Implementation, MapDefiner, Pin, read_schematic

pytestmark = pytest.mark.needs_corpus


def _sets() -> dict[str, list[CorpusItem]]:
    found: dict[str, list[CorpusItem]] = {}
    for item in manifest_items("altium-import"):
        (name,) = [use for use in item.uses if use.startswith("altium-set:")]
        found.setdefault(name, []).append(item)
    return dict(sorted(found.items()))


def test_map_records_are_saved_for_the_mapped_pins_only() -> None:
    """A footprint model that Altium saved holds a record only for a pin whose pads are not the pad of its
    own designator alone; its pads are numbered from 0 without a gap, and ``DESIMPCOUNT`` is their number.
    This is the form Altium saves; it says nothing of what Altium does with a record that Fenolite writes.
    The set with a heavy item is left out."""
    models = records = 0
    shapes: Counter[tuple[int, int, int]] = Counter()
    names: list[str] = []
    for name, items in _sets().items():
        if any(item.heavy for item in items):
            continue
        names.append(name)
        for item in items:
            if item.path.suffix.lower() != ".schdoc":
                continue
            document = read_schematic(require(item).read_bytes(), file=item.id)
            for component in document.components():
                pins = [r for r in (document.get(ref) for ref in component.children) if isinstance(r, Pin)]
                for model in (r for r in document.walk(component) if isinstance(r, Implementation)):
                    models += 1
                    found = [r for r in document.walk(model) if isinstance(r, MapDefiner)]
                    if not found:
                        continue
                    for record in found:
                        records += 1
                        indexes = record._indexes(r"DESIMP(\d+)")  # pyright: ignore[reportPrivateUsage]
                        assert indexes == tuple(range(len(indexes))) and indexes, "pads numbered from 0"
                        assert record.trusted_count("DESIMPCOUNT") == len(indexes)
                    identity = sum(1 for r in found if r.implementations == (r.interface,))
                    shapes[(len(pins), len(found), identity)] += 1
    print(f"sets {names}: footprint models {models}, map records {records}")
    print(f"(pins, records, identity records) of the models with a record: {dict(shapes)}")
    assert names == ["altium-set:02", "altium-set:03", "altium-set:04", "altium-set:05"]
    assert (models, records) == (295, 7)
    # 293 models hold no record; one holds a record for each of its 6 pins, one a single record for 8 pins;
    # no record names the pin's own pad alone
    assert dict(shapes) == {(6, 6, 0): 1, (8, 1, 0): 1}
