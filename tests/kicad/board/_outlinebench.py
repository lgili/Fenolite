# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The outline benches of change c0102 (capability kicad-oracle, "Outline shapes and holes pass the
oracle"; hypotheses H-K-OUTLINE-ARCS, H-K-OUTLINE-INVALID, H-K-OUTLINE-OUTSIDE and H-K-ZONE-BOX).

Every board is authored here with round values. A shape comes from ``fenolite.dsl.shape``; a board is
written in two ways: with its edges as ``Edge.Cuts`` graphics through the model API (``form`` ``graphics``,
which no outline code of the writer touches), and from a script, by the build (``form`` ``script``). The
probes record the first form; the tests require the second to give the same outcome.

- **Arcs.** A 60 × 40 mm board with corners of radius 3 mm, a round cut-out of 3.2 mm, a horizontal slot of
  12 × 2 mm, a slot of 12 × 1.5 mm turned 30° and a triangular cut-out.
- **Malformed outlines.** Six 40 × 30 mm boards: a round cut-out of 4 mm across the right edge, one touching
  it, two that overlap, a board ring that crosses itself, a cut-out inside a cut-out, and a control.
- **Copper outside.** A 50 × 30 mm board with a track and a via wholly outside it, or across its edge.
- **Zone box.** The board of the arcs with a zone on ``B.Cu`` whose outline is the box of the board ring.
"""

from __future__ import annotations

import dataclasses
import re
import tempfile
from collections.abc import Callable, Mapping
from fractions import Fraction
from functools import cache
from pathlib import Path

import _lenscases as lc
from _buildcases import _folder
from _outlinehelp import SHAPE, build_script, variant

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import pro
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.outline import board_outline, merge_outline, outline_case
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import mm, shape, to_model
from fenolite.geometry import Location, dist2_point_segment, point_in_ring
from fenolite.model.board import Board, Graphic, Outline, Track, Via, Zone, ZoneSettings
from fenolite.model.circuit import Circuit
from fenolite.model.circuit import Net as ModelNet
from fenolite.model.design import Design

MM = 1_000_000
Files = dict[str, str | bytes]
Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
FORMS = ("graphics", "script")
INVALID_CASES = ("cross", "touch", "overlap", "selfx", "nested", "inside")
EDGE_CLEARANCE = 500_000
"""KiCad's board-setup copper-to-edge clearance of a project without one."""
FILL_SLACK = 5_000
PROJECT = "{}\n"


def target() -> int:
    return 10 if lc.runner().major() >= 10 else 9


# --- the two forms of a board ---------------------------------------------------------------------


def graphics_of(outline: Outline, prefix: str) -> tuple[Graphic, ...]:
    """One ``Edge.Cuts`` graphic per edge of ``outline``: a line, or an arc through its mid."""
    mids = {(arc.ring, arc.edge): arc.mid for arc in outline.arcs}
    found: list[Graphic] = []
    for r, ring in enumerate((outline.points, *outline.cutouts)):
        for k, start in enumerate(ring):
            end = ring[(k + 1) % len(ring)]
            mid = mids.get((r, k))
            found.append(
                Graphic(
                    id=derived_id("gfx", "outlinebench", f"{prefix}:{r}:{k}"),
                    kind="line" if mid is None else "arc",
                    layer="Edge.Cuts",
                    points=(start, end) if mid is None else (start, mid, end),
                    width=100_000,
                )
            )
    return tuple(found)


def model_board(script: DslDesign, prefix: str, **items: object) -> Design:
    """The design of ``script`` with its outline as edge graphics, on two created copper layers."""
    model = to_model(script)
    assert model.board is not None and model.board.outline is not None
    board = Board(
        id=derived_id("brd", "outlinebench", prefix),
        layers=created_layers(2),
        graphics=graphics_of(model.board.outline, prefix),
        **items,  # type: ignore[arg-type]
    )
    return dataclasses.replace(Design.new(prefix, seed=0), board=board)


def arcs_script() -> DslDesign:
    """The bare board of the arcs as a script (no part): its outline and its four cut-outs."""
    d = DslDesign("arcs")
    d.board(outline=shape.rect(mm(0), mm(0), mm(60), mm(40), radius=mm(3)))
    for path in ARC_CUTOUTS:
        d.cutout(path())
    return d


def _turned_slot() -> object:
    # a slot of 12 × 1.5 mm about (45 mm, 31 mm), turned 30°: its centres lie 10.5 mm apart
    return shape.slot((mm(40.453), mm(28.375)), (mm(49.547), mm(33.625)), mm(1.5))


ARC_CUTOUTS: tuple[Callable[[], object], ...] = (
    lambda: shape.circle(mm(54), mm(8), mm(3.2)),
    lambda: shape.slot((mm(21), mm(36)), (mm(31), mm(36)), mm(2)),
    _turned_slot,
    lambda: ((mm(4), mm(30)), (mm(9), mm(30)), (mm(9), mm(36))),
)
ARCS_BOARD = (
    SHAPE
    + "design.board(outline=shape.rect(mm(0), mm(0), mm(60), mm(40), radius=mm(3)))\n"
    + "design.cutout(shape.circle(mm(54), mm(8), mm(3.2)))\n"
    + "design.cutout(shape.slot((mm(21), mm(36)), (mm(31), mm(36)), mm(2)))\n"
    + "design.cutout(shape.slot((mm(40.453), mm(28.375)), (mm(49.547), mm(33.625)), mm(1.5)))\n"
    + "design.cutout(((mm(4), mm(30)), (mm(9), mm(30)), (mm(9), mm(36))))"
)
"""The same board as the ``board()`` and ``cutout()`` lines of a blink variant."""
POUR = 'design.zone(gnd, layers=("B.Cu",))\n'


@cache
def arcs_files(form: str, zone: bool = False) -> tuple[tuple[str, str | bytes], ...]:
    """The files of the board of the arcs in ``form``; with ``zone``, with a ``GND`` zone on ``B.Cu``
    whose outline is the box of the board ring."""
    if form == "script":
        output = build_script(variant(ARCS_BOARD, append=POUR if zone else ""), target())
        assert output.files, [i.message for i in output.issues if i.severity == "error"]
        return tuple((k, v) for k, v in output.files.items() if not k.startswith(".fenolite/"))
    items: dict[str, object] = {}
    design = model_board(arcs_script(), "arcs")
    if zone:
        net = ModelNet(id=derived_id("net", "outlinebench", "GND"), name="GND")
        box = (Point(100 * MM, 100 * MM), Point(160 * MM, 100 * MM), Point(160 * MM, 140 * MM))
        area = Zone(
            id=derived_id("zon", "outlinebench", "GND"),
            outline=(*box, Point(100 * MM, 140 * MM)),
            name="GND",
            layers=("B.Cu",),
            net_id=net.id,
            # no pad joins the zone on this bare board, so its islands are kept
            settings=ZoneSettings(island_removal="never"),
        )
        items = {"zones": (area,)}
        assert design.board is not None
        design = dataclasses.replace(
            design, circuit=Circuit(nets=(net,)), board=dataclasses.replace(design.board, **items)
        )
    text = write_board(design, target=target()).text
    return (("blink.kicad_pcb", text), ("blink.kicad_pro", PROJECT))


def drc(files: Mapping[str, str | bytes], board: str = "blink.kicad_pcb") -> DrcReport | None:
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != board}
        return lc.runner().drc(Path(tmp) / board, files=extra).report


def types(report: DrcReport) -> list[str]:
    return [violation.type for violation in report.violations]


# --- arcs --------------------------------------------------------------------------------------------


@cache
def arcs_drc(form: str = "graphics") -> str:
    """``absent`` when ``pcb drc`` reports no ``invalid_outline`` for the board of the arcs."""
    report = drc(dict(arcs_files(form)))
    if report is None:
        return "inconclusive"
    return "present" if "invalid_outline" in types(report) else "absent"


def drill_hits(
    files: Mapping[str, str | bytes], board: str = "blink.kicad_pcb"
) -> dict[str, list[str]] | None:
    """The drill files of ``board`` with the options of ``exports.plan``: file name → its hit lines."""
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        args = ["pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm"]
        args += ["--excellon-separate-th", "--drill-origin", "absolute", "-o", "drill/", board]
        run = lc.runner().run(args, files=tops, folders=["drill"])
    if not run.ok:
        return None
    found: dict[str, list[str]] = {}
    for name, data in run.outputs.items():
        if name.startswith("drill/") and name.endswith(".drl"):
            lines = data.decode("utf-8", "replace").split("\n")
            found[name.removeprefix("drill/")] = [line for line in lines if re.match(r"^(G85)?X-?\d", line)]
    return found


@cache
def arcs_drill(form: str = "graphics") -> str:
    """``absent`` when the drill files hold no hole that is not a pad's or a via's: none at all on the bare
    board, and the two of the through-hole LED on the board built from the blink."""
    hits = drill_hits(dict(arcs_files(form)))
    if hits is None or not hits:
        return "inconclusive"
    total = sum(len(lines) for lines in hits.values())
    return "absent" if total == (0 if form == "graphics" else 2) else "present"


@cache
def arcs_keep() -> str:
    """``equal`` when, after ``pcb upgrade --force``, ``merge_outline`` finds the edges of the board built
    from the script signed and equal to the script's outline (KiCad 10 only)."""
    files = dict(arcs_files("script"))
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != "blink.kicad_pcb"}
        saved = lc.runner().upgrade_board(Path(tmp) / "blink.kicad_pcb", files=extra)
    board = read_board(saved.decode("utf-8"))
    built = build_script(variant(ARCS_BOARD), target()).design
    rounder = build_script(variant(ARCS_BOARD.replace("radius=mm(3)", "radius=mm(2)")), target()).design
    kept = outline_case(built, board) == "kept" and merge_outline(built, board).issues == ()
    signed = outline_case(rounder, board) == "replaced"
    return "equal" if kept and signed else "different"


# --- malformed outlines ------------------------------------------------------------------------------


def invalid_script(case: str) -> DslDesign:
    d = DslDesign(case)
    if case == "selfx":
        d.board(outline=((mm(0), mm(0)), (mm(40), mm(30)), (mm(40), mm(0)), (mm(0), mm(30))))
        return d
    d.board(mm(40), mm(30))
    cutouts = {
        "cross": ((39, 15, 4),),
        "touch": ((38, 15, 4),),
        "overlap": ((18, 15, 4), (21, 15, 4)),
        "nested": ((20, 15, 6), (20, 15, 2)),
        "inside": ((20, 15, 4),),
    }[case]
    for x, y, diameter in cutouts:
        d.cutout(shape.circle(mm(x), mm(y), mm(diameter)))
    return d


def invalid_text(case: str) -> str:
    return write_board(model_board(invalid_script(case), case), target=target()).text


@cache
def outline_invalid(case: str) -> str:
    """``present`` when KiCad reports ``invalid_outline`` for the malformed board ``case``."""
    report = drc({"blink.kicad_pcb": invalid_text(case), "blink.kicad_pro": PROJECT})
    if report is None:
        return "inconclusive"
    return "present" if "invalid_outline" in types(report) else "absent"


# --- copper outside the outline ----------------------------------------------------------------------


def outside_text(where: str) -> str:
    """A 50 × 30 mm board with a track and a via ``free`` of it (wholly outside) or ``across`` its right
    edge."""
    d = DslDesign(where)
    d.board(mm(50), mm(30))
    x = 160 if where == "free" else 148
    track = Track(
        id=derived_id("trk", "outlinebench", where),
        start=Point(x * MM, 105 * MM),
        end=Point((x + 6) * MM, 105 * MM),
        width=250_000,
        layer="F.Cu",
    )
    via = Via(
        id=derived_id("via", "outlinebench", where),
        position=Point((x + 2) * MM if where == "free" else 150 * MM, 120 * MM),
        diameter=600_000,
        drill=300_000,
        layers=("F.Cu", "B.Cu"),
    )
    return write_board(model_board(d, where, tracks=(track,), vias=(via,)), target=target()).text


@cache
def outline_outside(where: str) -> str:
    """``present`` when the track and the via each get a ``copper_edge_clearance``, ``absent`` when
    neither gets one."""
    report = drc({"blink.kicad_pcb": outside_text(where), "blink.kicad_pro": PROJECT})
    if report is None:
        return "inconclusive"
    found = types(report).count("copper_edge_clearance")
    return "present" if found >= 2 else "absent" if found == 0 else "inconclusive"


# --- the zone box --------------------------------------------------------------------------------------


def _distance2(point: Point, ring: tuple[Point, ...]) -> Fraction:
    return min(dist2_point_segment(point, a, b) for a, b in zip(ring, (*ring[1:], ring[0]), strict=True))


def edge_clearance(files: Mapping[str, str | bytes]) -> int:
    data = files["blink.kicad_pro"]
    text = data.decode("utf-8") if isinstance(data, bytes) else data
    found = pro.project_minimums(pro.read_project_text(text)).get("min_copper_edge_clearance", 0)
    return found or EDGE_CLEARANCE


@cache
def zone_box_fill(form: str = "graphics") -> str:
    """``absent`` when, after KiCad 10 refilled the zone on the box of the board ring, no fill vertex lies
    outside the board ring or inside a cut-out, and none lies closer to a ring than the board-setup edge
    clearance less 5 µm."""
    files = dict(arcs_files(form, True))
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != "blink.kicad_pcb"}
        saved = lc.runner().refill(Path(tmp) / "blink.kicad_pcb", files=extra).board
    if saved is None:
        return "inconclusive"
    board = read_board(saved.decode("utf-8"))
    assert board.board is not None
    rings = board_outline(board).rings
    vertices = [p for zone in board.board.zones for fill in zone.fills for p in fill.polygon]
    if len(rings) != 5 or len(vertices) < 8:
        return "inconclusive"
    least = (edge_clearance(files) - FILL_SLACK) ** 2
    for point in vertices:
        if point_in_ring(point, rings[0]) is not Location.INSIDE:
            return "present"
        if any(point_in_ring(point, ring) is not Location.OUTSIDE for ring in rings[1:]):
            return "present"
        if any(_distance2(point, ring) < least for ring in rings):
            return "present"
    return "absent"


def outline_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    probes: Probes = {
        "outline-arcs-drc": (arcs_drc, both),
        "outline-arcs-drill": (arcs_drill, both),
        "outline-arcs-keep": (arcs_keep, (10,)),
        "outline-outside-free": (lambda: outline_outside("free"), both),
        "outline-outside-across": (lambda: outline_outside("across"), both),
        "zone-box-fill": (zone_box_fill, (10,)),
    }
    for case in INVALID_CASES:
        probes[f"outline-invalid-{case}"] = (lambda case=case: outline_invalid(case), both)
    return probes


__all__ = [
    "ARCS_BOARD",
    "FORMS",
    "INVALID_CASES",
    "arcs_drc",
    "arcs_drill",
    "arcs_files",
    "arcs_keep",
    "invalid_script",
    "invalid_text",
    "outline_invalid",
    "outline_outside",
    "outline_probes",
    "zone_box_fill",
]
