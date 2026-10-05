# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rules benches (c0018 Decision 1; capability kicad-oracle, "Rules proofs carry a canary").

A bench is built through the model API and written with ``write_board`` for the running major, with a
``{}`` project file and the rules text next to it. Every bench carries the canary pair: two 0.25 mm
tracks on ``CANARY_A`` and ``CANARY_B`` on ``F.Cu`` with centres 1 mm apart, at least 10 mm from other
copper. The canary rule of ``tests/data/kicad/tokens/canary/canary.kicad_dru`` is placed right after
``(version 1)`` by ``with_canary``, so every later rule takes precedence over it. A report without the
canary violation fails the test ("rules file not loaded"); it never passes and never skips.

(The design calls this module ``_bench.py``; it is ``_rulebench.py`` because the flip bench of
``tests/kicad/board/_bench.py`` already takes that module name on the oracle tests' import path.)
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import pytest

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import kicad_uuid, write_board
from fenolite.core.coords import Point
from fenolite.geometry import thick_bbox
from fenolite.geometry.thick import Thick
from fenolite.model.board import (
    Arc,
    Board,
    FootprintInstance,
    Outline,
    Side,
    Track,
    Via,
    Zone,
    ZoneFill,
    ZoneSettings,
)
from fenolite.model.circuit import Circuit, Component, Net, NetClass, PinRef
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet

ROOT = Path(__file__).resolve().parents[3]
CANARY_FILE = ROOT / "tests" / "data" / "kicad" / "tokens" / "canary" / "canary.kicad_dru"
RULES = ROOT / "tests" / "data" / "kicad" / "rules"
LIBS = ROOT / "tests" / "data" / "libs"
PROJECT = "{}\n"
MM = 1_000_000
WIDTH = 250_000
ROW = 12 * MM
FIRST_ROW = 17 * MM
LEFT, RIGHT = 10 * MM, 20 * MM
BOARD_WIDTH = 40 * MM
CANARY_NETS = ("CANARY_A", "CANARY_B")
CANARY_TYPE = "clearance"
COURTYARD_WIDTH = 3 * MM
"""The courtyard rectangle of ``Mini_R_0603``, between its line centres."""
SILK_PITCH = 1_220_000
"""The centre distance at which the facing silkscreen lines of two stacked ``Mini_R_0603`` copies touch:
twice 0.55 mm plus the 0.12 mm line width."""


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


@dataclass(frozen=True)
class Bench:
    """A written-ready design and the KiCad uuids of its labelled items."""

    design: Design
    items: dict[str, tuple[str, ...]]

    def uuids(self, label: str) -> tuple[str, ...]:
        return self.items[label]


@dataclass
class Builder:
    """Collects nets, tracks, vias and footprints, one labelled row at a time. Change c0029 adds arcs, zones
    with a stored fill, net classes and model rules, for the copper parity benches."""

    nets: dict[str, Net] = field(default_factory=lambda: {})
    tracks: list[Track] = field(default_factory=lambda: [])
    vias: list[Via] = field(default_factory=lambda: [])
    arcs: list[Arc] = field(default_factory=lambda: [])
    zones: list[Zone] = field(default_factory=lambda: [])
    classes: dict[str, NetClass] = field(default_factory=lambda: {})
    class_of: dict[str, str] = field(default_factory=lambda: {})
    rules: list[Rule] = field(default_factory=lambda: [])
    footprints: list[FootprintInstance] = field(default_factory=lambda: [])
    components: list[Component] = field(default_factory=lambda: [])
    members: dict[str, list[PinRef]] = field(default_factory=lambda: {})
    items: dict[str, tuple[str, ...]] = field(default_factory=lambda: {})
    rows: int = 0
    edges: int = 0

    def net(self, name: str) -> str:
        if name not in self.nets:
            self.nets[name] = Net(id=_id("net", len(self.nets) + 1), name=name)
        return self.nets[name].id

    def track(self, label: str, net: str, y: int, *, layer: str = "F.Cu", width: int = WIDTH,
              x0: int = LEFT, x1: int = RIGHT) -> Track:  # fmt: skip
        track = Track(
            id=_id("trk", len(self.tracks) + 1),
            start=Point(x0, y),
            end=Point(x1, y),
            width=width,
            layer=layer,
            net_id=self.net(net),
        )
        self.tracks.append(track)
        self.items[label] = (kicad_uuid(track),)
        return track

    def via(self, label: str, net: str, at: Point, *, diameter: int = 600_000, drill: int = 300_000) -> Via:
        via = Via(
            id=_id("via", len(self.vias) + 1),
            position=at,
            diameter=diameter,
            drill=drill,
            layers=("F.Cu", "B.Cu"),
            net_id=self.net(net),
        )
        self.vias.append(via)
        self.items[label] = (kicad_uuid(via),)
        return via

    def row(self) -> int:
        y = FIRST_ROW + self.rows * ROW
        self.rows += 1
        return y

    def canary(self) -> None:
        self.track("canary_a", CANARY_NETS[0], 5 * MM)
        self.track("canary_b", CANARY_NETS[1], 6 * MM)

    def pair(self, label: str, net_a: str, net_b: str, *, gap: int = 4 * MM, layer: str = "F.Cu",
             width: int = WIDTH) -> None:  # fmt: skip
        """Two parallel tracks with an edge-to-edge ``gap``: items ``<label>_a`` and ``<label>_b``."""
        y = self.row()
        self.track(f"{label}_a", net_a, y, layer=layer, width=width)
        self.track(f"{label}_b", net_b, y + gap + width, layer=layer, width=width)

    def via_track(self, label: str, via_net: str, track_net: str, *, gap: int = 4 * MM) -> None:
        """A 0.6 mm via and a track with an edge-to-edge ``gap``: ``<label>_a`` (via) and ``<label>_b``."""
        y = self.row()
        self.via(f"{label}_a", via_net, Point((LEFT + RIGHT) // 2, y))
        self.track(f"{label}_b", track_net, y + 300_000 + gap + WIDTH // 2)

    def single(self, label: str, net: str, *, width: int = WIDTH) -> None:
        self.track(label, net, self.row(), width=width)

    def lone_via(self, label: str, net: str, *, diameter: int = 600_000, drill: int = 300_000) -> None:
        self.via(label, net, Point((LEFT + RIGHT) // 2, self.row()), diameter=diameter, drill=drill)

    def edge(self, label: str, net: str, *, gap: int = 4 * MM) -> None:
        """A vertical track ``gap`` from the left or the right board edge (alternating)."""
        x = gap + WIDTH // 2 if self.edges % 2 == 0 else BOARD_WIDTH - gap - WIDTH // 2
        self.edges += 1
        y0 = FIRST_ROW
        self.track(label, net, y0, x0=x, x1=x)
        track = self.tracks[-1]
        self.tracks[-1] = dataclasses.replace(track, start=Point(x, y0), end=Point(x, y0 + 5 * MM))

    def parts(self, label: str, refs: tuple[str, str], *, gap: int = 4 * MM, target: int) -> None:
        """Two placed ``Mini_R_0603`` copies, one above the other, with a pad gap of ``gap``.

        Each copy's pads are on a net of their own; items ``<label>_a`` and ``<label>_b`` are the pad uuids.
        """
        folder = "Mini.pretty" if target >= 10 else "Mini_v9.pretty"
        defn = read_footprint(LIBS / folder / "Mini_R_0603.kicad_mod", library="Mini")
        top = max(p.position.y + p.size.h // 2 for p in defn.pads)
        bottom = min(p.position.y - p.size.h // 2 for p in defn.pads)
        y = self.row()
        for side, (ref, at_y) in zip("ab", ((refs[0], y), (refs[1], y + top - bottom + gap)), strict=True):
            n = len(self.components) + 1
            component = Component(id=_id("cmp", n), ref=ref, value="R", lib_footprint_ref=defn.lib_id)
            placed = place_footprint(defn, component=component, at=Point((LEFT + RIGHT) // 2, at_y), key=ref)
            net_id = self.net(f"{ref}_NET")
            placed = dataclasses.replace(
                placed, pads=tuple(dataclasses.replace(p, net_id=net_id) for p in placed.pads)
            )
            self.members[net_id] = [PinRef(component.id, p.number) for p in placed.pads]
            self.components.append(component)
            self.footprints.append(placed)
            self.items[f"{label}_{side}"] = tuple(kicad_uuid(p) for p in placed.pads)

    def part(
        self,
        label: str,
        ref: str,
        at: Point,
        *,
        target: int,
        nets: Mapping[str, str],
        footprint: str = "Mini_R_0603",
        side: Side = "top",
        rotation: int = 0,
    ) -> FootprintInstance:
        """One placed ``Mini`` footprint whose pad ``number`` is on the net ``nets[number]`` (no net when the
        number is missing): item ``<label>`` holds every pad uuid and ``<label>:<number>`` the uuids of that
        pad (change c0029)."""
        folder = "Mini.pretty" if target >= 10 else "Mini_v9.pretty"
        defn = read_footprint(LIBS / folder / f"{footprint}.kicad_mod", library="Mini")
        n = len(self.components) + 1
        component = Component(id=_id("cmp", n), ref=ref, value=footprint, lib_footprint_ref=defn.lib_id)
        placed = place_footprint(defn, component=component, at=at, key=ref, side=side, rotation=rotation)
        pads = tuple(
            dataclasses.replace(pad, net_id=self.net(nets[pad.number]) if pad.number in nets else None)
            for pad in placed.pads
        )
        placed = dataclasses.replace(placed, pads=pads)
        for pad in pads:
            if pad.net_id is not None:
                self.members.setdefault(pad.net_id, []).append(PinRef(component.id, pad.number))
            if pad.number:
                self.items[f"{label}:{pad.number}"] = (
                    *self.items.get(f"{label}:{pad.number}", ()),
                    kicad_uuid(pad),
                )
        self.components.append(component)
        self.footprints.append(placed)
        self.items[label] = tuple(kicad_uuid(pad) for pad in pads)
        self.items[f"{label}:footprint"] = (kicad_uuid(placed),)
        return placed

    # --- rows of the new rule kinds (change c0071) -----------------------------------------------

    def courtyard_pair(self, label: str, refs: tuple[str, str], *, gap: int, target: int) -> None:
        """Two ``Mini_R_0603`` copies side by side whose courtyard rectangles (3 mm wide) are ``gap``
        apart: ``<label>_a`` and ``<label>_b`` hold the footprint uuids."""
        y = self.row()
        x = LEFT + 2 * MM
        for side, ref, at_x in (("a", refs[0], x), ("b", refs[1], x + COURTYARD_WIDTH + gap)):
            self.part(f"{label}_{side}:pads", ref, Point(at_x, y), target=target, nets={})
            self.items[f"{label}_{side}"] = self.items[f"{label}_{side}:pads:footprint"]

    def silk_pair(self, label: str, refs: tuple[str, str], *, gap: int, target: int) -> None:
        """Two ``Mini_R_0603`` copies one above the other whose facing silkscreen lines (0.12 mm wide,
        0.55 mm from each centre) are ``gap`` apart edge to edge, with every field hidden, so those two
        lines are the only silkscreen items that come close: ``<label>_a`` and ``<label>_b`` hold the
        footprint uuids."""
        y = self.row()
        x = (LEFT + RIGHT) // 2
        for side, ref, at_y in (("a", refs[0], y), ("b", refs[1], y + SILK_PITCH + gap)):
            placed = self.part(f"{label}_{side}:pads", ref, Point(x, at_y), target=target, nets={})
            hidden = tuple(dataclasses.replace(f, visible=False) for f in placed.fields)
            self.footprints[-1] = dataclasses.replace(placed, fields=hidden)
            self.items[f"{label}_{side}"] = self.items[f"{label}_{side}:pads:footprint"]

    # --- rows of the copper parity benches (change c0029) ----------------------------------------

    def netclass(self, name: str, clearance: int, *nets: str) -> None:
        """A net class with ``clearance``, holding ``nets`` (more are added with ``assign``)."""
        self.classes[name] = NetClass(id=_id("cls", len(self.classes) + 1), name=name, clearance=clearance)
        self.assign(name, *nets)

    def assign(self, netclass: str, *nets: str) -> None:
        for name in nets:
            self.net(name)
            self.class_of[name] = netclass

    def rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def via_pair(self, label: str, net_a: str, net_b: str, *, gap: int = 4 * MM) -> None:
        """Two 0.6 mm vias with an edge-to-edge ``gap``: ``<label>_a`` and ``<label>_b``."""
        y = self.row()
        x = (LEFT + RIGHT) // 2
        self.via(f"{label}_a", net_a, Point(x, y))
        self.via(f"{label}_b", net_b, Point(x, y + 600_000 + gap))

    def arc_pair(self, label: str, arc_net: str, track_net: str, *, gap: int = 4 * MM) -> None:
        """A 0.25 mm arc track of radius 3 mm and a straight track ``gap`` beyond its lowest point:
        ``<label>_a`` (the arc) and ``<label>_b``. The three arc points lie exactly on the circle."""
        y = self.row()
        x, radius = (LEFT + RIGHT) // 2, 3 * MM
        arc = Arc(
            id=_id("arc", len(self.arcs) + 1),
            start=Point(x - radius, y),
            mid=Point(x, y + radius),
            end=Point(x + radius, y),
            width=WIDTH,
            layer="F.Cu",
            net_id=self.net(arc_net),
        )
        self.arcs.append(arc)
        self.items[f"{label}_a"] = (kicad_uuid(arc),)
        self.track(f"{label}_b", track_net, y + radius + WIDTH + gap)

    def _pad_row(self, label: str, ref: str, footprint: str, pad_net: str, track_net: str, gap: int,
                 layer: str, target: int) -> None:  # fmt: skip
        y = self.row()
        at = Point((LEFT + RIGHT) // 2, y + 4 * MM)
        numbers = {"1": pad_net, "2": pad_net}
        self.part(f"{label}_a", ref, at, target=target, nets=numbers, footprint=footprint)
        pads = [pad for pad in board_pads(self.build().design) if pad.ref == ref]
        tops = [
            thick_bbox(Thick(entry.core, entry.width, entry.filled)).y0
            for pad in pads
            for entry in pad.copper
            if entry.layer == layer
        ]
        self.track(f"{label}_b", track_net, min(tops) - gap - WIDTH // 2, layer=layer)

    def pad_track(self, label: str, ref: str, pad_net: str, track_net: str, *, gap: int = 4 * MM,
                  target: int) -> None:  # fmt: skip
        """A placed ``Mini_R_0603`` whose pads are on ``pad_net`` and an ``F.Cu`` track ``gap`` above their
        flat upper edge: ``<label>_a`` (the pads) and ``<label>_b``."""
        self._pad_row(label, ref, "Mini_R_0603", pad_net, track_net, gap, "F.Cu", target)

    def tht_track(self, label: str, ref: str, pad_net: str, track_net: str, *, gap: int = 4 * MM,
                  target: int) -> None:  # fmt: skip
        """A placed ``Mini_LED_THT_3mm`` (a square and a round through-hole pad) and a ``B.Cu`` track ``gap``
        above the pads: ``<label>_a`` (the pads) and ``<label>_b``."""
        self._pad_row(label, ref, "Mini_LED_THT_3mm", pad_net, track_net, gap, "B.Cu", target)

    def filled_zone(self, label: str, net: str, top: int, *, clearance: int | None = None,
                    x0: int = LEFT, x1: int = RIGHT, name: str | None = None) -> Zone:  # fmt: skip
        """A zone on ``F.Cu`` whose stored fill is its own rectangular outline, 3 mm high from ``top``
        down: item ``<label>``. ``clearance`` is the zone's own clearance (the model's default of 0.5 mm
        when ``None``; change c0068)."""
        ring = (Point(x0, top), Point(x1, top), Point(x1, top + 3 * MM), Point(x0, top + 3 * MM))
        zone = Zone(
            id=_id("zon", len(self.zones) + 1),
            outline=ring,
            name=label if name is None else name,
            layers=("F.Cu",),
            net_id=self.net(net),
            fills=(ZoneFill("F.Cu", ring),),
            settings=ZoneSettings() if clearance is None else ZoneSettings(clearance=clearance),
        )
        self.zones.append(zone)
        self.items[label] = (kicad_uuid(zone),)
        return zone

    def fill_track(self, label: str, zone_net: str, track_net: str, *, gap: int = 4 * MM,
                   clearance: int | None = None) -> None:  # fmt: skip
        """A zone whose stored fill is its own rectangular outline and a track ``gap`` above it:
        ``<label>_a`` (the zone) and ``<label>_b``."""
        top = self.row() + 2 * MM
        self.filled_zone(f"{label}_a", zone_net, top, clearance=clearance, name=label)
        self.track(f"{label}_b", track_net, top - gap - WIDTH // 2)

    def fill_via(self, label: str, zone_net: str, via_net: str, *, gap: int = 4 * MM,
                 clearance: int | None = None) -> None:  # fmt: skip
        """A filled zone and a 0.6 mm via whose edge is ``gap`` above it: ``<label>_a`` (the zone) and
        ``<label>_b`` (change c0068)."""
        top = self.row() + 2 * MM
        self.filled_zone(f"{label}_a", zone_net, top, clearance=clearance, name=label)
        self.via(f"{label}_b", via_net, Point((LEFT + RIGHT) // 2, top - gap - 300_000))

    def fill_pad(self, label: str, ref: str, zone_net: str, pad_net: str, *, gap: int = 4 * MM,
                 clearance: int | None = None, target: int) -> None:  # fmt: skip
        """A placed ``Mini_R_0603`` whose pads are on ``pad_net`` and a filled zone ``gap`` below their
        flat lower edge: ``<label>_a`` (the zone) and ``<label>_b`` (the pads; change c0068)."""
        y = self.row()
        at = Point((LEFT + RIGHT) // 2, y)
        self.part(f"{label}_b", ref, at, target=target, nets={"1": pad_net, "2": pad_net})
        pads = [pad for pad in board_pads(self.build().design) if pad.ref == ref]
        bottoms = [
            thick_bbox(Thick(entry.core, entry.width, entry.filled)).y1
            for pad in pads
            for entry in pad.copper
            if entry.layer == "F.Cu"
        ]
        self.filled_zone(f"{label}_a", zone_net, max(bottoms) + gap, clearance=clearance, name=label)

    def build(self) -> Bench:
        height = FIRST_ROW + max(self.rows, 1) * ROW + 10 * MM
        nets = tuple(
            dataclasses.replace(
                n,
                members=tuple(self.members.get(n.id, ())),
                netclass_id=self.classes[self.class_of[n.name]].id if n.name in self.class_of else None,
            )
            for n in self.nets.values()
        )
        board = Board(
            id=_id("brd", 1),
            outline=Outline(
                id=_id("out", 1),
                points=(Point(0, 0), Point(BOARD_WIDTH, 0), Point(BOARD_WIDTH, height), Point(0, height)),
            ),
            layers=created_layers(2),
            footprints=tuple(self.footprints),
            tracks=tuple(self.tracks),
            arcs=tuple(self.arcs),
            vias=tuple(self.vias),
            zones=tuple(self.zones),
        )
        base = Design.new("rules-bench", seed=0)
        circuit = Circuit(
            components=tuple(self.components), nets=nets, netclasses=tuple(self.classes.values())
        )
        design = dataclasses.replace(base, circuit=circuit, board=board)
        if self.rules:
            design = dataclasses.replace(design, rules=RuleSet(id=_id("rst", 1), rules=tuple(self.rules)))
        return Bench(design, dict(self.items))


def builder() -> Builder:
    """A builder that already holds the canary pair."""
    made = Builder()
    made.canary()
    return made


# --- the canary -----------------------------------------------------------------------------------


@cache
def canary_rule() -> str:
    """The canary rule text of ``canary.kicad_dru`` (everything after its version line)."""
    lines = CANARY_FILE.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.startswith("(version")).strip() + "\n"


def with_canary(text: str) -> str:
    """``text`` with the canary rule right after its ``(version 1)`` line."""
    head, sep, rest = text.partition("(version 1)\n")
    if not sep:
        raise ValueError("the rules text has no '(version 1)' line")
    return f"{head}{sep}{canary_rule()}{rest}"


def scoped_canary_rule() -> str:
    """The canary rule with the condition ``A.NetName == 'CANARY_A'`` (change c0071).

    The plain canary matches every pair of items, and KiCad reports one violation per pair, so on a bench of
    holes, courtyards or silkscreen it takes the place of the violation under test. Scoped to its own net it
    still proves that the rules file was loaded."""
    head, sep, rest = canary_rule().partition("\n")
    return f"{head}{sep}\t(condition \"A.NetName == '{CANARY_NETS[0]}'\")\n{rest}"


def with_scoped_canary(text: str) -> str:
    """``text`` with the scoped canary rule right after its ``(version 1)`` line."""
    head, sep, rest = text.partition("(version 1)\n")
    if not sep:
        raise ValueError("the rules text has no '(version 1)' line")
    return f"{head}{sep}{scoped_canary_rule()}{rest}"


def violations_between(report: DrcReport, a: Collection[str], b: Collection[str],
                       kind: str | None = None) -> tuple[DrcViolation, ...]:  # fmt: skip
    """Violations naming an item of ``a`` and an item of ``b`` (of type ``kind`` when given)."""
    found: list[DrcViolation] = []
    for violation in report.violations:
        uuids = {item.uuid for item in violation.items}
        if (kind is None or violation.type == kind) and uuids & set(a) and uuids & set(b):
            found.append(violation)
    return tuple(found)


def violations_of(report: DrcReport, uuids: Iterable[str]) -> tuple[DrcViolation, ...]:
    wanted = set(uuids)
    return tuple(v for v in report.violations if {i.uuid for i in v.items} & wanted)


def canary_fired(report: DrcReport, bench: Bench) -> bool:
    return bool(violations_between(report, bench.uuids("canary_a"), bench.uuids("canary_b"), CANARY_TYPE))


def require_canary(report: DrcReport | None, bench: Bench) -> DrcReport:
    """The report, after failing the test with "rules file not loaded" when the canary is absent."""
    if report is None or not canary_fired(report, bench):
        pytest.fail(
            "rules file not loaded: the canary violation is absent from the DRC report", pytrace=False
        )
    return report


# --- running --------------------------------------------------------------------------------------


def drc(
    runner: KicadCli, bench: Bench, rules: str, target: int, *, project: str = PROJECT
) -> DrcReport | None:
    """``pcb drc`` on the bench written for ``target`` with ``rules`` next to it (``None``: no report).
    ``project`` is the text of the project file: ``{}`` unless a run needs board-setup minimums."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "bench.kicad_pcb"
        board.write_text(write_board(bench.design, target=target).text, encoding="utf-8")
        (folder / "bench.kicad_pro").write_text(project, encoding="utf-8")
        (folder / "bench.kicad_dru").write_text(rules, encoding="utf-8")
        files = {"bench.kicad_pro": folder / "bench.kicad_pro", "bench.kicad_dru": folder / "bench.kicad_dru"}
        run = runner.drc(board, files=files)
    return run.report


def outcome(found: bool) -> str:
    return "present" if found else "absent"


__all__ = [
    "Bench",
    "Builder",
    "builder",
    "canary_fired",
    "canary_rule",
    "drc",
    "outcome",
    "require_canary",
    "scoped_canary_rule",
    "violations_between",
    "violations_of",
    "with_canary",
    "with_scoped_canary",
]
