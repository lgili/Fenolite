# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net selection and rip-up preserve copper belonging to other nets."""

import dataclasses
import random

from fenolite.core.coords import Point
from fenolite.core.ids import new_id
from fenolite.model.board import Track
from fenolite.routing.select import rip, unrouted

from ._designs import routing_design


def test_unrouted_candidates_and_zone_opt_in() -> None:
    design = routing_design()
    assert unrouted(design) == ("A",)
    assert unrouted(design, include_zone_nets=True) == ("A", "GND")


def test_patterns_include_and_exclude() -> None:
    design = routing_design()
    assert unrouted(design, patterns=("*", "!A")) == ()
    assert unrouted(design, patterns=("A",)) == ("A",)


def test_rip_removes_only_selected_net_copper() -> None:
    design = routing_design()
    assert design.board is not None
    routed, count = rip(design, ("B",))
    assert count == 1
    assert routed.board is not None and routed.board.tracks == ()
    assert unrouted(routed) == ("A", "B")
    assert design.board.tracks


def test_rip_preserves_a_locked_track_if_model_has_lock_state() -> None:
    @dataclasses.dataclass(frozen=True, slots=True)
    class LockedTrack(Track):
        locked: bool = True

    design = routing_design()
    assert design.board is not None
    net_id = next(net.id for net in design.circuit.nets if net.name == "B")
    locked = LockedTrack(
        id=new_id("trk", random.Random(160017)),
        start=Point(0, 10),
        end=Point(1_000_000, 10),
        width=250_000,
        layer="F.Cu",
        net_id=net_id,
    )
    board = dataclasses.replace(design.board, tracks=(*design.board.tracks, locked))
    design = dataclasses.replace(design, board=board)
    ripped, count = rip(design, ("B",))
    assert count == 1
    assert ripped.board is not None and ripped.board.tracks == (locked,)
