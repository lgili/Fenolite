# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A stroke text keeps the font its record names through the import, KiCad and the writer (change c0460,
S-2253): the import keeps the name and the flags in the text's ``altium`` bag (``stroke_font``), the
conversion to KiCad carries them in ``Fenolite.Altium.StrokeFonts`` by KiCad uuid, and the writer writes
them in the stroke text's record. The free text here is authored for Fenolite; the public rows are read
from the corpus cache."""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

import pytest
from _convert import two_layer

from fenolite.backends.altium import lower, pcbdoc
from fenolite.backends.altium.adapter.ids import STROKE_FONT_KEY
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RawPrimitive, TextRecord
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import convert_project, strokefonts
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point
from fenolite.model.base import ExtBag
from fenolite.model.board import Size, Text
from fenolite.model.design import Design

MM = 1_000_000
UUID = "c0460000-0000-4000-8000-000000000010"


def _free(value: str | None) -> Text:
    """A stroke free text whose Altium bag holds ``value`` as its ``stroke_font``, or none."""
    ext = {} if value is None else {"altium": ExtBag(None, ((STROKE_FONT_KEY, value),))}
    return Text(
        id="txt-stroke",
        text="SF",
        position=Point(4 * MM, 4 * MM),
        layer="F.SilkS",
        size=Size(MM, MM),
        thickness=MM // 10,
        ext=ext,
    )


def _records(text: Text) -> list[TextRecord]:
    design = two_layer()
    assert design.board is not None
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, texts=(text,)))
    written = lower.write_design(design, allow_lossy=True).files[f"{design.header.name}.PcbDoc"]
    return [item for item in read_pcbdoc(written).texts if not isinstance(item, RawPrimitive)]


def test_the_writer_writes_a_stroke_texts_font() -> None:
    """A stroke text whose bag names its font is written with font type 0, the name and both flags; one
    without a bag keeps no name, and a bag value that is not well formed is not written."""
    (free,) = [r for r in _records(_free("11 Trebuchet MS")) if r.text == "SF"]
    assert (free.font_type, free.font_name, free.bold, free.italic) == (0, "Trebuchet MS", True, True)
    (bare,) = [r for r in _records(_free(None)) if r.text == "SF"]
    assert (bare.font_type, bare.font_name) == (0, "")
    for value in ("1 Arial", "21 Arial", "00 ", "00 " + "x" * 32):
        assert pcbdoc.text_font(_free(value)) is None


def test_a_stroke_texts_font_survives_the_import() -> None:
    """The import keeps the written record's name and flags in the text's bag."""
    from _altium_board6 import read_document

    design = two_layer()
    assert design.board is not None
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, texts=(_free("10 Arial"),)))
    name = f"{design.header.name}.PcbDoc"
    _, imported = read_document(lower.write_design(design, allow_lossy=True).files[name], name)
    assert imported.board is not None
    (text,) = [t for t in imported.board.texts if t.text == "SF"]
    assert strokefonts.font_of(text) == "10 Arial"


def test_the_carrier_reads_what_it_writes() -> None:
    fonts = {UUID: "00 Arial", UUID.replace("10", "11"): "11 Trebuchet MS"}
    assert strokefonts.read_carrier(strokefonts.carrier_text(fonts)) == fonts
    assert strokefonts.read_carrier(None) == {}
    assert strokefonts.read_carrier(b"\xff") == {}
    assert strokefonts.read_carrier(f"{UUID} 2 Arial\nnot a line\n{UUID} 00 Arial\n".encode()) == {
        UUID: "00 Arial"
    }


def _fonts(document: PcbDocument) -> Counter[tuple[int | None, str | None, bool | None, bool | None]]:
    records = [t for t in document.texts if not isinstance(t, RawPrimitive)]
    return Counter((t.font_type, t.font_name, t.bold, t.italic) for t in records)


def _round_trip(tmp_path: Path, source: Path) -> tuple[dict[str, str], bytes]:
    """``source`` converted to KiCad and back: the carried fonts and the written document."""
    kicad = convert_project(read_source(source), to="kicad", allow_lossy=True)
    folder = tmp_path / "kicad"
    for name, data in kicad.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    board = folder / kicad.read_back
    fonts = strokefonts.read_carrier(boardcarrier.carried(board.read_text("utf-8")).get(strokefonts.PROPERTY))
    back = convert_project(read_source(board), to="altium", allow_lossy=True)
    (written,) = [data for name, data in back.files.items() if name.endswith(".PcbDoc")]
    return fonts, written


ROWS = {"altium-third-party-pcbdoc-02": 83, "altium-third-party-pcbdoc-04": 15}
"""The stroke texts of each row (S-2253): designators and comments, and on ``-02`` one free text."""


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", sorted(ROWS))
def test_row_stroke_fonts_survive_kicad(tmp_path: Path, row: str) -> None:
    """The public rows come back with the font name and flags of every text record, stroke and TrueType."""
    from _corpus import manifest_items, require

    (item,) = [i for i in manifest_items("altium-pcbdoc") if i.id == row]
    source = require(item)
    fonts, written = _round_trip(tmp_path, source)
    assert len(fonts) == ROWS[row]
    before = _fonts(read_pcbdoc(source.read_bytes()))
    assert sum(n for (kind, name, _, _), n in before.items() if kind == 0 and name) == ROWS[row]
    assert _fonts(read_pcbdoc(written)) == before


def test_a_design_without_stroke_fonts_carries_none(tmp_path: Path) -> None:
    design: Design = two_layer()
    assert strokefonts.found(design.board) == {}
    assert strokefonts.found(None) == {}
