# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net selection by open connections, and a rip that keeps locked and kept copper (capability routing,
"Net selection"; change c0108)."""

import dataclasses
import random

import pytest

from fenolite.analysis.connectivity import connectivity
from fenolite.backends.kicad.frame import board_pads
from fenolite.core.coords import Point
from fenolite.core.ids import new_id
from fenolite.model.board import Arc, Track, Via
from fenolite.model.design import Design
from fenolite.routing.select import rip, unrouted

from ._designs import routing_design


def open_nets(design: Design) -> tuple[str, ...]:
    """What the route command passes: the nets with an open connection, from ``analysis.connectivity``."""
    return connectivity(design, pads=board_pads(design)).open_nets()


def test_open_nets() -> None:
    """Scenario "Unrouted nets": a net with a stub is selected, a joined net is not."""
    design = routing_design(stub=True)
    found = open_nets(design)
    assert found == ("A", "GND", "S")
    assert unrouted(design, found) == ("A", "S")
    assert unrouted(design, found, include_zone_nets=True) == ("A", "GND", "S")
    # a net of one pad is never selected, and a name that is not open is left out
    assert unrouted(design, ("A", "B", "NC", "S", "nothing")) == ("A", "B", "S")
    assert unrouted(design, ()) == ()
    assert unrouted(design, frozenset({"S"})) == ("S",)


def test_patterns_include_and_exclude() -> None:
    """Scenario "Patterns"."""
    design = routing_design(stub=True)
    found = open_nets(design)
    assert unrouted(design, found, patterns=("*", "!A")) == ("S",)
    assert unrouted(design, found, patterns=("A",)) == ("A",)
    assert unrouted(design, found, patterns=("!A",)) == ()


def test_the_old_call_fails_loudly() -> None:
    """Scenario "The old call fails loudly"."""
    with pytest.raises(TypeError):
        unrouted(routing_design())  # type: ignore[call-arg]


def test_rip_removes_only_selected_net_copper() -> None:
    design = routing_design()
    assert design.board is not None
    routed, count = rip(design, ("B",))
    assert count == 1
    assert routed.board is not None and routed.board.tracks == ()
    assert unrouted(routed, open_nets(routed)) == ("A", "B")
    assert design.board.tracks
    assert rip(design, ()) == (design, 0)


def test_rip_keeps_locked_and_kept_copper() -> None:
    """Scenario "Rip": locked and kept copper stay."""
    design = routing_design(stub=True)
    assert design.board is not None
    net_b = next(net.id for net in design.circuit.nets if net.name == "B")
    net_s = next(net.id for net in design.circuit.nets if net.name == "S")
    rng = random.Random(160017)
    locked = Track(
        id=new_id("trk", rng),
        start=Point(0, 10_000_000),
        end=Point(1_000_000, 10_000_000),
        width=250_000,
        layer="F.Cu",
        net_id=net_b,
        locked=True,
    )
    board = dataclasses.replace(design.board, tracks=(*design.board.tracks, locked))
    design = dataclasses.replace(design, board=board)
    (plain,) = [t for t in board.tracks if t.net_id == net_b and not t.locked]
    (stub,) = [t for t in board.tracks if t.net_id == net_s]
    ripped, count = rip(design, ("B", "S"), keep=frozenset({stub.id}))
    assert count == 1
    assert ripped.board is not None and ripped.board.tracks == (stub, locked)
    assert plain not in ripped.board.tracks
    # without ``keep`` the stub goes, the locked track stays
    ripped, count = rip(design, ("B", "S"))
    assert count == 2 and ripped.board is not None and ripped.board.tracks == (locked,)


def test_rip_honours_locked_arcs_and_vias() -> None:
    design = routing_design()
    assert design.board is not None
    net_b = next(net.id for net in design.circuit.nets if net.name == "B")
    rng = random.Random(160018)
    arcs = tuple(
        Arc(
            id=new_id("arc", rng),
            start=Point(0, 0),
            mid=Point(500_000, 500_000),
            end=Point(1_000_000, 0),
            width=250_000,
            layer="F.Cu",
            net_id=net_b,
            locked=flag,
        )  # fmt: skip
        for flag in (True, False)
    )
    vias = tuple(
        Via(
            id=new_id("via", rng),
            position=Point(0, 0),
            diameter=600_000,
            drill=300_000,
            layers=("F.Cu", "B.Cu"),
            net_id=net_b,
            locked=flag,
        )  # fmt: skip
        for flag in (False, True)
    )
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, arcs=arcs, vias=vias))
    ripped, count = rip(design, ("B",))
    assert count == 3
    assert ripped.board is not None
    assert ripped.board.arcs == (arcs[0],) and ripped.board.vias == (vias[1],) and ripped.board.tracks == ()
