# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The imported Altium sheet template is drawn by KiCad as ``layout`` predicts (change c0046, capability
sheet-templates; the oracle of c0012, ``test_sheet_acceptance.py``).

The authored template ``title_block`` (``tests/_altium_sheet.py``) is imported, written as a ``.kicad_wks``
and drawn on an A4 board with a seven-field title block. The SVG must lack the load-error message, draw
exactly the predicted texts, differ from the default sheet, and draw every predicted line within 0.01 mm.
This verifies the written file, not the reading of the Altium bytes: no ``kicad-cli`` path reads them.

The comparison of c0012 accepts a text whose SVG position is within half a text height below or above its
anchor, which covers the vertical justifications ``bottom`` and ``center``. KiCad draws a ``top``-justified
text one text height below its anchor (observed on 10.0.6), so ``predict`` moves the expected position of
such a text down by half a height; nothing else differs from ``_acceptance.prediction``."""

from __future__ import annotations

import tempfile
from functools import cache
from pathlib import Path

import _acceptance as acc
import _expected as ex
import _sheetcases as sc
import pytest
from _altium_sheet import template
from _sheet_bench import Expected, classify, export_sheet_svg
from _svg import SheetSvg

from fenolite.backends.altium.read.sheet import import_sheet
from fenolite.backends.kicad.wks import read_drawing_sheet, write_drawing_sheet
from fenolite.model.presentation import DrawingSheet, SheetText

pytestmark = pytest.mark.needs_kicad
SIZE = "A4"
_FOLDER = Path(tempfile.mkdtemp(prefix="fenolite-sheet-import-"))


@cache
def written(form: str) -> Path:
    """The ``.kicad_wks`` of the imported ``title_block`` in ``form``."""
    imported = import_sheet(template("title_block", form=form), name="title_block")  # type: ignore[arg-type]
    assert imported.source.paper == SIZE and not imported.issues
    path = _FOLDER / f"title_block-{form}.kicad_wks"
    path.write_text(write_drawing_sheet(imported.sheet).text, encoding="utf-8")
    return path


def predict(sheet: DrawingSheet, svg: SheetSvg) -> tuple[list[Expected], list[tuple[object, ...]]]:
    """``_acceptance.prediction``, with a ``top``-justified text expected half a height lower."""
    texts, lines = acc.prediction(sheet, svg, paper=acc.PAPER_NAMES[SIZE], block=ex.TITLE)
    items = [item for item in sheet.items if isinstance(item, SheetText)]
    assert len(items) == len(texts)  # no item repeats, so the two lists are in the same order
    moved = [
        Expected(want.text, want.x, want.y + want.height / 2, want.height) if item.vjustify == "top" else want
        for want, item in zip(texts, items, strict=True)
    ]
    return moved, lines  # type: ignore[return-value]


@pytest.mark.parametrize("form", ["binary", "ascii"])
def test_imported_title_block_is_drawn_as_predicted(form: str) -> None:
    text = acc.board(SIZE)
    case = export_sheet_svg(text, written(form))
    assert classify(case, default=sc.default(text=text), control=sc.control(text=text)) == "load"
    assert case.svg is not None
    sheet = read_drawing_sheet(written(form).read_text(encoding="utf-8"))
    texts, lines = predict(sheet, case.svg)
    assert len(texts) == 19 and len(lines) == 5 + 2 * 4
    assert {t.text for t in texts} >= {ex.TITLE.title, ex.TITLE.doc_id, ex.TITLE.revision}
    assert acc.problems_for(SIZE, case.svg, texts, lines) == []  # type: ignore[arg-type]


def test_both_forms_write_the_same_bytes() -> None:
    assert written("binary").read_bytes() == written("ascii").read_bytes()


def test_wrong_prediction_fails() -> None:
    case = export_sheet_svg(acc.board(SIZE), written("binary"))
    assert case.svg is not None
    sheet = read_drawing_sheet(written("binary").read_text(encoding="utf-8"))
    texts, lines = predict(sheet, case.svg)
    moved = [(lines[0][0] + 1, *lines[0][1:]), *lines[1:]]  # type: ignore[operator]
    assert acc.problems_for(SIZE, case.svg, texts, moved)  # type: ignore[arg-type]
    shifted = [Expected(texts[0].text, texts[0].x + 1, texts[0].y, texts[0].height), *texts[1:]]
    assert acc.problems_for(SIZE, case.svg, shifted, lines)  # type: ignore[arg-type]
