# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A build's sheet carries the document parameters of its title block that KiCad has no field for, and the
reader takes them back (``sheet_carrier.param_lines``, ``put_drawing``, ``take_drawing``; change c0470)."""

from __future__ import annotations

from fenolite.backends.kicad import sheet_carrier
from fenolite.model.drawn import DrawnSchematic, DrawnSheet

_SHEET = '(kicad_sch (version 20250114) (generator "eeschema") (paper "A4"))\n'


def test_param_lines_keep_only_the_parameters_kicad_has_no_field_for() -> None:
    block = (("title", "Top"), ("param.SheetNumber", "1"), ("param.Title", "x"), ("param.Bad", "a|b"))
    assert sheet_carrier.param_lines(block) == "|RECORD=41|OWNERPARTID=-1|NAME=SheetNumber|TEXT=1"
    assert sheet_carrier.sheet_params(sheet_carrier.param_lines(block)) == {"SheetNumber": "1"}


def test_a_built_sheet_brings_its_document_parameters_back() -> None:
    block = (("title", "Top"), ("param.SheetNumber", "1"), ("param.SheetTotal", "2"))
    drawn = DrawnSchematic("root", (DrawnSheet("root", title_block=block),))
    written = sheet_carrier.put_drawing({"top.kicad_sch": _SHEET}, drawn, "top.kicad_sch")
    read = DrawnSchematic("root", (DrawnSheet("root", title_block=(("title", "Top"),)),))
    back = sheet_carrier.take_drawing(written, read, "top.kicad_sch")
    assert back.sheets[0].title_block == block
