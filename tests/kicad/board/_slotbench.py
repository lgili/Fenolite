# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The slot benches of change c0167 (capability kicad-oracle, "Slots pass the oracle"; hypotheses
H-K-SLOT-OVERLAP, H-K-SLOT-UNION and H-K-HOLE-OVERLAP).

Every board is authored here with round values, on the 40 × 30 mm board of the design's measurements:

- **Overlap.** Two cut-outs of ``shape.slot`` 2 mm wide between the centres (10, 10)–(20, 10) mm and
  (20, 10)–(20, 20) mm: an L whose two round ends about (20, 10) mm overlap. Written through the model API
  with its edges as ``Edge.Cuts`` graphics, which no outline code of the writer touches.
- **Union.** The same L as one cut-out of seven vertices: its shared round end one quarter arc, its
  concave corner (19, 11) mm a plain vertex. Written the same way.
- **Drilled.** Two slots of ``design.hole(…, drill=mm(2), length=mm(12))`` forming the same L, built;
  and one of them with a plated hole of 2 mm copper 0.2 mm from it.
- **The shared fixture** ``tests/data/slots/design.py`` (H-K-SLOT-RING), built: a lone slot turned 30°, two
  slots merged into one ring of seven vertices, a round free hole and a cut-out with rounded corners. The
  merge needs the ``geo`` extra, which the oracle jobs do not install, so the probes read the boards that
  the build writes for targets 9 and 10, committed as ``tests/data/slots/slots_t<target>.kicad_pcb``;
  ``tests/unit/backends/kicad/test_slots_outline.py`` keeps them equal to a fresh build.
"""

from __future__ import annotations

import re
import runpy
import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path

import _lenscases as lc
from _buildcases import _folder
from _outlinebench import PROJECT, drc, drill_hits, model_board, target, types
from _outlinehelp import build_script

from fenolite.backends.kicad.outline import edge_outline, slots_of
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import arc_to, mm, shape, to_model

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
BOARD = "blink.kicad_pcb"
FIXTURE = Path(__file__).resolve().parents[2] / "data" / "slots" / "design.py"
FIXTURE_BOARD = "slots.kicad_pcb"
MICRON = 1_000
ELL_MID = (mm(20.707107), mm(9.292893))
"""The mid of the quarter arc about (20, 10) mm, 45° from both of its ends, rounded to the nanometre."""


def ell_script(merged: bool) -> DslDesign:
    """The bare 40 × 30 mm board with the L of two slots: as two overlapping cut-outs, or merged as one."""
    d = DslDesign("ellmerged" if merged else "elloverlap")
    d.board(mm(40), mm(30))
    if not merged:
        d.cutout(shape.slot((mm(10), mm(10)), (mm(20), mm(10)), mm(2)))
        d.cutout(shape.slot((mm(20), mm(10)), (mm(20), mm(20)), mm(2)))
        return d
    d.cutout(
        (
            (mm(10), mm(9)),
            (mm(20), mm(9)),
            arc_to(ELL_MID, (mm(21), mm(10))),
            (mm(21), mm(20)),
            arc_to((mm(20), mm(21)), (mm(19), mm(20))),
            (mm(19), mm(11)),
            (mm(10), mm(11)),
            arc_to((mm(9), mm(10)), (mm(10), mm(9))),
        )
    )
    return d


@cache
def ell_text(merged: bool) -> str:
    return write_board(model_board(ell_script(merged), "ell"), target=target()).text


def _ell_files(merged: bool) -> dict[str, str | bytes]:
    return {BOARD: ell_text(merged), "blink.kicad_pro": PROJECT}


@cache
def slot_overlap() -> str:
    """``present`` when ``pcb drc`` reports ``invalid_outline`` for the two overlapping cut-outs and the
    drill files hold no hit."""
    report = drc(_ell_files(False))
    hits = drill_hits(_ell_files(False))
    if report is None or hits is None:
        return "inconclusive"
    if any(hits.values()):
        return "different"
    return "present" if "invalid_outline" in types(report) else "absent"


@cache
def slot_union() -> str:
    """``absent`` when ``pcb drc`` reports no violation at all for the merged L."""
    report = drc(_ell_files(True))
    if report is None:
        return "inconclusive"
    return "present" if types(report) else "absent"


# --- drilled slots ----------------------------------------------------------------------------------------


def drilled_script(near: bool) -> DslDesign:
    """Two drilled slots forming the L; with ``near``, the horizontal one alone and a plated hole whose
    copper of 2 mm lies 0.2 mm from it."""
    d = DslDesign("drillednear" if near else "drilledell")
    d.board(mm(40), mm(30))
    d.hole("H1", mm(15), mm(10), drill=mm(2), length=mm(12))
    if near:
        d.hole("H2", mm(15), mm(12.2), drill=mm(1), pad=mm(2))
    else:
        d.hole("H2", mm(20), mm(15), drill=mm(2), length=mm(12), rot=90)
    return d


@cache
def drilled_types(near: bool) -> tuple[str, ...] | None:
    design = drilled_script(near)
    output = build_script(design, target())
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    files = {k: v for k, v in output.files.items() if not k.startswith(".fenolite/")}
    report = drc(files, f"{design.name}.kicad_pcb")
    return None if report is None else tuple(types(report))


@cache
def drilled_overlap() -> str:
    """``absent`` when no DRC finding about holes (a type that names a hole) is reported for the two
    overlapping drilled slots."""
    found = drilled_types(False)
    if found is None:
        return "inconclusive"
    return "present" if any("hole" in kind for kind in found) else "absent"


@cache
def drilled_near() -> str:
    """``present`` when the plated hole 0.2 mm from the drilled slot gives ``hole_clearance``."""
    found = drilled_types(True)
    if found is None:
        return "inconclusive"
    return "present" if "hole_clearance" in found else "absent"


# --- the shared fixture (task 4.4) --------------------------------------------------------------------


def fixture_design() -> DslDesign:
    design = runpy.run_path(str(FIXTURE))["design"]
    assert isinstance(design, DslDesign)
    return design


def fixture_board(major: int) -> Path:
    """The committed board of the shared fixture built for target ``major``."""
    return FIXTURE.parent / f"slots_t{major}.kicad_pcb"


@cache
def fixture_files() -> tuple[tuple[str, str | bytes], ...]:
    """The board of the shared fixture built for the running major, with an empty project."""
    return (
        (FIXTURE_BOARD, fixture_board(target()).read_text(encoding="utf-8")),
        ("slots.kicad_pro", PROJECT),
    )


@cache
def fixture_types() -> tuple[str, ...] | None:
    report = drc(dict(fixture_files()), FIXTURE_BOARD)
    return None if report is None else tuple(types(report))


@cache
def ring_drc() -> str:
    """``absent`` when ``pcb drc`` reports no ``invalid_outline`` for the built fixture."""
    found = fixture_types()
    if found is None:
        return "inconclusive"
    return "present" if "invalid_outline" in found else "absent"


@cache
def ring_drill() -> str:
    """``absent`` when the drill files hold the round hole ``H1`` alone: one hit of the NPTH file at
    (152, 132) mm and nothing else, so no slot, merged ring or cut-out reaches a drill file."""
    hits = drill_hits(dict(fixture_files()), FIXTURE_BOARD)
    if hits is None:
        return "inconclusive"
    every = [line for lines in hits.values() for line in lines]
    npth = [line for name, lines in hits.items() if "NPTH" in name for line in lines]

    def at_h1(line: str) -> bool:
        values = [abs(float(v)) for v in re.findall(r"[XY](-?\d+(?:\.\d+)?)", line)]
        return (
            "G85" not in line
            and len(values) == 2
            and abs(values[0] - 152) < 0.002
            and abs(values[1] - 132) < 0.002
        )

    return "absent" if len(every) == 1 and len(npth) == 1 and at_h1(npth[0]) else "present"


def _gap(a: int, b: int) -> int:
    gap = (a - b) % 180_000_000
    return min(gap, 180_000_000 - gap)


def read_back(text: str) -> str:
    """``equal`` when ``edge_outline`` and ``slots_of`` of the board ``text`` give the fixture's lone slot
    within 1 µm (its centre, length, width, and an end moved by its rotation), the merged L as a cut-out of
    seven vertices and three arcs, and the rounded cut-out with its four arcs."""
    model = to_model(fixture_design())
    assert model.board is not None and model.board.outline is not None
    s1 = next(slot for slot in model.board.outline.slots if slot.name == "S1")
    outline = edge_outline(read_board(text))
    if outline is None or len(outline.cutouts) != 3:
        return "different"
    found = slots_of(outline)
    if len(found) != 1:
        return "different"
    (lone,) = found
    near = (
        abs(lone.center.x - s1.center.x) <= MICRON
        and abs(lone.center.y - s1.center.y) <= MICRON
        and abs(lone.length - s1.length) <= MICRON
        and abs(lone.width - s1.width) <= MICRON
        # an end of the slot moves by gap · π / 180° · length / 2, below 1 µm
        and _gap(lone.rotation, s1.rotation) * s1.length // 2 <= MICRON * 57_295_779
    )
    arcs: dict[int, int] = {}
    for arc in outline.arcs:
        arcs[arc.ring] = arcs.get(arc.ring, 0) + 1
    sizes = sorted((len(ring), arcs.get(r, 0)) for r, ring in enumerate(outline.cutouts, start=1))
    return "equal" if near and sizes == [(4, 2), (7, 3), (8, 4)] else "different"


@cache
def ring_read() -> str:
    """``read_back`` of the built fixture re-saved by ``pcb upgrade --force`` (10.0.x)."""
    files = dict(fixture_files())
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != FIXTURE_BOARD}
        saved = lc.runner().upgrade_board(Path(tmp) / FIXTURE_BOARD, files=extra)
    return read_back(saved.decode("utf-8"))


def slot_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    return {
        "slot-overlap": (slot_overlap, both),
        "slot-union": (slot_union, both),
        "slot-drilled-overlap": (drilled_overlap, both),
        "slot-drilled-near": (drilled_near, both),
        "slot-ring-drc": (ring_drc, both),
        "slot-ring-drill": (ring_drill, both),
        "slot-ring-read": (ring_read, (10,)),
    }


__all__ = [
    "drilled_near",
    "drilled_overlap",
    "drilled_types",
    "ell_script",
    "ell_text",
    "fixture_board",
    "fixture_files",
    "read_back",
    "ring_drc",
    "ring_drill",
    "ring_read",
    "slot_overlap",
    "slot_probes",
    "slot_union",
]
