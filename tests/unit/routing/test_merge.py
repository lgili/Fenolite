# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Merging appends only valid copper and rejects the whole result on any invalid item."""

import random

import pytest

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.roundtrip import rt1
from fenolite.core.coords import Point
from fenolite.core.ids import new_id
from fenolite.model.board import Track
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.protocol import RoutingResult

from ._designs import routing_design


def test_append_tracks_with_original_board_unchanged() -> None:
    design = routing_design()
    assert design.board is not None
    net_id = next(net.id for net in design.circuit.nets if net.name == "A")
    additions = tuple(
        Track(
            id=new_id("trk", random.Random(seed)),
            start=Point(seed * 100_000, 0),
            end=Point(seed * 100_000, 500_000),
            width=250_000,
            layer="F.Cu",
            net_id=net_id,
        )
        for seed in (100, 101)
    )
    merged = apply(design, RoutingResult(tracks=additions))
    assert merged.board is not None
    assert merged.board.tracks == (*design.board.tracks, *additions)
    assert design.board.tracks == (design.board.tracks[0],)
    assert merged.circuit == design.circuit


def test_refuses_foreign_net_without_partial_merge() -> None:
    design = routing_design()
    foreign = Track(
        id=new_id("trk", random.Random(102)),
        start=Point(0, 0),
        end=Point(1, 0),
        width=200_000,
        layer="F.Cu",
        net_id="net_missing",
    )
    with pytest.raises(RoutingError) as error:
        apply(design, RoutingResult(tracks=(foreign,)))
    assert [issue.code for issue in error.value.issues] == ["route.bad-item"]
    assert design.board is not None and len(design.board.tracks) == 1


@pytest.mark.parametrize("target", (9, 10))
def test_merged_board_passes_rt1_on_both_targets(target: int) -> None:
    design = routing_design()
    assert design.board is not None
    net_id = next(net.id for net in design.circuit.nets if net.name == "A")
    addition = Track(
        id=new_id("trk", random.Random(160018)),
        start=Point(500_000, 0),
        end=Point(500_000, 500_000),
        width=250_000,
        layer="F.Cu",
        net_id=net_id,
    )
    merged = apply(design, RoutingResult(tracks=(addition,)))
    text = write_board(merged, target=target).text
    assert read_board(text, file=f"merged-t{target}.kicad_pcb").board is not None
    assert rt1(text, file=f"merged-t{target}.kicad_pcb").passed
