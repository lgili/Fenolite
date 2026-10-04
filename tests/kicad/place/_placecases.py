# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0022 (capability kicad-oracle, "Moved footprints pass the oracle"): the ``place-*``
rows of ``_probes.PROBES``.

The move probes take the blink built for the running major, move footprints with ``move_footprint`` and
ask ``pcb export pos`` and ``pcb export ipcd356`` where they are and which nets their pads hold
(``H-K-PLACE-MOVE``). The touch probe places pairs of the authored ``Frame_Shapes`` footprint, whose
courtyard is an exact rectangle, so that they share an edge, share a corner, or overlap by 20 µm (the
positive control), and reads KiCad's ``courtyards_overlap`` violations (``H-K-PLACE-TOUCH``).
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import _framebench
import _lenscases as lc
from _boards import mm
from _buildcases import _folder
from _buildhelp import resolver
from _frame import pos_problems, read_pos

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.ipcd356 import read_ipcd356
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.replace import footprint_ref, move_footprint
from fenolite.core.coords import Point
from fenolite.model.board import FootprintInstance, Side
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
Files = dict[str, str | bytes]
Move = tuple[str, Point | None, int | None, Side | None]
"""``(reference, shift, rotation in microdegrees, side)``; ``None`` keeps a value."""
MM = 1_000_000
MOVES: Mapping[str, tuple[Move, ...]] = {
    "translate": (("R1", Point(3 * MM, 2 * MM), None, None), ("D1", Point(-4 * MM, 0), None, None)),
    "rotate": (("R1", None, 90_000_000, None), ("D1", None, 30_000_000, None)),
    "flip": (("R1", None, None, "bottom"), ("D1", Point(0, -2 * MM), None, "top")),
}
"""The moves of each probe on the blink: ``R1`` is on the top at 0° and ``D1`` on the bottom at 0°."""
MARGIN = 20_000
"""How far the control pair of the touch bench overlaps."""
WIDTH = 6 * MM
"""The side of the ``Frame_Shapes`` courtyard, the rectangle (−3 mm, −2 mm)–(3 mm, 4 mm)."""
TOUCH_KINDS: Mapping[str, Point] = {
    "edge": Point(WIDTH, 0),
    "corner": Point(WIDTH, WIDTH),
    "control": Point(WIDTH - MARGIN, 0),
}
"""Where the second footprint of a pair lies from the first."""
SIDES: tuple[Side, ...] = ("top", "bottom")


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


# --- moved footprints (H-K-PLACE-MOVE) ------------------------------------------------------------


def by_ref(design: Design) -> dict[str, FootprintInstance]:
    assert design.board is not None
    return {footprint_ref(design, fp): fp for fp in design.board.footprints}


def definitions(design: Design, target: int) -> dict[str, FootprintDef]:
    """The library definition of every footprint of the blink, from its project table."""
    assert design.board is not None
    found = resolver(target)
    return {fp.lib_ref: found.footprint(fp.lib_ref) for fp in design.board.footprints}


def moved_design(design: Design, moves: tuple[Move, ...], target: int) -> Design:
    known = definitions(design, target)
    for ref, shift, rotation, side in moves:
        fp = by_ref(design)[ref]
        at = None if shift is None else Point(fp.position.x + shift.x, fp.position.y + shift.y)
        design = move_footprint(design, fp.id, at=at, rotation=rotation, side=side, definitions=known)
    return design


@cache
def moved_files(case: str, target: int) -> Files:
    """The built blink of ``target`` with the moves of ``case`` applied by ``move_footprint``."""
    files = dict(lc.built_files(target))
    design = read_board(lc.text_of(files), file=lc.BOARD)
    files[lc.BOARD] = write_board(moved_design(design, MOVES[case], target), target=target).text
    return files


def pad_nets(files: Mapping[str, str | bytes]) -> dict[tuple[str, str], str]:
    """``pcb export ipcd356`` of the board of ``files``: (reference, pin) → net name."""
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != lc.BOARD}
        export = read_ipcd356(runner().export_ipcd356(Path(tmp) / lc.BOARD, files=extra))
    return {(r.ref, r.pin): r.net for r in export.records if r.ref != "VIA"}


def pos_text(files: Mapping[str, str | bytes]) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != lc.BOARD}
        return runner().export_pos_csv(Path(tmp) / lc.BOARD, files=extra)


def move_problems(case: str, target: int) -> list[str]:
    """What differs between the request and what ``kicad-cli`` reads, for the moves of ``case``."""
    before = lc.built_files(target)
    after = moved_files(case, target)
    old = by_ref(read_board(lc.text_of(before), file=lc.BOARD))
    design = read_board(lc.text_of(after), file=lc.BOARD)
    new = by_ref(design)
    problems: list[str] = []
    for ref, shift, rotation, side in MOVES[case]:
        was, now = old[ref], new[ref]
        wanted = (
            was.position if shift is None else Point(was.position.x + shift.x, was.position.y + shift.y),
            was.rotation if rotation is None else rotation,
            was.side if side is None else side,
        )
        if (now.position, now.rotation, now.side) != wanted:
            problems.append(f"{ref}: the written board holds {now.position, now.rotation, now.side}")
        if now.native_ids != was.native_ids:
            problems.append(f"{ref}: the uuid changed")
    rows = read_pos(pos_text(after))
    problems += pos_problems(design, rows)
    if {row.ref for row in rows} != set(new):
        problems.append(f"pos rows {sorted(row.ref for row in rows)}")
    nets_before, nets_after = pad_nets(before), pad_nets(after)
    if nets_before != nets_after or not nets_before:
        problems.append("the IPC-D-356 pad nets changed")
    return problems


def move_outcome(case: str) -> str:
    return "equal" if not move_problems(case, major()) else "different"


# --- touching courtyards (H-K-PLACE-TOUCH) --------------------------------------------------------


@cache
def touch_bench(target: int) -> tuple[Design, dict[frozenset[str], str]]:
    """Six pairs of ``Frame_Shapes`` at 0°, on the top and on the bottom: an edge pair, a corner pair and a
    control pair overlapping by 20 µm; and ``{uuid of a, uuid of b} → "<kind> <side>"``."""
    placed: list[tuple[Component, FootprintInstance]] = []
    pairs: dict[frozenset[str], str] = {}
    n = 0
    for row, side in enumerate(SIDES):
        for column, (kind, shift) in enumerate(TOUCH_KINDS.items()):
            at = mm(15 + 30 * column, 15 + 25 * row)
            n += 1
            first = _framebench._place(target, f"A{n}", "Frame_Shapes", "Frame", at, 0, side, 2 * n - 1)  # pyright: ignore[reportPrivateUsage]
            second = _framebench._place(target, f"B{n}", "Frame_Shapes", "Frame", at, 0, side, 2 * n)  # pyright: ignore[reportPrivateUsage]
            moved = dataclasses.replace(second[1], position=Point(at.x + shift.x, at.y + shift.y))
            placed += [first, (second[0], moved)]
            pairs[frozenset({first[1].native_ids["kicad"], moved.native_ids["kicad"]})] = f"{kind} {side}"
    return _framebench._design(placed, 110, 65), pairs  # pyright: ignore[reportPrivateUsage]


def touch_report(target: int) -> DrcReport | None:
    design, _ = touch_bench(target)
    with tempfile.TemporaryDirectory() as tmp:
        return _framebench.drc(runner(), design, target, Path(tmp))


@cache
def touch_hits() -> dict[str, int] | None:
    """``pair label → number of courtyards_overlap violations`` on the running major (``None``: no report)."""
    target = major()
    report = touch_report(target)
    return None if report is None else _framebench.courtyard_hits(report, touch_bench(target)[1])


def touch_outcome() -> str:
    """``absent`` when no touching pair fires, ``present`` when every one does, ``different`` for a mix;
    ``inconclusive`` when a control pair does not fire exactly once."""
    hits = touch_hits()
    if hits is None:
        return "reject"
    if any(hits[f"control {side}"] != 1 for side in SIDES):
        return "inconclusive"
    touching = [count for label, count in hits.items() if not label.startswith("control")]
    if not any(touching):
        return "absent"
    return "present" if all(touching) else "different"


def place_probes() -> Probes:
    both = (9, 10)
    return {
        "place-move-translate": (lambda: move_outcome("translate"), both),
        "place-move-rotate": (lambda: move_outcome("rotate"), both),
        "place-move-flip": (lambda: move_outcome("flip"), both),
        "place-touch": (touch_outcome, both),
    }


__all__ = [
    "MOVES",
    "TOUCH_KINDS",
    "by_ref",
    "definitions",
    "move_outcome",
    "move_problems",
    "moved_design",
    "moved_files",
    "pad_nets",
    "place_probes",
    "touch_bench",
    "touch_hits",
    "touch_outcome",
]
