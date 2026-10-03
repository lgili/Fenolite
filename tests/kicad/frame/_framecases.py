# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0028 (capability kicad-oracle, "Script copper passes the oracle"): the ``pcb-frame-*``
rows of ``_probes.PROBES``.

The uuid probes come first (design Decision 17): a board whose tracks and via carry copper uuids must load
on both majors and keep those uuids through a 10.0.6 re-save, before any resolution code relies on them.
"""

from __future__ import annotations

import dataclasses
import runpy
import tempfile
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import _framebench
from _buildcases import _folder
from _buildhelp import build
from _layout_edit import move_footprint
from _probe_boards import MM, ORIGIN, probe_board

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.copper import copper_uuid, is_copper_uuid
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import copper, moves, placements, to_model
from fenolite.lens.preserve import ExistingProject, prepare
from fenolite.model.board import Track, Via
from fenolite.model.design import Design

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
UUID_KEY = "probe"
UUID_LOCATORS = ("seg[0]", "seg[1]", "via[1]")
ROUTED_DIR = Path(__file__).resolve().parents[3] / "examples" / "blink_routed"
ROUTED = "blink_routed"
ROUTED_BOARD = f"{ROUTED}.kicad_pcb"
D1_SHIFT = 4 * MM
JUDGED_TYPES = ("clearance", "shorting_items")
Files = dict[str, str | bytes]


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def _at(x: float, y: float) -> Point:
    return Point(ORIGIN + round(x * MM), ORIGIN + round(y * MM))


def uuid_board(target: int) -> Design:
    """The blink for ``target`` with two ``GND`` tracks and one via whose native ids are copper uuids."""
    design = probe_board(target)
    assert design.board is not None
    gnd = next(net.id for net in design.circuit.nets if net.name == "GND")
    ids = [copper_uuid(UUID_KEY, locator) for locator in UUID_LOCATORS]
    tracks = (
        Track(
            id=derived_id("trk", "kicad", ids[0]),
            native_ids={"kicad": ids[0]},
            start=_at(20, 26),
            end=_at(25, 26),
            width=300_000,
            layer="F.Cu",
            net_id=gnd,
        ),
        Track(
            id=derived_id("trk", "kicad", ids[1]),
            native_ids={"kicad": ids[1]},
            start=_at(25, 26),
            end=_at(30, 26),
            width=300_000,
            layer="B.Cu",
            net_id=gnd,
        ),
    )
    via = Via(
        id=derived_id("via", "kicad", ids[2]),
        native_ids={"kicad": ids[2]},
        position=_at(25, 26),
        diameter=600_000,
        drill=300_000,
        layers=("F.Cu", "B.Cu"),
        net_id=gnd,
    )
    board = dataclasses.replace(design.board, tracks=tracks, vias=(via,))
    return dataclasses.replace(design, board=board)


def copper_ids(text: str) -> set[str]:
    """The KiCad uuids of the tracks and vias of a board text."""
    board = read_board(text, file="board.kicad_pcb").board
    assert board is not None
    return {item.native_ids["kicad"] for item in (*board.tracks, *board.vias)}


def uuid_load(target: int) -> str:
    from _probes import load

    text = write_board(uuid_board(target), target=target).text
    assert copper_ids(text) == {copper_uuid(UUID_KEY, locator) for locator in UUID_LOCATORS}
    return load(text)


def uuid_keep() -> str:
    """``equal`` when a 10.0.6 re-save keeps every copper uuid of the target-10 board."""
    import _triad

    text = write_board(uuid_board(10), target=10).text
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "board.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        board.with_suffix(".kicad_pro").write_text(_triad.PROJECT, encoding="utf-8")
        saved = runner().upgrade_board(board, files=_triad.project(board)).decode("utf-8")
    return "equal" if copper_ids(saved) == copper_ids(text) and saved != text else "different"


# --- routed blink (H-G-FRAME-ROUTE) ---------------------------------------------------------------


def routed_script() -> DslDesign:
    design = runpy.run_path(str(ROUTED_DIR / "design.py"))["design"]
    assert isinstance(design, DslDesign)
    return design


def _project_files(output_files: Mapping[str, bytes]) -> Files:
    return {rel: data for rel, data in output_files.items() if not rel.startswith(".fenolite/")}


@cache
def routed_files(target: int) -> Files:
    """A fresh build of ``examples/blink_routed/design.py`` for ``target``, copper intents resolved."""
    design = routed_script()
    output = build(design, target, project_dir=ROUTED_DIR, copper_intents=copper(design))
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return _project_files(output.files)


def board_text(files: Mapping[str, str | bytes]) -> str:
    data = files[ROUTED_BOARD]
    return data.decode("utf-8") if isinstance(data, bytes) else data


def routed_drc(files: Mapping[str, str | bytes]) -> DrcReport | None:
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != ROUTED_BOARD}
        return runner().drc(Path(tmp) / ROUTED_BOARD, files=extra).report


def script_uuids(text: str) -> set[str]:
    return {uuid for uuid in copper_ids(text) if is_copper_uuid(uuid)}


def route_outcome(files: Mapping[str, str | bytes]) -> str:
    """``absent`` when the report holds no unconnected item and no clearance or short naming script copper."""
    report = routed_drc(files)
    if report is None:
        return "reject"
    ours = script_uuids(board_text(files))
    judged = [v for v in report.violations if v.type in JUDGED_TYPES and {i.uuid for i in v.items} & ours]
    return "absent" if not report.unconnected_items and not judged else "present"


def cut_files(target: int) -> Files:
    """The routed build without the ``led_a`` segment that reaches ``D1``."""
    from fenolite.backends.kicad.sexpr import Node, dumps, parse

    files = dict(routed_files(target))
    root = parse(board_text(files))
    gone = copper_uuid("led_a", "seg[2]")
    kept = [
        c for c in root.children if not (isinstance(c, Node) and c.name == "segment" and gone in dumps(c))
    ]
    assert len(kept) == len(root.children) - 1
    files[ROUTED_BOARD] = dumps(root.with_children(kept), style="kicad")
    return files


def cut_outcome(target: int) -> str:
    """``present`` when the cut board reports exactly one unconnected item."""
    report = routed_drc(cut_files(target))
    if report is None:
        return "reject"
    return {0: "absent", 1: "present"}.get(len(report.unconnected_items), "different")


def rebuilt(files: Mapping[str, str | bytes], target: int) -> Files:
    """``build_design`` of the routed blink over the board, project and rules of ``files``."""
    design = routed_script()

    def text(name: str) -> str | None:
        data = files.get(name)
        return None if data is None else data.decode("utf-8") if isinstance(data, bytes) else data

    existing = ExistingProject(text(ROUTED_BOARD), text(f"{ROUTED}.kicad_pro"), text(f"{ROUTED}.kicad_dru"))
    ready = prepare(to_model(design), placements(design), existing, name=ROUTED, moves=moves(design))
    output = build(
        design,
        target,
        project_dir=ROUTED_DIR,
        prepared=ready,
        placements_override=ready.placements,
        copper_intents=copper(design),
    )
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return _project_files(output.files)


@cache
def moved_files(target: int) -> Files:
    """The routed build whose ``D1`` was moved 4 mm down (re-saved by ``pcb upgrade --force`` on 10.0),
    rebuilt. The move is along Y: 4 mm to the right would bring the ``LED_A`` track, which follows pad 2,
    within 0.06 mm of pad 1, a real clearance violation that KiCad reports (``docs/copper.md``)."""
    files = dict(routed_files(target))
    files[ROUTED_BOARD] = move_footprint(board_text(files), "D1", 0, D1_SHIFT)
    if runner().major() >= 10 and target >= 10:
        with tempfile.TemporaryDirectory() as tmp:
            tops = _folder(files, Path(tmp))
            extra = {k: v for k, v in tops.items() if k != ROUTED_BOARD}
            files[ROUTED_BOARD] = (
                runner().upgrade_board(Path(tmp) / ROUTED_BOARD, files=extra).decode("utf-8")
            )
    return rebuilt(files, target)


def moved_outcome(target: int) -> str:
    """``absent`` as for the route probe, on the rebuild after ``D1`` moved; ``different`` when the copper
    did not follow the pad or changed its ids."""
    files = moved_files(target)
    before, after = board_text(routed_files(target)), board_text(files)
    if script_uuids(before) != script_uuids(after):
        return "different"
    moved = read_board(after, file=ROUTED_BOARD)
    assert moved.board is not None
    ends = {t.native_ids["kicad"]: t.end for t in moved.board.tracks}
    original = read_board(before, file=ROUTED_BOARD)
    assert original.board is not None
    was = {t.native_ids["kicad"]: t.end for t in original.board.tracks}
    key = copper_uuid("led_a", "seg[2]")
    if ends[key] != Point(was[key].x, was[key].y + D1_SHIFT):
        return "different"
    return route_outcome(files)


def running_target() -> int:
    return runner().major()


# --- canaries on the frame bench (H-G-FRAME-SHAPE, H-G-FRAME-CRTYD) ------------------------------


@cache
def shape_hits(near: bool) -> dict[str, int] | None:
    """Clearance violations per probe on the near or the far board (``None``: no report)."""
    target = running_target()
    design, labels = _framebench.shape_bench(target, near)
    with tempfile.TemporaryDirectory() as tmp:
        report = _framebench.drc(runner(), design, target, Path(tmp))
    return None if report is None else _framebench.clearance_hits(report, labels)


def shape_outcome(near: bool) -> str:
    """Near: ``present`` when every probe fires exactly once. Far: ``absent`` when none fires."""
    hits = shape_hits(near)
    if hits is None:
        return "reject"
    if near:
        return "present" if all(count == 1 for count in hits.values()) else "different"
    return "absent" if not any(hits.values()) else "present"


@cache
def courtyard_hits(overlap: bool) -> dict[str, int] | None:
    target = running_target()
    design, pairs = _framebench.courtyard_bench(target, overlap)
    with tempfile.TemporaryDirectory() as tmp:
        report = _framebench.drc(runner(), design, target, Path(tmp))
    return None if report is None else _framebench.courtyard_hits(report, pairs)


def courtyard_outcome(overlap: bool) -> str:
    hits = courtyard_hits(overlap)
    if hits is None:
        return "reject"
    if overlap:
        return "present" if all(count == 1 for count in hits.values()) else "different"
    return "absent" if not any(hits.values()) else "present"


def frame_probes() -> Probes:
    both = (9, 10)
    return {
        "pcb-frame-shape-near": (lambda: shape_outcome(True), both),
        "pcb-frame-shape-far": (lambda: shape_outcome(False), both),
        "pcb-frame-crtyd-overlap": (lambda: courtyard_outcome(True), both),
        "pcb-frame-crtyd-gap": (lambda: courtyard_outcome(False), both),
        "pcb-frame-route": (lambda: route_outcome(routed_files(running_target())), both),
        "pcb-frame-route-cut": (lambda: cut_outcome(running_target()), both),
        "pcb-frame-route-moved": (lambda: moved_outcome(running_target()), both),
        "pcb-frame-uuid-9": (lambda: uuid_load(9), both),
        "pcb-frame-uuid-10": (lambda: uuid_load(10), (10,)),
        "pcb-frame-uuid-keep": (uuid_keep, (10,)),
    }


__all__ = [
    "ROUTED_BOARD",
    "UUID_KEY",
    "UUID_LOCATORS",
    "board_text",
    "copper_ids",
    "cut_files",
    "frame_probes",
    "moved_files",
    "route_outcome",
    "routed_drc",
    "routed_files",
    "uuid_board",
    "uuid_keep",
    "uuid_load",
]
