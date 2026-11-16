# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An Altium text keeps its anchor (change c0492): the import justifies every text left and bottom, the
corner of its box (``H-A-IMP-TEXT-ANCHOR``), and the writer writes that corner for any justification."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _textanchor import MM, STROKE, anchor_design, document, ink

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RawPrimitive, TextRecord
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.convert import convert_project
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point
from fenolite.model.board import FieldJustifyH, FieldJustifyV, Size, Text
from fenolite.model.design import Design
from fenolite.silk.extents import TextKey, estimate

KICAD_IMPORT = {
    "R1": (-3_366_600, -68_300, -1_690_800, 1_083_700),
    "D1": (16_771_738, 2_120_149, 18_607_299, 4_147_435),
}
"""The ink boxes of the two designators of the authored document as ``kicad-cli pcb import altium`` 10.0.6
gives them (task 1.1, ``test_text_anchor_oracle_c0492.py``), relative to ``R1``'s position."""


def _read(data: bytes, folder: Path) -> Design:
    path = folder / "anchor.PcbDoc"
    path.write_bytes(data)
    return AltiumBackend().read(path).design


def _records(data: bytes) -> list[TextRecord]:
    return [item for item in read_pcbdoc(data).texts if not isinstance(item, RawPrimitive)]


def test_a_designator_converted_to_kicad(tmp_path: Path) -> None:
    """Scenario "A designator converted to KiCad": ``(justify left bottom)``, mirrored on the bottom, and the
    ink within one stroke width of KiCad's own import."""
    source = tmp_path / "altium" / "anchor.PcbDoc"
    source.parent.mkdir()
    source.write_bytes(document(anchor_design()))
    conversion = convert_project(read_source(source), to="kicad", allow_lossy=True)
    (name,) = [name for name in conversion.files if name.endswith(".kicad_pcb")]
    target = tmp_path / "kicad" / name
    target.parent.mkdir()
    target.write_bytes(conversion.files[name])
    pcb = parse(target.read_text(encoding="utf-8"))
    justify = sorted(
        " ".join(a.value for a in node.find("effects").find("justify").atoms())  # type: ignore[union-attr]
        for fp in pcb.nodes("footprint")
        for node in fp.nodes("property")
        if node.atoms()[0].value == "Reference"
    )
    assert justify == ["left bottom", "left bottom mirror"]
    found = ink(read_board(target))
    for ref, box in KICAD_IMPORT.items():
        assert max(abs(a - b) for a, b in zip(found[ref], box, strict=True)) <= STROKE, ref


def test_the_import_keeps_the_position_and_the_id(tmp_path: Path) -> None:
    """The anchor is the record's position as before; the content id takes no justification."""
    design = _read(document(anchor_design()), tmp_path)
    assert design.board is not None
    free = {t.text: t for t in design.board.texts}
    refs = {c.id: c.ref for c in design.circuit.components}
    r1 = next(fp.position for fp in design.board.footprints if refs.get(fp.component_id) == "R1")
    # the source's F0 lies at (10, 35) mm and R1 at (20, 15) mm
    # (the document's frame rounds to whole nanometres of the mil grid)
    assert (
        abs(free["F0"].position.x - r1.x + 10 * MM) <= 2 and abs(free["F0"].position.y - r1.y - 20 * MM) <= 2
    )
    assert (free["B90"].h_justify, free["B90"].v_justify) == ("left", "bottom")
    again = _read(document(anchor_design()), tmp_path)
    assert again.board is not None
    assert [t.id for t in again.board.texts] == [t.id for t in design.board.texts]


def test_a_centred_designator_from_a_script(tmp_path: Path) -> None:
    """Scenario "A centred designator from a script": a 1 mm designator centred at the part's origin is read
    back with its ink centred on that origin within one stroke width."""
    design = anchor_design()
    board = design.board
    assert board is not None
    first = board.footprints[0]
    fields = tuple(
        dataclasses.replace(f, position=Point(0, 0), rotation=0, h_justify="center", v_justify="center")
        if f.name == "Reference"
        else f
        for f in first.fields
    )
    centred = dataclasses.replace(
        design,
        board=dataclasses.replace(
            board, footprints=(dataclasses.replace(first, fields=fields), *board.footprints[1:])
        ),
    )
    ref = {c.id: c.ref for c in design.circuit.components}[first.component_id]
    back = _read(document(centred), tmp_path)
    assert back.board is not None
    refs = {c.id: c.ref for c in back.circuit.components}
    places = {refs.get(f.component_id): f.position for f in back.board.footprints}
    x0, y0, x1, y1 = ink(back)[ref]  # relative to R1
    middle = ((x0 + x1) // 2 + places["R1"].x, (y0 + y1) // 2 + places["R1"].y)
    assert abs(middle[0] - places[ref].x) <= STROKE and abs(middle[1] - places[ref].y) <= STROKE


def _free(h: FieldJustifyH, v: FieldJustifyV, face: str = "") -> Text:
    return Text(
        id=f"txt-{h}-{v}-{face}",
        text="AB12",
        position=Point(5 * MM, 5 * MM),
        layer="F.SilkS",
        size=Size(MM, MM),
        thickness=STROKE,
        rotation=90_000_000,
        h_justify=h,
        v_justify=v,
        face=face,
    )


@pytest.mark.parametrize("face", ["", "Arial"])
@pytest.mark.parametrize(("h", "v"), [("center", "center"), ("right", "top"), ("left", "bottom")])
def test_a_free_text_of_any_justification_is_written_at_its_corner(
    h: FieldJustifyH, v: FieldJustifyV, face: str
) -> None:
    """Design D3 and the maintainer's decision of 2026-11-15: a stroke or TrueType free text of any
    justification is written, not refused, at the corner whose left-bottom ink is the text's own."""
    design = anchor_design()
    assert design.board is not None
    text = _free(h, v, face)
    data = document(dataclasses.replace(design, board=dataclasses.replace(design.board, texts=(text,))))
    (record,) = [r for r in _records(data) if r.text == "AB12"]
    assert record.font_type == (1 if face else 0)
    corner = pcbdoc.text_corner(text, text.text, STROKE, mirrored=False)
    own = estimate(TextKey("AB12", MM, MM, STROKE, h, v))
    lb = estimate(TextKey("AB12", MM, MM, STROKE, "left", "bottom"))
    assert own is not None and lb is not None
    # at 90° the reading direction is up (-y) and the text's down is +x
    expected = Point(5 * MM + (own.y1 - lb.y1), 5 * MM - (own.x0 - lb.x0))
    assert abs(corner.x - expected.x) <= 1 and abs(corner.y - expected.y) <= 1
    if (h, v) == ("left", "bottom"):
        assert corner == text.position


def test_a_mirrored_text_moves_the_other_way() -> None:
    text = dataclasses.replace(_free("center", "center"), rotation=0)
    plain = pcbdoc.text_corner(text, text.text, STROKE, mirrored=False)
    mirrored = pcbdoc.text_corner(text, text.text, STROKE, mirrored=True)
    assert plain.x < text.position.x < mirrored.x
    assert plain.y == mirrored.y > text.position.y
    assert pcbdoc.text_corner(dataclasses.replace(text, text=" "), " ", STROKE, False) == text.position
