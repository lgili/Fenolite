# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored boards for the pour engine of change c0215 (capability altium-pour): small two-layer documents
written straight from a ``PcbDocSpec`` (free pads, tracks, vias, zones, keep-outs) and read back as the
engine reads them. Every value here is authored for these tests; none comes from another project.

Coordinates are millimetres in the frame of the placements (Y down), the board 40 mm by 30 mm from (0, 0).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from fenolite.backends.altium import pcbdoc, rulemap
from fenolite.backends.altium.pcbdoc import FreePad, PcbDocSpec
from fenolite.backends.altium.pour import PourMode, PourReading, PourResult, pour_reading, read_pour
from fenolite.core.coords import Point, Size
from fenolite.model.board import Keepout, Pad, PadKind, PadShape, Track, Via, Zone, ZoneSettings
from fenolite.model.rules import Rule, Selector

MM = 1_000_000
MIL = 25_400
WIDTH, HEIGHT = 40, 30
FILENAME = "pour.PcbDoc"
DEFAULT_SETTINGS = ZoneSettings()


def mm(value: float) -> int:
    return round(value * MM)


def at(x: float, y: float) -> Point:
    return Point(mm(x), mm(y))


def rect(x0: float, y0: float, x1: float, y1: float) -> tuple[Point, ...]:
    return (at(x0, y0), at(x1, y0), at(x1, y1), at(x0, y1))


OUTLINE = rect(0, 0, WIDTH, HEIGHT)


def zone(
    ident: str,
    net: str | None,
    outline: Sequence[Point] = rect(1, 1, WIDTH - 1, HEIGHT - 1),
    *,
    layer: str = "F.Cu",
    priority: int = 0,
    settings: ZoneSettings = DEFAULT_SETTINGS,
) -> Zone:
    return Zone(
        id=ident, outline=tuple(outline), layers=(layer,), net_id=net, priority=priority, settings=settings
    )


def pad(
    ident: str,
    net: str | None,
    x: float,
    y: float,
    *,
    shape: PadShape = "rect",
    size: tuple[float, float] = (1.0, 1.0),
    kind: PadKind = "smd",
    drill: float | None = None,
    rotation: int = 0,
) -> FreePad:
    layers = ("F.Cu",) if kind == "smd" else ("F.Cu", "B.Cu")
    model = Pad(
        id=ident,
        number="1",
        shape=shape,
        size=Size(mm(size[0]), mm(size[1])),
        position=at(x, y),
        kind=kind,
        rotation=rotation,
        drill=None if drill is None else mm(drill),
        layers=layers,
    )
    return FreePad(model, net=net)


def track(ident: str, net: str | None, a: tuple[float, float], b: tuple[float, float], width: float = 0.25,
          layer: str = "F.Cu") -> Track:  # fmt: skip
    return Track(id=ident, start=at(*a), end=at(*b), width=mm(width), layer=layer, net_id=net)


def via(ident: str, net: str | None, x: float, y: float, diameter: float = 0.6, drill: float = 0.3) -> Via:
    return Via(id=ident, position=at(x, y), diameter=mm(diameter), drill=mm(drill), layers=("F.Cu", "B.Cu"),
               net_id=net)  # fmt: skip


def clearance(value: float, name: str = "clearance") -> Rule:
    """A clearance rule of ``value`` mm for every object."""
    return Rule(id=f"rule_{name}", name=name, kind="clearance", selector_a=Selector("all"), min=mm(value))


@dataclass(frozen=True)
class Board:
    """An authored board: its items and the clearance rules of its design (lowered as a build lowers
    them)."""

    zones: tuple[Zone, ...]
    pads: tuple[FreePad, ...] = ()
    tracks: tuple[Track, ...] = ()
    vias: tuple[Via, ...] = ()
    keepouts: tuple[Keepout, ...] = ()
    rules: tuple[Rule, ...] = field(default=())

    def spec(self) -> PcbDocSpec:
        nets = sorted(
            {
                *(z.net_id for z in self.zones if z.net_id),
                *(p.net for p in self.pads if p.net),
                *(t.net_id for t in self.tracks if t.net_id),
                *(v.net_id for v in self.vias if v.net_id),
            }
        )
        lowered = rulemap.lower(self.rules).records if self.rules else ()
        return PcbDocSpec(
            outline=OUTLINE,
            nets=tuple(nets),
            zones=self.zones,
            free_pads=self.pads,
            tracks=self.tracks,
            vias=self.vias,
            keepouts=self.keepouts,
            design_rules=tuple(lowered),
        )

    def write(self, *, pour: PourMode = "computed") -> pcbdoc.PcbDocResult:
        return pcbdoc.write_pcbdoc_result(self.spec(), filename=FILENAME, pour=pour)

    def base(self) -> PourReading:
        """The reading of the computed document without its pour regions, which the engine pours."""
        data = pcbdoc.write_pcbdoc_result(self.spec(), filename=FILENAME, pour="computed", pour_regions=False)
        return read_pour(data.data, file=FILENAME)

    def pour(self) -> tuple[PourReading, PourResult]:
        reading = self.base()
        return reading, pour_reading(reading)
