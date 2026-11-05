# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The gallery images drawn from the library viewer's scenes (change c0405, ``gallery_images``).

The footprint, the symbol and the sheet below are authored for this test."""

from __future__ import annotations

import re

import pytest

from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.cli._library_gallery import schematic_svg
from fenolite.library.gallery_images import (
    footprint_media,
    footprint_svg,
    symbol_media,
    symbol_svg,
)
from fenolite.view.catalog import catalog_scene

LAND = """(footprint "Authored_THT_3"
\t(version 20241229)
\t(generator "pcbnew")
\t(layer "F.Cu")
\t(fp_line (start -3 -1.5) (end 3 -1.5) (stroke (width 0.12) (type solid)) (layer "F.SilkS")
\t\t(uuid "00000000-0000-4000-8000-000000000101"))
\t(fp_arc (start -1 1.5) (mid 0 2.5) (end 1 1.5) (stroke (width 0.12) (type solid)) (layer "F.SilkS")
\t\t(uuid "00000000-0000-4000-8000-000000000102"))
\t(fp_rect (start -3.5 -2) (end 3.5 3) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd")
\t\t(uuid "00000000-0000-4000-8000-000000000103"))
\t(pad "2" thru_hole circle (at 0 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask")
\t\t(uuid "00000000-0000-4000-8000-000000000104"))
\t(pad "1" thru_hole rect (at -2.54 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask")
\t\t(uuid "00000000-0000-4000-8000-000000000105"))
\t(pad "3" thru_hole circle (at 2.54 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask")
\t\t(uuid "00000000-0000-4000-8000-000000000106"))
)
"""
SYMBOL = """(kicad_symbol_lib (version 20241209) (generator "authored")
\t(symbol "Authored_Diode" (in_bom yes) (on_board yes)
\t\t(property "Reference" "D" (at 0 2.54 0) (effects (font (size 1.27 1.27))))
\t\t(property "Value" "Authored_Diode" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))
\t\t(symbol "Authored_Diode_0_1"
\t\t\t(polyline (pts (xy -1.27 1.27) (xy -1.27 -1.27) (xy 1.27 0) (xy -1.27 1.27))
\t\t\t\t(stroke (width 0.254) (type default)) (fill (type outline)))
\t\t\t(circle (center 0 0) (radius 2) (stroke (width 0.2) (type default)) (fill (type none))))
\t\t(symbol "Authored_Diode_1_1"
\t\t\t(pin passive line (at -3.81 0 0) (length 2.54) (name "A" (effects (font (size 1.27 1.27))))
\t\t\t\t(number "1" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at 3.81 0 180) (length 2.54) (name "K" (effects (font (size 1.27 1.27))))
\t\t\t\t(number "2" (effects (font (size 1.27 1.27))))))))
"""

SHEET = """(kicad_sch (version 20250114) (generator "authored") (uuid "00000000-0000-4000-8000-000000000201")
\t(paper "A4")
\t(wire (pts (xy 50.8 50.8) (xy 76.2 50.8)) (stroke (width 0) (type default))
\t\t(uuid "00000000-0000-4000-8000-000000000202"))
\t(label "IN" (at 50.8 50.8 0) (effects (font (size 1.27 1.27)) (justify left bottom))
\t\t(uuid "00000000-0000-4000-8000-000000000203"))
)
"""


def test_footprint_image_marks_pin_one() -> None:
    land = read_footprint(LAND, library="Authored")
    scene = catalog_scene(land)
    data = footprint_svg(land, scene)
    assert data == footprint_svg(land, catalog_scene(land))  # same definition, same bytes
    text = data.decode("utf-8")
    assert text.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="') and text.endswith("</svg>\n")
    ring = re.search(r'<rect class="pin1" x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"', text)
    assert ring is not None
    x, y, w, h = (int(v) for v in ring.groups())
    assert (x + w // 2, y + h // 2) == (-2540, 0) and w > 1600  # pad "1", not the first pad in the file
    assert 'class="copper"' in text and 'class="silkscreen"' in text and 'class="courtyard"' in text
    assert 'class="drill"' in text and text.count('fill="#0d1219"') == 3  # three holes
    assert re.search(r'<path d="M-1000,1500A1000,1000 0 0 [01] 1000,1500"', text)  # the authored arc
    assert ">1</text>" in text and ">3</text>" in text
    assert "<script" not in text and "http" not in text.split("xmlns", 1)[1].split('"', 2)[2]


def test_footprint_facts() -> None:
    land = read_footprint(LAND, library="Authored")
    media = footprint_media(land, catalog_scene(land))
    assert [view.name for view in media.views] == ["footprint.svg"] and media.missing is None
    facts = dict(media.facts)
    assert (
        facts["Pads"] == "3" and facts["Pad kinds"] == "3 thru_hole" and facts["Package"] == "Authored_THT_3"
    )


def test_symbol_image_and_pins() -> None:
    (diode,) = read_symbol_library(SYMBOL, library="Authored")
    scene = catalog_scene(diode)
    data = symbol_svg(diode, scene)
    assert data == symbol_svg(diode, catalog_scene(diode))
    text = data.decode("utf-8")
    assert "<title>Symbol Authored:Authored_Diode</title>" in text
    assert "<polygon " in text and "<ellipse " in text and ">K</text>" in text
    media = symbol_media(diode, scene)
    assert dict(media.facts) == {"Pins": "2", "Units": "1", "Reference": "D"}
    assert media.table == (("Pin", "Name", "Type"), (("1", "A", "passive"), ("2", "K", "passive")))


def test_schematic_image_is_cropped_without_its_frame() -> None:
    title = "Block Authored:link, usage schematic"
    data = schematic_svg(SHEET, name="schematic.kicad_sch", title=title)
    assert data == schematic_svg(SHEET, name="schematic.kicad_sch", title=title)
    text = data.decode("utf-8")
    match = re.match(r'<svg xmlns="http://www.w3.org/2000/svg" viewBox="(-?\d+) (-?\d+) (\d+) (\d+)"', text)
    assert match is not None
    x, y, w, h = (int(v) for v in match.groups())
    # The wire runs from 50.8 mm to 76.2 mm: the image holds it with a small margin, not the A4 sheet.
    assert 45_000 < x < 50_800 and 76_200 < x + w < 82_000 and h < 15_000
    assert ">IN</text>" in text and "<polyline " in text
    assert "<title>Block Authored:link, usage schematic</title>" in text
    assert ">1</text>" not in text  # no zone numbers of the drawing sheet


def test_empty_schematic_is_refused() -> None:
    empty = '(kicad_sch (version 20250114) (generator "authored") (paper "A4"))\n'
    with pytest.raises(ValueError, match="draws nothing"):
        schematic_svg(empty, name="schematic.kicad_sch", title="Block")
