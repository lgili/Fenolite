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
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import pytest

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import kicad_uuid, write_board
from fenolite.core.coords import Point
from fenolite.model.board import Board, FootprintInstance, Outline, Track, Via
from fenolite.model.circuit import Circuit, Component, Net, PinRef
from fenolite.model.design import Design

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
    """Collects nets, tracks, vias and footprints, one labelled row at a time."""

    nets: dict[str, Net] = field(default_factory=lambda: {})
    tracks: list[Track] = field(default_factory=lambda: [])
    vias: list[Via] = field(default_factory=lambda: [])
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

    def build(self) -> Bench:
        height = FIRST_ROW + max(self.rows, 1) * ROW + 10 * MM
        nets = tuple(
            dataclasses.replace(n, members=tuple(self.members.get(n.id, ()))) for n in self.nets.values()
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
            vias=tuple(self.vias),
        )
        base = Design.new("rules-bench", seed=0)
        design = dataclasses.replace(
            base, circuit=Circuit(components=tuple(self.components), nets=nets), board=board
        )
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


def drc(runner: KicadCli, bench: Bench, rules: str, target: int) -> DrcReport | None:
    """``pcb drc`` on the bench written for ``target`` with ``rules`` next to it (``None``: no report)."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "bench.kicad_pcb"
        board.write_text(write_board(bench.design, target=target).text, encoding="utf-8")
        (folder / "bench.kicad_pro").write_text(PROJECT, encoding="utf-8")
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
    "violations_between",
    "violations_of",
    "with_canary",
]
