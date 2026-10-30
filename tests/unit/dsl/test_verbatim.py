# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Verbatim items in the DSL (capability design-dsl, "Verbatim items in the DSL"; change c0277): recorded as
given, never parsed by the DSL."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, DslError, Part, mm, to_model


def test_recorded_not_parsed() -> None:
    """Scenario "Recorded, not parsed"."""
    design = Design("v")
    design.board(mm(20), mm(20))
    design.verbatim("art/qr", "(barcode (at 120 80))")
    design.verbatim("rule/hv", '(rule "hv" (constraint clearance (min 2mm)))', target="kicad_dru")
    part = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603")
    part.verbatim("mark", "(fp_line (start 0 0) (end 1 0))")
    design.add(part)
    assert design.verbatim_items["art/qr"] == ("(barcode (at 120 80))", "kicad_pcb")
    board = to_model(design).board
    assert board is not None
    items = {item.key: item for item in board.verbatim}
    assert set(items) == {"art/qr", "rule/hv", "R1/mark"}
    assert items["R1/mark"].target == "footprint" and items["R1/mark"].component_id is not None
    assert items["art/qr"].text == "(barcode (at 120 80))"
    for bad, match in (("", "text"), ("   ", "text")):
        with pytest.raises(DslError, match=match):
            design.verbatim("bad", bad)
    with pytest.raises(DslError, match="already used"):
        design.verbatim("art/qr", "(x)")
    with pytest.raises(DslError, match="target"):
        design.verbatim("t", "(x)", target="kicad_sch")
    with pytest.raises(DslError, match="key"):
        design.verbatim("a b", "(x)")
    with pytest.raises(DslError, match="already used"):
        part.verbatim("mark", "(x)")
