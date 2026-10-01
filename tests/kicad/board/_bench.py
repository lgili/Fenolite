# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The flip bench (c0017 Decision 18): the three Mini footprints at 0°, 30°, 90° and 180° on the top
and on the bottom, the three negative controls and the missing-table control.

Every board is written for the running major in its own folder with a ``{}`` project file and, except
for the missing-table control, a project ``fp-lib-table`` whose row ``Mini`` points at the copied
library (``Mini.pretty`` in 10.0 syntax, ``Mini_v9.pretty`` in 9.0 syntax).
"""

from __future__ import annotations

import dataclasses
import shutil
from collections.abc import Callable
from pathlib import Path

from _boards import mm, square
from _triad import LIBS, PROJECT, library

from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import FULL_TURN, write_board
from fenolite.model.board import Board, FootprintInstance, Outline, Side
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design

DEFINITIONS = (("R", "Mini_R_0603"), ("D", "Mini_LED_THT_3mm"), ("U", "Mini_QFP-32_7x7mm_P0.8mm"))
ANGLES = (0, 30, 90, 180)
SIDES: tuple[Side, ...] = ("top", "bottom")
CONTROL_ANGLE = 30_000_000
TABLE_10 = (
    "(fp_lib_table\n\t(version 7)\n"
    '\t(lib (name "Mini") (type "KiCad") (uri "${{KIPRJMOD}}/{folder}") (options "") (descr ""))\n)\n'
)
TABLE_9 = (
    '(fp_lib_table\n  (lib (name Mini)(type KiCad)(uri ${{KIPRJMOD}}/{folder})(options "")(descr ""))\n)\n'
)
Alter = Callable[[FootprintInstance, FootprintInstance], FootprintInstance]


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def _design(placed: list[tuple[Component, FootprintInstance]], width: int, height: int) -> Design:
    base = Design.new("bench", seed=0)
    board = Board(
        id=_id("brd", 1),
        outline=Outline(id=_id("out", 1), points=square(0, 0, width, height)),
        layers=created_layers(2),
        footprints=tuple(fp for _, fp in placed),
    )
    return dataclasses.replace(base, circuit=Circuit(components=tuple(c for c, _ in placed)), board=board)


def bench(target: int) -> Design:
    """24 placements: each definition at each angle on each side, 12 mm apart."""
    placed: list[tuple[Component, FootprintInstance]] = []
    n = 0
    for row, (prefix, name) in enumerate(DEFINITIONS):
        defn = read_footprint(library(target) / f"{name}.kicad_mod", library="Mini")
        for column, (side, angle) in enumerate((s, a) for s in SIDES for a in ANGLES):
            n += 1
            ref = f"{prefix}{column + 1}"
            component = Component(id=_id("cmp", n), ref=ref, value=name, lib_footprint_ref=defn.lib_id)
            at = mm(8 + 12 * column, 10 + 14 * row)
            instance = place_footprint(
                defn, component=component, at=at, rotation=angle * 1_000_000, side=side, key=ref
            )
            placed.append((component, instance))
    return _design(placed, 100, 45)


def control(target: int, alter: Alter | None = None) -> Design:
    """One bottom QFP at 30°, exact or changed by ``alter(placed, top)``."""
    defn = read_footprint(library(target) / "Mini_QFP-32_7x7mm_P0.8mm.kicad_mod", library="Mini")
    component = Component(id=_id("cmp", 1), ref="U1", value="QFP", lib_footprint_ref=defn.lib_id)
    kwargs = {"component": component, "at": mm(15, 15), "rotation": CONTROL_ANGLE, "key": "U1"}
    placed = place_footprint(defn, side="bottom", **kwargs)  # type: ignore[arg-type]
    if alter is not None:
        placed = alter(placed, place_footprint(defn, side="top", **kwargs))  # type: ignore[arg-type]
    return _design([(component, placed)], 30, 30)


def unmirrored(placed: FootprintInstance, top: FootprintInstance) -> FootprintInstance:
    """Bottom footprint whose pads keep the library positions (not mirrored about local X)."""
    positions = {p.number: p.position for p in top.pads}
    return dataclasses.replace(
        placed, pads=tuple(dataclasses.replace(p, position=positions[p.number]) for p in placed.pads)
    )


def relative_angles(placed: FootprintInstance, top: FootprintInstance) -> FootprintInstance:
    """Bottom footprint whose stored pad angles leave out the footprint angle."""
    pads = tuple(
        dataclasses.replace(p, rotation=(p.rotation - placed.rotation) % FULL_TURN) for p in placed.pads
    )
    return dataclasses.replace(placed, pads=pads)


def wrong_flip_angle(placed: FootprintInstance, top: FootprintInstance) -> FootprintInstance:
    """The footprint written at −θ with every child unchanged (stored pad angles kept)."""
    rotation = (-placed.rotation) % FULL_TURN
    delta = placed.rotation - rotation
    pads = tuple(dataclasses.replace(p, rotation=(p.rotation + delta) % FULL_TURN) for p in placed.pads)
    return dataclasses.replace(placed, rotation=rotation, pads=pads)


CONTROLS: dict[str, Alter] = {
    "unmirrored": unmirrored,
    "relative-angles": relative_angles,
    "flip-angle": wrong_flip_angle,
}


def write(design: Design, target: int, folder: Path, *, table: bool = True) -> tuple[Path, dict[str, Path]]:
    """The board, its ``{}`` project file and (with ``table``) the library and its ``fp-lib-table``."""
    folder.mkdir(parents=True, exist_ok=True)
    board = folder / "bench.kicad_pcb"
    board.write_text(write_board(design, target=target).text, encoding="utf-8")
    files = {"bench.kicad_pro": folder / "bench.kicad_pro"}
    files["bench.kicad_pro"].write_text(PROJECT, encoding="utf-8")
    if table:
        lib = library(target)
        shutil.copytree(lib, folder / lib.name, dirs_exist_ok=True)
        text = (TABLE_10 if target >= 10 else TABLE_9).format(folder=lib.name)
        (folder / "fp-lib-table").write_text(text, encoding="utf-8")
        files |= {"fp-lib-table": folder / "fp-lib-table", lib.name: folder / lib.name}
    return board, files


__all__ = ["ANGLES", "CONTROLS", "DEFINITIONS", "LIBS", "SIDES", "bench", "control", "write"]
