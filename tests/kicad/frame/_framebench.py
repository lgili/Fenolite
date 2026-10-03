# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The frame bench (c0028; capability kicad-oracle, "Board-frame queries agree with kicad-cli").

The three Mini footprints and the authored footprints of ``tests/data/libs/Frame.pretty``, each placed
with ``place_footprint`` at 0°, 90°, 180°, 270° and 30° on both sides, every pad on a net of its own. A
bench board is written for the running major with a ``{}`` project file, a project ``fp-lib-table`` and a
rules file that sets every clearance to 0.2 mm, so no verdict rests on KiCad's defaults.

Two canaries with negative controls judge the geometry: probe vias placed by exact bisection 20 µm inside
and 20 µm outside the clearance of a pad's copper entries, and pairs of footprints whose placed extents
overlap by 20 µm or stay 20 µm apart.
"""

from __future__ import annotations

import dataclasses
import shutil
from collections.abc import Sequence
from fractions import Fraction
from functools import cache
from pathlib import Path

from _boards import mm, square
from _triad import LIBS, PROJECT, library

from fenolite.backends.base import BoardPad, DrcReport, PadCopper
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.dru import write_rules
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.frame import board_pads, placed_extent
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point
from fenolite.geometry import (
    Location,
    Polygon,
    Transform,
    dist2_point_segment,
    point_in_ring,
    polygons_intersect,
)
from fenolite.model.board import Board, FootprintInstance, Outline, Side, Via
from fenolite.model.circuit import Circuit, Component, Net, PinRef
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("R", "Mini_R_0603", "Mini"),
    ("D", "Mini_LED_THT_3mm", "Mini"),
    ("U", "Mini_QFP-32_7x7mm_P0.8mm", "Mini"),
    ("S", "Frame_Shapes", "Frame"),
    ("O", "Frame_Round", "Frame"),
    ("N", "Frame_NoCourtyard", "Frame"),
    ("P", "Frame_OpenCourtyard", "Frame"),
    ("T", "Frame_Trapezoid", "Frame"),
    ("L", "Frame_Loop", "Frame"),
)
ANGLES = (0, 90, 180, 270, 30)
SIDES: tuple[Side, ...] = ("top", "bottom")
PITCH = 14
CLEARANCE = 200_000
MARGIN = 20_000
PROBE_DIAMETER, PROBE_DRILL = 400_000, 200_000
PROBE_NET = "PROBE"
SHAPE_PREFIX = "S"
"""The references whose pads get probe vias: the ``Frame_Shapes`` placements, one pad of each shape."""
COURTYARD_KINDS: tuple[tuple[str, str, str], ...] = (
    ("rect", "Frame_Shapes", "Frame"),
    ("loop", "Frame_Loop", "Frame"),
    ("circle", "Frame_Round", "Frame"),
)
OVERLAP = {"rect": MARGIN, "loop": MARGIN, "circle": 2 * MARGIN}
"""How far the extents of a pair overlap on the overlap board. A circle courtyard needs 40 µm: its extent is
an outer polygon up to 5 µm outside the circle, and KiCad itself reports two circle courtyards only once
they overlap by more than 10 µm (measured on 10.0.6: none at 10 µm, one at 15 µm; ``H-G-FRAME-CRTYD-2``)."""
BOARD_NAME = "bench.kicad_pcb"
TOP_ONLY = frozenset({"Frame_Trapezoid"})
"""Footprints the bench places on the top side only."""


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def _folder(target: int, library_name: str) -> Path:
    return library(target) if library_name == "Mini" else LIBS / "Frame.pretty"


def _design(
    placed: Sequence[tuple[Component, FootprintInstance]], width: int, height: int, vias: Sequence[Via] = ()
) -> Design:
    """A two-layer board holding ``placed``, each pad on a net of its own, and ``vias`` on ``PROBE``."""
    nets: list[Net] = []
    footprints: list[FootprintInstance] = []
    for component, footprint in placed:
        pads = []
        for pad in footprint.pads:
            if pad.number:
                net = Net(
                    id=_id("net", len(nets) + 1),
                    name=f"{component.ref}_{pad.number}",
                    members=(PinRef(component.id, pad.number),),
                )
                nets.append(net)
                pad = dataclasses.replace(pad, net_id=net.id)
            pads.append(pad)
        footprints.append(dataclasses.replace(footprint, pads=tuple(pads)))
    probe = Net(id=_id("net", len(nets) + 1), name=PROBE_NET)
    board = Board(
        id=_id("brd", 1),
        outline=Outline(id=_id("out", 1), points=square(0, 0, width, height)),
        layers=created_layers(2),
        footprints=tuple(footprints),
        vias=tuple(dataclasses.replace(via, net_id=probe.id) for via in vias),
    )
    circuit = Circuit(components=tuple(c for c, _ in placed), nets=(*nets, probe))
    return dataclasses.replace(Design.new("bench", seed=0), circuit=circuit, board=board)


def _place(target: int, ref: str, name: str, lib: str, at: Point, angle: int, side: Side, n: int):  # type: ignore[no-untyped-def]
    defn = read_footprint(_folder(target, lib) / f"{name}.kicad_mod", library=lib)
    component = Component(id=_id("cmp", n), ref=ref, value=name, lib_footprint_ref=defn.lib_id)
    return component, place_footprint(
        defn, component=component, at=at, rotation=angle * 1_000_000, side=side, key=ref
    )


def placements(target: int) -> list[tuple[Component, FootprintInstance]]:
    """85 placements: each definition at each angle on each side (the trapezoid on the top only), ``PITCH``
    mm apart."""
    placed: list[tuple[Component, FootprintInstance]] = []
    n = 0
    for row, (prefix, name, lib) in enumerate(DEFINITIONS):
        for column, (side, angle) in enumerate((s, a) for s in SIDES for a in ANGLES):
            n += 1
            if name in TOP_ONLY and side == "bottom":
                continue  # ``place_footprint`` refuses to mirror a ``rect_delta`` (c0017)
            at = mm(10 + PITCH * column, 10 + PITCH * row)
            placed.append(_place(target, f"{prefix}{column + 1}", name, lib, at, angle, side, n))
    return placed


SIZE = (20 + PITCH * len(SIDES) * len(ANGLES), 20 + PITCH * len(DEFINITIONS))


@cache
def bench(target: int) -> Design:
    return _design(placements(target), *SIZE)


def rules_text(target: int) -> str:
    """A rules file with one rule: every clearance is 0.2 mm."""
    rule = Rule(
        id=_id("rul", 1), name="frame_clearance", kind="clearance", selector_a=Selector("all"), min=CLEARANCE
    )
    return write_rules(RuleSet(id=_id("rst", 1), rules=(rule,)), target=target)


def _table(target: int) -> str:
    names = (("Mini", library(target).name), ("Frame", "Frame.pretty"))
    if target >= 10:
        rows = "".join(
            f'\t(lib (name "{nick}") (type "KiCad") (uri "${{KIPRJMOD}}/{folder}") (options "") (descr ""))\n'
            for nick, folder in names
        )
        return f"(fp_lib_table\n\t(version 7)\n{rows})\n"
    rows = "".join(
        f'  (lib (name {nick})(type KiCad)(uri ${{KIPRJMOD}}/{folder})(options "")(descr ""))\n'
        for nick, folder in names
    )
    return f"(fp_lib_table\n{rows})\n"


def write(design: Design, target: int, folder: Path) -> tuple[Path, dict[str, Path]]:
    """The board with its ``{}`` project file, rules file, library table and the two libraries."""
    folder.mkdir(parents=True, exist_ok=True)
    board = folder / BOARD_NAME
    board.write_text(write_board(design, target=target).text, encoding="utf-8")
    texts = {
        "bench.kicad_pro": PROJECT,
        "bench.kicad_dru": rules_text(target),
        "fp-lib-table": _table(target),
    }
    files: dict[str, Path] = {}
    for name, text in texts.items():
        (folder / name).write_text(text, encoding="utf-8")
        files[name] = folder / name
    for lib in (library(target), LIBS / "Frame.pretty"):
        shutil.copytree(lib, folder / lib.name, dirs_exist_ok=True)
        files[lib.name] = folder / lib.name
    return board, files


def drc(runner: KicadCli, design: Design, target: int, folder: Path) -> DrcReport | None:
    board, files = write(design, target, folder)
    return runner.drc(board, files=files).report


# --- the clearance canary -------------------------------------------------------------------------


def _core_dist2(point: Point, entry: PadCopper) -> Fraction:
    core = entry.core
    if len(core) == 1:
        return Fraction((point.x - core[0].x) ** 2 + (point.y - core[0].y) ** 2)
    if entry.filled:
        if point_in_ring(point, core) is not Location.OUTSIDE:
            return Fraction(0)
        edges = list(zip(core, (*core[1:], core[0]), strict=True))
    else:
        edges = list(zip(core, core[1:], strict=False))
    return min(dist2_point_segment(point, a, b) for a, b in edges)


def gap_at_least(point: Point, entries: Sequence[PadCopper], diameter: int, gap: int) -> bool:
    """Whether a disc of ``diameter`` at ``point`` keeps at least ``gap`` from every entry, exactly:
    ``dist ≥ gap + d/2 + w/2`` compared as ``4·dist² ≥ (2·gap + d + w)²``."""
    return all(4 * _core_dist2(point, e) >= (2 * gap + diameter + e.width) ** 2 for e in entries)


def probe_point(pad: BoardPad, diagonal: bool, gap: int) -> Point:
    """The first point along the pad's local +X axis (or its +X+Y diagonal) where a probe via keeps
    ``gap`` from the pad's copper, found by bisection on integer nanometres."""
    move = Transform.placement(pad.position, pad.rotation)

    def at(t: int) -> Point:
        return move.apply(Point(t, t if diagonal else 0))

    low, high = 0, 10_000_000
    assert gap_at_least(at(high), pad.copper, PROBE_DIAMETER, gap)
    while high - low > 1:
        middle = (low + high) // 2
        if gap_at_least(at(middle), pad.copper, PROBE_DIAMETER, gap):
            high = middle
        else:
            low = middle
    return at(high)


def probe_uuid(n: int) -> str:
    return f"0b5e7a10-0000-4000-8000-{n:012d}"


@cache
def shape_bench(target: int, near: bool) -> tuple[Design, dict[str, str]]:
    """The bench with two probe vias per pad of the ``Frame_Shapes`` placements, 20 µm inside (``near``)
    or outside the 0.2 mm clearance, and ``probe uuid → "<ref>.<pad> edge|corner"``."""
    design = bench(target)
    gap = CLEARANCE - MARGIN if near else CLEARANCE + MARGIN
    vias: list[Via] = []
    labels: dict[str, str] = {}
    for pad in board_pads(design):
        if not pad.ref.startswith(SHAPE_PREFIX) or not pad.copper:
            continue
        for diagonal in (False, True):
            uuid = probe_uuid(len(vias) + 1)
            vias.append(
                Via(
                    id=_id("via", len(vias) + 1),
                    native_ids={"kicad": uuid},
                    position=probe_point(pad, diagonal, gap),
                    diameter=PROBE_DIAMETER,
                    drill=PROBE_DRILL,
                    layers=("F.Cu", "B.Cu"),
                )
            )
            labels[uuid] = f"{pad.ref}.{pad.number} {'corner' if diagonal else 'edge'}"
    return _design(placements(target), *SIZE, vias=vias), labels


def clearance_hits(report: DrcReport, labels: dict[str, str]) -> dict[str, int]:
    """``probe label → number of clearance violations naming it``."""
    hits = dict.fromkeys(labels.values(), 0)
    for violation in report.violations:
        if violation.type != "clearance":
            continue
        for item in violation.items:
            if item.uuid in labels:
                hits[labels[item.uuid]] += 1
    return hits


# --- the courtyard canary -------------------------------------------------------------------------


def _own_polygons(footprint: FootprintInstance) -> list[Polygon]:
    return [Polygon(ring) for ring in placed_extent(footprint).own]


def _touch(a: FootprintInstance, b: FootprintInstance) -> bool:
    return any(polygons_intersect(p, q) for p in _own_polygons(a) for q in _own_polygons(b))


def first_clear(a: FootprintInstance, b: FootprintInstance) -> int:
    """The smallest shift of ``b`` along +X, in nanometres, at which its extent no longer meets ``a``'s."""

    def shifted(dx: int) -> FootprintInstance:
        return dataclasses.replace(b, position=Point(b.position.x + dx, b.position.y))

    low, high = 0, 20_000_000
    assert _touch(a, shifted(low)) and not _touch(a, shifted(high))
    while high - low > 1:
        middle = (low + high) // 2
        if _touch(a, shifted(middle)):
            low = middle
        else:
            high = middle
    return high


@cache
def courtyard_bench(target: int, overlap: bool) -> tuple[Design, dict[frozenset[str], str]]:
    """Pairs of equal footprints, the second shifted along X from the first contact of their extents by
    −20 µm (``overlap``; −40 µm for circles, see ``OVERLAP``) or +20 µm, for each courtyard kind on each
    side at 0° and 30°; and
    ``{uuid of a, uuid of b} → "<kind> <side> <angle>"``."""
    placed: list[tuple[Component, FootprintInstance]] = []
    pairs: dict[frozenset[str], str] = {}
    n = 0
    for row, (kind, name, lib) in enumerate(COURTYARD_KINDS):
        for column, (side, angle) in enumerate((s, a) for s in SIDES for a in (0, 30)):
            at = mm(15 + 30 * column, 15 + 20 * row)
            n += 1
            first = _place(target, f"A{n}", name, lib, at, angle, side, 2 * n - 1)
            second = _place(target, f"B{n}", name, lib, at, angle, side, 2 * n)
            shift = first_clear(first[1], second[1]) + (-OVERLAP[kind] if overlap else MARGIN)
            moved = dataclasses.replace(second[1], position=Point(at.x + shift, at.y))
            placed += [first, (second[0], moved)]
            pairs[frozenset({first[1].native_ids["kicad"], moved.native_ids["kicad"]})] = (
                f"{kind} {side} {angle}"
            )
    return _design(placed, 140, 80), pairs


def courtyard_hits(report: DrcReport, pairs: dict[frozenset[str], str]) -> dict[str, int]:
    """``pair label → number of courtyards_overlap violations naming both footprints``."""
    hits = dict.fromkeys(pairs.values(), 0)
    for violation in report.violations:
        if violation.type != "courtyards_overlap":
            continue
        label = pairs.get(frozenset(item.uuid for item in violation.items))
        if label is not None:
            hits[label] += 1
    return hits


__all__ = [
    "ANGLES",
    "CLEARANCE",
    "DEFINITIONS",
    "MARGIN",
    "SIDES",
    "bench",
    "clearance_hits",
    "courtyard_bench",
    "courtyard_hits",
    "drc",
    "first_clear",
    "gap_at_least",
    "probe_point",
    "rules_text",
    "shape_bench",
    "write",
]
