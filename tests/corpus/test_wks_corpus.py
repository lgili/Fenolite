# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT1 and opaque count on the corpus worksheet (capability kicad-file-backend, "Drawing sheet files are
read", scenario "Demo worksheet read"; change c0012). Reading third-party worksheets stays INFERRED."""

from __future__ import annotations

import pytest
from _corpus import manifest_items, require

from fenolite.backends.kicad.sexpr import parse, tree_equal
from fenolite.backends.kicad.slots import from_ext_all
from fenolite.backends.kicad.wks import opaque_count, read_drawing_sheet, rebuild_drawing_sheet
from fenolite.model.base import Opaque
from fenolite.model.presentation import SheetText

pytestmark = pytest.mark.needs_corpus
DEMO = "kicad-demo-10-0-6-wks-01"


def test_demo_worksheet() -> None:
    (item,) = [i for i in manifest_items("rt0") if i.id == DEMO]
    path = require(item)
    text = path.read_bytes().decode("utf-8")
    sheet = read_drawing_sheet(text, file=DEMO)
    assert tree_equal(rebuild_drawing_sheet(sheet), parse(text))
    root_opaque = [s for s in from_ext_all(sheet.ext["kicad"])["."] if isinstance(s, Opaque)]
    heads = [parse(s.fragment).name for s in root_opaque]  # type: ignore[union-attr]
    assert "polygon" in heads
    percent = [s.fragment for s in root_opaque if s.fragment.startswith("(tbtext") and "%" in s.fragment]
    assert len(percent) == 13  # 14 codes: one text holds two
    assert not any("%" in i.text for i in sheet.items if isinstance(i, SheetText))
    assert opaque_count(sheet) >= len(root_opaque)
