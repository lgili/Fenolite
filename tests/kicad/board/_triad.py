# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The triad (c0017 Decision 19): a created board with three placed Mini footprints, built through the
model API and written with ``write_board``.

``R1`` (``Mini_R_0603``, top, 0°), ``D1`` (``Mini_LED_THT_3mm``, bottom, 90°) and ``U1``
(``Mini_QFP-32_7x7mm_P0.8mm``, top, 30°) on a 50 × 30 mm two-copper board, with three nets, two tracks
and one zone on ``B.Cu``. Definitions come from ``Mini.pretty`` for target 10 and ``Mini_v9.pretty``
for target 9, both read with ``library="Mini"``.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from _boards import mm, square

from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import write_board
from fenolite.core.units import Udeg
from fenolite.geometry import Point, Transform
from fenolite.model.board import Board, FootprintInstance, Outline, Side, Track, Zone
from fenolite.model.circuit import Circuit, Component, Net, PinRef
from fenolite.model.design import Design

LIBS = Path(__file__).resolve().parents[2] / "data" / "libs"
PROJECT = "{}\n"
PLACEMENTS: tuple[tuple[str, str, str, Point, Udeg, Side], ...] = (
    ("R1", "1k", "Mini_R_0603", mm(10, 10), 0, "top"),
    ("D1", "LED", "Mini_LED_THT_3mm", mm(24, 12), 90_000_000, "bottom"),
    ("U1", "MCU", "Mini_QFP-32_7x7mm_P0.8mm", mm(38, 15), 30_000_000, "top"),
)
NETS: dict[str, tuple[tuple[str, str], ...]] = {
    "VIN": (("R1", "1"), ("U1", "1")),
    "LED_A": (("R1", "2"), ("D1", "2")),
    "GND": (("D1", "1"), ("U1", "9")),
}


def library(target: int) -> Path:
    return LIBS / ("Mini.pretty" if target >= 10 else "Mini_v9.pretty")


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def pad_position(fp: FootprintInstance, number: str) -> Point:
    pad = next(p for p in fp.pads if p.number == number)
    return Transform.placement(fp.position, fp.rotation).apply(pad.position)


def triad(target: int) -> Design:
    """The triad for ``target`` (9 or 10)."""
    nets = {name: Net(id=_id("net", i), name=name) for i, name in enumerate(NETS, start=1)}
    by_pin = {pin: nets[name].id for name, pins in NETS.items() for pin in pins}
    components: list[Component] = []
    footprints: list[FootprintInstance] = []
    for i, (ref, value, name, at, rotation, side) in enumerate(PLACEMENTS, start=1):
        defn = read_footprint(library(target) / f"{name}.kicad_mod", library="Mini")
        component = Component(id=_id("cmp", i), ref=ref, value=value, lib_footprint_ref=defn.lib_id)
        placed = place_footprint(defn, component=component, at=at, rotation=rotation, side=side, key=ref)
        pads = tuple(dataclasses.replace(p, net_id=by_pin.get((ref, p.number))) for p in placed.pads)
        components.append(component)
        footprints.append(dataclasses.replace(placed, pads=pads))
    fps = {ref: fp for (ref, *_), fp in zip(PLACEMENTS, footprints, strict=True)}
    tracks = (
        Track(id=_id("trk", 1), start=pad_position(fps["R1"], "2"), end=pad_position(fps["D1"], "2"),
              width=250_000, layer="F.Cu", net_id=nets["LED_A"].id),
        Track(id=_id("trk", 2), start=pad_position(fps["R1"], "1"), end=pad_position(fps["U1"], "1"),
              width=250_000, layer="F.Cu", net_id=nets["VIN"].id),
    )  # fmt: skip
    zone = Zone(id=_id("zon", 1), outline=square(2, 20, 48, 28), layers=("B.Cu",), net_id=nets["GND"].id)
    members = {
        nets[name].id: tuple(PinRef(next(c.id for c in components if c.ref == ref), pin) for ref, pin in pins)
        for name, pins in NETS.items()
    }
    circuit = Circuit(
        components=tuple(components),
        nets=tuple(dataclasses.replace(n, members=members[n.id]) for n in nets.values()),
    )
    base = Design.new("triad", seed=0)
    board = Board(
        id=_id("brd", 1),
        outline=Outline(id=_id("out", 1), points=square(0, 0, 50, 30)),
        layers=created_layers(2),
        footprints=tuple(footprints),
        tracks=tracks,
        zones=(zone,),
    )
    return dataclasses.replace(base, circuit=circuit, board=board)


def pad_count(design: Design) -> int:
    assert design.board is not None
    return sum(len(fp.pads) for fp in design.board.footprints)


def write(design: Design, target: int, folder: Path, name: str = "triad") -> Path:
    """The design written for ``target`` as ``<folder>/<name>.kicad_pcb``, with a ``{}`` project file."""
    folder.mkdir(parents=True, exist_ok=True)
    board = folder / f"{name}.kicad_pcb"
    board.write_text(write_board(design, target=target).text, encoding="utf-8")
    (folder / f"{name}.kicad_pro").write_text(PROJECT, encoding="utf-8")
    return board


def project(board: Path) -> dict[str, Path]:
    """The ``files`` argument of the runner helpers: the project file next to ``board``."""
    return {board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
