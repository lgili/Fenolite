# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the copper-check tests (change c0029): generated thick shapes for the brute-force tests and
a small builder of designs with copper.

(``tests/_copper.py`` holds the fixtures of manual copper, change c0028.)
"""

from __future__ import annotations

import dataclasses
import math
import random
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Protocol

from fenolite.backends.base import BoardPad, PadCopper
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board, source_info, write_board
from fenolite.core.coords import Point, Size
from fenolite.core.provenance import Provenance
from fenolite.geometry import GeometryError, Thick
from fenolite.model.board import (
    Arc,
    FootprintInstance,
    Keepout,
    Pad,
    PadKind,
    Track,
    Via,
    ViaType,
    Zone,
    ZoneFill,
    ZoneSettings,
)
from fenolite.model.circuit import Circuit, Component, Net, NetClass
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleKind, RuleSeverity, Selector

KICAD_TESTS = Path(__file__).resolve().parent / "kicad"


class Bench(Protocol):
    """What ``_rulebench.Bench`` gives: a design and the KiCad uuids of its labelled items."""

    design: Design
    items: dict[str, tuple[str, ...]]

    def uuids(self, label: str) -> tuple[str, ...]: ...


SCALES = ((50, 20), (10**9, 10**7), (2_000_000, 600_000))
"""``(coordinate bound, width bound)`` of the generated cases: a tiny grid where shapes touch and tie
often, the full range of the kernel, and board-like sizes."""


def _point(rng: random.Random, bound: int, near: Point | None = None) -> Point:
    if near is not None:
        reach = max(1, bound // 8)
        return Point(near.x + rng.randint(-reach, reach), near.y + rng.randint(-reach, reach))
    return Point(rng.randint(-bound, bound), rng.randint(-bound, bound))


def _ring(rng: random.Random, bound: int, centre: Point, count: int) -> tuple[Point, ...]:
    """A star-shaped ring of ``count`` vertices around ``centre`` (simple by construction)."""
    radius = max(3, bound // 6)
    angles = sorted(rng.uniform(0, 2 * math.pi) for _ in range(count))
    return tuple(
        Point(
            centre.x + round(math.cos(angle) * rng.randint(radius // 2 + 1, radius)),
            centre.y + round(math.sin(angle) * rng.randint(radius // 2 + 1, radius)),
        )
        for angle in angles
    )


def _shape(rng: random.Random, bound: int, width_bound: int, near: Point | None) -> Thick | None:
    kind = rng.choice(("disc", "stadium", "polyline", "long", "ring", "big-ring"))
    start = _point(rng, bound, near)
    width = rng.choice((0, 1, 2, rng.randint(0, width_bound), rng.randint(0, width_bound)))
    try:
        if kind == "disc":
            return Thick((start,), max(width, 1))
        if kind == "stadium":
            return Thick((start, _point(rng, bound, start)), width)
        if kind in ("polyline", "long"):
            count = rng.randint(3, 6) if kind == "polyline" else rng.randint(18, 30)
            points = [start]
            for _ in range(count - 1):
                points.append(_point(rng, bound, points[-1]))
            return Thick(tuple(points), width)
        count = rng.randint(3, 7) if kind == "ring" else rng.randint(18, 40)
        return Thick(_ring(rng, bound, start, count), width, filled=True)
    except GeometryError:
        return None


@cache
def thick_cases(count: int = 900, seed: int = 20261004) -> tuple[tuple[Thick, Thick], ...]:
    """``count`` generated pairs of discs, stadiums, polylines and filled rings, a third per scale of
    ``SCALES``; half of the pairs are built near each other, so touching and overlapping shapes are
    common."""
    rng = random.Random(seed)
    pairs: list[tuple[Thick, Thick]] = []
    while len(pairs) < count:
        bound, width_bound = SCALES[len(pairs) % len(SCALES)]
        first = _shape(rng, bound, width_bound, None)
        if first is None:
            continue
        near = first.core[0] if rng.random() < 0.5 else None
        second = _shape(rng, bound, width_bound, near)
        if second is not None:
            pairs.append((first, second))
    return tuple(pairs)


# --- designs for the copper check -------------------------------------------------------------------

SHA = "0" * 64


def ident(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def mm(value: float) -> int:
    return round(value * 1_000_000)


def _provenance(locator: str) -> Provenance | None:
    return Provenance("kicad", "bench.kicad_pcb", SHA, locator) if locator else None


@dataclass
class Copper:
    """A design under construction for the copper-check tests: nets, classes, rules and copper items, built
    through the model API on a created board of 2 or 4 copper layers. ``pads`` collects the board-frame
    records a frame would give."""

    layers: int = 2
    nets: dict[str, Net] = field(default_factory=lambda: {})
    classes: dict[str, NetClass] = field(default_factory=lambda: {})
    rules: list[Rule] = field(default_factory=lambda: [])
    tracks: list[Track] = field(default_factory=lambda: [])
    arcs: list[Arc] = field(default_factory=lambda: [])
    vias: list[Via] = field(default_factory=lambda: [])
    zones: list[Zone] = field(default_factory=lambda: [])
    keepouts: list[Keepout] = field(default_factory=lambda: [])
    footprints: dict[str, FootprintInstance] = field(default_factory=lambda: {})
    components: list[Component] = field(default_factory=lambda: [])
    pads: list[BoardPad] = field(default_factory=lambda: [])
    count: int = 0

    def _next(self, prefix: str) -> str:
        self.count += 1
        return ident(prefix, self.count)

    def netclass(self, name: str, clearance: int | None) -> NetClass:
        self.classes[name] = NetClass(id=self._next("ncl"), name=name, clearance=clearance)
        return self.classes[name]

    def net(self, name: str | None, netclass: str | None = None) -> str | None:
        """The id of the net ``name`` (created on first use, in ``netclass`` when given); ``None`` for no
        net."""
        if name is None:
            return None
        if name not in self.nets:
            class_id = self.classes[netclass].id if netclass is not None else None
            self.nets[name] = Net(id=self._next("net"), name=name, netclass_id=class_id)
        return self.nets[name].id

    def rule(
        self,
        name: str,
        minimum: int | None,
        a: Selector | None = None,
        b: Selector | None = None,
        *,
        priority: int = 0,
        severity: RuleSeverity = "error",
        layers: tuple[str, ...] = (),
        kind: RuleKind = "clearance",
    ) -> Rule:
        rule = Rule(
            id=self._next("rul"),
            name=name,
            kind=kind,
            selector_a=a if a is not None else Selector("all"),
            selector_b=b,
            layers=layers,
            min=minimum,
            severity=severity,
            priority=priority,
        )
        self.rules.append(rule)
        return rule

    def track(
        self,
        net: str | None,
        a: Point,
        b: Point,
        *,
        width: int = 250_000,
        layer: str = "F.Cu",
        locator: str = "",
    ) -> Track:
        track = Track(
            id=self._next("trk"),
            provenance=_provenance(locator),
            start=a,
            end=b,
            width=width,
            layer=layer,
            net_id=self.net(net),
        )
        self.tracks.append(track)
        return track

    def arc(
        self, net: str | None, a: Point, mid: Point, b: Point, *, width: int = 250_000, layer: str = "F.Cu"
    ) -> Arc:
        arc = Arc(
            id=self._next("arc"), start=a, mid=mid, end=b, width=width, layer=layer, net_id=self.net(net)
        )
        self.arcs.append(arc)
        return arc

    def via(
        self,
        net: str | None,
        at: Point,
        *,
        diameter: int = 600_000,
        layers: tuple[str, str] = ("F.Cu", "B.Cu"),
        via_type: ViaType = "through",
        locator: str = "",
    ) -> Via:
        via = Via(
            id=self._next("via"),
            provenance=_provenance(locator),
            position=at,
            diameter=diameter,
            drill=diameter // 2,
            layers=layers,
            net_id=self.net(net),
            via_type=via_type,
        )
        self.vias.append(via)
        return via

    def zone(
        self,
        net: str | None,
        outline: Sequence[Point],
        *,
        layer: str = "F.Cu",
        priority: int = 0,
        fills: Sequence[Sequence[Point]] = (),
        name: str = "",
        locator: str = "",
        clearance: int | None = None,
    ) -> Zone:
        """A zone; ``clearance`` is its own clearance (the model's default of 0.5 mm when ``None``)."""
        zone = Zone(
            id=self._next("zon"),
            provenance=_provenance(locator),
            outline=tuple(outline),
            name=name,
            layers=(layer,),
            net_id=self.net(net),
            priority=priority,
            fills=tuple(ZoneFill(layer, tuple(polygon)) for polygon in fills),
            settings=ZoneSettings() if clearance is None else ZoneSettings(clearance=clearance),
        )
        self.zones.append(zone)
        return zone

    def pad(
        self,
        ref: str,
        number: str,
        net: str | None,
        *entries: PadCopper,
        kind: PadKind = "smd",
        layers: tuple[str, ...] = ("F.Cu",),
    ) -> BoardPad:
        """A model pad of the component ``ref`` and the board-frame record a frame would give for it, with
        ``entries`` as its copper."""
        footprint = self.footprints.get(ref)
        if footprint is None:
            component = Component(id=self._next("cmp"), ref=ref, value="X")
            self.components.append(component)
            footprint = FootprintInstance(
                id=self._next("fpi"), component_id=component.id, lib_ref="Bench:Part", position=Point(0, 0)
            )
        at = entries[0].core[0] if entries else Point(0, 0)
        pad = Pad(
            id=self._next("pad"),
            number=number,
            shape="rect",
            size=Size(1_000_000, 1_000_000),
            position=at,
            kind=kind,
            layers=layers,
            net_id=self.net(net),
        )
        self.footprints[ref] = dataclasses.replace(footprint, pads=(*footprint.pads, pad))
        record = BoardPad(
            footprint_id=footprint.id,
            ref=ref,
            path=ref,
            pad_id=pad.id,
            number=number,
            kind=kind,
            position=at,
            rotation=0,
            side="top",
            layers=layers,
            net_id=pad.net_id,
            net=net,
            copper=tuple(entries),
        )
        self.pads.append(record)
        return record

    def build(self) -> Design:
        base = Design.new("copper-bench", seed=0)
        assert base.board is not None and base.rules is not None
        board = dataclasses.replace(
            base.board,
            layers=created_layers(self.layers),
            footprints=tuple(self.footprints.values()),
            tracks=tuple(self.tracks),
            arcs=tuple(self.arcs),
            vias=tuple(self.vias),
            zones=tuple(self.zones),
            keepouts=tuple(self.keepouts),
        )
        circuit = Circuit(
            components=tuple(self.components),
            nets=tuple(self.nets.values()),
            netclasses=tuple(self.classes.values()),
        )
        rules = dataclasses.replace(base.rules, rules=tuple(self.rules))
        return dataclasses.replace(base, circuit=circuit, board=board, rules=rules)


def rect_entry(x0: int, y0: int, x1: int, y1: int, layer: str = "F.Cu") -> PadCopper:
    """A filled rectangular copper entry, as the frame gives for a ``rect`` pad."""
    return PadCopper(layer, (Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)), 0, filled=True)


def disc_entry(x: int, y: int, diameter: int, layer: str = "F.Cu", *, exact: bool = True) -> PadCopper:
    return PadCopper(layer, (Point(x, y),), diameter, exact=exact)


def bridge_pads(text: str, ref: str, from_pad: str, across_pad: str, *, width: int = 250_000) -> str:
    """The board ``text`` with one more segment: on the net and the copper layer of pad ``from_pad`` of the
    footprint ``ref``, from that pad's centre to the centre of pad ``across_pad``. The board is read with
    ``read_board`` and written again with ``write_board`` for its own major, so nothing else changes."""
    design = read_board(text, file="board.kicad_pcb")
    assert design.board is not None
    pads = {pad.number: pad for pad in KicadBackend().board_pads(design) if pad.ref == ref}
    start, end = pads[from_pad], pads[across_pad]
    layer = next(entry.layer for entry in start.copper)
    track = Track(
        id=ident("trk", 990_000 + len(design.board.tracks)),
        start=start.position,
        end=end.position,
        width=width,
        layer=layer,
        net_id=start.net_id,
    )
    board = dataclasses.replace(design.board, tracks=(*design.board.tracks, track))
    info = source_info(design)
    major = info.major if info is not None and info.major is not None else 10
    return write_board(dataclasses.replace(design, board=board), target=major).text


def bridged_project(tmp_path: Path, *, major: int) -> Path:
    """The authored built project of ``tests/_projects.py`` with one ``F.Cu`` track of the net of ``R1``
    pad 1 (``VIN``) laid from that pad to pad 2 of ``R1``, which is on another net: a short that
    Fenolite wrote."""
    from _projects import STEM, authored_project

    root = authored_project(tmp_path, major=major, built=True)
    board = root / f"{STEM}.kicad_pcb"
    board.write_text(bridge_pads(board.read_text(encoding="utf-8"), "R1", "1", "2"), encoding="utf-8")
    return root


def renet_bench(name: str, target: int = 10) -> Bench:
    """The re-net bench ``name`` of ``tests/kicad/copper/_benches.py`` (capability kicad-oracle, "Via re-net
    probe"), for hermetic tests: its design and the uuids of its labelled items."""
    for folder in (KICAD_TESTS / "rules", KICAD_TESTS / "copper"):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    import _benches  # pyright: ignore[reportMissingImports]

    bench: Bench = _benches.renet_bench(name, target)
    return bench


__all__ = [
    "SCALES",
    "Bench",
    "Copper",
    "bridge_pads",
    "bridged_project",
    "disc_entry",
    "ident",
    "mm",
    "rect_entry",
    "renet_bench",
    "thick_cases",
]
