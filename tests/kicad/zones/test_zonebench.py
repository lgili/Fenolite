# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The zone bench is sound without ``kicad-cli`` (change c0031): its boards parse and read back for both
targets, its exact measurement helpers give known answers on authored rings, and the Gerber helper reads
an authored plot (``docs/formats/kicad/gerber.md``)."""

from __future__ import annotations

from fractions import Fraction

import _gerber
import _zonebench as zb
import pytest

from fenolite.backends.kicad import zones
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.core.coords import Point
from fenolite.model.board import ZoneSettings

MM = zb.MM


def square(x0: float, y0: float, x1: float, y1: float) -> tuple[Point, ...]:
    return (zb.mm(x0, y0), zb.mm(x1, y0), zb.mm(x1, y1), zb.mm(x0, y1))


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("name", sorted(zb.CASES))
def test_every_case_parses_and_reads_back(name: str, target: int) -> None:
    text = zb.case_text(zb.CASES[name], target)
    zone = zb.zone_node(parse(text))
    assert [c.name for c in zone.nodes() if c.name in zb.SETTING_HEADS] == list(zb.SETTING_HEADS)
    assert (zone.find("filled_areas_thickness") is not None) == (target == 9)
    design = read_board(text)
    assert design.board is not None
    assert [z.name for z in design.board.zones] == [zb.ZONE_NAME]
    assert [len(fp.pads) for fp in design.board.footprints] == [2, 2]
    assert len(design.board.tracks) == 6


def test_pad_and_footprint_overrides_are_written() -> None:
    text = zb.case_text(zb.CASES["fp-2-pad-1"], 10)
    footprint = parse(text).nodes("footprint")[0]
    assert footprint.find("zone_connect") == zb._fragments("(zone_connect 2)")[0]
    pads = {p.atoms()[0].value: p.find("zone_connect") for p in footprint.nodes("pad")}
    assert pads["1"] == zb._fragments("(zone_connect 1)")[0] and pads["2"] is None


def test_defaults_literal_is_what_the_emitter_writes() -> None:
    emitted = zones.emit_settings(ZoneSettings(), filled=False, locked=False, major=10)
    assert list(emitted.values()) == zb._fragments(zb.DEFAULTS_T10)


def test_zone_children_per_target() -> None:
    for target in (9, 10):
        zone = zb.zone_node(parse(zb.case_text(zb.CASES["island-below-50"], target)))
        fill = zone.find("fill")
        assert fill is not None
        assert [c.name for c in fill.nodes()][-2:] == ["island_removal_mode", "island_area_min"]
        assert fill.find("island_area_min") == zb._fragments("(island_area_min 50)")[0]
        assert zone.find("hatch") == zones.HATCH_EDGE
    nine = zb.zone_node(parse(zb.case_text(zb.CASES["thermal"], 9))).find("fill")
    ten = zb.zone_node(parse(zb.case_text(zb.CASES["thermal"], 10))).find("fill")
    assert nine is not None and nine.find("island_removal_mode") is None
    assert ten is not None and ten.find("island_removal_mode") is not None


def test_case_settings_reach_the_model() -> None:
    for name, case in zb.CASES.items():
        design = read_board(zb.case_text(case, 10))
        assert design.board is not None
        (zone,) = design.board.zones
        assert zone.settings.effective() == case.zone_settings.effective(), name
        assert zone.filled is case.filled


def test_in_fill_and_crossings() -> None:
    rings = [square(0, 0, 10, 10)]
    assert zb.in_fill(zb.mm(5, 5), rings) and not zb.in_fill(zb.mm(11, 5), rings)
    assert zb.crossings(zb.mm(-1, 5), zb.mm(11, 5), rings) == [
        (Fraction(0), Fraction(5 * MM)),
        (10 * MM, 5 * MM),
    ]
    assert zb.spans(zb.mm(-1, 5), zb.mm(11, 5), rings) == [(False, MM), (True, 10 * MM), (False, MM)]
    with pytest.raises(ValueError, match="axis-aligned"):
        zb.crossings(zb.mm(0, 0), zb.mm(1, 2), rings)


def test_a_slit_of_no_width_is_copper() -> None:
    # an outline joined to a square hole by a slit along y = 5 mm (the way KiCad writes a fill with a hole)
    ring = (
        zb.mm(0, 0), zb.mm(10, 0), zb.mm(10, 10), zb.mm(0, 10), zb.mm(0, 5), zb.mm(4, 5), zb.mm(4, 6),
        zb.mm(6, 6), zb.mm(6, 4), zb.mm(4, 4), zb.mm(4, 5), zb.mm(0, 5),
    )  # fmt: skip
    assert zb.in_fill(zb.mm(2, 5), [ring]) and not zb.in_fill(zb.mm(5, 5), [ring])
    assert zb.spans(Point(2 * MM, 1 * MM), Point(2 * MM, 9 * MM), [ring]) == [(True, 8 * MM)]
    assert zb.spans(Point(5 * MM, 1 * MM), Point(5 * MM, 9 * MM), [ring]) == [
        (True, 3 * MM), (False, 2 * MM), (True, 3 * MM)
    ]  # fmt: skip


def test_gap_to_pad() -> None:
    rect = zb.Spot("r", zb.mm(5, 5), 2 * MM, False)
    disc = zb.Spot("c", zb.mm(5, 5), 2 * MM, True)
    hole = square(3.5, 3.5, 6.5, 6.5)
    assert zb.gap_to_pad(rect, [hole]) == 500_000
    assert zb.gap_to_pad(disc, [hole]) == 500_000
    assert zb.gap_to_pad(disc, [square(7, 0, 9, 10)]) == MM


def _box(x0: int, y0: int, x1: int, y1: int) -> tuple[Point, ...]:
    return (Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1))


def _thermal_rings(spot: zb.Spot, gap: int, spoke: int) -> list[tuple[Point, ...]]:
    """A frame of copper ``gap`` away from the pad, joined to it by four spokes on the axes."""
    c, inner, outer, half = spot.centre, spot.size // 2, spot.size // 2 + gap, spoke // 2
    far = outer + MM
    return [
        _box(c.x - far, c.y - far, c.x + far, c.y - outer),
        _box(c.x - far, c.y + outer, c.x + far, c.y + far),
        _box(c.x - far, c.y - outer, c.x - outer, c.y + outer),
        _box(c.x + outer, c.y - outer, c.x + far, c.y + outer),
        _box(c.x + inner, c.y - half, c.x + outer, c.y + half),
        _box(c.x - outer, c.y - half, c.x - inner, c.y + half),
        _box(c.x - half, c.y + inner, c.x + half, c.y + outer),
        _box(c.x - half, c.y - outer, c.x + half, c.y - inner),
    ]


def test_patterns_and_thermal_measurements() -> None:
    spot = zb.GND_SMD
    rings = _thermal_rings(spot, 400_000, 350_000)
    assert zb.pattern(spot, 400_000, rings) == "axes"
    assert zb.spoke_width(spot, 400_000, rings) == 350_000
    assert zb.relief_gap(spot, rings) == 400_000
    c = spot.centre
    assert (
        zb.pattern(spot, 400_000, [square(c.x / MM - 5, c.y / MM - 5, c.x / MM + 5, c.y / MM + 5)]) == "solid"
    )
    assert zb.pattern(spot, 400_000, [square(30, 20, 31, 21)]) == "none"
    probes = zb.round_probes(zb.GND_THT, 500_000)
    assert set(probes) == {*zb.AXES, *zb.DIAGONALS}
    diagonal = probes["se"]
    assert diagonal.x - zb.GND_THT.centre.x == diagonal.y - zb.GND_THT.centre.y == 777_817


def test_hatch_spans_on_an_authored_grid() -> None:
    bars = [square(15 + 2.5 * k, 20, 16 + 2.5 * k, 29) for k in range(9)]
    rows = zb.hatch_spans(bars)
    assert len(rows) == len(zb.HATCH_ROWS)
    assert all(length == (MM if inside else 1_500_000) for row in rows for inside, length in row)


GERBER = """\
G04 authored for the Fenolite tests*
%FSLAX46Y46*%
%MOMM*%
%LPD*%
G01*
D10*
X1000000Y-1000000D02*
X2000000D01*
G36*
X26000000Y-6000000D02*
G01X34000000D01*
Y-14000000D01*
X26000000D01*
Y-6000000D01*
G37*
G36*
X0Y0D02*
X-1500000Y250000D01*
X0Y500000D01*
G37*
M02*
"""


def test_region_extents() -> None:
    assert _gerber.region_extents(GERBER) == [
        (26_000_000, -14_000_000, 34_000_000, -6_000_000),
        (-1_500_000, 0, 0, 500_000),
    ]


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("%FSLAX46Y46*%", "%FSLAX36Y36*%", "FSLAX46Y46"),
        ("%MOMM*%", "%MOIN*%", "MOMM"),
        ("G01X34000000D01*", "G02X34000000I1J1D01*", "arc"),
        ("G37*\nM02*", "M02*", "not closed"),
    ],
)
def test_region_extents_refuses_what_it_does_not_read(old: str, new: str, message: str) -> None:
    assert old in GERBER
    with pytest.raises(ValueError, match=message):
        _gerber.region_extents(GERBER.replace(old, new))
