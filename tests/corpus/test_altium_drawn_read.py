# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium drawn extractor on the public schematic rows (change c0470, tasks 1.1 and 2.5; capability
drawn-schematic, "Drawn content of read Altium sheets", scenario "Public documents read without error").

The census counts the root records of rows ``-01`` to ``-17`` per record class and per report kind; both
tables are those of ``docs/evidence/conversion.md`` ("Schematic records — c0470 census"). Counts only; no
value leaves the cache."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest
from _corpus import manifest_items, require

from fenolite.backends.altium import drawn_read
from fenolite.backends.altium.adapter.netlist import SheetInput, resolve
from fenolite.backends.altium.read import sch
from fenolite.model.drawn_connect import resolve as resolve_drawn

pytestmark = pytest.mark.needs_corpus
ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "evidence" / "conversion.md"
ROWS = [
    item
    for item in manifest_items("altium")
    if re.fullmatch(r"altium-third-party-schdoc-(0[1-9]|1[0-7])", item.id)
]
DRAWN_ITEM = {
    "Sheet": "paper and title block",
    "Parameter": "title block",
    "Template": "carrier",
    "Component": "symbol",
    "Wire": "wire",
    "Bus": "bus",
    "BusEntry": "bus entry",
    "Junction": "junction",
    "NetLabel": "label",
    "Port": "label",
    "PowerPort": "power",
    "SheetSymbol": "sheet reference",
    "NoErc": "no-connect",
    "SignalHarness": "bus and opaque",
    "HarnessConnector": "labels and opaque",
}
"""The drawn item a root record class becomes; every other class is a typed opaque item."""


def _read(path: Path) -> list[SheetInput]:
    data = path.read_bytes()
    return [SheetInput(path.name, "", sch.read_schematic(data, file=path.name))]


def _table(heading: str) -> list[list[str]]:
    text = DOC.read_text(encoding="utf-8")
    start = text.index(heading)
    rows: list[list[str]] = []
    for line in text[start:].splitlines()[1:]:
        if rows and not line.startswith("|"):
            break
        if line.startswith("|") and not line.startswith("|---"):
            rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def _census() -> tuple[Counter[str], dict[str, Counter[str]]]:
    classes: Counter[str] = Counter()
    kinds: dict[str, Counter[str]] = {}
    for item in ROWS:
        found = drawn_read.extract_with_pins(_read(require(item)))
        for per_sheet in found.classes.values():
            classes.update(per_sheet)
        kinds[item.id] = Counter(found.counts)
    return classes, kinds


def test_census_of_record_classes() -> None:
    """Task 1.1: the root records per class, the kind each is reported under and the drawn item it becomes;
    no class is left without a drawn item."""
    classes, _ = _census()
    rows = _table("### Root records per class")
    expected = {row[0]: (int(row[1]), row[2], row[3]) for row in rows[1:]}
    actual = {
        name: (count, drawn_read.RECORD_KINDS.get(name, "schematic-graphic"), DRAWN_ITEM.get(name, "opaque"))
        for name, count in classes.items()
    }
    assert actual == expected


def test_census_of_kinds_per_row() -> None:
    """Task 1.1 and task 2.5: the root records per report kind of each row."""
    _, kinds = _census()
    rows = _table("### Root records per kind and row")
    header = rows[0][1:]
    expected = {
        row[0]: {kind: int(value) for kind, value in zip(header, row[1:], strict=True) if value != "0"}
        for row in rows[1:]
    }
    assert {row: dict(counts) for row, counts in kinds.items()} == expected


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_public_row_reads_without_error(item) -> None:  # type: ignore[no-untyped-def]
    """Task 2.5: no row gives an ``error`` issue, and the nets resolved from the drawing equal the nets of
    ``altium-import`` for the same document."""
    inputs = _read(require(item))
    resolved = resolve(inputs, issues=[])
    found = drawn_read.extract_with_pins(inputs, resolved=resolved)
    assert [issue.message for issue in found.issues if issue.severity == "error"] == []
    netlist = resolve_drawn(found.drawn, found.pins)
    paths = {
        resolved.component_ids[key]: "/".join((*resolved.instances[key[0]].names, ref))
        for key, ref in resolved.refs.items()
    }
    native = {
        tuple(sorted((paths[p.component], p.designator) for p in net.pins)) for net in resolved.netlist.nets
    }
    drawn = {tuple(sorted(net.members)) for net in netlist.nets}
    assert {net for net in drawn if len(net) > 1} == {net for net in native if len(net) > 1}
