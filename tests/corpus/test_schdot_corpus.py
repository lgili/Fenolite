# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sheet import on the public Altium sheet templates (change c0046, capability sheet-templates,
"Authored sheet fixtures and corpus rows"; hypotheses ``H-A-RD-SHT-SAME``, ``-OWNER``, ``-AREA``,
``-STRINGS`` and ``-IMAGE``).

The rows are measurement material. This file asserts the form, the paper, the accounting and that the
written ``.kicad_wks`` reads back; the census holds counts per record kind and per key name only. No text,
name, coordinate or image of a row is asserted, printed or stored."""

from __future__ import annotations

from collections import Counter

import pytest
from _boards import census
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.sheet import (
    NOT_REPRESENTABLE,
    SHEET_STYLES,
    import_sheet,
    neutral_text,
)
from fenolite.backends.kicad.wks import read_drawing_sheet, write_drawing_sheet

pytestmark = pytest.mark.needs_corpus
SHEETS = manifest_items("altium-sheet")
SCHEMATICS = manifest_items("altium-sch")
PAPERS = {
    "altium-third-party-schdot-01": "A4",
    "altium-third-party-schdot-02": "A3",
    "altium-third-party-schdot-03": "A4",
}
"""The neutral paper of each row, from its ``SHEETSTYLE`` (a missing key is style 0)."""
DRAWN = frozenset({4, 6, 7, 13, 14, 30})
GRAPHICS = DRAWN | frozenset(NOT_REPRESENTABLE)
"""The kinds of the graphics table: the drawn ones and the ones reported as not representable."""
SILENT = (sch.Template, sch.Parameter)


def test_three_rows_of_two_repositories() -> None:
    assert sorted(item.id for item in SHEETS) == sorted(PAPERS)
    for item in SHEETS:
        assert {"altium", "origin:third-party", "altium-sch", "altium-sheet"} <= set(item.uses)
        assert "cfb" not in item.uses


def _accounted(document: sch.SchDocument, data: bytes) -> Counter[str]:
    """Import ``data`` and check that every template record is imported or reported, exactly once."""
    result = import_sheet(data, allow_lossy=True)
    template_records: list[sch.SchRecord] = []
    chosen: set[int] = set()
    for record in document.records[1:]:
        owner = record.owner
        if owner is None or (owner.index in chosen and isinstance(document.get(owner), sch.Template)):
            chosen.add(record.ref.index)
            template_records.append(record)
    counted = [record for record in template_records if not isinstance(record, SILENT)]
    main = [where for where in result.reported if where.startswith("record[")]
    assert len(set(result.reported)) == len(result.reported)
    assert sum(result.imported.values()) + len(main) == len(counted)
    assert set(main) <= {f"record[{record.ref.index}]" for record in counted}
    warned = {issue.where for issue in result.issues if issue.severity == "warning"}
    assert set(result.reported) <= warned
    assert set(result.imported) <= DRAWN
    counts = Counter({f"imported {kind}": count for kind, count in result.imported.items()})
    counts.update(issue.code for issue in result.issues)
    counts["items"] = len(result.sheet.items)
    counts["special strings"] = len(result.strings)
    counts["parameters"] = len(result.parameters)
    return counts


@pytest.mark.parametrize("item", SHEETS, ids=lambda item: item.id)
def test_corpus_templates_import(item: CorpusItem) -> None:
    data = require(item).read_bytes()
    document = sch.read_schematic(data, file=item.id)
    # H-A-RD-SHT-SAME: read as a schematic, sheet record first, every graphic record a root.
    sheet = document.sheet
    assert sheet is not None and sheet.props is not None
    graphics = [record for record in document.records[1:] if record.record_id in GRAPHICS]
    assert graphics and all(record.owner is None for record in graphics)
    assert document.additional == () and not document.templates()
    result = import_sheet(data, file=item.id, allow_lossy=True)
    assert result.source.form == "binary"
    assert result.source.paper == PAPERS[item.id]
    # H-A-RD-SHT-AREA: the style is one of the table.
    assert result.source.style is not None and 0 <= result.source.style < len(SHEET_STYLES)
    counts = _accounted(document, data)
    written = write_drawing_sheet(result.sheet, allow_lossy=True)
    back = read_drawing_sheet(written.text)
    assert back.setup == result.sheet.setup and back.items == result.sheet.items
    kinds = Counter(str(record.record_id) for record in document.records[1:])
    keys: Counter[str] = Counter()
    for record in document.records:
        if record.props is not None:
            keys.update(f"{record.record_id}:{key.rstrip('0123456789')}" for key in record.props.keys())
    census("schdot", item.id, {"kinds": dict(kinds), "keys": dict(keys), "import": dict(counts)})


@pytest.mark.parametrize("item", SCHEMATICS, ids=lambda item: item.id)
def test_template_records_of_every_schematic_row(item: CorpusItem) -> None:
    """``H-A-RD-SHT-OWNER``, ``-STRINGS`` and ``-IMAGE`` on every schematic row: the children of a record 39
    are graphics, every special string maps or is reported, and every embedded image has its file."""
    data = require(item).read_bytes()
    document = sch.read_schematic(data, file=item.id)
    children = [document.get(ref) for template in document.templates() for ref in template.children]
    assert all(child.record_id in GRAPHICS for child in children)
    counts = _accounted(document, data)
    classes: Counter[str] = Counter()
    for label in document.of_type(sch.Label):
        if label.text.startswith("="):
            classes[neutral_text(label.text)[1]] += 1
    assert set(classes) <= {"token", "param", "dynamic", "unknown"}
    assert counts["altium.sheet.unknown-string"] <= classes["unknown"]
    assert counts["altium.sheet.dynamic-string"] <= classes["dynamic"]
    images = document.of_type(sch.Image)
    embedded = [image for image in images if image.embedded]
    assert all(document.image_data(image) is not None for image in embedded)
    census(
        "schdot_owner",
        item.id,
        {
            "templates": len(document.templates()),
            "children": dict(Counter(str(child.record_id) for child in children)),
            "strings": dict(classes),
            "images": len(images),
            "embedded": len(embedded),
        },
    )
