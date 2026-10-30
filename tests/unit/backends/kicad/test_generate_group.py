# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The generator extensions of the role copper (change c0243, decisions 3, 6 and 7; capability net-roles,
"Power and switch-node copper"): band records of one ``group`` united into one zone, a barrier over a net
set resolved after the bands, and stitching limited to a patch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest
from _buildhelp import blink, build

import fenolite.dsl as dsl
from fenolite.core.coords import Point
from fenolite.dsl import BOARD_ORIGIN
from fenolite.geometry import Location, Polygon, area2, point_in_ring
from fenolite.lens.build import BuildOutput
from fenolite.model.board import Zone

GROUP = "role.power.VIN.B_Cu"


def mm(value: float) -> int:
    """``value`` millimetres in nanometres."""
    return round(value * 1_000_000)


def _at(x: float, y: float) -> Point:
    return Point(BOARD_ORIGIN.x + mm(x), BOARD_ORIGIN.y + mm(y))


@dataclass(frozen=True, slots=True)
class Band:
    """A band record as another package makes one: the c0224 attributes, with a ``group``."""

    call: ClassVar[str] = "band"
    name: str
    net: str
    spine: tuple[Point, ...]
    width: int
    max_width: int
    step: int
    layers: tuple[str, ...]
    clearance: int | None = mm(1)
    priority: int = 2
    group: str | None = GROUP
    connection: str | None = None

    @property
    def key(self) -> str:
        return f"{self.call}.{self.name}"


@dataclass(frozen=True, slots=True)
class Barrier:
    call: ClassVar[str] = "barrier"
    name: str
    nets: tuple[str, ...]
    setback: int
    layers: tuple[str, ...]
    forbid: tuple[str, ...] = ("tracks", "vias", "pours")
    pieces: bool = True
    netclass: str = ""

    @property
    def key(self) -> str:
        return self.name  # a role record is keyed by its name, ``role.*``


@dataclass(frozen=True, slots=True)
class Stitch:
    call: ClassVar[str] = "stitch_pieces"
    name: str
    net: str
    pitch: int
    layers: tuple[str, ...]
    min_vias: int = 2
    diameter: int | None = mm(0.6)
    drill: int | None = mm(0.3)
    clearance: int | None = mm(0.2)
    margin: int = 0
    patch: tuple[Point, ...] | None = None
    avoid: tuple[tuple[Point, ...], ...] = ()

    @property
    def key(self) -> str:
        return self.name


ACROSS = Band("role.power.VIN.0", "VIN", (_at(26, 24.5), _at(46, 24.5)), mm(3), mm(6), mm(1.5), ("B.Cu",))
UP = Band("role.power.VIN.1", "VIN", (_at(36, 24.5), _at(36, 12)), mm(3), mm(6), mm(1.5), ("B.Cu",))


def _zones(output: BuildOutput, prefix: str) -> list[Zone]:
    board = output.design.board
    assert board is not None
    return [zone for zone in board.zones if zone.name.startswith(prefix)]


def _errors(output: BuildOutput) -> list[str]:
    return [found.code for found in output.issues if found.severity == "error"]


def test_one_band_of_a_group_needs_no_union() -> None:
    output = build(blink(), generated_copper=(ACROSS,))
    assert _errors(output) == []
    (zone,) = _zones(output, "role.")
    assert zone.name == GROUP and zone.locked and zone.priority == 2 and zone.settings.clearance == mm(1)
    assert not _zones(output, "band.")


def test_a_branching_group_is_one_zone() -> None:
    """Two bands of a T: one zone that holds both outlines, so KiCad sees no ``zones_intersect``."""
    alone = {band.name: _zones(build(blink(), generated_copper=(band,)), "role.")[0] for band in (ACROSS, UP)}
    output = build(blink(), generated_copper=(UP, ACROSS))
    assert _errors(output) == []
    (zone,) = _zones(output, "role.")
    assert zone.name == GROUP and Polygon(zone.outline).is_simple()
    for single in alone.values():
        for point in single.outline:
            assert point_in_ring(point, zone.outline) is not Location.OUTSIDE
    total = sum(abs(area2(single.outline)) for single in alone.values())
    assert max(abs(area2(s.outline)) for s in alone.values()) < abs(area2(zone.outline)) < total


def test_a_group_without_the_union(monkeypatch: pytest.MonkeyPatch) -> None:
    from fenolite.geometry import boolean
    from fenolite.geometry.errors import backend_unavailable

    def missing(prefer: str | None = None, *, operation: str | None = None) -> object:
        raise backend_unavailable("no union", where="union")

    monkeypatch.setattr(boolean, "select_backend", missing)
    output = build(blink(), generated_copper=(UP, ACROSS))
    (found,) = [i for i in output.issues if i.severity == "error"]
    assert found.code == "kicad.generate.unknown" and "geo extra" in found.message
    assert not _zones(output, "role.")


def test_the_connection_of_a_role_band() -> None:
    output = build(blink(), generated_copper=(Band(**{**_fields(ACROSS), "connection": "solid"}),))
    (zone,) = _zones(output, "role.")
    assert zone.settings.connection == "solid"


def _fields(band: Band) -> dict[str, object]:
    return {name: getattr(band, name) for name in Band.__slots__}  # type: ignore[attr-defined]


def test_a_net_barrier_holds_the_band() -> None:
    """A barrier over ``nets``, resolved after the bands: its outer hull holds the band of the net."""
    barrier = Barrier("role.hv.VIN", ("VIN",), mm(1), ("B.Cu",))
    output = build(blink(), generated_copper=(barrier, ACROSS))
    assert _errors(output) == []
    (zone,) = _zones(output, "role.power")
    board = output.design.board
    assert board is not None
    areas = [area for area in board.keepouts if area.name.startswith("role.hv.VIN.")]
    assert areas and all(area.no_copper_pour and area.no_tracks for area in areas)
    xs = [p.x for area in areas for p in area.outline]
    ys = [p.y for area in areas for p in area.outline]
    for point in zone.outline:
        assert min(xs) < point.x < max(xs) and min(ys) < point.y < max(ys)
    for area in areas:  # the barrier's inner edge may touch the band, never enter it
        assert not any(point_in_ring(q, zone.outline) is Location.INSIDE for q in area.outline)
        assert not any(point_in_ring(q, area.outline) is Location.INSIDE for q in zone.outline)


def _pours(design: dsl.Design) -> None:
    gnd = design.nets["GND"]
    corners = ((2, 2), (48, 2), (48, 28), (2, 28))
    design.zone(
        gnd, layers=("F.Cu",), name="GND_TOP", outline=tuple((dsl.mm(x), dsl.mm(y)) for x, y in corners)
    )
    design.zone(gnd, layers=("B.Cu",), name="GND_BOT")


def test_stitches_limited_to_a_patch() -> None:
    """Vias only inside the patch and outside the rings to avoid; the count is that of the patch."""
    patch = (_at(4, 4), _at(14, 4), _at(14, 10), _at(4, 10))
    avoid = ((_at(4, 4), _at(8, 4), _at(8, 10), _at(4, 10)),)
    design = blink()
    _pours(design)
    stitch = Stitch("role.via.GND", "GND", mm(1.2), ("F.Cu", "B.Cu"), min_vias=5, patch=patch, avoid=avoid)
    output = build(design, generated_copper=(stitch,), copper_intents=dsl.copper(design))
    assert _errors(output) == []
    board = output.design.board
    assert board is not None
    assert len(board.vias) >= 5
    for via in board.vias:
        assert point_in_ring(via.position, patch) is Location.INSIDE
        assert point_in_ring(via.position, avoid[0]) is Location.OUTSIDE
    short = Stitch("role.via.GND", "GND", mm(1.2), ("F.Cu", "B.Cu"), min_vias=500, patch=patch)
    design = blink()
    _pours(design)
    output = build(design, generated_copper=(short,), copper_intents=dsl.copper(design))
    (found,) = [i for i in output.issues if i.code == "kicad.generate.stitch-short"]
    assert "the patch" in found.message and "fewer than 500" in found.message
