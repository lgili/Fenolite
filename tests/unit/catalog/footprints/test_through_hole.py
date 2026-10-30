# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Through-hole lands of ``dip``, ``to`` and ``header`` (change c0260, requirement "Through-hole lands",
scenario "DIP drill")."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fenolite.catalog.footprints import generate
from fenolite.catalog.footprints.lands import LandTable
from fenolite.catalog.footprints.record import Package

Record = Callable[..., Package]


def test_dip_drill(record: Record) -> None:
    def thick(raw: dict[str, Any]) -> None:
        raw["lead"] = {"width": "0.35mm..0.56mm", "thickness": "0.20mm..0.38mm", "length": "2.92mm..3.81mm"}

    table = LandTable(version=1, hole_clearance=230_000, annular_ring=350_000)
    result = generate(record("dip8", thick), table=table)
    fp = result.footprint
    assert fp is not None
    assert {pad.drill for pad in fp.pads} == {910_000}
    assert {pad.size.w for pad in fp.pads} == {910_000 + 2 * 350_000}
    assert result.land.drill == 910_000 and result.land.pad_diameter == 1_610_000


def test_dip_with_lands_1(record: Record) -> None:
    fp = generate(record("dip8")).footprint
    assert fp is not None and fp.kind == "through_hole"
    pads = {pad.number: pad for pad in fp.pads}
    # The 626-05 lead: 0.56 x 0.36 mm max, diagonal 665 733 nm, plus 0.2 mm, up to the grid.
    assert pads["1"].drill == 870_000 and pads["1"].size.w == 870_000 + 700_000
    assert pads["1"].shape == "rect" and {pads[n].shape for n in "2345678"} == {"circle"}
    assert (pads["1"].position.x, pads["1"].position.y) == (-3_810_000, -3_810_000)
    assert (pads["8"].position.x, pads["8"].position.y) == (3_810_000, -3_810_000)
    assert pads["1"].layers == ("*.Cu", "*.Mask") and pads["1"].kind == "thru_hole"


def test_wide_pads_become_ovals(record: Record) -> None:
    result = generate(record("to220"))
    fp = result.footprint
    assert fp is not None
    clipped = [i for i in result.issues if i.code == "package.pads-clipped"]
    assert len(clipped) == 1 and clipped[0].severity == "warning"
    pads = {pad.number: pad for pad in fp.pads}
    assert pads["2"].shape == "oval" and pads["2"].size.w == 2_540_000 - 200_000
    assert pads["1"].shape == "rect"  # pad 1 square-cornered under drawing/1
    assert [pads[n].position.x for n in "123"] == [-2_540_000, 0, 2_540_000]


def test_header_numbering(record: Record) -> None:
    fp = generate(record("header1x2")).footprint
    assert fp is not None and [(p.number, p.position.x) for p in fp.pads] == [
        ("1", -1_270_000),
        ("2", 1_270_000),
    ]

    def two_rows(raw: dict[str, Any]) -> None:
        raw.update(name="HDR2x3_P2.54", rows=2, columns=3)

    rows_first = {p.number: p.position for p in generate(record("header1x2", two_rows)).footprint.pads}  # type: ignore[union-attr]
    assert (rows_first["1"].x, rows_first["1"].y) == (-2_540_000, -1_270_000)
    assert (rows_first["2"].x, rows_first["2"].y) == (-2_540_000, 1_270_000)

    def columns_first(raw: dict[str, Any]) -> None:
        two_rows(raw)
        raw["numbering"] = "columns-first"

    columns = {p.number: p.position for p in generate(record("header1x2", columns_first)).footprint.pads}  # type: ignore[union-attr]
    assert (columns["2"].x, columns["2"].y) == (0, -1_270_000) and (columns["4"].x, columns["4"].y) == (
        -2_540_000,
        1_270_000,
    )


def test_no_hole_constants(record: Record) -> None:
    result = generate(record("dip8"), table=LandTable(version=1))
    assert result.footprint is None and [i.code for i in result.issues] == ["package.no-goals"]


def test_smd_to_with_tab(record: Record) -> None:
    def dpak(raw: dict[str, Any]) -> None:
        raw.update(mount="smd", name="TO3_DPAK_Test", span="9.40mm..10.40mm")
        raw["tab"] = {"width": "5.0mm..5.5mm", "length": "1.0mm..1.6mm", "number": "2"}
        raw["land"] = {
            "source": "S-0377 test",
            "pad": {"length": "2.6mm", "width": "1.1mm"},
            "row_spacing": "8.6mm",
            "tab": {"length": "5.7mm", "width": "5.6mm", "at": "2.5mm"},
        }

    fp = generate(record("to220", dpak)).footprint
    assert fp is not None
    pads = {p.number: p for p in fp.pads}
    assert set(pads) == {"1", "2", "3"}  # lead 2 is the tab
    assert pads["1"].position.y == 4_300_000 and pads["2"].position.y == -2_500_000
    assert (pads["2"].size.w, pads["2"].size.h) == (5_600_000, 5_700_000)
