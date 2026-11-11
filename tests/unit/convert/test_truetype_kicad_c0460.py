# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A KiCad TrueType text holds its face, bold and italic in the model (change c0460, task 1.3).

The KiCad reader projects them when a text's font names a face, so a text read from KiCad holds the fact a
text read from Altium holds, and a conversion through KiCad gives Altium its TrueType texts back. A text in
KiCad's stroke font keeps its bold and italic in its slots, as before (change c0277): its canonical JSON
does not change. The boards are the committed two-layer board, edited.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RawPrimitive, TextRecord
from fenolite.backends.kicad import pcb
from fenolite.backends.kicad._libread import truetype_font
from fenolite.backends.kicad.fpitems import with_footprint_items
from fenolite.backends.kicad.sexpr import Node, parse_fragment
from fenolite.convert import convert_project
from fenolite.convert.sources import read_source
from fenolite.model.canonical import dumps, to_data

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
FONT = r"(%s[\s\S]*?\(font)(\s*)([\s\S]*?\(thickness [^)]*\))"
"""The opening of the font of the item that ``%s`` starts, and its children up to ``thickness``."""
USER = '\t\t(fp_text user "TTU" (at 0 2 90) (layer "F.SilkS") (uuid "c0460000-0000-4000-8000-000000000002") (effects (font (face "Arial") (size 1 1) (thickness 0.15) italic)))\n'  # noqa: E501


def _board(tmp_path: Path, *, faces: bool = True, bold_stroke: bool = False) -> Path:
    """The committed board; with ``faces`` its board text in Arial bold, its first Reference field in Arial
    italic and a user text of its first footprint in Arial italic (KiCad 7's bare flag); with
    ``bold_stroke`` its board text bold in the stroke font."""
    text = BOARD.read_text("utf-8")
    item, field = re.escape('(gr_text "FENOLITE"'), re.escape('(property "Reference" "R1"')
    if faces:
        text, made = re.subn(FONT % item, r'\1\2(face "Arial")\2\3\2(bold yes)', text, count=1)
        text, more = re.subn(FONT % field, r'\1\2(face "Arial")\2\3\2(italic yes)', text, count=1)
        assert made == more == 1
        at = text.index('\t\t(property "Value" "330"')
        text = text[:at] + USER + text[at:]
    elif bold_stroke:
        text, made = re.subn(FONT % item, r"\1\2\3\2(bold yes)", text, count=1)
        assert made == 1
    path = tmp_path / "board" / BOARD.name
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return path


def _font(text: str) -> Node:
    found = parse_fragment(text)
    assert isinstance(found, Node)
    return found


def _records(document: bytes) -> list[TextRecord]:
    return [item for item in read_pcbdoc(document).texts if not isinstance(item, RawPrimitive)]


def test_the_font_of_a_truetype_text() -> None:
    """``(bold yes)``, ``(bold)`` and KiCad 7's bare ``bold`` set the flag, ``(bold no)`` does not; a font
    without a face, with an empty one or with ``KiCad Font`` (KiCad's own) is the stroke font."""
    font = _font('(font (face "Arial") (size 1 1) (bold yes) italic)')
    assert truetype_font(font) == ("Arial", True, True)
    assert truetype_font(_font('(font (face "Arial") (bold) (italic no))')) == ("Arial", True, False)
    assert truetype_font(_font("(font (size 1 1) (bold yes))")) is None
    assert truetype_font(_font('(font (face "") (bold yes))')) is None
    assert truetype_font(_font('(font (face "KiCad Font") (bold yes))')) is None  # KiCad's stroke font
    assert truetype_font(None) is None


def test_the_reader_projects_a_truetype_font(tmp_path: Path) -> None:
    """The board text, the Reference field and the footprint's user text hold their face, bold and italic,
    and the board writes back as it was read."""
    path = _board(tmp_path)
    design = pcb.read_board(path)
    assert design.board is not None
    (text,) = [t for t in design.board.texts if t.text == "FENOLITE"]
    assert (text.face, text.bold, text.italic) == ("Arial", True, False)
    (field,) = [f for fp in design.board.footprints for f in fp.fields if f.face is not None]
    assert (field.name, field.face, field.bold, field.italic) == ("Reference", "Arial", False, True)
    projected = with_footprint_items(design).design.board
    assert projected is not None
    (user,) = [t for fp in projected.footprints for t in fp.texts if t.text == "TTU"]
    assert (user.face, user.bold, user.italic) == ("Arial", False, True)
    written = pcb.write_board(design, target=9).text
    assert written.count('(face "Arial")') == path.read_text("utf-8").count('(face "Arial")') == 3
    # a board text writes its font from its slots: the projection does not change the board; a field's font
    # is modelled (change c0277), so the field writes the face it holds
    cleared = dataclasses.replace(
        design.board,
        texts=tuple(dataclasses.replace(t, face="", bold=False, italic=False) for t in design.board.texts),
    )
    assert pcb.write_board(dataclasses.replace(design, board=cleared), target=9).text == written


def test_a_stroke_text_keeps_its_canonical_json(tmp_path: Path) -> None:
    """Pinned: a board without a face projects no font, so its canonical JSON names none, and a bold text
    of the stroke font keeps its bold in its slots."""
    plain = pcb.read_board(_board(tmp_path / "plain", faces=False)).board
    assert plain is not None
    assert not {'"face"', '"bold"', '"italic"'} & {
        word for word in dumps(plain).split() if word.endswith('"')
    }
    bold = pcb.read_board(_board(tmp_path / "bold", faces=False, bold_stroke=True)).board
    assert bold is not None
    (text,) = [t for t in bold.texts if t.text == "FENOLITE"]
    assert (text.face, text.bold, text.italic) == ("", False, False)
    assert not {"face", "bold", "italic"} & set(to_data(text))


def test_truetype_texts_come_back_from_kicad(tmp_path: Path) -> None:
    """Scenario "A TrueType text survives the round trip": the KiCad board's TrueType texts are TrueType
    text records of the Altium document a conversion writes, with their face, bold and italic; a stroke
    text stays a stroke text."""
    conversion = convert_project(read_source(_board(tmp_path)), to="altium", allow_lossy=True)
    (document,) = [data for name, data in conversion.files.items() if name.endswith(".PcbDoc")]
    records = _records(document)
    (free,) = [r for r in records if r.text == "FENOLITE"]
    assert (free.font_type, free.font_name, free.bold, free.italic) == (1, "Arial", True, False)
    (designator,) = [r for r in records if r.is_designator and r.font_type == 1]
    assert (designator.font_name, designator.bold, designator.italic) == ("Arial", False, True)
    (user,) = [r for r in records if r.text == "TTU"]
    assert (user.font_type, user.font_name, user.italic) == (1, "Arial", True)
    assert all(r.font_type == 0 for r in records if r.is_comment)


def test_zero_height_truetype_footprint_text_returns(tmp_path: Path) -> None:
    board = _board(tmp_path)
    board.write_text(
        board.read_text("utf-8").replace(USER, USER.replace("(size 1 1)", "(size 0 0)")), "utf-8"
    )

    conversion = convert_project(read_source(board), to="altium", allow_lossy=True)
    (document,) = [data for name, data in conversion.files.items() if name.endswith(".PcbDoc")]
    (user,) = [record for record in _records(document) if record.text == "TTU"]
    assert user.prefix.component == 0
    assert (user.font_type, user.font_name, user.bold, user.italic) == (1, "Arial", False, True)
    assert (user.height, user.stroke_width, user.rotation) == (0, 59055, 90.0)
