# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of the arcs and via kinds of script copper (change c0068; capability kicad-oracle, "Arcs and via
kinds pass the oracle"; ``H-G-FRAME-ARC``, ``H-K-COPPER-VIAKINDS``).

**Arc.** The routed blink with the corner of its ``led_drv`` track at (8 mm, 7 mm) replaced by a quarter
circle of radius 1 mm: a track, an arc step and a track. The arc must load, join the copper at its two end
points (no unconnected item; exactly one when the arc is taken out) and keep its uuid through a 10.0
re-save.

**Via kinds.** The blink on four copper layers with one track per kind on a net of its own, which holds no
pad: a point, a via step of the kind, a point. The two segments of a track are on the two layers of its via,
so the net is in one piece only when the via joins them.
"""

from __future__ import annotations

import runpy
import tempfile
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import _framecases as fc
from _buildcases import _folder
from _buildhelp import BLINK, BLINK_DIR, build

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import Net, arc_to, copper, mm, via_step

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
Files = dict[str, str | bytes]
ARC = copper_uuid("led_drv", "arc[3]")
ARC_MID = (mm("8.292893"), mm("7.292893"))
"""The middle of the quarter circle from (8, 8) to (9, 7) around (9, 8), rounded to the nanometre."""
BLINK_BOARD = "blink.kicad_pcb"
KINDS: Mapping[str, tuple[str, str]] = {
    "blind": ("F.Cu", "In1.Cu"),
    "micro": ("B.Cu", "In2.Cu"),
    "buried": ("In1.Cu", "In2.Cu"),
}
"""A via kind → the layer its track starts on and the layer its via step changes to."""
SIZES = {"diameter": mm(0.6), "drill": mm(0.3)}


# --- the arc ----------------------------------------------------------------------------------------


def arc_script() -> DslDesign:
    """The routed blink whose ``led_drv`` track bends through an arc step."""
    design = fc.routed_script()
    u1, r1 = design.parts["U1"], design.parts["R1"]
    del design.copper_intents["led_drv"]
    design.track(
        "led_drv",
        u1.pad(1), (mm(8), mm(12.2)), (mm(8), mm(8)), arc_to(ARC_MID, (mm(9), mm(7))), (mm(31.2), mm(7)),
        r1.pad(1),
        width=mm(0.3),
    )  # fmt: skip
    return design


@cache
def arc_files(target: int) -> Files:
    design = arc_script()
    output = build(design, target, project_dir=fc.ROUTED_DIR, copper_intents=copper(design))
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def arc_uuids(text: str) -> set[str]:
    board = read_board(text, file=fc.ROUTED_BOARD).board
    assert board is not None
    return {arc.native_ids["kicad"] for arc in board.arcs}


def arc_outcome(target: int) -> str:
    """``absent`` when the report holds no unconnected item and no violation that names the arc."""
    files = arc_files(target)
    assert arc_uuids(fc.board_text(files)) == {ARC}
    report = fc.routed_drc(files)
    if report is None:
        return "reject"
    named = [v for v in report.violations if ARC in {item.uuid for item in v.items}]
    return "absent" if not report.unconnected_items and not named else "present"


def arc_cut_files(target: int) -> Files:
    """The arc build without its arc."""
    files = dict(arc_files(target))
    root = parse(fc.board_text(files))
    kept = [c for c in root.children if not (isinstance(c, Node) and c.name == "arc" and ARC in dumps(c))]
    assert len(kept) == len(root.children) - 1
    files[fc.ROUTED_BOARD] = dumps(root.with_children(kept), style="kicad")
    return files


def arc_cut_outcome(target: int) -> str:
    """``present`` when the board without the arc reports exactly one unconnected item."""
    report = fc.routed_drc(arc_cut_files(target))
    if report is None:
        return "reject"
    return {0: "absent", 1: "present"}.get(len(report.unconnected_items), "different")


def arc_keep() -> str:
    """``equal`` when a 10.0 re-save keeps the uuid of the arc."""
    files = arc_files(10)
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != fc.ROUTED_BOARD}
        saved = fc.runner().upgrade_board(Path(tmp) / fc.ROUTED_BOARD, files=extra).decode("utf-8")
    return "equal" if arc_uuids(saved) == {ARC} and saved != fc.board_text(files) else "different"


# --- via kinds --------------------------------------------------------------------------------------


def net_name(kind: str) -> str:
    return f"VK_{kind.upper()}"


def via_script(kinds: tuple[str, ...]) -> DslDesign:
    """The blink on four copper layers with one two-layer track per kind of ``kinds``."""
    text = BLINK.read_text(encoding="utf-8").replace(
        "design.board(mm(50), mm(30))", "design.board(mm(50), mm(30), copper=4)"
    )
    assert "copper=4" in text
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "design.py"
        script.write_text(text, encoding="utf-8", newline="\n")
        design = runpy.run_path(str(script))["design"]
    assert isinstance(design, DslDesign)
    for row, kind in enumerate(kinds):
        start, to = KINDS[kind]
        net = Net(net_name(kind))
        design.add(net)
        y = mm(3 + 2 * row)
        design.track(
            kind,
            (mm(24), y),
            via_step(mm(28), y, to=to, kind=kind, **SIZES),
            (mm(32), y),
            layer=start,
            net=net,
            width=mm(0.3),
        )
    return design


def kinds_for(target: int) -> tuple[str, ...]:
    """The kinds a board of ``target`` can hold: a ``buried`` via needs target 10."""
    return tuple(kind for kind in KINDS if kind != "buried" or target >= 10)


@cache
def via_files(target: int) -> Files:
    design = via_script(kinds_for(target))
    output = build(design, target, project_dir=BLINK_DIR, copper_intents=copper(design))
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


@cache
def via_report(target: int) -> DrcReport | None:
    files = via_files(target)
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != BLINK_BOARD}
        return fc.runner().drc(Path(tmp) / BLINK_BOARD, files=extra).report


def via_outcome(kind: str, target: int) -> str:
    """``absent`` when the board loads, no violation names the via, and no unconnected item names a
    segment of its track: the net of the track holds nothing else, so it is in one piece only when the
    via joins its two layers."""
    report = via_report(target)
    if report is None:
        return "reject"
    board = read_board(
        fc.board_text({fc.ROUTED_BOARD: via_files(target)[BLINK_BOARD]}), file=BLINK_BOARD
    ).board
    assert board is not None
    via = copper_uuid(kind, "via[1]")
    (made,) = [v for v in board.vias if v.native_ids["kicad"] == via]
    assert made.via_type == kind and set(made.layers) == set(KINDS[kind])
    segments = {copper_uuid(kind, "seg[0]"), copper_uuid(kind, "seg[1]")}
    assert segments <= {t.native_ids["kicad"] for t in board.tracks}
    named = [v for v in report.violations if via in {item.uuid for item in v.items}]
    loose = [u for u in report.unconnected_items if {item.uuid for item in u.items} & (segments | {via})]
    return "absent" if not named and not loose else "present"


def via_cut_loose(kind: str, target: int) -> bool:
    """The control of ``via_outcome``: whether the board without the via of ``kind`` reports an unconnected
    item that names a segment of its track. Without it a silent report would prove nothing."""
    files = dict(via_files(target))
    data = files[BLINK_BOARD]
    root = parse(data.decode("utf-8") if isinstance(data, bytes) else data)
    via = copper_uuid(kind, "via[1]")
    kept = [c for c in root.children if not (isinstance(c, Node) and c.name == "via" and via in dumps(c))]
    assert len(kept) == len(root.children) - 1
    files[BLINK_BOARD] = dumps(root.with_children(kept), style="kicad")
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != BLINK_BOARD}
        report = fc.runner().drc(Path(tmp) / BLINK_BOARD, files=extra).report
    assert report is not None
    segments = {copper_uuid(kind, "seg[0]"), copper_uuid(kind, "seg[1]")}
    return any({item.uuid for item in u.items} & segments for u in report.unconnected_items)


def arc_probes() -> Probes:
    both = (9, 10)
    target = fc.running_target
    return {
        "pcb-frame-arc": (lambda: arc_outcome(target()), both),
        "pcb-frame-arc-cut": (lambda: arc_cut_outcome(target()), both),
        "pcb-frame-arc-keep": (arc_keep, (10,)),
        "pcb-frame-via-blind": (lambda: via_outcome("blind", target()), both),
        "pcb-frame-via-micro": (lambda: via_outcome("micro", target()), both),
        "pcb-frame-via-buried": (lambda: via_outcome("buried", target()), (10,)),
    }


__all__ = [
    "ARC",
    "KINDS",
    "arc_cut_files",
    "arc_files",
    "arc_outcome",
    "arc_probes",
    "arc_script",
    "kinds_for",
    "via_cut_loose",
    "via_files",
    "via_outcome",
    "via_report",
    "via_script",
]
