# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``gullwing`` family (change c0260, scenarios "A gull-wing record is drawn", "SOT-23 sides", "Dual-row
top view")."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fenolite.catalog.footprints import generate
from fenolite.catalog.footprints.lands import Goals, LandTable
from fenolite.catalog.footprints.record import Package

Record = Callable[..., Package]


def _pads(result: Any) -> dict[str, Any]:
    assert result.footprint is not None
    return {pad.number: pad for pad in result.footprint.pads}


def test_dual_row_top_view(record: Record) -> None:
    pads = _pads(generate(record("soic8")))
    assert (pads["1"].position.x, pads["1"].position.y) == (-2_750_000, -1_905_000)
    assert (pads["4"].position.x, pads["4"].position.y) == (-2_750_000, 1_905_000)
    assert (pads["5"].position.x, pads["5"].position.y) == (2_750_000, 1_905_000)
    assert (pads["8"].position.x, pads["8"].position.y) == (2_750_000, -1_905_000)


def test_drawing_0_keeps_the_0_6_placement(record: Record) -> None:
    pads = _pads(generate(record("soic8", lambda raw: raw["generate"].update(drawing=0))))
    assert pads["1"].position.y == 1_905_000 and pads["8"].position.y == 1_905_000
    assert pads["1"].shape == "rect" and pads["1"].corner_ratio is None


def test_sot23_sides(record: Record) -> None:
    def sot23(raw: dict[str, Any]) -> None:
        raw.update(name="SOT23_3_Test", pins=3)
        raw["side"] = [
            {"edge": "left", "numbers": ["1", "2"], "positions": [0, 2]},
            {"edge": "right", "numbers": ["3"], "positions": [1]},
        ]

    pads = _pads(generate(record("sot23_5", sot23)))
    assert pads["1"].position.x < 0 and pads["2"].position.x < 0 < pads["3"].position.x
    assert (pads["1"].position.y, pads["2"].position.y, pads["3"].position.y) == (-950_000, 950_000, 0)


def test_sot23_5_numbers(record: Record) -> None:
    pads = _pads(generate(record("sot23_5")))
    assert [pads[n].position.y for n in "123"] == [-950_000, 0, 950_000]
    assert (pads["5"].position.y, pads["4"].position.y) == (-950_000, 950_000)
    assert {abs(p.position.x) for p in pads.values()} == {1_300_000}


def _qfp(raw: dict[str, Any]) -> None:
    raw.update(name="QFP16_Test", pins=16, pitch="0.65mm", arrangement="quad")
    raw.pop("span")
    raw.update(span_x="5.80mm..6.20mm", span_y="5.80mm..6.20mm")
    raw["body"] = {"length": "3.80mm..4.00mm", "width": "3.80mm..4.00mm"}
    raw["land"] = {
        "source": "S-0855 test",
        "pad": {"length": "1.0mm", "width": "0.4mm"},
        "row_spacing_x": "5.4mm",
        "row_spacing_y": "5.4mm",
    }


def test_quad_numbering_and_axes(record: Record) -> None:
    pads = _pads(generate(record("soic8", _qfp)))
    order = [pads[str(n)] for n in range(1, 17)]
    left, bottom, right, top = order[0:4], order[4:8], order[8:12], order[12:16]
    assert all(p.position.x == -2_700_000 for p in left) and [p.position.y for p in left] == sorted(
        p.position.y for p in left
    )
    assert all(p.position.y == 2_700_000 for p in bottom) and [p.position.x for p in bottom] == sorted(
        p.position.x for p in bottom
    )
    assert all(p.position.x == 2_700_000 for p in right) and [p.position.y for p in right] == sorted(
        (p.position.y for p in right), reverse=True
    )
    assert all(p.position.y == -2_700_000 for p in top)
    assert order[0].position.y < 0  # pin 1 at the upper left
    assert all(p.size.w > p.size.h for p in left + right) and all(p.size.h > p.size.w for p in top + bottom)


def test_quad_corners_keep_the_pad_gap(record: Record) -> None:
    def crowded(raw: dict[str, Any]) -> None:
        _qfp(raw)
        raw.pop("land")
        raw.update(span_x="4.60mm..4.80mm", span_y="4.60mm..4.80mm", name="QFP16_Crowded")
        raw["lead"] = {"length": "0.40mm..0.60mm", "width": "0.25mm..0.35mm"}

    table = LandTable(version=1, goals={"gullwing": Goals(300_000, 700_000, 30_000)})
    result = generate(record("soic8", crowded), table=table)
    pads = _pads(result)
    assert "package.pads-clipped" in [i.code for i in result.issues]
    left, top = pads["1"], pads["16"]
    dx = max(0, (top.position.x - top.size.w // 2) - (left.position.x + left.size.w // 2))
    dy = max(0, (left.position.y - left.size.h // 2) - (top.position.y + top.size.h // 2))
    assert dx * dx + dy * dy >= table.pad_gap**2


def test_tab_from_the_manufacturer_land(record: Record) -> None:
    def tab(raw: dict[str, Any]) -> None:
        raw.update(name="SOT223_Test", pins=4)
        raw["side"] = [{"edge": "left", "numbers": ["1", "2", "3"], "positions": [0, 1, 2]}]
        raw["tab"] = {"number": "4", "width": "2.9mm..3.1mm", "length": "0.3mm..0.6mm", "edge": "right"}
        raw["land"]["tab"] = {"length": "1.1mm", "width": "3.2mm", "at": "1.3mm"}

    pads = _pads(generate(record("sot23_5", tab)))
    assert (pads["4"].position.x, pads["4"].position.y) == (1_300_000, 0)
    assert (pads["4"].size.w, pads["4"].size.h) == (1_100_000, 3_200_000)


def test_tab_without_goals(record: Record) -> None:
    def tab(raw: dict[str, Any]) -> None:
        raw.update(name="SOT223_Test", pins=4)
        raw.pop("land")
        raw["side"] = [{"edge": "left", "numbers": ["1", "2", "3"], "positions": [0, 1, 2]}]
        raw["tab"] = {"number": "4", "width": "2.9mm..3.1mm", "length": "0.3mm..0.6mm", "edge": "right"}

    result = generate(record("sot23_5", tab))
    assert result.footprint is None and [i.code for i in result.issues] == ["package.no-goals"]
    assert "smd-tab" in result.issues[0].message


def test_fine_pitch_class(record: Record) -> None:
    def fine(raw: dict[str, Any]) -> None:
        raw.update(name="SSOP8_Test", pitch="0.5mm")
        raw["lead"] = {"length": "0.40mm..1.27mm", "width": "0.17mm..0.27mm"}
        raw.pop("land")

    result = generate(record("soic8", fine), table=LandTable(version=1, goals={"gullwing": Goals(1, 1, 1)}))
    assert [i.code for i in result.issues] == ["package.no-goals"] and "gullwing-fine" in result.issues[
        0
    ].message
