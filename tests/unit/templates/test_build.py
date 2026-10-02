# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sheet builder (capability sheet-templates, "Frame, reference zones and title-block grid", "Optional logo
bitmap" and "Sheets built from templates are deterministic"; change c0012)."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from _specs import BASE, TITLE, ZONES

from fenolite.backends.kicad.wks import read_drawing_sheet, write_drawing_sheet
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model import canonical
from fenolite.model.presentation import SheetBitmap, SheetPoint, SheetShape, SheetText
from fenolite.templates import TemplateError, build_sheet, layout, load_spec

LOGO = Path(__file__).resolve().parents[2] / "data" / "kicad" / "sheets" / "logo_1x1.png"
A4 = (297_000_000, 210_000_000)


def test_frame_and_setup() -> None:
    sheet = build_sheet(load_spec(BASE))
    assert sheet.setup.left_margin == 20_000_000 and sheet.setup.text_size == (1_500_000, 1_500_000)
    (frame,) = sheet.items
    assert frame == SheetShape("rect", SheetPoint("lt", 0, 0), SheetPoint("rb", 0, 0), width=700_000)


def test_zone_band_items() -> None:
    sheet = build_sheet(load_spec(ZONES))
    texts = [i for i in sheet.items if isinstance(i, SheetText)]
    assert [(t.text, t.pos.corner) for t in texts] == [("1", "lt"), ("1", "lb"), ("A", "lt"), ("A", "rt")]
    assert all(t.repeat.label_step == 1 and t.justify == "center" for t in texts)
    assert texts[0].pos == SheetPoint("lt", 25_000_000, 2_500_000)


def test_ids_and_determinism() -> None:
    spec = load_spec(ZONES + TITLE)
    first, second = build_sheet(spec), build_sheet(spec)
    assert first.id == derived_id("wks", "template", "test")
    assert canonical.dumps(first) == canonical.dumps(second)
    assert write_drawing_sheet(first).text == write_drawing_sheet(second).text


def test_built_sheet_survives_a_round_trip() -> None:
    sheet = build_sheet(load_spec(ZONES + TITLE))
    back = read_drawing_sheet(write_drawing_sheet(sheet, target=10).text)
    assert (back.setup, back.items) == (sheet.setup, sheet.items)


def test_cell_texts_inside_their_cells() -> None:
    spec = load_spec(BASE + TITLE)
    lay = layout(build_sheet(spec), width=A4[0], height=A4[1])
    # the grid sits at the right-bottom corner of the margin box: x 167 to 287 mm, y 184 to 200 mm
    title, sheet, lot = (167, 257, 184, 192), (257, 287, 184, 192), (167, 197, 192, 200)
    cells = {"{title}": title, "Title": title, "{sheet}": sheet, "Sheet": sheet, "{param:LOT_NO}": lot}
    for text in lay.texts:
        x0, x1, y0, y1 = (v * 1_000_000 for v in cells[text.text])
        half = text.size[1] // 2
        assert x0 <= text.x <= x1 and y0 <= text.y - half and text.y + half <= y1, text


def test_no_line_inside_a_spanned_cell() -> None:
    lay = layout(build_sheet(load_spec(BASE + TITLE)), width=A4[0], height=A4[1])
    inner = [ln for ln in lay.lines if ln.x1 == ln.x2 == 197_000_000]  # border between columns 0 and 1
    assert [(ln.y1, ln.y2) for ln in inner] == [(192_000_000, 200_000_000)]  # only in row 1


def test_too_wide_is_a_warning() -> None:
    wide = TITLE.replace("columns = [30, 60, 30]", "columns = [310, 60, 30]")
    issues: list[Issue] = []
    build_sheet(load_spec(BASE + wide), issues=issues)
    assert [i.code for i in issues] == ["template.too-wide", "template.too-wide"]


def test_png_logo_embedded(tmp_path: Path) -> None:
    (tmp_path / "logo.png").write_bytes(LOGO.read_bytes())
    spec = load_spec(BASE + '[bitmap]\npath = "logo.png"\ncorner = "lt"\nx = 5\ny = 5\nscale = 1\n')
    sheet = build_sheet(spec, base_dir=tmp_path)
    (bitmap,) = [i for i in sheet.items if isinstance(i, SheetBitmap)]
    assert bitmap.pos == SheetPoint("lt", 5_000_000, 5_000_000) and bitmap.scale_ppm == 1_000_000
    assert base64.b64decode(bitmap.png) == LOGO.read_bytes()
    assert layout(sheet, width=A4[0], height=A4[1]).bitmaps == 1


def test_not_a_png(tmp_path: Path) -> None:
    (tmp_path / "logo.png").write_text("GIF89a")
    spec = load_spec(BASE + '[bitmap]\npath = "logo.png"\n')
    with pytest.raises(TemplateError) as info:
        build_sheet(spec, base_dir=tmp_path)
    assert [i.code for i in info.value.issues] == ["template.bitmap-not-png"]


def test_unreadable_bitmap(tmp_path: Path) -> None:
    with pytest.raises(TemplateError) as info:
        build_sheet(load_spec(BASE + '[bitmap]\npath = "missing.png"\n'), base_dir=tmp_path)
    assert [(i.code, i.where) for i in info.value.issues] == [("template.bad-value", "bitmap.path")]
