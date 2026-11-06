# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A TrueType text keeps its font through the Altium writer and the import (change c0460)."""

import dataclasses
from pathlib import Path

import pytest
from _convert import two_layer

from fenolite.backends.altium import lower, pcbdoc
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RawPrimitive, TextRecord
from fenolite.core.coords import Point
from fenolite.model.board import Size, Text
from fenolite.model.design import Design

MM = 1_000_000
FACE = "Arial"


def _free(**font: object) -> Text:
    return Text(
        id="txt-tt",
        text="TT",
        position=Point(4 * MM, 4 * MM),
        layer="F.SilkS",
        size=Size(MM, MM),
        thickness=MM // 10,
        **font,  # type: ignore[arg-type]
    )


def _design(text: Text) -> Design:
    """The two-layer board with ``text`` as a free text and a TrueType reference field on its first
    footprint."""
    design = two_layer()
    assert design.board is not None
    first, *rest = design.board.footprints
    fields = tuple(
        dataclasses.replace(field, face=FACE, bold=False, italic=True) if field.name == "Reference" else field
        for field in first.fields
    )
    assert any(field.name == "Reference" for field in fields)
    board = dataclasses.replace(
        design.board,
        texts=(*design.board.texts, text),
        footprints=(dataclasses.replace(first, fields=fields), *rest),
    )
    return dataclasses.replace(design, board=board)


def _written(design: Design) -> bytes:
    return lower.write_design(design, allow_lossy=True).files[f"{design.header.name}.PcbDoc"]


def _records(document: bytes) -> list[TextRecord]:
    return [item for item in read_pcbdoc(document).texts if not isinstance(item, RawPrimitive)]


def test_a_text_with_a_face_is_written_as_truetype() -> None:
    """Scenario "A free text with a face": font type 1, bold 1 and the font name; a stroke text stays font
    type 0 with no name."""
    records = _records(_written(_design(_free(face=FACE, bold=True))))
    free = next(item for item in records if item.text == "TT")
    assert (free.font_type, free.bold, free.italic, free.font_name) == (1, True, False, FACE)
    designator = next(item for item in records if item.is_designator)
    assert (designator.font_type, designator.bold, designator.italic, designator.font_name) == (
        1,
        False,
        True,
        FACE,
    )
    comment = next(item for item in records if item.is_comment)
    assert (comment.font_type, comment.font_name) == (0, "")
    record = pcbdoc.text_record("A", layer=21, at=Point(0, 0), component=0, designator=True, wide_index=0)
    assert record == pcbdoc.text_record(
        "A", layer=21, at=Point(0, 0), component=0, designator=True, wide_index=0, font=None
    )


def test_truetype_texts_read_back_with_their_font(tmp_path: Path) -> None:
    """Scenario "A TrueType designator keeps its font": the import gives the free text and the reference
    field their face, bold and italic."""
    path = tmp_path / "tt.PcbDoc"
    path.write_bytes(_written(_design(_free(face=FACE, bold=True))))
    board = AltiumBackend().read(path).design.board
    assert board is not None
    text = next(item for item in board.texts if item.text == "TT")
    assert (text.face, text.bold, text.italic) == (FACE, True, False)
    references = [field for fp in board.footprints for field in fp.fields if field.name == "Reference"]
    assert [(f.face, f.bold, f.italic) for f in references if f.face] == [(FACE, False, True)]
    assert all(f.face is None for f in references if f.face != FACE)


def test_stroke_styles_and_long_faces_are_still_refused() -> None:
    assert pcbdoc.text_problem_of(_free(face=FACE, bold=True, italic=True)) is None
    assert "bold" in (pcbdoc.text_problem_of(_free(bold=True)) or "")
    assert "knockout" in (pcbdoc.text_problem_of(_free(face=FACE, knockout=True)) or "")
    long = "F" * (pcbdoc.FONT_NAME_CHARS + 1)
    assert "longer" in (pcbdoc.text_problem_of(_free(face=long)) or "")
    with pytest.raises(ValueError, match="longer"):
        pcbdoc.text_record(
            "A",
            layer=21,
            at=Point(0, 0),
            component=0,
            designator=True,
            wide_index=0,
            font=pcbdoc.TextFont(long),
        )
