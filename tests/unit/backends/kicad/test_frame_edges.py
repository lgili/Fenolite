# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edge rings of a KiCad board frame (capability backend-protocol, "Board edges of a frame"; change
c0169). The boards are the shared slot fixture of change c0167 and boards authored here."""

from __future__ import annotations

import dataclasses
import importlib.util
import runpy
from pathlib import Path

import pytest

from fenolite import dsl
from fenolite.backends.base import BoardFrame, EdgeRing
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copperrules import EDGE_CLEARANCE_DEFAULT, design_rules_from_texts
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.dsl import mm, shape
from fenolite.model.board import Graphic

GEO = importlib.util.find_spec("pyclipper") is not None
needs_geo = pytest.mark.skipif(not GEO, reason="the union needs pyclipper of the geo extra")
SLOTS = Path(__file__).resolve().parents[3] / "data" / "slots"
BACKEND = KicadBackend()
MM = 1_000_000


def fixture() -> dsl.Design:
    design = runpy.run_path(str(SLOTS / "design.py"))["design"]
    assert isinstance(design, dsl.Design)
    return design


def test_kicad_backend_is_a_frame_with_edges() -> None:
    assert isinstance(BACKEND, BoardFrame)


@pytest.mark.parametrize("target", [9, 10])
def test_edges_of_a_read_fixture(target: int) -> None:
    board = read_board((SLOTS / f"slots_t{target}.kicad_pcb").read_text(encoding="utf-8"))
    rings = BACKEND.board_edges(board)
    assert rings is not None
    assert [ring.name for ring in rings] == ["board", "edge ring 1", "edge ring 2", "edge ring 3"]
    # the lone slot (two arcs), the rounded cut-out (four arcs) and the merged L (three arcs)
    shapes = sorted((len(ring.points), sum(m is not None for m in ring.mids)) for ring in rings[1:])
    assert shapes == [(4, 2), (7, 3), (8, 4)]
    assert len(rings[0].points) == 4 and set(rings[0].mids) == {None}


@needs_geo
def test_edges_of_the_model_name_slots_and_merged_rings() -> None:
    rings = BACKEND.board_edges(dsl.to_model(fixture()))
    assert rings is not None
    assert [ring.name for ring in rings] == ["board", "cut-out 1", "slot S1", "slot S2 + slot S3"]
    by_name = {ring.name: ring for ring in rings}
    assert sum(m is not None for m in by_name["slot S1"].mids) == 2
    assert len(by_name["slot S2 + slot S3"].points) == 7


def test_edges_of_a_lone_slot_without_the_union() -> None:
    d = dsl.Design("lone")
    d.board(mm(40), mm(30))
    d.slot(mm(20), mm(15), length=mm(12), width=mm(2), name="S1")
    d.cutout(shape.circle(mm(8), mm(8), mm(3)))
    rings = BACKEND.board_edges(dsl.to_model(d))
    assert rings is not None
    assert [ring.name for ring in rings] == ["board", "cut-out 1", "slot S1"]
    slot = rings[2]
    # the stadium about (120, 115) mm of the board frame: its long edges 1 mm from its axis
    assert {p.y for p in slot.points} == {114 * MM, 116 * MM}


def test_edges_without_an_outline_are_none() -> None:
    design = dsl.to_model(dsl.Design("bare"))
    assert design.board is None or BACKEND.board_edges(design) is None
    d = dsl.Design("open")
    d.board(mm(10), mm(10))
    model = dsl.to_model(d)
    assert model.board is not None
    line = Graphic(
        id="gfx_00000000-0000-4000-8000-000000000001",
        kind="line",
        layer="Edge.Cuts",
        points=(Point(0, 0), Point(5 * MM, 0)),
        width=100_000,
    )
    board = dataclasses.replace(model.board, outline=None, graphics=(line,))
    assert BACKEND.board_edges(dataclasses.replace(model, board=board)) is None


def test_edge_ring_mids_default_to_lines() -> None:
    ring = EdgeRing("board", (Point(0, 0), Point(1, 0), Point(0, 1)))
    assert ring.mids == (None, None, None)
    with pytest.raises(ValueError, match="as many mids"):
        EdgeRing("board", (Point(0, 0), Point(1, 0), Point(0, 1)), (None,))


def test_edge_minimum_of_the_project() -> None:
    design = dsl.to_model(fixture())
    unset = design_rules_from_texts(design, project_text=None, rules_text=None)
    assert unset.min_edge_clearance == EDGE_CLEARANCE_DEFAULT == 500_000
    assert unset.edge_floor_over_rules is False
    text = '{"board": {"design_settings": {"rules": {"min_copper_edge_clearance": 0.8}}}}'
    found = design_rules_from_texts(design, project_text=text, rules_text=None)
    assert found.min_edge_clearance == 800_000
    empty = design_rules_from_texts(design, project_text="{}", rules_text=None)
    assert empty.min_edge_clearance == EDGE_CLEARANCE_DEFAULT
