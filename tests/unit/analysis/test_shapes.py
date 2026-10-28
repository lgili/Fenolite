# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pour-shape checks of change c0213 (capability board-analyses, "Neck kind", "Tips and slivers", "Loop
kind", "Balance kind" and "Pour shape tables"), on the authored benches of ``tests/_shapebench.py``."""

from __future__ import annotations

import pytest
from _shapebench import GRID, balance, loop, neck, tips

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.pour import PourCopper, pour_copper
from fenolite.analysis.requirements import SCHEMA, LoopReq, NeckReq, NetSelector, load_requirements
from fenolite.analysis.shapes import (
    BalanceRow,
    LoopRow,
    NeckRow,
    analyze_balance,
    analyze_loops,
    analyze_necks,
    cell_widths,
    loop_areas,
)
from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.frame import board_pads
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Level
from fenolite.model.design import Design

MM = 1_000_000
HEAD = f'schema = "{SCHEMA}"\n'
NECK = HEAD + '[[neck]]\nselect = { net = "GND" }\nmin_width_nm = 500000\n'
LOOPS = HEAD + "".join(
    f'[[loop]]\nname = "{name}"\npads = ["U1-4", "{name}-1", "{name}-2", "U1-2"]\n'
    f"max_area_nm2 = {10 * MM * MM}\n"
    for name in ("C1", "C2")
)


def poured(design: Design, grid: int = GRID) -> tuple[tuple[BoardPad, ...], PourCopper]:
    assert design.board is not None
    pads = board_pads(design)
    return pads, pour_copper(design, pads=pads, boundary=board_boundary(design.board), grid=grid)


# --- tables ---------------------------------------------------------------------------------------------


def test_tables_load_and_refuse() -> None:
    """Scenario "The two tables load"."""
    loaded = load_requirements(NECK + '[[loop]]\nname = "gate"\npads = ["Q1-1", "U1-3"]\n')
    assert loaded.necks == (NeckReq(NetSelector(net="GND"), 500_000),)
    assert loaded.loops == (LoopReq("gate", ("Q1-1", "U1-3"), None),)
    bad = (
        ('[[neck]]\nselect = { net = "GND" }\nmin_width_nm = 0.5\n', "min_width_nm"),
        ('[[loop]]\nname = "gate"\npads = ["Q1-1"]\n', "pads"),
        (
            '[[loop]]\nname = "a"\npads = ["Q1-1", "U1-1"]\n[[loop]]\nname = "a"\npads = ["Q1-1", "U1-1"]\n',
            "name",
        ),
    )
    for text, key in bad:
        with pytest.raises(FormatError, match=key):
            load_requirements(HEAD + text, file="req.toml")
    with pytest.raises(FormatError, match="unknown key"):
        load_requirements(HEAD + '[[loop]]\nname = "a"\npads = ["Q1-1", "U1-1"]\narea = 1\n')


# --- necks, tips and slivers ----------------------------------------------------------------------------


def test_necks_of_a_pour() -> None:
    """Scenario "A neck of a pour": the 0.3 mm band between the two keep-outs, on a raster of 0.05 mm."""
    design = neck()
    _, pour = poured(design)
    assert [(z.state, z.layer) for z in pour.zones] == [("saved_fill", "F.Cu")]
    report = analyze_necks(design, pour=pour, requirements=load_requirements(NECK))
    (row,) = report.rows
    assert isinstance(row, NeckRow) and (row.net, row.layer, row.shape) == ("GND", "F.Cu", "neck")
    assert row.width == 300_000 and row.limit == 500_000 and row.copper == ("saved_fill",)
    assert 20 * MM < row.at.x < 22 * MM and 14_850_000 < row.at.y < 15_150_000
    assert [i.code for i in report.issues] == ["analysis.neck-narrow"]
    assert report.issues[0].severity == "error" and report.evidence.level is Level.INFERRED
    assert report.summary == {"nets": 1, "necks": 1, "tips": 0, "slivers": 0, "skipped": 0}
    # a row of 0.3 mm or less finds nothing: the band is as wide as the row
    level = load_requirements(HEAD + '[[neck]]\nselect = { netclass = "*" }\nmin_width_nm = 300000\n')
    assert analyze_necks(design, pour=pour, requirements=level).rows == ()


def test_necks_without_a_row_or_matching_none() -> None:
    """Scenario "Neck rows missing or unmatched"."""
    design = neck()
    _, pour = poured(design)
    bare = analyze_necks(design, pour=pour, requirements=None)
    assert bare.rows == () and [(i.code, i.where) for i in bare.issues] == [
        ("analysis.input-missing", "neck")
    ]
    other = load_requirements(HEAD + '[[neck]]\nselect = { net = "VBUS" }\nmin_width_nm = 500000\n')
    unmatched = analyze_necks(design, pour=pour, requirements=other)
    assert unmatched.rows == ()
    assert [(i.code, i.where) for i in unmatched.issues] == [("analysis.requirement-unmatched", "net VBUS")]


def test_tips_and_slivers() -> None:
    """Scenario "A finger and a strip": the finger is a tip 3 mm long, the strip a sliver; the corners of the
    square reach a fraction of the width and are no tip."""
    design = tips()
    _, pour = poured(design)
    report = analyze_necks(design, pour=pour, requirements=load_requirements(NECK))
    rows = [row for row in report.rows if isinstance(row, NeckRow)]
    assert [(row.shape, row.width) for row in rows] == [("tip", 300_000), ("sliver", 300_000)]
    tip, sliver = rows
    assert tip.extent == 3 * MM and 20 * MM < tip.at.x < 23 * MM
    assert sliver.extent is None and 25 * MM < sliver.at.x < 25_300_000
    assert [i.code for i in report.issues] == ["analysis.neck-narrow"] * 2


def test_cell_widths_of_bands() -> None:
    """A run along an axis is ``n·g``; a diagonal run ``n·g·√2`` rounded down."""
    band = {(i, j) for i in range(10) for j in range(3)}
    widths = cell_widths(band, 100)
    assert widths[(5, 1)] == 300 and widths[(0, 0)] == 141  # a corner: one cell along a diagonal
    assert cell_widths({(0, 0), (1, 1), (2, 2)}, 100)[(1, 1)] == 100


# --- loops ----------------------------------------------------------------------------------------------


def test_loops_and_their_baseline() -> None:
    """Scenario "Two decoupling loops": legs along copper where the pads share a net and copper joins them."""
    design = loop()
    pads, pour = poured(design, MM // 4)
    report = analyze_loops(design, pads=pads, pour=pour, requirements=load_requirements(LOOPS))
    first, second = (row for row in report.rows if isinstance(row, LoopRow))
    assert (first.name, first.area_nm2, second.name, second.area_nm2) == (
        "C1",
        3 * MM * MM,
        "C2",
        20 * MM * MM,
    )
    assert [leg.kind for leg in first.legs] == ["copper", "straight", "copper", "straight"]
    assert [leg.kind for leg in second.legs] == ["copper", "straight", "straight", "straight"]
    assert second.legs[0].length == 10 * MM and report.evidence.level is Level.INFERRED
    assert [(i.code, i.where) for i in report.issues] == [("analysis.loop-area", "C2")]
    # against the board where C2 sits 5 mm from U1: C2 grew by 10 mm², C1 did not change
    other = loop(far=25)
    other_pads, other_pour = poured(other, MM // 4)
    rows, _ = loop_areas(other, pads=other_pads, pour=other_pour, requirements=load_requirements(LOOPS))
    baseline = {row.name: row.area_nm2 for row in rows}
    compared = analyze_loops(
        design, pads=pads, pour=pour, requirements=load_requirements(LOOPS), baseline=baseline
    )
    changes = [
        (row.name, row.baseline_nm2, row.change_nm2) for row in compared.rows if isinstance(row, LoopRow)
    ]
    assert changes == [("C1", 3 * MM * MM, 0), ("C2", 10 * MM * MM, 10 * MM * MM)]


def test_loops_without_rows_and_with_a_missing_pad() -> None:
    design = loop()
    pads, pour = poured(design, MM // 4)
    bare = analyze_loops(design, pads=pads, pour=pour, requirements=None)
    assert bare.rows == () and [i.code for i in bare.issues] == ["analysis.input-missing"]
    text = HEAD + '[[loop]]\nname = "gate"\npads = ["U1-4", "Q9-1"]\n'
    report = analyze_loops(design, pads=pads, pour=pour, requirements=load_requirements(text))
    (row,) = report.rows
    assert isinstance(row, LoopRow) and row.area_nm2 is None
    assert [(i.code, i.where) for i in report.issues] == [("analysis.requirement-unmatched", "gate")]


# --- balance --------------------------------------------------------------------------------------------


def test_balance_of_a_two_pad_part() -> None:
    """Scenario "A pad on a pour and a pad on a track": the 3 mm window of pad 1 is all fill but the pad,
    that of pad 2 holds 1 mm of the 0.5 mm track."""
    design = balance()
    pads, pour = poured(design, MM // 4)
    report = analyze_balance(design, pads=pads, pour=pour)
    (row,) = report.rows
    assert isinstance(row, BalanceRow) and (row.part, row.pads, row.layer) == ("R1", ("R1-1", "R1-2"), "F.Cu")
    assert row.copper_nm2 == (8 * MM * MM, MM * MM // 2) and row.ratio_permille == 16_000
    assert report.issues == () and report.evidence.level is Level.INFERRED
    # U1, C1 and C2 of the loop bench each have two SMD pads on F.Cu; nothing is judged
    others = analyze_balance(loop(), pads=board_pads(loop()), pour=poured(loop(), MM // 4)[1])
    assert [row.part for row in others.rows if isinstance(row, BalanceRow)] == ["C1", "C2", "U1"]
