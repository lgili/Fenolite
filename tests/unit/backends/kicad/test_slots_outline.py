# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots and merged rings of a board outline in the KiCad backend (capability kicad-file-backend, "Outline
shape checks", "Slots and merged rings in the board file", "Outline read back from the edges", "Free holes
refused by name"; change c0167)."""

from __future__ import annotations

import dataclasses
import importlib.util
import os
import runpy
import sys
from pathlib import Path

import pytest
from _outlinehelp import build_script

from fenolite import dsl
from fenolite.backends.kicad import outline as outline_mod
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.outline import (
    board_outline,
    check_outline,
    edge_outline,
    lower_outline,
    lowered_outline,
    outline_box,
    slots_of,
)
from fenolite.backends.kicad.pcb import FREE_HOLE_HINT, read_board, write_board
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.dsl import mm, shape, to_model
from fenolite.lens.preserve import fill_inputs_digest
from fenolite.model.board import Hole
from fenolite.model.design import Design

GEO = importlib.util.find_spec("pyclipper") is not None
needs_geo = pytest.mark.skipif(not GEO, reason="the union needs pyclipper of the geo extra")
MM = 1_000_000


def model(*calls: str) -> Design:
    """The model of a 40 × 30 mm board with the ``slot()`` and ``cutout()`` calls given."""
    d = dsl.Design("slots")
    d.board(mm(40), mm(30))
    for call in calls:
        exec(f"d.{call}", {"d": d, "mm": mm, "shape": shape})  # noqa: S102 - the scenario's own call
    return dsl.to_model(d)


SLOT_A = 'slot(mm(15), mm(10), length=mm(12), width=mm(2), name="A")'
SLOT_B = 'slot(mm(20), mm(15), length=mm(12), width=mm(2), rot=90, name="B")'


def hide_pyclipper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pyclipper", None)  # an import of it now fails


@needs_geo
def test_overlapping_slots_merged() -> None:
    issues = check_outline(model(SLOT_A, SLOT_B))
    assert [(i.code, i.severity) for i in issues] == [("kicad.outline.merged", "info")]
    assert "slot A" in issues[0].message and "slot B" in issues[0].message


def test_overlapping_slots_refused_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    hide_pyclipper(monkeypatch)
    issues = check_outline(model(SLOT_A, SLOT_B))
    assert [(i.code, i.severity) for i in issues] == [("kicad.outline.overlap", "error")]
    assert "slot A" in issues[0].message and "slot B" in issues[0].message
    assert issues[0].hint == "pip install 'fenolite[geo]'"


@needs_geo
def test_overlapping_cutouts_merged() -> None:
    circles = ("cutout(shape.circle(mm(18), mm(15), mm(4)))", "cutout(shape.circle(mm(21), mm(15), mm(4)))")
    issues = check_outline(model(*circles))
    assert [i.code for i in issues] == ["kicad.outline.merged"]
    assert "cut-out 1" in issues[0].message and "cut-out 2" in issues[0].message
    lowered = lowered_outline(model(*circles).board.outline)  # type: ignore[union-attr]
    assert len(lowered.cutouts) == 1
    # the union keeps two arcs of each circle's outer side: four arcs, through the two new vertices
    assert len(lowered.arcs) == 4


def test_a_lone_slot_is_one_more_cutout() -> None:
    design = model("slot(mm(15), mm(10), length=mm(12), width=mm(2))")
    assert design.board is not None and design.board.outline is not None
    assert check_outline(design) == ()
    lowered = lowered_outline(design.board.outline)
    assert lowered.slots == () and lowered.id == design.board.outline.id
    assert lowered.cutouts == (
        (
            Point(110 * MM, 109 * MM),
            Point(120 * MM, 109 * MM),
            Point(120 * MM, 111 * MM),
            Point(110 * MM, 111 * MM),
        ),
    )
    assert [(a.ring, a.edge, a.mid) for a in lowered.arcs] == [
        (1, 1, Point(121 * MM, 110 * MM)),
        (1, 3, Point(109 * MM, 110 * MM)),
    ]
    assert lower_outline(design.board.outline).names == ("board", "slot S1")
    found = board_outline(design)
    assert len(found.rings) == 2 and not found.exact


def test_an_outline_without_slots_is_not_lowered() -> None:
    design = model("cutout(shape.circle(mm(10), mm(10), mm(3.2)))")
    assert design.board is not None and design.board.outline is not None
    assert lowered_outline(design.board.outline) is design.board.outline


def test_slots_of_a_bad_size_and_outside_the_board() -> None:
    design = model("slot(mm(15), mm(10), length=mm(12), width=mm(2))")
    assert design.board is not None and design.board.outline is not None
    outline = design.board.outline
    bad = dataclasses.replace(outline, slots=(dataclasses.replace(outline.slots[0], width=3),))
    issues = check_outline(dataclasses.replace(design, board=dataclasses.replace(design.board, outline=bad)))
    assert [i.code for i in issues] == ["kicad.outline.invalid"] and issues[0].where == "slot S1"
    across = check_outline(model('slot(mm(38), mm(10), length=mm(12), width=mm(2), name="E")'))
    assert [i.code for i in across] == ["kicad.outline.invalid"] and "slot E" in across[0].message


def test_box_and_digest_see_the_slots() -> None:
    plain = model()
    slotted = model("slot(mm(15), mm(10), length=mm(12), width=mm(2))")
    assert outline_box(slotted) == outline_box(plain) == (100 * MM, 100 * MM, 140 * MM, 130 * MM)
    assert fill_inputs_digest(plain, project=None, rules=None) != fill_inputs_digest(
        slotted, project=None, rules=None
    )
    assert slotted.board is not None and slotted.board.outline is not None
    texts = outline_mod.edge_texts(slotted.board.outline)
    assert "arc 120000000 109000000 120000000 111000000 121000000 110000000" in texts


@needs_geo
def test_the_lowering_follows_the_installed_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    design = model(SLOT_A, SLOT_B)
    assert design.board is not None and design.board.outline is not None
    merged = lower_outline(design.board.outline)
    assert merged.merged == (("slot A", "slot B"),) and len(merged.outline.cutouts) == 1
    hide_pyclipper(monkeypatch)
    unmerged = lower_outline(design.board.outline)
    assert unmerged.unmerged == (("slot A", "slot B"),) and len(unmerged.outline.cutouts) == 2


# --- the board file (task 4.2) -----------------------------------------------------------------------


def _written(design: Design, target: int) -> Node:
    assert design.board is not None
    board = dataclasses.replace(design.board, layers=created_layers(2))
    return parse(write_board(dataclasses.replace(design, board=board), target=target).text)


def _xy(node: Node, head: str) -> tuple[int, int]:
    found = node.find(head)
    assert found is not None
    x, y = (round(float(atom.value) * MM) for atom in found.atoms())
    return x, y


@pytest.mark.parametrize("target", [9, 10])
def test_a_lone_slot_as_a_stadium(target: int) -> None:
    root = _written(model("slot(mm(15), mm(10), length=mm(12), width=mm(2))"), target)
    lines = {(_xy(n, "start"), _xy(n, "end")) for n in root.nodes("gr_line")}
    arcs = {_xy(n, "mid") for n in root.nodes("gr_arc")}
    assert ((110 * MM, 109 * MM), (120 * MM, 109 * MM)) in lines
    assert ((120 * MM, 111 * MM), (110 * MM, 111 * MM)) in lines
    assert len(lines) == 6  # the four lines of the board and the two of the slot
    assert arcs == {(121 * MM, 110 * MM), (109 * MM, 110 * MM)}


def test_overlap_through_the_model_api(monkeypatch: pytest.MonkeyPatch) -> None:
    design = model(SLOT_A, SLOT_B)
    hide_pyclipper(monkeypatch)
    with pytest.raises(LossyWriteError) as info:
        write_board(design)
    (issue,) = info.value.issues
    assert issue.code == "kicad.board.outline-overlap"
    assert "slot A" in issue.message and "slot B" in issue.message


@needs_geo
def test_merged_slots_are_written_as_one_ring() -> None:
    root = _written(model(SLOT_A, SLOT_B), 10)
    assert len(root.nodes("gr_line")) == 4 + 4 and len(root.nodes("gr_arc")) == 3


def test_a_model_hole() -> None:
    design = model()
    assert design.board is not None
    hole = Hole(
        id="hol_00000000-0000-4000-8000-000000000001", position=Point(110 * MM, 110 * MM), drill=3_200_000
    )
    with pytest.raises(LossyWriteError) as info:
        write_board(dataclasses.replace(design, board=dataclasses.replace(design.board, holes=(hole,))))
    (issue,) = info.value.issues
    assert issue.code == "kicad.board.free-hole" and issue.where == hole.id
    assert issue.hint == FREE_HOLE_HINT
    assert FREE_HOLE_HINT.startswith("declare a hole with design.hole(), or place a board-only footprint")
    assert FREE_HOLE_HINT.endswith("with an unnumbered np_thru_hole pad")


# --- read back (task 4.3) ----------------------------------------------------------------------------

FIXTURE = Path(__file__).resolve().parents[4] / "tests" / "data" / "slots" / "design.py"


WRITE_VARIABLE = "FENOLITE_SLOTS_WRITE"


def built_text(target: int) -> str:
    """The board of the shared fixture as the build writes it for ``target``."""
    design = runpy.run_path(str(FIXTURE))["design"]
    output = build_script(design, target)
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return output.files["slots.kicad_pcb"].decode("utf-8")


def fixture_board(target: int = 10) -> Design:
    """The shared fixture built for ``target`` and read back with ``read_board``."""
    return read_board(built_text(target))


@needs_geo
@pytest.mark.parametrize("target", [9, 10])
def test_the_committed_fixture_boards_are_current(target: int) -> None:
    """The oracle jobs install no ``geo`` extra, so ``tests/kicad/board/_slotbench.py`` reads the boards of
    the fixture committed beside it; ``FENOLITE_SLOTS_WRITE=1`` writes them again."""
    path = FIXTURE.parent / f"slots_t{target}.kicad_pcb"
    text = built_text(target)
    if os.environ.get(WRITE_VARIABLE) == "1":
        path.write_text(text, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == text, f"run with {WRITE_VARIABLE}=1 to write {path.name} again"


def _rotation_gap(a: int, b: int) -> int:
    gap = (a - b) % 180_000_000
    return min(gap, 180_000_000 - gap)


@needs_geo
def test_read_back_the_fixture() -> None:
    model_slots = {s.name: s for s in to_model(runpy.run_path(str(FIXTURE))["design"]).board.outline.slots}  # type: ignore[union-attr]
    board = fixture_board()
    assert board.board is not None and board.board.outline is None  # the lens owns the edges
    outline = edge_outline(board)
    assert outline is not None and len(outline.cutouts) == 3
    found = slots_of(outline)
    assert len(found) == 1
    (lone,) = found
    s1 = model_slots["S1"]
    assert abs(lone.center.x - s1.center.x) <= 1_000 and abs(lone.center.y - s1.center.y) <= 1_000
    assert abs(lone.length - s1.length) <= 1_000 and abs(lone.width - s1.width) <= 1_000
    # the rotation moves an end of the slot by less than 1 µm
    assert _rotation_gap(lone.rotation, s1.rotation) * s1.length // 2 <= 1_000 * 57_295_779
    arcs: dict[int, int] = {}
    for arc in outline.arcs:
        arcs[arc.ring] = arcs.get(arc.ring, 0) + 1
    sizes = sorted((len(ring), arcs.get(r, 0)) for r, ring in enumerate(outline.cutouts, start=1))
    assert sizes == [(4, 2), (7, 3), (8, 4)]  # the lone slot, the merged L, the rounded cut-out


def test_read_back_an_exact_slot() -> None:
    design = model('slot(mm(15), mm(10), length=mm(12), width=mm(2), rot=90, name="V")')
    assert design.board is not None
    text = write_board(
        dataclasses.replace(design, board=dataclasses.replace(design.board, layers=created_layers(2)))
    )
    outline = edge_outline(read_board(text.text))
    assert outline is not None
    (slot,) = slots_of(outline)
    assert (slot.center, slot.length, slot.width, slot.rotation) == (
        Point(115 * MM, 110 * MM),
        12 * MM,
        2 * MM,
        90_000_000,
    )
    assert slot.name == "" and slot.id.startswith("slt_")


def test_read_back_no_edges_and_no_stadium() -> None:
    assert edge_outline(Design.new("none", seed=0)) is None
    circle = model("cutout(shape.circle(mm(10), mm(10), mm(3.2)))")
    assert circle.board is not None and circle.board.outline is not None
    assert slots_of(circle.board.outline) == ()
