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
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

from _outlinebench import PROJECT, drc, drill_hits, model_board, target, types
from _outlinehelp import build_script

from fenolite.backends.kicad.pcb import write_board
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import arc_to, mm, shape

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
BOARD = "blink.kicad_pcb"
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


def slot_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    return {
        "slot-overlap": (slot_overlap, both),
        "slot-union": (slot_union, both),
        "slot-drilled-overlap": (drilled_overlap, both),
        "slot-drilled-near": (drilled_near, both),
    }


__all__ = [
    "drilled_near",
    "drilled_overlap",
    "drilled_types",
    "ell_script",
    "ell_text",
    "slot_overlap",
    "slot_probes",
    "slot_union",
]
