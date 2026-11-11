# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from dataclasses import replace

import pytest

from fenolite.backends.kicad.frame import board_pads
from fenolite.cli.placement_protection import inspect_attachments
from fenolite.core.coords import Point
from fenolite.model.board import Track, Zone, ZoneFill
from fenolite.placement.constraints import MechanicalReservation, PlacementConstraints
from fenolite.placement.protection import placement_scope

from ._constrained_fixture import board, part


def test_saved_fill_and_cross_net_track_protect_only_touched_footprints():
    design = board(part("A", 10, 10), part("B", 25, 10), part("C", 35, 10))
    track = Track(id="track", start=Point(10, 10), end=Point(15, 10), width=2, layer="F.Cu", net_id="b")
    polygon = (Point(21, 6), Point(29, 6), Point(29, 14), Point(21, 14))
    fill = Zone(id="zone", outline=polygon, layers=("F.Cu",), net_id="a", fills=(ZoneFill("F.Cu", polygon),))
    design = replace(design, board=replace(design.board, tracks=(track,), zones=(fill,)))
    selected = ("C", "B", "A")
    attached = inspect_attachments(design, tuple(board_pads(design)), selected)
    assert attached == {"A": ("attached_copper",), "B": ("attached_copper",), "C": ()}
    scope = placement_scope(design.board, selected, PlacementConstraints(), attachments=attached)
    assert scope.movable == ("C",)


def test_source_lock_board_lock_anchor_and_missing_inspection_are_independent():
    design = board(part("A", 5, 10, locked=True), part("B", 12, 10), part("C", 20, 10), part("D", 28, 10))
    constraints = PlacementConstraints(reservations=(MechanicalReservation("fix", "C", "p_C"),))
    scope = placement_scope(
        design.board,
        ("A", "B", "C", "D"),
        constraints,
        attachments={"A": (), "B": (), "C": ()},
        source_locks=frozenset({"B"}),
    )
    assert scope.movable == ()
    assert dict(scope.fixed) == {
        "A": ("board_lock",),
        "B": ("source_lock",),
        "C": ("mechanical_anchor",),
        "D": ("attachment_unchecked",),
    }
    with pytest.raises(ValueError, match="existing footprint"):
        placement_scope(design.board, ("unmapped",), constraints, attachments={})


def test_missing_pad_projection_and_netless_copper_are_unknown():
    design = board(part("A", 10, 10))
    assert inspect_attachments(design, (), ("A",))["A"] == ("attachment_unchecked",)
    track = Track(id="unnetted", start=Point(10, 10), end=Point(12, 10), width=2, layer="F.Cu")
    unknown = replace(design, board=replace(design.board, tracks=(track,)))
    assert inspect_attachments(unknown, tuple(board_pads(unknown)), ("A",))["A"] == ("attachment_unchecked",)
