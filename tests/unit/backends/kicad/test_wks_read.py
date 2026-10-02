# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawing-sheet reader and RT1 (capability kicad-file-backend, "Drawing sheet files are read", and
design-model, "Identifiers of drawing sheets"; change c0012)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.kicad.sexpr import parse, tree_equal
from fenolite.backends.kicad.slots import from_ext_all
from fenolite.backends.kicad.wks import ISSUE_CODES, opaque_count, read_drawing_sheet, rebuild_drawing_sheet
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.base import Opaque
from fenolite.model.presentation import SheetBitmap, SheetPoint, SheetShape, SheetText

DATA = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad"
SHEETS = DATA / "sheets"
MM = 1_000_000
FIXTURES = sorted(SHEETS.glob("*.kicad_wks")) + sorted((DATA / "tokens").glob("*.kicad_wks"))
HEAD = (
    '(kicad_wks (version 20231118) (generator "fenolite") (setup (textsize 1.5 1.5) (linewidth 0.15)'
    " (textlinewidth 0.15) (left_margin 10) (right_margin 10) (top_margin 10) (bottom_margin 10))"
)


def sheet_text(*items: str) -> str:
    return HEAD + " " + " ".join(items) + ")"


def codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


def test_every_modelled_kind_read() -> None:
    sheet = read_drawing_sheet(SHEETS / "all_items.kicad_wks")
    kinds = {type(i).__name__ + ":" + getattr(i, "kind", "") for i in sheet.items}
    assert kinds == {"SheetShape:rect", "SheetShape:line", "SheetText:", "SheetBitmap:"}
    points = [p for i in sheet.items for p in ((i.start, i.end) if isinstance(i, SheetShape) else (i.pos,))]
    assert {p.corner for p in points} == {"lt", "lb", "rt", "rb"}
    assert {i.scope for i in sheet.items} == {"all", "first_only", "not_first"}
    texts = [i for i in sheet.items if isinstance(i, SheetText)]
    assert {(t.justify, t.vjustify) for t in texts} >= {
        ("center", "center"),
        ("right", "top"),
        ("left", "bottom"),
    }
    assert any(t.bold and t.italic for t in texts)
    title = next(t for t in texts if t.name == "title")
    assert title.pos == SheetPoint("rb", 90 * MM, 20 * MM)  # no corner atom
    assert title.rotation == 90_000_000 and title.max_len == 80 * MM and title.max_height == 5 * MM
    label = next(t for t in texts if t.text == "A")
    assert (label.repeat.count, label.repeat.step_y, label.repeat.label_step) == (8, 50 * MM, 2)
    tick = next(i for i in sheet.items if i.name == "tick")
    assert tick.repeat.label_step == 1  # incrlabel absent
    bitmap = next(i for i in sheet.items if isinstance(i, SheetBitmap))
    assert bitmap.scale_ppm == 500_000
    import base64

    assert base64.b64decode(bitmap.png) == (SHEETS / "logo_1x1.png").read_bytes()
    assert opaque_count(sheet) == 0


def test_tokens_read_back_as_neutral_text() -> None:
    text = sheet_text('(tbtext "${TITLE} / ${COMMENT1} / ${LOT_NO} / {x}" (pos 10 10))')
    (item,) = read_drawing_sheet(text).items
    assert isinstance(item, SheetText)
    assert item.text == "{title} / {doc_id} / {param:LOT_NO} / {{x}}"


def test_explicit_default_corner_kept() -> None:
    text = sheet_text('(tbtext "A" (pos 10 10 rbcorner))')
    issues: list[Issue] = []
    sheet = read_drawing_sheet(text, issues=issues)
    (item,) = sheet.items
    assert isinstance(item, SheetText) and item.pos == SheetPoint("rb", 10 * MM, 10 * MM)
    slots = from_ext_all(sheet.ext["kicad"])["item[0]"]
    assert Opaque("(pos 10 10 rbcorner)") in slots
    assert codes(issues) == ["kicad.wks.kept-opaque"]
    assert tree_equal(rebuild_drawing_sheet(sheet), parse(text))


@pytest.mark.parametrize(
    "item",
    ['(tbtext "${SHEETNAME}" (pos 10 10))', '(tbtext "Title: %T" (pos 10 10))', '(tbtext "${bad" (pos 1 1))'],
)
def test_text_kept_opaque(item: str) -> None:
    issues: list[Issue] = []
    sheet = read_drawing_sheet(sheet_text(item), issues=issues)
    assert sheet.items == () and opaque_count(sheet) == 1
    assert codes(issues) == ["kicad.wks.kept-opaque"]
    assert tree_equal(rebuild_drawing_sheet(sheet), parse(sheet_text(item)))


def test_sub_micrometre_length_on_a_modelled_item() -> None:
    path = SHEETS / "sub_um.kicad_wks"
    issues: list[Issue] = []
    sheet = read_drawing_sheet(path, issues=issues)
    assert [type(i) for i in sheet.items] == [SheetText]
    assert codes(issues) == ["kicad.wks.kept-opaque"] and "50.0006" in issues[0].message
    assert tree_equal(rebuild_drawing_sheet(sheet), parse(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    "item",
    [
        '(tbtext "A" (pos 10 10 bogcorner))',
        '(tbtext "A" (pos 10 10) (option bogus))',
        '(tbtext "A" (pos 10 10) (font heavy))',
        '(tbtext "A" (pos 10 10) (justify middle))',
        '(tbtext "A" (pos 1 1) (rotate 0.0000001))',
        '(bitmap (pos 1 1) (scale 0.0000001) (pngdata (data "89")))',
        '(tbtext "A" (pos 10 10) (pos 1 1))',
    ],
)
def test_unmappable_items_kept_opaque(item: str) -> None:
    issues: list[Issue] = []
    sheet = read_drawing_sheet(sheet_text(item), issues=issues)
    assert opaque_count(sheet) >= 1
    assert "kicad.wks.kept-opaque" in codes(issues)
    assert tree_equal(rebuild_drawing_sheet(sheet), parse(sheet_text(item)))


def test_unmodelled_child_is_an_opaque_slot() -> None:
    text = sheet_text('(tbtext "A" (pos 10 10) (font (face "Mono") (size 2 2)) (frobnicate 1))')
    sheet = read_drawing_sheet(text)
    (item,) = sheet.items
    assert isinstance(item, SheetText) and item.size == (2 * MM, 2 * MM)
    groups = from_ext_all(sheet.ext["kicad"])
    assert Opaque("(frobnicate 1)") in groups["item[0]"]
    assert Opaque('(face "Mono")') in groups["item[0]/font[0]"]
    assert tree_equal(rebuild_drawing_sheet(sheet), parse(text))


def test_legacy_root() -> None:
    issues: list[Issue] = []
    sheet = read_drawing_sheet(DATA / "tokens" / "page_layout.kicad_wks", issues=issues)
    assert "kicad.wks.legacy-root" in codes(issues)
    assert rebuild_drawing_sheet(sheet).name == "page_layout"


def test_same_name_same_id() -> None:
    first = read_drawing_sheet(SHEETS / "all_items.kicad_wks")
    second = read_drawing_sheet(SHEETS / "all_items.kicad_wks")
    assert first.id == second.id == derived_id("wks", "kicad", "all_items")
    assert read_drawing_sheet(sheet_text(), name="frame").id == derived_id("wks", "kicad", "frame")
    assert read_drawing_sheet(sheet_text()).id == derived_id("wks", "kicad", "")


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_rt1_on_authored_fixtures(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    sheet = read_drawing_sheet(text, file=path.name)
    assert tree_equal(rebuild_drawing_sheet(sheet), parse(text))


def test_read_codes_are_closed() -> None:
    issues: list[Issue] = []
    for path in FIXTURES:
        read_drawing_sheet(path, issues=issues)
    for issue in issues:
        assert issue.code in ISSUE_CODES or issue.code.startswith("kicad.version."), issue.code
        if issue.code in ISSUE_CODES:
            assert issue.severity == ISSUE_CODES[issue.code]


def test_future_worksheet_is_read_with_a_warning() -> None:
    issues: list[Issue] = []
    read_drawing_sheet(sheet_text().replace("20231118", "29991231"), issues=issues)
    assert "kicad.version.future" in codes(issues)


def test_missing_setup_refused() -> None:
    from fenolite.core.errors import FormatError

    with pytest.raises(FormatError, match="setup"):
        read_drawing_sheet('(kicad_wks (version 20231118) (generator "x"))')
